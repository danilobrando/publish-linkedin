"""
Diagnóstico y auto-reparación.

    python doctor.py            # 8 chequeos, en español, con qué hacer en cada uno
    python doctor.py --quiet    # solo el veredicto (para automatizaciones)
    python doctor.py fix        # repara lo que se pueda solo
    python doctor.py fix --quiet

Un conector que falla en silencio es peor que uno que no existe: crees que
está funcionando. Esto existe para que la respuesta a "¿por qué no publicó?"
tome 5 segundos y no 40 minutos.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import registro as R

OK, AVISO, MAL = "ok", "aviso", "mal"
ICONO = {OK: "✓", AVISO: "!", MAL: "✗"}

# Días antes del vencimiento en que empezamos a avisar. El token dura ~60 y
# LinkedIn no manda ningún aviso: si nadie mira, se vence y el conector muere
# el día menos oportuno.
AVISO_VENCIMIENTO_DIAS = 7


def _chequeo(nombre, estado, detalle, arreglo=""):
    return {"nombre": nombre, "estado": estado, "detalle": detalle, "arreglo": arreglo}


def correr_chequeos() -> list[dict]:
    out = []

    # 0 · Simulacro. Si está activo, NADA de lo que sigue tocó LinkedIn: un
    # tablero verde aquí no significa que el conector funcione. El vigilante
    # diario quedaría ciego sin este aviso.
    if os.environ.get("PUBLISH_LINKEDIN_SIMULACRO", "") not in ("", "0", "false"):
        out.append(_chequeo("Modo", AVISO,
                            "SIMULACRO activo: no se contacta a LinkedIn",
                            "unset PUBLISH_LINKEDIN_SIMULACRO para un diagnóstico real"))

    # 1 · Dependencias
    try:
        import mcp, requests  # noqa: F401
        out.append(_chequeo("Dependencias", OK, "mcp y requests instalados"))
    except ImportError as e:
        out.append(_chequeo("Dependencias", MAL, f"falta {e.name}",
                            ".venv/bin/pip install -r requirements.txt"))
        return out  # sin esto no se puede seguir

    from linkedin import (KC_CLIENT_ID, KC_CLIENT_SECRET, REDIRECT_URI, SCOPES,
                          ErrorLinkedIn, LinkedIn, cargar_token,
                          donde_viven_los_secretos, kc_leer)

    # 2 · Almacén de secretos
    out.append(_chequeo("Almacén de secretos", OK, donde_viven_los_secretos()))

    # 3 · Credenciales de la app
    cid = kc_leer(KC_CLIENT_ID)
    if cid and kc_leer(KC_CLIENT_SECRET):
        out.append(_chequeo("Credenciales de la app", OK, f"client_id …{cid[-4:]}"))
    else:
        out.append(_chequeo("Credenciales de la app", MAL, "no están guardadas",
                            "python auth.py credenciales"))
        return out

    # 4 · Token
    tok = cargar_token()
    if not tok:
        out.append(_chequeo("Token", MAL, "no hay token", "python auth.py login"))
        return out
    quedan = tok.get("expires_at", 0) - time.time()
    venc = time.strftime("%Y-%m-%d %H:%M", time.localtime(tok.get("expires_at", 0)))
    if quedan <= 0:
        out.append(_chequeo("Token", MAL, f"VENCIÓ el {venc}", "python auth.py login"))
        return out
    dias = int(quedan / 86400)
    if dias <= AVISO_VENCIMIENTO_DIAS:
        out.append(_chequeo("Token", AVISO, f"vence en {dias} días ({venc})",
                            "python auth.py login  ← hazlo antes de que se venza"))
    else:
        out.append(_chequeo("Token", OK, f"vigente {dias} días (hasta {venc})"))

    # 5 · Permiso de publicar
    if "w_member_social" in tok.get("scopes", []):
        out.append(_chequeo("Permiso de publicar", OK, "w_member_social presente"))
    else:
        out.append(_chequeo("Permiso de publicar", MAL,
                            "falta w_member_social — el token no puede publicar",
                            "Activa 'Share on LinkedIn' en la app y corre auth.py login"))

    # 6 · LinkedIn responde (red + token válido + versión de API viva)
    try:
        yo = LinkedIn.desde_keychain().quien_soy()
        out.append(_chequeo("LinkedIn responde", OK, f"{yo['nombre']} · {yo['urn']}"))
    except ErrorLinkedIn as e:
        out.append(_chequeo("LinkedIn responde", MAL, str(e)[:140],
                            "python auth.py login"))
    except Exception as e:  # red caída, DNS, proxy
        out.append(_chequeo("LinkedIn responde", MAL, f"sin conexión: {type(e).__name__}",
                            "Revisa tu internet y vuelve a correr el doctor"))

    # 7 · Diarios escribibles — se verifica LEYENDO DE VUELTA.
    # Antes era `try: registrar() except: MAL`, y como registrar() nunca levanta
    # excepciones, el chequeo era estructuralmente incapaz de fallar: juraba que
    # los diarios se escribían mientras no se escribían.
    marca = f"doctor-{os.getpid()}-{int(time.time())}"
    R.registrar("DOCTOR", chequeo=marca)
    if R.DIARIO_ROTO:
        out.append(_chequeo("Diarios", MAL, f"no se puede escribir: {R.DIARIO_ROTO}",
                            f"Revisa permisos de {R.EVENTOS} y de {R.HOME}"))
    elif any(d.get("chequeo") == marca for d in R.leer_eventos(int(time.time()) - 60)):
        out.append(_chequeo("Diarios", OK, f"{R.HOME} (escrito y releído)"))
    else:
        out.append(_chequeo("Diarios", MAL,
                            "escribí pero no pude releer el evento",
                            f"Revisa {R.EVENTOS}: puede estar corrupto o lleno"))

    # 8 · Lock
    if R.LOCK.exists():
        edad = time.time() - R.LOCK.stat().st_mtime
        if edad > R.LOCK_RANCIO:
            out.append(_chequeo("Lock", AVISO, f"hay un lock rancio de {int(edad/3600)}h",
                                "python doctor.py fix"))
        else:
            out.append(_chequeo("Lock", AVISO, f"publicación en curso ({int(edad)}s)",
                                "Espera a que termine"))
    else:
        out.append(_chequeo("Lock", OK, "libre"))

    # 9 · Registro en Claude Code (informativo: no siempre hay CLI disponible)
    out.append(_chequeo("Redirect URI", OK, REDIRECT_URI +
                        "  ← debe estar igual en la pestaña Auth de tu app"))
    return out


def version() -> str:
    """Versión del conector. Para que un reporte de bug diga contra qué corría."""
    v = (Path(__file__).parent / "VERSION")
    return v.read_text(encoding="utf-8").strip() if v.exists() else "desconocida"


def veredicto(chequeos: list[dict]) -> str:
    if any(c["estado"] == MAL for c in chequeos):
        return MAL
    if any(c["estado"] == AVISO for c in chequeos):
        return AVISO
    return OK


def doctor(quiet: bool = False) -> int:
    cs = correr_chequeos()
    v = veredicto(cs)
    if quiet:
        malos = [c["nombre"] for c in cs if c["estado"] == MAL]
        print(f"{v}" + (f": {', '.join(malos)}" if malos else ""))
        return 0 if v == OK else (1 if v == AVISO else 2)
    ancho = max(len(c["nombre"]) for c in cs)
    for c in cs:
        print(f"  {ICONO[c['estado']]} {c['nombre'].ljust(ancho)}  {c['detalle']}")
        if c["arreglo"] and c["estado"] != OK:
            print(f"    {' ' * ancho}  → {c['arreglo']}")
    print()
    print({OK: "Todo en orden.",
           AVISO: "Funciona, pero hay algo que atender.",
           MAL: "Hay algo roto. Mira las flechas de arriba, o corre: python doctor.py fix",
           }[v])
    return 0 if v == OK else (1 if v == AVISO else 2)


def fix(quiet: bool = False) -> int:
    """Repara lo que se pueda sin intervención humana. Lo demás lo dice claro."""
    hechos, pendientes = [], []

    # Lock rancio: se puede quitar solo.
    if R.LOCK.exists():
        edad = time.time() - R.LOCK.stat().st_mtime
        if edad > R.LOCK_RANCIO:
            try:
                R.LOCK.unlink()
                R.registrar("FIX", accion="lock_rancio_eliminado", edad_s=int(edad))
                hechos.append(f"Quité un lock rancio de {int(edad/3600)}h")
            except OSError as e:
                pendientes.append(f"No pude quitar el lock: {e}")
        else:
            pendientes.append(f"Hay una publicación en curso ({int(edad)}s). Espera.")

    # Permisos del directorio: se pueden corregir solos.
    try:
        R._asegurar_home()
        if os.name != "nt":
            modo = R.HOME.stat().st_mode & 0o777
            if modo != 0o700:
                os.chmod(R.HOME, 0o700)
                hechos.append(f"Corregí permisos de {R.HOME} ({oct(modo)} → 0o700)")
    except OSError as e:
        pendientes.append(f"No pude ajustar permisos: {e}")

    # Lo que NO se puede arreglar solo: necesita un humano.
    for c in correr_chequeos():
        if c["estado"] == MAL and c["arreglo"]:
            pendientes.append(f"{c['nombre']}: {c['arreglo']}")

    if quiet:
        print(f"{'reparado' if hechos else 'sin cambios'}"
              + (f" | pendiente: {len(pendientes)}" if pendientes else ""))
    else:
        for h in hechos:
            print(f"  ✓ {h}")
        if not hechos:
            print("  (no había nada que reparar automáticamente)")
        if pendientes:
            print("\n  Esto necesita que lo hagas tú:")
            for p in pendientes:
                print(f"  → {p}")
    return 2 if pendientes else 0


if __name__ == "__main__":
    args = sys.argv[1:]
    quiet = "--quiet" in args or "-q" in args
    libres = [a for a in args if not a.startswith("-")]
    cmd = libres[0] if libres else "doctor"
    if cmd == "version" or "--version" in args:
        print(version())
        sys.exit(0)
    if cmd not in ("doctor", "fix"):
        print(f"Comando desconocido: {cmd}\n"
              "Usa: doctor [--quiet] | fix [--quiet] | version", file=sys.stderr)
        sys.exit(64)   # EX_USAGE
    sys.exit(fix(quiet) if cmd == "fix" else doctor(quiet))
