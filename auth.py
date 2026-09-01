"""
Autenticación con LinkedIn. Tres comandos:

    python auth.py credenciales  # pega el client_id/secret de tu app → Keychain
    python auth.py login         # abre el navegador, tú das Allow, guarda el token
    python auth.py estado        # ¿tengo token? ¿hasta cuándo?

    python auth.py importar [ruta]   # (opcional) migra credenciales desde un .mcp.json

El token se guarda en el Keychain de macOS, no en un archivo.
"""
from __future__ import annotations

import getpass
import http.server
import json
import secrets
import sys
import threading
import time
import urllib.parse
import webbrowser

import requests

from linkedin import (KC_CLIENT_ID, KC_CLIENT_SECRET, KC_TOKEN, REDIRECT_URI,
                      SCOPES, ErrorLinkedIn, LinkedIn, cargar_token,
                      credenciales_app, guardar_token, kc_guardar, kc_leer)

AUTORIZAR = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
PUERTO = 8765

_recibido: dict = {}


class _Callback(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        _recibido.update({k: v[0] for k, v in q.items()})
        ok = "code" in _recibido
        cuerpo = ("<h2>Listo. Ya puedes cerrar esta pestaña.</h2>" if ok
                  else f"<h2>Falló: {_recibido.get('error_description', 'sin código')}</h2>")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(f"<html><body style='font-family:sans-serif;padding:3rem'>{cuerpo}</body></html>".encode())

    def log_message(self, *a):  # silencio
        pass


def credenciales() -> None:
    """Pide el Client ID y el Secret de tu app y los guarda en el Keychain.

    Se piden por teclado a propósito: pasarlos como argumento los dejaría
    guardados en el historial del shell.
    """
    print("Los encuentras en https://www.linkedin.com/developers/apps → pestaña Auth\n")
    cid = input("Client ID: ").strip()
    secret = getpass.getpass("Client Secret (no se ve al escribir): ").strip()
    if not cid or not secret:
        print("✗ Ambos son obligatorios.")
        sys.exit(1)
    kc_guardar(KC_CLIENT_ID, cid)
    kc_guardar(KC_CLIENT_SECRET, secret)
    print(f"\n✓ Guardadas en el Keychain (client_id …{cid[-4:]})")
    print("  Siguiente: python auth.py login")


def importar_desde_mcp_json(ruta: str | None = None) -> None:
    """Migra credenciales que ya estén en un .mcp.json hacia el Keychain.

    Solo sirve si ya tenías el servidor configurado con las credenciales en
    texto plano. Si vienes de cero, usa `credenciales`.
    """
    ruta = ruta or (sys.argv[2] if len(sys.argv) > 2 else "")
    if not ruta:
        print("✗ Falta la ruta: python auth.py importar /ruta/al/.mcp.json")
        print("  Si vienes de cero, usa: python auth.py credenciales")
        sys.exit(1)
    try:
        env = json.load(open(ruta))["mcpServers"]["linkedin"]["env"]
        cid, secret = env["LINKEDIN_CLIENT_ID"], env["LINKEDIN_CLIENT_SECRET"]
    except (OSError, KeyError, json.JSONDecodeError) as e:
        print(f"✗ No pude leer credenciales de {ruta}: {e}")
        print("  Usa mejor: python auth.py credenciales")
        sys.exit(1)
    kc_guardar(KC_CLIENT_ID, cid)
    kc_guardar(KC_CLIENT_SECRET, secret)
    print(f"✓ Credenciales en el Keychain (client_id …{cid[-4:]})")
    print(f"  Ojo: siguen también en texto plano en {ruta} — bórralas de ahí cuando esto funcione.")


def login() -> None:
    cid, secret = credenciales_app()
    estado = secrets.token_urlsafe(16)

    servidor = http.server.HTTPServer(("localhost", PUERTO), _Callback)
    threading.Thread(target=servidor.handle_request, daemon=True).start()

    url = AUTORIZAR + "?" + urllib.parse.urlencode({
        "response_type": "code", "client_id": cid,
        "redirect_uri": REDIRECT_URI, "state": estado, "scope": " ".join(SCOPES),
    })
    print("Abriendo el navegador. Dale Allow.\nSi no abre solo:\n  " + url)
    webbrowser.open(url)

    limite = time.time() + 120
    while not _recibido and time.time() < limite:
        time.sleep(0.3)

    if not _recibido:
        print("✗ Se agotaron los 2 minutos sin respuesta.")
        sys.exit(1)
    if "code" not in _recibido:
        print(f"✗ LinkedIn devolvió error: {_recibido.get('error_description', _recibido)}")
        sys.exit(1)
    if _recibido.get("state") != estado:
        print("✗ El 'state' no coincide. Aborto por seguridad (posible CSRF).")
        sys.exit(1)

    r = requests.post(TOKEN_URL, timeout=30, data={
        "grant_type": "authorization_code", "code": _recibido["code"],
        "redirect_uri": REDIRECT_URI, "client_id": cid, "client_secret": secret,
    })
    if r.status_code != 200:
        print(f"✗ Falló el canje del código ({r.status_code}): {r.text[:300]}")
        sys.exit(1)

    d = r.json()
    token = {
        "access_token": d["access_token"],
        "expires_at": int(time.time()) + int(d.get("expires_in", 0)),
        "scopes": SCOPES,
    }
    # LinkedIn solo entrega refresh_token a apps aprobadas para ello. La mayoría
    # no lo recibe y hay que volver a autorizar cada ~60 días. Si algún día llega,
    # lo guardamos para poder renovarlo sin intervención.
    if d.get("refresh_token"):
        token["refresh_token"] = d["refresh_token"]
        token["refresh_expires_at"] = int(time.time()) + int(
            d.get("refresh_token_expires_in", 0))
        print("✓ La app entrega refresh_token: se podrá renovar sin volver a autorizar.")
    else:
        print("  Nota: esta app no entrega refresh_token. Vas a tener que volver a")
        print("  correr 'auth.py login' cuando venza (~60 días). El vigilante te avisa.")
    guardar_token(token)
    print("✓ Token guardado en el Keychain.")
    yo = LinkedIn.desde_keychain().quien_soy()
    print(f"✓ Autenticado como {yo['nombre']} ({yo['urn']})")


def estado() -> int:
    cid = kc_leer(KC_CLIENT_ID)
    if not cid or not kc_leer(KC_CLIENT_SECRET):
        print("✗ Todavía no hay credenciales de la app. "
              "Corre: python auth.py credenciales", file=sys.stderr)
        return 2
    print(f"✓ Credenciales de la app guardadas (client_id …{cid[-4:]})")
    tok = cargar_token()
    if not tok:
        print("✗ Falta autenticarte. Corre: python auth.py login", file=sys.stderr)
        return 2
    quedan = tok["expires_at"] - time.time()
    venc = time.strftime("%Y-%m-%d %H:%M", time.localtime(tok["expires_at"]))
    if quedan <= 0:
        print(f"✗ Token VENCIDO el {venc}. Corre: python auth.py login", file=sys.stderr)
        return 2
    print(f"✓ Token vigente hasta {venc} ({int(quedan / 86400)} días)")
    print(f"  Scopes: {', '.join(tok.get('scopes', []))}")
    try:
        yo = LinkedIn.desde_keychain().quien_soy()
        print(f"✓ LinkedIn responde: {yo['nombre']} ({yo['urn']})")
    except ErrorLinkedIn as e:
        print(f"✗ El token existe pero LinkedIn lo rechaza: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "estado"
    comandos = {"credenciales": credenciales, "importar": importar_desde_mcp_json,
                "login": login, "estado": estado}
    if cmd not in comandos:
        print(f"Comando desconocido: {cmd}\n"
              "Usa: credenciales | login | estado | importar <ruta>", file=sys.stderr)
        sys.exit(64)   # EX_USAGE
    sys.exit(comandos[cmd]() or 0)
