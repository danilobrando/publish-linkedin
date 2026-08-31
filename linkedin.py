"""
Cliente mínimo de LinkedIn: autenticación y publicación. Nada más.

Diseñado para leerse completo en una pantalla. Si necesitas algo que no
está aquí, escríbelo tú — no instales una plataforma de 87 herramientas
para usar tres.

API oficial (OAuth 2.0 + scope w_member_social). No usa cookies del
navegador: eso vive en zona gris de los términos de LinkedIn.
"""
from __future__ import annotations

import json
import os
import platform
import re
import stat
import subprocess
import sys
import time
from pathlib import Path

import requests

API = "https://api.linkedin.com"
# LinkedIn versiona por YYYYMM y lo exige en CADA llamada. Retira versiones a los
# ~12 meses: una version vencida devuelve 426 NONEXISTENT_VERSION y no publica nada.
# Por eso `_renegociar_version()` la recalcula sola en vez de morir en silencio.
API_VERSION = "202608"
REDIRECT_URI = "http://localhost:8765/callback"
SCOPES = ["openid", "profile", "email", "w_member_social"]

# Los secretos viven en el Keychain de macOS, nunca en un archivo de texto.
KC_CLIENT_ID = "PUBLISH_LINKEDIN_CLIENT_ID"
KC_CLIENT_SECRET = "PUBLISH_LINKEDIN_CLIENT_SECRET"
KC_TOKEN = "PUBLISH_LINKEDIN_TOKEN"

# Caracteres reservados del formato "little text" de LinkedIn. Sin escapar,
# el post se trunca o se deforma en silencio.
# https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/little-text-format
RESERVADOS = ["\\", "|", "{", "}", "[", "]", "<", ">", "*", "_", "~"]


class ErrorLinkedIn(Exception):
    """Falla esperable: sin token, token vencido, o la API respondió mal."""


# --------------------------------------------------------------------------
# Almacén de secretos
#
# En macOS: Keychain, que es lo correcto.
# Fuera de macOS: archivo en ~/.config con permisos 0600 (solo tu usuario).
# No es tan bueno como el Keychain, pero es honesto y funciona en Windows y
# Linux. La alternativa —dejar el secreto en un .json legible por todos— es
# peor, y es exactamente lo que este servidor existe para evitar.
# --------------------------------------------------------------------------

ES_MACOS = platform.system() == "Darwin"
DIR_SECRETOS = Path(
    os.environ.get("PUBLISH_LINKEDIN_HOME", Path.home() / ".config" / "publish-linkedin")
)


def _ruta_secreto(servicio: str) -> Path:
    return DIR_SECRETOS / f"{servicio}.secret"


def kc_leer(servicio: str) -> str | None:
    if ES_MACOS:
        r = subprocess.run(
            ["security", "find-generic-password", "-s", servicio, "-w"],
            capture_output=True, text=True,
        )
        return r.stdout.strip() or None if r.returncode == 0 else None
    f = _ruta_secreto(servicio)
    if not f.exists():
        return None
    return f.read_text(encoding="utf-8").strip() or None


def kc_guardar(servicio: str, valor: str) -> None:
    if ES_MACOS:
        subprocess.run(
            ["security", "add-generic-password", "-U", "-s", servicio,
             "-a", servicio, "-w", valor],
            check=True, capture_output=True,
        )
        return
    DIR_SECRETOS.mkdir(parents=True, exist_ok=True)
    os.chmod(DIR_SECRETOS, 0o700)
    f = _ruta_secreto(servicio)
    f.write_text(valor, encoding="utf-8")
    os.chmod(f, 0o600)


def donde_viven_los_secretos() -> str:
    return "Keychain de macOS" if ES_MACOS else f"{DIR_SECRETOS} (permisos 0600)"


def credenciales_app() -> tuple[str, str]:
    cid, secret = kc_leer(KC_CLIENT_ID), kc_leer(KC_CLIENT_SECRET)
    if not cid or not secret:
        raise ErrorLinkedIn(
            "Faltan credenciales de la app en el Keychain. "
            "Corre: python auth.py credenciales"
        )
    return cid, secret


def cargar_token() -> dict | None:
    crudo = kc_leer(KC_TOKEN)
    return json.loads(crudo) if crudo else None


def guardar_token(token: dict) -> None:
    kc_guardar(KC_TOKEN, json.dumps(token))


def escapar(texto: str) -> str:
    """Escapa los reservados. Deja pasar los hashtags (#palabra) intactos."""
    for c in RESERVADOS:
        texto = texto.replace(c, "\\" + c)
    # '#' solo se escapa cuando NO abre un hashtag real
    return re.sub(r"#(?![\w])", r"\\#", texto)


# --------------------------------------------------------------------------
# Cliente
# --------------------------------------------------------------------------

