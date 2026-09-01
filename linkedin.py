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
# Se pide el mínimo. `email` se quitó: nunca se usó, y pedir un permiso que no
# necesitas es lo que hace que la gente le desconfíe a una app.
SCOPES = ["openid", "profile", "w_member_social"]

# Los secretos viven en el Keychain de macOS, nunca en un archivo de texto.
KC_CLIENT_ID = "PUBLISH_LINKEDIN_CLIENT_ID"
KC_CLIENT_SECRET = "PUBLISH_LINKEDIN_CLIENT_SECRET"
KC_TOKEN = "PUBLISH_LINKEDIN_TOKEN"

# Caracteres reservados del formato "little text" de LinkedIn. Sin escapar,
# el post se trunca o se deforma en silencio.
# https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/little-text-format
# El backslash va PRIMERO o se escaparían los escapes que agregamos después.
# '@', '(' y ')' también son reservados según la doc de little text: sin
# escaparlos, un "(hola)" puede interpretarse como marcado y deformar el post.
RESERVADOS = ["\\", "|", "{", "}", "[", "]", "(", ")", "<", ">", "*", "_", "~", "@"]

# Freno de seguridad para pruebas. Con PUBLISH_LINKEDIN_SIMULACRO=1, publicar()
# y borrar() NUNCA tocan la red: devuelven una respuesta falsa y lo declaran.
#
# Existe porque el 31-ago-2026 dos pruebas automatizadas publicaron de verdad en
# un perfil real. Redirigir el directorio de datos no basta: el token vive en el
# Keychain y sigue siendo válido. Una suite de pruebas jamás debe poder escribir
# en producción por accidente.
SIMULACRO = os.environ.get("PUBLISH_LINKEDIN_SIMULACRO", "") not in ("", "0", "false")


class ErrorLinkedIn(Exception):
    """Falla esperable: sin token, token vencido, o la API respondió mal."""


# --------------------------------------------------------------------------
# Catálogo de errores
#
# LinkedIn responde con códigos y cuerpos que no dicen qué hacer. Cada entrada
# traduce un fallo real a una frase que el usuario puede actuar. Si un error no
# está aquí, se muestra crudo — pero entonces falta una entrada.
# --------------------------------------------------------------------------

CATALOGO = {
    "NONEXISTENT_VERSION": (
        "LinkedIn retiró la versión de API que estábamos usando. El cliente busca "
        "una vigente y reintenta solo; si ves esto, la renegociación también falló."),
    "REVOKED_ACCESS_TOKEN": (
        "Revocaste el acceso desde LinkedIn (o lo hizo el dueño de la app). "
        "Corre: python auth.py login"),
    "EXPIRED_ACCESS_TOKEN": (
        "El token venció. Corre: python auth.py login"),
    "INVALID_ACCESS_TOKEN": (
        "El token no sirve. Suele pasar si rotaron el Client Secret de la app. "
        "Corre: python auth.py login"),
    "ACCESS_DENIED": (
        "A la app le falta el producto 'Share on LinkedIn', o el token no pidió "
        "el permiso w_member_social. Revisa la pestaña Products y vuelve a hacer login."),
    "UGC_VALIDATIONS_FAILED": (
        "LinkedIn rechazó el contenido del post. Casi siempre es un URN mal formado "
        "o un carácter reservado sin escapar."),
    "NOT_FOUND": (
        "Ese post no existe. O ya lo borraste, o el URN no es de un post tuyo."),
    "DUPLICATE_POST": (
        "LinkedIn detectó que ya publicaste algo idéntico. Cambia el texto."),
}


