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

try:
    from mcp.server.mcpserver import MCPServer
except ImportError as _e:  # mcp 1.x tenía esta clase con otro nombre
    raise SystemExit(
        "Necesitas mcp 2.0 o más nuevo (tienes una versión vieja donde esta "
        "clase se llamaba FastMCP).\n"
        "  .venv/bin/pip install -U 'mcp[cli]>=2.0'"
    ) from _e

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
    except Exception as e:
        return f"✗ No pude preguntarle a LinkedIn ({type(e).__name__}): {e}"
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
        previo = R.ya_publicado(texto)
        _esc = escapar(texto)
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
                f"{_esc[:300]}{'…' if len(_esc) > 300 else ''}\n\n"
                f"Para publicarlo de verdad, vuelve a llamarme con confirmar=True.")

    # Sin diario no hay protección contra duplicados. Publicar a ciegas es peor
    # que no publicar: nos negamos y lo decimos.
    if not R.diario_sano():
        return ("✗ No publico: no puedo escribir el diario de eventos.\n"
                f"  {R.DIARIO_ROTO}\n"
                "  Sin ese archivo no hay protección contra publicar dos veces "
                "lo mismo. Corre linkedin_doctor para ver cómo arreglarlo.")

    h = R.huella(texto)
    try:
        with R.Lock(f"publicar {len(texto)}c"):
            # La idempotencia se revisa DENTRO del lock: fuera, dos procesos
            # podían leer "no hay duplicado" a la vez y publicar los dos.
            previo = R.ya_publicado(texto)
            if previo:
                R.registrar("DUPLICADO_BLOQUEADO", huella=h,
                            urn_previo=previo.get("urn", ""))
                return (f"✗ No lo publiqué: este mismo texto ya salió el {previo['ts']}.\n"
                        f"  {previo.get('urn', '')}\n"
                        f"  Si el anterior estaba mal, bórralo con linkedin_borrar y "
                        f"vuelve a intentar.")

            # Escritura anticipada: si el proceso muere, o LinkedIn acepta el
            # post y se cae al responder, queda constancia de que SE INTENTÓ.
            # Sin esto, un timeout deja el post vivo y sin rastro, y el próximo
            # intento lo duplica.
            hoy = R.publicados_hoy()
            if hoy >= R.LIMITE_DIARIO:
                R.registrar("LIMITE_DIARIO", publicados=hoy)
                return (f"✗ No publico: ya salieron {hoy} posts en las últimas 24 "
                        f"horas y el techo es {R.LIMITE_DIARIO}.\n"
                        f"  Es un límite de daño, por si algo se quedó en bucle. "
                        f"Súbelo con PUBLISH_LINKEDIN_LIMITE_DIARIO si de verdad "
                        f"quieres publicar más.")

            R.registrar("INTENTO", huella=h, chars=len(texto), visibilidad=visibilidad,
                        extracto=texto[:120])
            r = LinkedIn.desde_keychain().publicar(texto, visibilidad)
    except R.BloqueadoError as e:
        R.registrar("BLOQUEADO", huella=h, motivo=str(e))
        return f"✗ {e}"
    except ErrorLinkedIn as e:
        R.registrar("FALLO", huella=h, error=str(e)[:300])
        return f"✗ No se publicó: {e}"
    except Exception as e:
        # Red caída, DNS, timeout, proxy que devuelve HTML. Es el modo de falla
        # más común y el único que antes no dejaba ni una línea en el diario.
        R.registrar("FALLO_RED", huella=h, tipo=type(e).__name__, error=str(e)[:300])
        return (f"✗ No se pudo publicar ({type(e).__name__}): {e}\n"
                f"  OJO: si esto fue un timeout, el post PUDO haberse creado. "
                f"Revisa tu perfil antes de reintentar.\n"
                f"  Diagnostica con linkedin_doctor.")

    R.registrar("PUBLICADO", urn=r["urn"], chars=r["caracteres"],
                visibilidad=r["visibilidad"], huella=h,
                extracto=texto[:120], simulacro=bool(r.get("simulacro")))
    if r.get("simulacro"):
        return (f"🧪 SIMULACRO — no se tocó LinkedIn (PUBLISH_LINKEDIN_SIMULACRO activo).\n"
                f"  URN falso: {r['urn']}")
    return f"✓ Publicado.\n  {r['url']}\n  {r['urn']}"


