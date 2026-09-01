"""
Pruebas. Corren SIEMPRE bajo simulacro: nunca tocan LinkedIn.

    python prueba.py

El simulacro se activa aquí arriba, antes de importar nada. No es opcional:
el 31-ago-2026 dos pruebas publicaron de verdad en un perfil real porque el
token del Keychain sigue siendo válido aunque redirijas el directorio de datos.
"""
import os
import sys
import tempfile
import time

os.environ["PUBLISH_LINKEDIN_SIMULACRO"] = "1"           # ← antes de importar
os.environ["PUBLISH_LINKEDIN_HOME"] = tempfile.mkdtemp()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import registro as R          # noqa: E402
from linkedin import LinkedIn, ErrorLinkedIn, escapar  # noqa: E402

fallos = []


def prueba(nombre):
    def deco(fn):
        try:
            fn()
            print(f"  ✓ {nombre}")
        except AssertionError as e:
            fallos.append(nombre)
            print(f"  ✗ {nombre} — {e}")
        except Exception as e:
            fallos.append(nombre)
            print(f"  ✗ {nombre} — {type(e).__name__}: {e}")
        return fn
    return deco


print("\nSEGURIDAD")

@prueba("el simulacro está activo (nada toca la red)")
def _():
    from linkedin import SIMULACRO
    assert SIMULACRO, "SIMULACRO debe estar activo en las pruebas"

@prueba("publicar bajo simulacro no llama a LinkedIn")
def _():
    r = LinkedIn({"access_token": "falso", "expires_at": time.time() + 999}).publicar("hola")
    assert r.get("simulacro") is True, r
    assert r["urn"].startswith("urn:li:share:SIMULACRO"), r


print("\nESCAPADO (formato little text)")

@prueba("escapa los reservados")
def _():
    assert escapar("*a* _b_ [c]") == "\\*a\\* \\_b\\_ \\[c\\]"

@prueba("deja pasar los hashtags")
def _():
    assert escapar("#TribuIA") == "#TribuIA"

@prueba("escapa la almohadilla suelta")
def _():
    assert "\\#" in escapar("cuesta # pesos")


print("\nURN")

@prueba("acepta el URN pelado")
def _():
    assert LinkedIn.limpiar_urn("urn:li:share:123") == "urn:li:share:123"

@prueba("acepta la URL completa del post")
def _():
    u = "https://www.linkedin.com/feed/update/urn:li:share:123/"
    assert LinkedIn.limpiar_urn(u) == "urn:li:share:123"

@prueba("aguanta barra y salto de línea pegados")
def _():
    assert LinkedIn.limpiar_urn("urn:li:share:123/\n") == "urn:li:share:123"

@prueba("rechaza basura")
def _():
    try:
        LinkedIn.limpiar_urn("no soy un urn")
        assert False, "debió reventar"
    except ErrorLinkedIn:
        pass


print("\nIDEMPOTENCIA")

@prueba("la huella ignora espacios y mayúsculas")
def _():
    assert R.huella("Hola  mundo") == R.huella("hola\nMUNDO")
    assert R.huella("a") != R.huella("b")

@prueba("detecta un texto ya publicado")
def _():
    R.registrar("PUBLICADO", huella=R.huella("dup"), urn="urn:li:share:5")
    assert R.ya_publicado("dup")["urn"] == "urn:li:share:5"

@prueba("borrar libera la republicación")
def _():
    R.olvidar("urn:li:share:5")
    assert R.ya_publicado("dup") is None

@prueba("un texto nuevo no queda bloqueado")
def _():
    assert R.ya_publicado("jamás publicado") is None

@prueba("fuera de la ventana ya no bloquea")
def _():
    viejo = int(time.time()) - R.VENTANA_IDEMPOTENCIA - 10
    with R.EVENTOS.open("a") as f:
        import json
        f.write(json.dumps({"ts": "viejo", "epoch": viejo, "evento": "PUBLICADO",
                            "huella": R.huella("antiguo"), "urn": "x"}) + "\n")
    assert R.ya_publicado("antiguo") is None


print("\nLOCK")

@prueba("dos locks simultáneos no conviven")
def _():
    with R.Lock("a"):
        try:
            with R.Lock("b"):
                assert False, "permitió dos locks"
        except R.BloqueadoError:
            pass

@prueba("el lock se suelta al salir")
def _():
    with R.Lock("c"):
        pass
    assert not R.LOCK.exists()

@prueba("roba un lock rancio de más de 2h")
def _():
    R.LOCK.write_text("pid=99999 zombi")
    viejo = time.time() - R.LOCK_RANCIO - 60
    os.utime(R.LOCK, (viejo, viejo))
    with R.Lock("d"):
        pass

@prueba("un diario con una línea corrupta no invalida el resto")
def _():
    with R.EVENTOS.open("a") as f:
        f.write("{ esto no es json\n")
    assert isinstance(R.leer_eventos(), list)


print("\nDOCTOR")

@prueba("corre los chequeos sin reventar")
def _():
    import doctor as D
    cs = D.correr_chequeos()
    assert len(cs) >= 5, f"esperaba varios chequeos, hubo {len(cs)}"
    assert D.veredicto(cs) in (D.OK, D.AVISO, D.MAL)


print()
if fallos:
    print(f"✗ {len(fallos)} prueba(s) fallaron: {', '.join(fallos)}")
    sys.exit(1)
print("✓ Todas las pruebas pasan. LinkedIn nunca fue contactado.")
