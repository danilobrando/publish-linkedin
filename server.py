"""
Servidor MCP: publish-linkedin

Tres herramientas. Ni una más.

    linkedin_estado()      ¿estoy autenticado y hasta cuándo?
    linkedin_quien_soy()   ¿como quién voy a publicar?
    linkedin_publicar()    publica — con freno de mano

El freno de mano: `publicar` NO publica a menos que reciba confirmar=True.
Sin eso hace un ensayo y te muestra exactamente qué saldría. Un sistema
autónomo sin freno no es autonomía, es un accidente esperando.

Cada publicación real queda registrada en el diario de auditoría.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from linkedin import (ErrorLinkedIn, LinkedIn, cargar_token,
                      donde_viven_los_secretos, escapar, kc_leer,
                      KC_CLIENT_ID)

mcp = MCPServer("publish-linkedin")

DIARIO = Path(os.environ.get(
    "PUBLISH_LINKEDIN_LOG",
    Path.home() / ".config" / "publish-linkedin" / "publicaciones.log",
))


def _registrar(linea: str) -> None:
    DIARIO.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with DIARIO.open("a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')}\t{linea}\n")


@mcp.tool()
def linkedin_estado() -> str:
    """Revisa si hay un token de LinkedIn vigente y qué permisos tiene."""
    if not kc_leer(KC_CLIENT_ID):
        return ("✗ Todavía no hay credenciales de tu app de LinkedIn.\n"
                "  En la terminal, dentro de la carpeta del proyecto:\n"
                "    .venv/bin/python auth.py credenciales\n"
                "  Las sacas de linkedin.com/developers/apps → pestaña Auth.")
    tok = cargar_token()
    if not tok:
        return ("✗ Ya hay credenciales, pero falta autenticarte.\n"
                "  En la terminal: .venv/bin/python auth.py login")
    quedan = tok["expires_at"] - time.time()
    venc = time.strftime("%Y-%m-%d %H:%M", time.localtime(tok["expires_at"]))
    if quedan <= 0:
        return f"✗ Token VENCIDO el {venc}. En la terminal: python auth.py login"
    return (f"✓ Token vigente hasta {venc} ({int(quedan / 86400)} días)\n"
            f"  Permisos: {', '.join(tok.get('scopes', []))}\n"
            f"  Secretos en: {donde_viven_los_secretos()}\n"
            f"  Diario de auditoría: {DIARIO}")


@mcp.tool()
def linkedin_quien_soy() -> str:
    """Confirma contra LinkedIn en qué cuenta se publicaría. Verifica que el token sirve."""
    try:
        yo = LinkedIn.desde_keychain().quien_soy()
    except ErrorLinkedIn as e:
        return f"✗ {e}"
    return f"✓ {yo['nombre']}\n  {yo['urn']}"


@mcp.tool()
def linkedin_publicar(texto: str, confirmar: bool = False,
                      visibilidad: str = "PUBLIC") -> str:
    """Publica un post en LinkedIn.

    FRENO DE MANO: con confirmar=False (el default) NO publica — hace un
    ensayo y devuelve exactamente qué se enviaría. Solo publica de verdad
    cuando un humano pasa confirmar=True.

    Args:
        texto: el post. Máximo 3000 caracteres.
        confirmar: True para publicar de verdad. False = ensayo.
        visibilidad: PUBLIC (todos) o CONNECTIONS (solo contactos).
    """
    if visibilidad not in ("PUBLIC", "CONNECTIONS"):
        return f"✗ Visibilidad inválida: {visibilidad}. Usa PUBLIC o CONNECTIONS."
    if len(texto) > 3000:
        return f"✗ El texto tiene {len(texto)} caracteres; el máximo son 3000."
    if not texto.strip():
        return "✗ El texto está vacío."

    if not confirmar:
        _registrar(f"ENSAYO\t{len(texto)} chars\t{visibilidad}")
        return (f"⏸  ENSAYO — no se publicó nada.\n\n"
                f"Se enviaría a LinkedIn ({visibilidad}, {len(texto)}/3000 caracteres):\n"
                f"{'─' * 60}\n{texto}\n{'─' * 60}\n"
                f"Tal como lo recibe la API (con reservados escapados):\n"
                f"{escapar(texto)[:300]}{'…' if len(texto) > 300 else ''}\n\n"
                f"Para publicarlo de verdad, vuelve a llamarme con confirmar=True.")

    try:
        r = LinkedIn.desde_keychain().publicar(texto, visibilidad)
    except ErrorLinkedIn as e:
        _registrar(f"FALLO\t{e}")
        return f"✗ No se publicó: {e}"

    _registrar(f"PUBLICADO\t{r['urn']}\t{r['caracteres']} chars\t{r['visibilidad']}")
    return f"✓ Publicado.\n  {r['url']}\n  {r['urn']}"


@mcp.tool()
def linkedin_borrar(urn: str) -> str:
    """Borra un post que acabas de publicar. El botón de deshacer.

    Args:
        urn: el URN que devolvió linkedin_publicar (urn:li:share:… o urn:li:ugcPost:…)
    """
    try:
        LinkedIn.desde_keychain().borrar(urn)
    except ErrorLinkedIn as e:
        _registrar(f"FALLO_BORRAR\t{urn}\t{e}")
        return f"✗ No se pudo borrar: {e}"
    _registrar(f"BORRADO\t{urn}")
    return f"✓ Borrado de LinkedIn: {urn}"


if __name__ == "__main__":
    mcp.run()