def traducir_error(codigo: int, cuerpo: str) -> str:
    """Convierte una respuesta cruda de LinkedIn en algo que se pueda actuar."""
    for clave, explicacion in CATALOGO.items():
        if clave in (cuerpo or ""):
            return f"{explicacion} (LinkedIn dijo {clave}, HTTP {codigo})"
    if codigo == 429:
        return "LinkedIn está limitando las publicaciones. Espera unos minutos."
    if codigo in (401, 403):
        return ("LinkedIn rechazó el permiso. Revisa que el token no haya vencido "
                "(python auth.py estado) y que la app tenga 'Share on LinkedIn'.")
    if codigo >= 500:
        return "LinkedIn tuvo un error de su lado. Reintenta en un momento."
    return f"LinkedIn respondió {codigo}: {(cuerpo or '')[:200]}"



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


def _escapar_tramo(texto: str) -> str:
    for c in RESERVADOS:
        texto = texto.replace(c, "\\" + c)
    # '#' solo se escapa cuando NO abre un hashtag real
    return re.sub(r"#(?![\w])", r"\\#", texto)


def escapar(texto: str) -> str:
    """Escapa los reservados, **sin destrozar las menciones**.

    Una mención se escribe `@[Nombre](urn:li:person:X)` y usa cuatro caracteres
    que también son reservados: `@ [ ] ( )`. Escaparlos a ciegas convierte la
    etiqueta en texto literal — el post sale con los corchetes a la vista y sin
    notificar a nadie. Por eso el texto se parte en tramos y solo se escapa lo
    que NO es una anotación.
    """
    from menciones import partir
    return "".join(t if es_anotacion else _escapar_tramo(t)
                   for es_anotacion, t in partir(texto))


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
            # Solo se acepta una versión que LinkedIn respondió BIEN. Antes
            # bastaba con que la respuesta no trajera el string, así que un 401
            # o un error de red promovía una versión cualquiera y enmascaraba
            # el problema real.
            if r.status_code == 200:
                API_VERSION = v
                return True
        return False

    def _post_con_reintento(self, payload: dict, intentos: int = 3):
        """POST reintentando SOLO ante 429.

        Un 429 significa que LinkedIn rechazó la petición sin procesarla: es
        seguro repetirla. Un 5xx NO dice nada — LinkedIn pudo haber creado el
        post y haberse caído al responder (típico cuando hay un CDN de por
        medio). Reintentar ahí publica dos veces.

        Esto estuvo mal escrito: el código reintentaba también ante 5xx, con un
        comentario que afirmaba que era seguro "porque quien llama ya pasó el
        control de idempotencia". Era falso — ese control lee eventos ya
        escritos, y el PUBLICADO de esta llamada todavía no existe. El fallo
        más caro del proyecto estaba dentro del intento de evitarlo.
        """
        espera = 2
        for intento in range(1, intentos + 1):
            r = requests.post(f"{API}/rest/posts", headers=self._headers(),
                              json=payload, timeout=30)
            if r.status_code != 429 or intento == intentos:
                return r
            try:
                pausa = min(int(r.headers.get("Retry-After", espera)), 60)
            except (TypeError, ValueError):
                pausa = espera
            time.sleep(pausa)
            espera *= 2
        return r

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token['access_token']}",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": API_VERSION,
            "Content-Type": "application/json",
        }

    def quien_soy(self) -> dict:
        if SIMULACRO:
            self._urn = "urn:li:person:SIMULACRO"
            return {"nombre": "Perfil de simulacro", "urn": self._urn}
        r = requests.get(f"{API}/v2/userinfo", headers=self._headers(), timeout=20)
        # Si la versión de API caducó, esto falla igual que publicar. Sin esta
        # renegociación, el doctor y `auth.py estado` reportarían "roto" con un
        # mensaje que no dice que basta con cambiar un número.
        if r.status_code == 426 and "NONEXISTENT_VERSION" in r.text:
            if self._renegociar_version():
                r = requests.get(f"{API}/v2/userinfo", headers=self._headers(), timeout=20)
        if r.status_code != 200:
            raise ErrorLinkedIn(traducir_error(r.status_code, r.text))
        d = r.json()
        self._urn = f"urn:li:person:{d['sub']}"
        # El correo NO se devuelve: esta salida se proyecta en pantalla.
        return {"nombre": d.get("name"), "urn": self._urn}

    def publicar(self, texto: str, visibilidad: str = "PUBLIC",
                 adjunto: str | None = None, titulo: str | None = None) -> dict:
        if not texto.strip():
            raise ErrorLinkedIn("El texto está vacío.")
        # LinkedIn cuenta el texto YA escapado. Un post lleno de reservados
        # puede pasar de 3000 al escaparse aunque el original no llegara.
        escapado = escapar(texto)
        if len(escapado) > 3000:
            extra = f" (queda en {len(escapado)} al escapar los caracteres reservados)" \
                if len(escapado) != len(texto) else ""
            raise ErrorLinkedIn(
                f"El texto tiene {len(texto)} caracteres{extra}; el máximo es 3000.")
        if self._urn is None:
            self.quien_soy()

        # El adjunto se valida SIEMPRE, incluso en simulacro: así una ruta mala
        # o un archivo demasiado pesado se detectan probando, no publicando.
        clase_adjunto = None
        if adjunto:
            from medios import ErrorMedio, clasificar, subir
            try:
                _, clase_adjunto, _ = clasificar(adjunto)
            except ErrorMedio as e:
                raise ErrorLinkedIn(str(e)) from e

        if SIMULACRO:
            falso = f"urn:li:share:SIMULACRO{abs(hash(texto)) % 10**16}"
            return {"urn": falso, "url": None, "caracteres": len(texto),
                    "visibilidad": visibilidad, "simulacro": True,
                    "adjunto": clase_adjunto}

        contenido = None
        if adjunto:
            urn_medio, clase_adjunto = subir(
                self._headers(), API, self._urn, adjunto, self.token["access_token"])
            # Las imágenes llevan altText (accesibilidad); los documentos, title
            # (es lo que LinkedIn muestra como nombre del PDF en el feed).
            if clase_adjunto == "imagen":
                contenido = {"media": {"id": urn_medio, "altText": titulo or ""}}
            else:
                from pathlib import Path as _P
                contenido = {"media": {"id": urn_medio,
                                       "title": titulo or _P(adjunto).stem}}

        payload = {
            "author": self._urn,
            "commentary": escapado,
            "visibility": visibilidad,
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        if contenido:
            payload["content"] = contenido
        r = self._post_con_reintento(payload)

        # Versión caducada: renegocia una vigente y reintenta UNA vez.
        if r.status_code == 426 and "NONEXISTENT_VERSION" in r.text:
            if not self._renegociar_version():
                raise ErrorLinkedIn(
                    f"La versión {API_VERSION} caducó y no encontré ninguna vigente "
                    "en los últimos 12 meses. Revisa la consola de LinkedIn Developer."
                )
            r = self._post_con_reintento(payload)

        # LinkedIn limita por app y por miembro. Con muchas personas usando la
        # misma app, esto se ve — y el mensaje crudo no dice qué hacer.
        if r.status_code >= 500:
            raise ErrorLinkedIn(
                f"LinkedIn falló de su lado ({r.status_code}) y NO reintenté a "
                "propósito: puede que el post SÍ se haya creado y no lo sepamos. "
                "Revisa tu perfil antes de volver a publicar."
            )
        if r.status_code != 201:
            raise ErrorLinkedIn(traducir_error(r.status_code, r.text))

        urn = r.headers.get("x-restli-id", "")
        return {
            "urn": urn,
            "url": f"https://www.linkedin.com/feed/update/{urn}/" if urn else None,
            "caracteres": len(texto),
            "visibilidad": visibilidad,
            "adjunto": clase_adjunto,
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
        if SIMULACRO:
            return
        r = requests.delete(
            f"{API}/rest/posts/{urllib.parse.quote(urn, safe='')}",
            headers=self._headers(), timeout=30,
        )
        if r.status_code not in (200, 204):
            raise ErrorLinkedIn(traducir_error(r.status_code, r.text))
