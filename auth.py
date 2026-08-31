"""
Autenticación con LinkedIn. Tres comandos:

    python auth.py importar    # trae client_id/secret al Keychain (una vez)
    python auth.py login       # abre el navegador, tú das Allow, guarda el token
    python auth.py estado      # ¿tengo token? ¿hasta cuándo?

El token se guarda en el Keychain de macOS, no en un archivo.
"""
from __future__ import annotations

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


def importar_desde_mcp_json(ruta: str = "/Users/dannybravo/second-brain/.mcp.json") -> None:
    """Migra las credenciales que hoy están en texto plano hacia el Keychain."""
    try:
        env = json.load(open(ruta))["mcpServers"]["linkedin"]["env"]
        cid, secret = env["LINKEDIN_CLIENT_ID"], env["LINKEDIN_CLIENT_SECRET"]
    except (OSError, KeyError) as e:
        print(f"✗ No pude leer credenciales de {ruta}: {e}")
        print("  Guárdalas a mano:")
        print(f'  security add-generic-password -U -s {KC_CLIENT_ID} -a {KC_CLIENT_ID} -w "TU_ID"')
        print(f'  security add-generic-password -U -s {KC_CLIENT_SECRET} -a {KC_CLIENT_SECRET} -w "TU_SECRET"')
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
    guardar_token({
        "access_token": d["access_token"],
        "expires_at": int(time.time()) + int(d.get("expires_in", 0)),
        "scopes": SCOPES,
    })
    print("✓ Token guardado en el Keychain.")
    yo = LinkedIn.desde_keychain().quien_soy()
    print(f"✓ Autenticado como {yo['nombre']} ({yo['urn']})")


def estado() -> None:
    tok = cargar_token()
    if not tok:
        print("✗ Sin token. Corre: python auth.py login")
        return
    quedan = tok["expires_at"] - time.time()
    venc = time.strftime("%Y-%m-%d %H:%M", time.localtime(tok["expires_at"]))
    if quedan <= 0:
        print(f"✗ Token VENCIDO el {venc}. Corre: python auth.py login")
        return
    print(f"✓ Token vigente hasta {venc} ({int(quedan / 86400)} días)")
    print(f"  Scopes: {', '.join(tok.get('scopes', []))}")
    try:
        yo = LinkedIn.desde_keychain().quien_soy()
        print(f"✓ LinkedIn responde: {yo['nombre']} ({yo['urn']})")
    except ErrorLinkedIn as e:
        print(f"✗ El token existe pero LinkedIn lo rechaza: {e}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "estado"
    {"importar": importar_desde_mcp_json, "login": login, "estado": estado}.get(
        cmd, lambda: print(f"Comando desconocido: {cmd}\nUsa: importar | login | estado")
    )()