@mcp.tool()
def linkedin_borrar(urn: str, confirmar: bool = False) -> str:
    """Borra un post publicado. El botón de deshacer.

    FRENO DE MANO: igual que publicar, no borra sin confirmar=True. Borrar es
    irreversible y el URN puede venir de cualquier parte del contexto.

    Args:
        urn: el URN que devolvió linkedin_publicar (urn:li:share:… o urn:li:ugcPost:…)
        confirmar: True para borrar de verdad. False = solo dice qué borraría.
    """
    try:
        limpio_previo = LinkedIn.limpiar_urn(urn)
    except ErrorLinkedIn as e:
        return f"✗ {e}"
    if not confirmar:
        return (f"⏸  ENSAYO — no se borró nada.\n"
                f"Se borraría de LinkedIn, de forma irreversible:\n"
                f"  {limpio_previo}\n"
                f"  https://www.linkedin.com/feed/update/{limpio_previo}/\n\n"
                f"Para borrarlo de verdad, vuelve a llamarme con confirmar=True.")
    try:
        LinkedIn.desde_keychain().borrar(urn)
    except ErrorLinkedIn as e:
        R.registrar("FALLO_BORRAR", urn=urn, error=str(e)[:300])
        return f"✗ No se pudo borrar: {e}"
    except Exception as e:
        R.registrar("FALLO_BORRAR", urn=urn, tipo=type(e).__name__, error=str(e)[:300])
        return f"✗ No se pudo borrar ({type(e).__name__}): {e}"
    from linkedin import SIMULACRO
    R.registrar("BORRADO", urn=limpio_previo, simulacro=SIMULACRO)
    R.olvidar(limpio_previo)   # su huella deja de bloquear una republicación
    if SIMULACRO:
        return f"🧪 SIMULACRO — no se tocó LinkedIn. URN: {limpio_previo}"
    return f"✓ Borrado de LinkedIn: {limpio_previo}"


@mcp.tool()
def linkedin_doctor(reparar: bool = False) -> str:
    """Diagnostica el conector: credenciales, token, permisos, red, diarios, lock.

    Úsame cuando el usuario reporte CUALQUIER problema con LinkedIn antes de
    ponerte a adivinar.

    Args:
        reparar: True intenta arreglar solo lo que se pueda (locks rancios, permisos).
    """
    import doctor as D
    reparaciones = []
    if reparar:
        if D.R.LOCK.exists():
            edad = time.time() - D.R.LOCK.stat().st_mtime
            if edad > D.R.LOCK_RANCIO:
                try:
                    D.R.LOCK.unlink()
                    D.R.registrar("FIX", accion="lock_rancio_eliminado", edad_s=int(edad))
                    reparaciones.append(f"✓ Quité un lock rancio de {int(edad / 3600)}h")
                except OSError as e:
                    reparaciones.append(f"✗ No pude quitar el lock: {e}")
            else:
                reparaciones.append(f"· Hay una publicación en curso ({int(edad)}s). Espera.")
        try:
            import os as _os
            D.R._asegurar_home()
            if _os.name != "nt":
                modo = D.R.HOME.stat().st_mode & 0o777
                if modo != 0o700:
                    _os.chmod(D.R.HOME, 0o700)
                    reparaciones.append(f"✓ Corregí permisos de {D.R.HOME}")
        except OSError as e:
            reparaciones.append(f"✗ No pude ajustar permisos: {e}")
        if not reparaciones:
            reparaciones.append("· No había nada que reparar automáticamente")
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
    cabeza = ("\n".join(reparaciones) + "\n\n") if reparaciones else ""
    return cabeza + "\n".join(lineas) + f"\n\n{resumen}"


if __name__ == "__main__":
    mcp.run()
