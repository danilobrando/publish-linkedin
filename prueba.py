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


print("\nCATÁLOGO DE ERRORES")

@prueba("traduce un token revocado")
def _():
    from linkedin import traducir_error
    m = traducir_error(401, '{"code":"REVOKED_ACCESS_TOKEN"}')
    assert "auth.py login" in m, m

@prueba("traduce una versión de API caducada")
def _():
    from linkedin import traducir_error
    assert "versión" in traducir_error(426, '{"code":"NONEXISTENT_VERSION"}')

@prueba("un 429 sin código conocido dice qué hacer")
def _():
    from linkedin import traducir_error
    assert "Espera" in traducir_error(429, "{}")

@prueba("un 5xx se atribuye a LinkedIn, no al usuario")
def _():
    from linkedin import traducir_error
    assert "su lado" in traducir_error(503, "")

@prueba("un código desconocido no se traga el cuerpo")
def _():
    from linkedin import traducir_error
    assert "418" in traducir_error(418, "raro")


print("\nREGRESIONES DE LA REVISIÓN DE EXPERTOS")

@prueba("5xx NO se reintenta (reintentar duplicaba el post)")
def _():
    import inspect
    from linkedin import LinkedIn
    src = inspect.getsource(LinkedIn._post_con_reintento)
    assert "!= 429" in src, "debe reintentar solo ante 429"
    assert "status_code < 500" not in src, "no debe reintentar ante 5xx"

@prueba("el límite de 3000 se mide sobre el texto YA escapado")
def _():
    from linkedin import LinkedIn, ErrorLinkedIn
    import time
    cli = LinkedIn({"access_token": "x", "expires_at": time.time() + 999})
    # 1600 asteriscos -> 3200 al escapar
    try:
        cli.publicar("*" * 1600)
        assert False, "debió rechazarlo por longitud"
    except ErrorLinkedIn as e:
        assert "3000" in str(e), e

@prueba("los reservados incluyen paréntesis y arroba")
def _():
    from linkedin import escapar
    assert escapar("(hola)") == "\\(hola\\)"
    assert escapar("a@b") == "a\\@b"

@prueba("un evento de simulacro no bloquea la publicación real")
def _():
    R.registrar("PUBLICADO", huella=R.huella("sim"), urn="urn:li:share:SIMULACRO1",
                simulacro=True)
    assert R.ya_publicado("sim") is None, "un simulacro no debe bloquear"

@prueba("el diario roto se detecta y se recuerda")
def _():
    import os
    R.registrar("previo", x=1)
    modo = R.EVENTOS.stat().st_mode
    os.chmod(R.EVENTOS, 0o400)
    try:
        R.DIARIO_ROTO = None
        assert R.diario_sano() is False, "debe detectar que no puede escribir"
        assert R.DIARIO_ROTO, "debe recordar el motivo"
    finally:
        os.chmod(R.EVENTOS, modo)
        R.DIARIO_ROTO = None

@prueba("leer_eventos aguanta json válido pero no-objeto")
def _():
    with R.EVENTOS.open("a") as f:
        f.write("null\n42\n[1,2]\n")
    assert isinstance(R.leer_eventos(), list)

@prueba("el diario humano no se parte con errores multilínea")
def _():
    R.registrar("FALLO", error="linea1\nlinea2\nlinea3")
    ultima = R.DIARIO.read_text(encoding="utf-8").strip().splitlines()[-1]
    assert "linea1 linea2 linea3" in ultima, ultima

@prueba("el chequeo de diarios SÍ puede fallar")
def _():
    import os, doctor as D
    modo = R.EVENTOS.stat().st_mode
    os.chmod(R.EVENTOS, 0o400)
    try:
        R.DIARIO_ROTO = None
        c = [x for x in D.correr_chequeos() if x["nombre"] == "Diarios"][0]
        assert c["estado"] == D.MAL, "el chequeo era incapaz de fallar"
    finally:
        os.chmod(R.EVENTOS, modo)
        R.DIARIO_ROTO = None

@prueba("el doctor avisa cuando el simulacro está activo")
def _():
    import doctor as D
    nombres = [c["nombre"] for c in D.correr_chequeos()]
    assert "Modo" in nombres, "debe avisar que no tocó LinkedIn"

@prueba("borrar tiene freno de mano")
def _():
    import inspect, server
    assert "confirmar" in inspect.signature(server.linkedin_borrar.fn
                                            if hasattr(server.linkedin_borrar, "fn")
                                            else server.linkedin_borrar).parameters


@prueba("el techo diario cuenta solo publicaciones reales")
def _():
    antes = R.publicados_hoy()
    R.registrar("PUBLICADO", huella=R.huella("t1"), urn="u1")
    R.registrar("PUBLICADO", huella=R.huella("t2"), urn="u2", simulacro=True)
    assert R.publicados_hoy() == antes + 1, "el simulacro no debe contar"


print("\nADJUNTOS (imagen y PDF)")

