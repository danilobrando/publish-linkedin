"""
Adjuntar una imagen o un PDF a un post.

LinkedIn no acepta el archivo dentro del post: hay que subirlo antes, en tres
pasos, y recién entonces referenciar el URN que devuelve.

    1. POST /rest/{images|documents}?action=initializeUpload  → uploadUrl + urn
    2. PUT  uploadUrl  con el binario                          → sube el archivo
    3. POST /rest/posts  con content.media.id = ese urn        → crea el post

Un solo adjunto por post. Varias imágenes usan otra forma (`content.multiImage`)
que no está aquí porque no se ha necesitado — si la necesitas, escríbela.
"""
from __future__ import annotations

import mimetypes
import os
from pathlib import Path

import requests

# LinkedIn documenta límites distintos por tipo. Se validan aquí para fallar
# con un mensaje claro en vez de con un 400 críptico después de subir 40 MB.
LIMITES = {
    "imagen": 10 * 1024 * 1024,        # 10 MB
    "documento": 100 * 1024 * 1024,    # 100 MB
}

TIPOS_IMAGEN = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png", ".gif": "image/gif",
}
TIPOS_DOCUMENTO = {
    ".pdf": "application/pdf",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class ErrorMedio(Exception):
    """El archivo no sirve, o LinkedIn rechazó la subida."""


def clasificar(ruta: str | Path) -> tuple[Path, str, str]:
    """Valida el archivo y devuelve (ruta, clase, content-type).

    `clase` es "imagen" o "documento": determina el endpoint y el campo que
    LinkedIn espera en el post (altText para imágenes, title para documentos).
    """
    p = Path(os.path.expanduser(str(ruta))).resolve()
    if not p.exists():
        raise ErrorMedio(f"No existe el archivo: {p}")
    if not p.is_file():
        raise ErrorMedio(f"No es un archivo: {p}")

    ext = p.suffix.lower()
    if ext in TIPOS_IMAGEN:
        clase, ctype = "imagen", TIPOS_IMAGEN[ext]
    elif ext in TIPOS_DOCUMENTO:
        clase, ctype = "documento", TIPOS_DOCUMENTO[ext]
    else:
        aceptados = ", ".join(sorted(TIPOS_IMAGEN) + sorted(TIPOS_DOCUMENTO))
        raise ErrorMedio(
            f"LinkedIn no acepta '{ext}' por esta vía. Sirven: {aceptados}")

    tam = p.stat().st_size
    if tam == 0:
        raise ErrorMedio(f"El archivo está vacío: {p.name}")
    if tam > LIMITES[clase]:
        raise ErrorMedio(
            f"{p.name} pesa {tam / 1048576:.1f} MB y el máximo para una "
            f"{clase} es {LIMITES[clase] // 1048576} MB.")

    # El contenido real manda sobre la extensión: un .png que en realidad es un
    # PDF hace que LinkedIn acepte la subida y después muestre un post roto.
    real = mimetypes.guess_type(p.name)[0]
    if real and real != ctype:
        raise ErrorMedio(f"La extensión dice {ctype} pero el archivo parece {real}.")

    return p, clase, ctype


def descripcion(ruta: str | Path) -> str:
    """Una línea legible del adjunto, para mostrar en el ensayo."""
    p, clase, ctype = clasificar(ruta)
    return f"{clase}: {p.name} ({p.stat().st_size / 1024:.0f} KB, {ctype})"


def subir(sesion_headers: dict, api: str, propietario_urn: str,
          ruta: str | Path, token: str) -> tuple[str, str]:
    """Sube el archivo y devuelve (urn, clase). Dos llamadas a LinkedIn.

    `sesion_headers` son los headers versionados del cliente; el PUT del binario
    va SIN ellos (LinkedIn rechaza el header de versión en esa URL firmada).
    """
    p, clase, ctype = clasificar(ruta)
    recurso = "images" if clase == "imagen" else "documents"

    r = requests.post(
        f"{api}/rest/{recurso}?action=initializeUpload",
        headers=sesion_headers, timeout=30,
        json={"initializeUploadRequest": {"owner": propietario_urn}},
    )
    if r.status_code not in (200, 201):
        raise ErrorMedio(
            f"LinkedIn no dejó iniciar la subida de la {clase} "
            f"({r.status_code}): {r.text[:250]}")

    valor = (r.json() or {}).get("value", {})
    url = valor.get("uploadUrl")
    urn = valor.get(recurso[:-1])          # "image" o "document"
    if not url or not urn:
        raise ErrorMedio(f"LinkedIn respondió sin uploadUrl o sin urn: {str(valor)[:200]}")

    with p.open("rb") as f:
        # Timeout generoso: un PDF de 100 MB por una conexión lenta tarda.
        r2 = requests.put(url, data=f, timeout=300,
                          headers={"Authorization": f"Bearer {token}",
                                   "Content-Type": ctype})
    if r2.status_code not in (200, 201):
        raise ErrorMedio(
            f"Falló la subida del binario ({r2.status_code}): {r2.text[:250]}")

    return urn, clase
