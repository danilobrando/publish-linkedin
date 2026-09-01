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

import registro as R
from linkedin import (ErrorLinkedIn, LinkedIn, cargar_token,
                      donde_viven_los_secretos, escapar, kc_leer,
                      KC_CLIENT_ID)

mcp = MCPServer("publish-linkedin")

DIARIO = R.DIARIO


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

    previo = R.ya_publicado(texto)

    if not confirmar:
        R.registrar("ENSAYO", chars=len(texto), visibilidad=visibilidad,
                    huella=R.huella(texto))
        aviso = ""
        if previo:
            aviso = (f"\n⚠️  OJO: este mismo texto ya se publicó el {previo['ts']}.\n"
                     f"    {previo.get('urn', '')}\n"
                     f"    Si confirmas, me voy a negar. Cambia el texto, o borra el "
                     f"anterior con linkedin_borrar.\n")
        return (f"⏸  ENSAYO — no se publicó nada.\n{aviso}\n"
                f"Se enviaría a LinkedIn ({visibilidad}, {len(texto)}/3000 caracteres):\n"
                f"{'─' * 60}\n{texto}\n{'─' * 60}\n"
                f"Tal como lo recibe la API (con reservados escapados):\n"
                f"{escapar(texto)[:300]}{'…' if len(texto) > 300 else ''}\n\n"
                f"Para publicarlo de verdad, vuelve a llamarme con confirmar=True.")

    # Idempotencia: el fallo más caro de un publicador no es fallar, es duplicar.
    if previo:
        R.registrar("DUPLICADO_BLOQUEADO", huella=R.huella(texto),
                    urn_previo=previo.get("urn", ""))
        return (f"✗ No lo publiqué: este mismo texto ya salió el {previo['ts']}.\n"
                f"  {previo.get('urn', '')}\n"
                f"  Si de verdad quieres repetirlo, cambia algo del texto. Si el "
                f"anterior estaba mal, bórralo primero con linkedin_borrar y "
                f"entonces sí puedo republicarlo.")

    try:
        with R.Lock(f"publicar {len(texto)}c"):
            r = LinkedIn.desde_keychain().publicar(texto, visibilidad)
    except R.BloqueadoError as e:
        R.registrar("BLOQUEADO", motivo=str(e))
        return f"✗ {e}"
    except ErrorLinkedIn as e:
        R.registrar("FALLO", error=str(e)[:300])
        return f"✗ No se publicó: {e}"

    R.registrar("PUBLICADO", urn=r["urn"], chars=r["caracteres"],
                visibilidad=r["visibilidad"], huella=R.huella(texto),
                simulacro=bool(r.get("simulacro")))
    if r.get("simulacro"):
        return (f"🧪 SIMULACRO — no se tocó LinkedIn (PUBLISH_LINKEDIN_SIMULACRO activo).\n"
                f"  URN falso: {r['urn']}")
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
        R.registrar("FALLO_BORRAR", urn=urn, error=str(e)[:300])
        return f"✗ No se pudo borrar: {e}"
    limpio = LinkedIn.limpiar_urn(urn)
    R.registrar("BORRADO", urn=limpio)
    R.olvidar(limpio)   # su huella deja de bloquear una republicación
    return f"✓ Borrado de LinkedIn: {limpio}"


@mcp.tool()
def linkedin_doctor(reparar: bool = False) -> str:
    """Diagnostica el conector: credenciales, token, permisos, red, diarios, lock.

    Úsame cuando el usuario reporte CUALQUIER problema con LinkedIn antes de
    ponerte a adivinar.

    Args:
        reparar: True intenta arreglar solo lo que se pueda (locks rancios, permisos).
    """
    import doctor as D
    if reparar:
        hechos, pendientes = [], []
        if D.R.LOCK.exists():
            edad = time.time() - D.R.LOCK.stat().st_mtime
            if edad > D.R.LOCK_RANCIO:
                try:
                    D.R.LOCK.unlink()
                    hechos.append(f"Quité un lock rancio de {int(edad / 3600)}h")
                except OSError as e:
                    pendientes.append(f"No pude quitar el lock: {e}")
    cs = D.correr_chequeos()
    ancho = max(len(c["nombre"]) for c in cs)
    lineas = [f"{D.ICONO[c['estado']]} {c['nombre'].ljust(ancho)}  {c['detalle']}"
              + (f"\n  {' ' * ancho}  → {c['arreglo']}"
                 if c["arreglo"] and c["estado"] != D.OK else "")
              for c in cs]
    v = D.veredicto(cs)
    resumen = {D.OK: "Todo en orden.",
               D.AVISO: "Funciona, pero hay algo que atender.",
               D.MAL: "Hay algo roto — mira las flechas."}[v]
    return "\n".join(lineas) + f"\n\n{resumen}"


if __name__ == "__main__":
    mcp.run()