class LinkedIn:
    def __init__(self, token: dict):
        self.token = token
        self._urn: str | None = None

    @classmethod
    def desde_keychain(cls) -> "LinkedIn":
        token = cargar_token()
        if not token:
            raise ErrorLinkedIn("No hay token. Corre: python auth.py login")
        if token.get("expires_at", 0) < time.time():
            venc = time.strftime("%Y-%m-%d", time.localtime(token["expires_at"]))
            raise ErrorLinkedIn(f"El token venció el {venc}. Corre: python auth.py login")
        return cls(token)

    def _renegociar_version(self) -> bool:
        """LinkedIn retiró la versión fijada. Busca la más reciente que siga activa.

        Sin esto, el conector muere en silencio ~12 meses después de escribirse:
        es exactamente como caducó el repo del que se copió esta constante.
        """
        global API_VERSION
        hoy = time.localtime()
        for atras in range(0, 13):
            mes, anio = hoy.tm_mon - atras, hoy.tm_year
            while mes <= 0:
                mes += 12
                anio -= 1
            v = f"{anio}{mes:02d}"
            if v == API_VERSION:
                continue
            r = requests.get(
                f"{API}/v2/userinfo", timeout=15,
                headers={"Authorization": f"Bearer {self.token['access_token']}",
                         "X-Restli-Protocol-Version": "2.0.0", "LinkedIn-Version": v},
            )
            if "NONEXISTENT_VERSION" not in r.text:
                API_VERSION = v
                return True
        return False

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token['access_token']}",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": API_VERSION,
            "Content-Type": "application/json",
        }

    def quien_soy(self) -> dict:
        r = requests.get(f"{API}/v2/userinfo", headers=self._headers(), timeout=20)
        if r.status_code != 200:
            raise ErrorLinkedIn(f"userinfo devolvió {r.status_code}: {r.text[:300]}")
        d = r.json()
        self._urn = f"urn:li:person:{d['sub']}"
        # El correo NO se devuelve: esta salida se proyecta en pantalla.
        return {"nombre": d.get("name"), "urn": self._urn}

    def publicar(self, texto: str, visibilidad: str = "PUBLIC") -> dict:
        if not texto.strip():
            raise ErrorLinkedIn("El texto está vacío.")
        if len(texto) > 3000:
            raise ErrorLinkedIn(f"El texto tiene {len(texto)} caracteres; el máximo es 3000.")
        if self._urn is None:
            self.quien_soy()

        payload = {
            "author": self._urn,
            "commentary": escapar(texto),
            "visibility": visibilidad,
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        r = requests.post(f"{API}/rest/posts", headers=self._headers(),
                          json=payload, timeout=30)

        # Versión caducada: renegocia una vigente y reintenta UNA vez.
        if r.status_code == 426 and "NONEXISTENT_VERSION" in r.text:
            if not self._renegociar_version():
                raise ErrorLinkedIn(
                    f"La versión {API_VERSION} caducó y no encontré ninguna vigente "
                    "en los últimos 12 meses. Revisa la consola de LinkedIn Developer."
                )
            r = requests.post(f"{API}/rest/posts", headers=self._headers(),
                              json=payload, timeout=30)

        # LinkedIn limita por app y por miembro. Con muchas personas usando la
        # misma app, esto se ve — y el mensaje crudo no dice qué hacer.
        if r.status_code == 429:
            espera = r.headers.get("Retry-After")
            cuanto = f" Reintenta en {espera} segundos." if espera else " Espera unos minutos."
            raise ErrorLinkedIn(
                "LinkedIn está limitando las publicaciones (429)." + cuanto +
                " No es un error tuyo: es el límite de la app o de tu cuenta."
            )
        if r.status_code in (401, 403):
            raise ErrorLinkedIn(
                f"LinkedIn rechazó el permiso ({r.status_code}). Revisa dos cosas: "
                "que el token no haya vencido (auth.py estado) y que la app tenga "
                f"activo el producto 'Share on LinkedIn'. Respuesta: {r.text[:200]}"
            )
        if r.status_code != 201:
            raise ErrorLinkedIn(f"LinkedIn respondió {r.status_code}: {r.text[:400]}")

        urn = r.headers.get("x-restli-id", "")
        return {
            "urn": urn,
            "url": f"https://www.linkedin.com/feed/update/{urn}/" if urn else None,
            "caracteres": len(texto),
            "visibilidad": visibilidad,
        }

    @staticmethod
    def limpiar_urn(crudo: str) -> str:
        """Acepta lo que un humano realmente pega y devuelve un URN válido.

        Sirve tanto 'urn:li:share:123' como la URL completa del post o el URN
        con barra y salto de línea pegados detrás. LinkedIn rechaza cualquier
        carácter de más con un 400 críptico.
        """
        m = re.search(r"urn:li:(?:share|ugcPost|activity):\d+", crudo or "")
        if not m:
            raise ErrorLinkedIn(f"No reconozco un URN de post en: {crudo!r}")
        return m.group(0)

    def borrar(self, urn: str) -> None:
        """Borra un post ya publicado. El botón de deshacer.

        LinkedIn exige el URN percent-encoded en la ruta.
        """
        import urllib.parse
        urn = self.limpiar_urn(urn)
        r = requests.delete(
            f"{API}/rest/posts/{urllib.parse.quote(urn, safe='')}",
            headers=self._headers(), timeout=30,
        )
        if r.status_code not in (200, 204):
            raise ErrorLinkedIn(f"No se pudo borrar ({r.status_code}): {r.text[:300]}")
