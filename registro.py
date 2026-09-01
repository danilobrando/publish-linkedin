"""
Registro, lock e idempotencia.

Tres cosas que separan "funciona en mi máquina" de algo que puede correr solo:

1. **Diario estructurado** (jsonl) — para poder preguntarle cosas, no solo leerlo.
2. **Lock** — dos ejecuciones a la vez no publican el mismo post dos veces.
3. **Idempotencia** — el mismo texto no sale dos veces en 24 horas.

El fallo más caro de un publicador no es que falle: es que publique dos veces.
Falla en público, con tu nombre, y no hay forma de decir "fue el sistema".
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

HOME = Path(os.environ.get(
    "PUBLISH_LINKEDIN_HOME", Path.home() / ".config" / "publish-linkedin"))

# El diario legible por humanos. Se conserva porque es el que se muestra en pantalla.
DIARIO = Path(os.environ.get("PUBLISH_LINKEDIN_LOG", HOME / "publicaciones.log"))
# El diario que se puede consultar. Es la fuente de verdad para idempotencia.
EVENTOS = Path(os.environ.get("PUBLISH_LINKEDIN_JSONL", HOME / "eventos.jsonl"))
LOCK = HOME / "publicando.lock"

VENTANA_IDEMPOTENCIA = int(os.environ.get("PUBLISH_LINKEDIN_VENTANA_H", "24")) * 3600
LOCK_RANCIO = 2 * 3600  # 2h: si un lock lleva más tiempo, el proceso murió


def _asegurar_home() -> None:
    HOME.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(HOME, 0o700)
    except OSError:
        pass  # Windows no siempre deja; el directorio ya es del usuario


def huella(texto: str) -> str:
    """Identidad del contenido, insensible a espacios de más.

    Si alguien reintenta con el mismo texto y un salto de línea distinto,
    sigue siendo el mismo post para efectos de no duplicarlo.
    """
    normal = " ".join((texto or "").split()).lower()
    return hashlib.sha256(normal.encode("utf-8")).hexdigest()[:16]


# Si el diario de eventos deja de escribirse, la idempotencia se queda ciega
# sin avisar: `ya_publicado` consulta ESE archivo. Un `sudo python doctor.py`
# basta para dejarlo root:wheel y romperlo para siempre, en silencio.
# Por eso el fallo se recuerda y se grita una vez.
DIARIO_ROTO: str | None = None


def registrar(evento: str, **campos) -> None:
    """Escribe en los dos diarios.

    No revienta al llamador —perder el log no debe tumbar una publicación—
    pero tampoco se calla: deja `DIARIO_ROTO` puesto para que quien publica
    pueda negarse, y avisa una sola vez por stderr.
    """
    global DIARIO_ROTO
    ahora = time.time()
    marca = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ahora))
    try:
        _asegurar_home()
        fila = {"ts": marca, "epoch": int(ahora), "evento": evento, **campos}
        with EVENTOS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")
        DIARIO_ROTO = None
    except OSError as e:
        if DIARIO_ROTO is None:
            print(f"publish-linkedin: NO puedo escribir {EVENTOS} ({e}). "
                  "Sin ese archivo no hay protección contra duplicados.",
                  file=sys.stderr)
        DIARIO_ROTO = str(e)
    try:
        # Los saltos de línea romperían el formato de una línea por evento.
        extra = "\t".join(f"{k}={str(v).replace(chr(10), ' ')}"
                           for k, v in campos.items() if k != "texto")
        with DIARIO.open("a", encoding="utf-8") as f:
            f.write(f"{marca}\t{evento}\t{extra}\n")
    except OSError:
        pass


def diario_sano() -> bool:
    """¿Se puede confiar en el diario para no duplicar? Verifica escribiendo."""
    registrar("CHEQUEO", origen="diario_sano")
    return DIARIO_ROTO is None


def leer_eventos(desde_epoch: int = 0) -> list[dict]:
    if not EVENTOS.exists():
        return []
    out = []
    try:
        crudo = EVENTOS.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    for linea in crudo.splitlines():
        if not linea.strip():
            continue
        try:
            d = json.loads(linea)
        except json.JSONDecodeError:
            continue  # una línea corrupta no invalida el diario
        if not isinstance(d, dict):
            continue  # json válido pero no un evento (p.ej. "null" o un número)
        if d.get("epoch", 0) >= desde_epoch:
            out.append(d)
    return out


def ya_publicado(texto: str) -> dict | None:
    """¿Este mismo texto ya salió dentro de la ventana? Devuelve el evento previo.

    Se recorre hacia atrás y gana el evento MÁS RECIENTE de esa huella: si lo
    último fue un ANULADO (porque el post se borró), no hay duplicado que
    impedir y se puede volver a publicar.
    """
    h = huella(texto)
    corte = int(time.time()) - VENTANA_IDEMPOTENCIA
    for d in reversed(leer_eventos(corte)):
        if d.get("huella") != h:
            continue
        if d.get("simulacro"):
            continue  # un post de simulacro nunca salió: no debe bloquear el real
        if d.get("evento") == "ANULADO":
            return None
        if d.get("evento") == "PUBLICADO":
            return d
    return None


def olvidar(urn: str) -> None:
    """Tras borrar un post, su huella deja de bloquear una republicación.

    Si borraste algo para corregirlo, el sistema no debe impedirte volver a
    publicarlo. Se registra un evento que anula el anterior.
    """
    for d in reversed(leer_eventos()):
        if d.get("evento") == "PUBLICADO" and d.get("urn") == urn:
            registrar("ANULADO", huella=d.get("huella"), urn=urn)
            return


class Lock:
    """Lock de archivo con robo de lock rancio.

    Si un proceso murió a mitad de una publicación, su lock queda ahí para
    siempre y nadie más puede publicar. A las 2 horas se considera muerto y
    se roba — dejando constancia en el diario.
    """

    def __init__(self, motivo: str = ""):
        self.motivo = motivo
        self.tomado = False

    def _crear_exclusivo(self) -> bool:
        """Crea el lock de forma atómica. False si ya existía.

        `O_CREAT | O_EXCL` es una sola operación del sistema: o lo creas tú, o
        alguien más lo tenía. La versión anterior hacía `exists()` y después
        `write_text()` — dos pasos, con una ventana en medio por la que
        entraban varios publicadores a la vez. Medido: 2 de 8 procesos.
        """
        try:
            fd = os.open(str(LOCK), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            return False
        with os.fdopen(fd, "w") as f:
            f.write(f"pid={os.getpid()} {self.motivo} {time.strftime('%H:%M:%S')}")
        return True

    def __enter__(self) -> "Lock":
        _asegurar_home()
        if self._crear_exclusivo():
            self.tomado = True
            return self

        # Ya había uno. ¿Está vivo o quedó de un proceso muerto?
        try:
            edad = time.time() - LOCK.stat().st_mtime
        except OSError:
            # Desapareció entre medio: alguien lo soltó. Un intento más.
            if self._crear_exclusivo():
                self.tomado = True
                return self
            edad = 0
        if edad < LOCK_RANCIO:
            dueno = ""
            try:
                dueno = LOCK.read_text(encoding="utf-8").strip()[:120]
            except OSError:
                pass
            raise BloqueadoError(
                f"Hay otra publicación en curso desde hace {int(edad)}s"
                + (f" ({dueno})" if dueno else "")
                + ". Espera a que termine."
            )

        # Rancio: se roba, pero de forma que solo UNO gane la carrera.
        try:
            os.unlink(str(LOCK))
        except OSError:
            pass
        if not self._crear_exclusivo():
            raise BloqueadoError("Otro proceso se quedó con el lock. Reintenta.")
        registrar("LOCK_RANCIO_ROBADO", edad_s=int(edad))
        self.tomado = True
        return self

    def __exit__(self, *exc) -> None:
        if self.tomado:
            try:
                LOCK.unlink()
            except OSError:
                pass
        return None


class BloqueadoError(Exception):
    """Otra publicación está en curso."""
