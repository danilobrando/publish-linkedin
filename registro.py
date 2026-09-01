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


def registrar(evento: str, **campos) -> None:
    """Escribe en los dos diarios. Nunca revienta al llamador."""
    _asegurar_home()
    ahora = time.time()
    marca = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ahora))
    try:
        fila = {"ts": marca, "epoch": int(ahora), "evento": evento, **campos}
        with EVENTOS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")
    except OSError:
        pass
    try:
        extra = "\t".join(f"{k}={v}" for k, v in campos.items() if k != "texto")
        with DIARIO.open("a", encoding="utf-8") as f:
            f.write(f"{marca}\t{evento}\t{extra}\n")
    except OSError:
        pass


def leer_eventos(desde_epoch: int = 0) -> list[dict]:
    if not EVENTOS.exists():
        return []
    out = []
    try:
        for linea in EVENTOS.read_text(encoding="utf-8").splitlines():
            if not linea.strip():
                continue
            try:
                d = json.loads(linea)
            except json.JSONDecodeError:
                continue  # una línea corrupta no invalida el diario
            if d.get("epoch", 0) >= desde_epoch:
                out.append(d)
    except OSError:
        return []
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

    def __enter__(self) -> "Lock":
        _asegurar_home()
        if LOCK.exists():
            try:
                edad = time.time() - LOCK.stat().st_mtime
            except OSError:
                edad = LOCK_RANCIO + 1
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
            registrar("LOCK_RANCIO_ROBADO", edad_s=int(edad))
        LOCK.write_text(f"pid={os.getpid()} {self.motivo} {time.strftime('%H:%M:%S')}",
                        encoding="utf-8")
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
