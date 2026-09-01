"""
Prueba de concurrencia real del lock. Procesos de verdad, no hilos.

    python prueba_concurrencia.py

Vive aparte de `prueba.py` porque necesita `multiprocessing` con `spawn`, y eso
exige un archivo real como punto de entrada — no se puede correr desde stdin.

POR QUÉ EXISTE: el lock original hacía `exists()` y después `write_text()`. Son
dos operaciones con una ventana en medio, y por esa ventana entraban varios
publicadores a la vez. Medido en la revisión: 2 de 8 procesos ganaban el lock
simultáneamente. Con `O_CREAT | O_EXCL` es una sola operación del sistema.

Sin esta prueba, esa regresión vuelve sin que nadie se entere.
"""
import multiprocessing as mp
import os
import sys
import tempfile
import time

# 15 rondas, no 5. La carrera del lock viejo se manifiesta en ~1 de cada 5
# rondas: con 5 rondas el detector se le escapaba un tercio de las veces.
# Con 15 la probabilidad de no detectarla baja a ~4%, y cuesta 3 segundos.
RONDAS = 15
PROCESOS = 8


def intenta(i: int, dir_datos: str, q, barrera) -> None:
    # Cada proceso apunta al MISMO directorio: si no, cada uno tendría su
    # propio archivo de lock y la prueba pasaría siempre sin probar nada.
    os.environ["PUBLISH_LINKEDIN_HOME"] = dir_datos
    os.environ["PUBLISH_LINKEDIN_SIMULACRO"] = "1"
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import registro as R

    if str(R.HOME) != dir_datos:
        q.put(f"ERROR:HOME quedó en {R.HOME}")
        return

    # Todos esperan aquí y atacan en el mismo instante. Sin esta barrera los
    # procesos llegan escalonados, nunca coinciden dentro de la ventana del
    # check-then-act, y la prueba da verde con un lock roto — lo comprobé.
    try:
        barrera.wait(timeout=20)
    except Exception:
        pass

    try:
        with R.Lock(f"p{i}"):
            q.put("GANO")
            time.sleep(0.05)         # sostener el lock mientras los otros chocan
    except R.BloqueadoError:
        q.put("BLOQUEADO")
    except Exception as e:
        q.put(f"ERROR:{type(e).__name__}: {e}")


def main() -> int:
    malas = 0
    for ronda in range(1, RONDAS + 1):
        datos = tempfile.mkdtemp()
        q = mp.Queue()
        barrera = mp.Barrier(PROCESOS)
        ps = [mp.Process(target=intenta, args=(i, datos, q, barrera))
              for i in range(PROCESOS)]
        for p in ps:
            p.start()
        for p in ps:
            p.join(timeout=30)
        res = [q.get() for _ in range(PROCESOS)]

        ganaron = res.count("GANO")
        errores = [r for r in res if r.startswith("ERROR")]
        ok = ganaron == 1 and not errores
        malas += 0 if ok else 1
        if not ok:
            print(f"  ronda {ronda}: {ganaron}/{PROCESOS} ganaron"
                  f"{'  ' + errores[0][:60] if errores else ''}  ✗ CARRERA")
        elif ronda == 1 or ronda == RONDAS:
            print(f"  ronda {ronda}: {ganaron}/{PROCESOS} ganaron, "
                  f"{res.count('BLOQUEADO')} bloqueados  ✓")

    print()
    if malas:
        print(f"✗ {malas}/{RONDAS} rondas con carrera: el lock NO es atómico.")
        return 1
    print(f"✓ Lock atómico: exactamente un ganador en {RONDAS} rondas "
          f"de {PROCESOS} procesos simultáneos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