def _archivos_prueba():
    import struct, zlib, pathlib
    d = pathlib.Path(os.environ["PUBLISH_LINKEDIN_HOME"])
    png = d / "p.png"
    if not png.exists():
        def ch(t, x):
            c = t + x
            return struct.pack(">I", len(x)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)
        filas = b"".join(b"\x00" + b"\xff\x00\x00" * 4 for _ in range(4))
        png.write_bytes(b"\x89PNG\r\n\x1a\n"
                        + ch(b"IHDR", struct.pack(">IIBBBBB", 4, 4, 8, 2, 0, 0, 0))
                        + ch(b"IDAT", zlib.compress(filas)) + ch(b"IEND", b""))
    pdf = d / "p.pdf"
    if not pdf.exists():
        pdf.write_bytes(b"%PDF-1.4\n1 0 obj\n<< >>\nendobj\ntrailer\n<< >>\n%%EOF\n")
    return png, pdf

@prueba("clasifica una imagen y un PDF")
def _():
    from medios import clasificar
    png, pdf = _archivos_prueba()
    assert clasificar(png)[1] == "imagen"
    assert clasificar(pdf)[1] == "documento"

@prueba("rechaza una extensión que LinkedIn no acepta")
def _():
    from medios import clasificar, ErrorMedio
    z = os.path.join(os.environ["PUBLISH_LINKEDIN_HOME"], "x.zip")
    open(z, "w").write("x")
    try:
        clasificar(z); assert False, "debió rechazarlo"
    except ErrorMedio as e:
        assert ".zip" in str(e)

@prueba("rechaza un archivo que no existe")
def _():
    from medios import clasificar, ErrorMedio
    try:
        clasificar("/no/existe.png"); assert False, "debió rechazarlo"
    except ErrorMedio as e:
        assert "No existe" in str(e)

@prueba("rechaza un archivo vacío")
def _():
    from medios import clasificar, ErrorMedio
    v = os.path.join(os.environ["PUBLISH_LINKEDIN_HOME"], "vacio.png")
    open(v, "wb").close()
    try:
        clasificar(v); assert False, "debió rechazarlo"
    except ErrorMedio as e:
        assert "vacío" in str(e)

@prueba("rechaza un archivo que pasa del límite")
def _():
    from medios import clasificar, ErrorMedio, LIMITES
    g = os.path.join(os.environ["PUBLISH_LINKEDIN_HOME"], "grande.png")
    with open(g, "wb") as f:
        f.write(b"\0" * (LIMITES["imagen"] + 1))
    try:
        clasificar(g); assert False, "debió rechazarlo"
    except ErrorMedio as e:
        assert "MB" in str(e)

@prueba("el adjunto entra en la huella (mismo texto + otra imagen = otro post)")
def _():
    png, pdf = _archivos_prueba()
    a = R.huella("igual" + "\n@@" + str(png))
    b = R.huella("igual" + "\n@@" + str(pdf))
    assert a != b, "dos adjuntos distintos deben dar huellas distintas"

@prueba("el adjunto se valida incluso en simulacro")
def _():
    from linkedin import LinkedIn, ErrorLinkedIn
    import time as _t
    cli = LinkedIn({"access_token": "x", "expires_at": _t.time() + 999})
    try:
        cli.publicar("hola", adjunto="/no/existe.png")
        assert False, "debió rechazar la ruta mala aun en simulacro"
    except ErrorLinkedIn:
        pass

@prueba("un post con adjunto en simulacro no toca la red")
def _():
    from linkedin import LinkedIn
    import time as _t
    png, _pdf = _archivos_prueba()
    r = LinkedIn({"access_token": "x", "expires_at": _t.time() + 999}).publicar(
        "hola", adjunto=str(png))
    assert r["simulacro"] and r["adjunto"] == "imagen", r

@prueba("limpiar_urn acepta el ugcPost que devuelven los PDF")
def _():
    from linkedin import LinkedIn
    assert LinkedIn.limpiar_urn("urn:li:ugcPost:123") == "urn:li:ugcPost:123"


print("\nDOCTOR")

@prueba("corre los chequeos sin reventar, con o sin credenciales")
def _():
    import doctor as D
    cs = D.correr_chequeos()
    # En un clon fresco no hay credenciales y los chequeos paran temprano: eso
    # es correcto, no un fallo. Lo que se prueba es que NUNCA revienta y que
    # siempre emite un veredicto.
    assert len(cs) >= 2, f"esperaba al menos dependencias y almacén, hubo {len(cs)}"
    assert D.veredicto(cs) in (D.OK, D.AVISO, D.MAL)
    assert all({"nombre", "estado", "detalle"} <= set(c) for c in cs)

@prueba("cada chequeo en MAL dice qué hacer")
def _():
    import doctor as D
    for c in D.correr_chequeos():
        if c["estado"] == D.MAL:
            assert c["arreglo"], f"'{c['nombre']}' falla sin decir cómo arreglarlo"

@prueba("version() responde algo")
def _():
    import doctor as D
    assert D.version() and D.version() != ""


print()
if fallos:
    print(f"✗ {len(fallos)} prueba(s) fallaron: {', '.join(fallos)}")
    sys.exit(1)
print("✓ Todas las pruebas pasan. LinkedIn nunca fue contactado.")
