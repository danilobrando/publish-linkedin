"""
Mencionar (taguear) a alguien en un post.

LinkedIn no tiene un campo de menciones: van **dentro del texto**, con esta
anotación del formato "little text":

    Gracias a @[Andrés Caicedo](urn:li:person:ABC123) por la idea.

Verificado contra la API: `POST /rest/posts` devuelve 201 con esa anotación.

## El problema real no es el formato, es la URN

Con los productos que tiene esta app —Share on LinkedIn y Sign In con OpenID—
**no hay forma programática de averiguar la URN de otra persona.** Probado:

    /v2/people?q=search        → 404  no existe para esta app
    /v2/people/(vanityName:…)  → 403  ACCESS_DENIED, partner API
    /v2/connections            → 403
    /rest/organizations        → 403
    /v2/userinfo (yo mismo)    → 200  ✓ lo único accesible

Resolver URNs ajenas exige el Marketing Developer Platform de LinkedIn, que es
una solicitud de negocio con revisión humana, no un permiso que se activa.

Por eso las URNs se guardan **a mano, una vez por persona**, en un directorio
local. Es tedioso la primera vez y gratis todas las siguientes: se mencionan
siempre a las mismas veinte personas.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

DIRECTORIO = Path(os.environ.get(
    "PUBLISH_LINKEDIN_HOME", Path.home() / ".config" / "publish-linkedin")
) / "menciones.json"

# @[Texto visible](urn:li:person:XXX)  ·  también organization
ANOTACION = re.compile(r"@\[([^\]\n]{1,100})\]\((urn:li:(?:person|organization):[A-Za-z0-9_-]+)\)")
# @Nombre Apellido  — la forma corta que se expande desde el directorio
CORTA = re.compile(r"@([A-Za-zÁÉÍÓÚÜÑáéíóúüñ][\wÁÉÍÓÚÜÑáéíóúüñ.'-]*(?:\s+[A-ZÁÉÍÓÚÜÑ][\wÁÉÍÓÚÜÑáéíóúüñ.'-]*){0,3})")


class ErrorMencion(Exception):
    """El directorio no se pudo leer, o la URN no tiene forma válida."""


def cargar() -> dict[str, str]:
    """Directorio local: nombre → URN. Vacío si no existe."""
    if not DIRECTORIO.exists():
        return {}
    try:
        d = json.loads(DIRECTORIO.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ErrorMencion(f"No pude leer {DIRECTORIO}: {e}") from e
    return {k: v for k, v in d.items() if isinstance(v, str)}


def guardar(nombre: str, urn: str) -> None:
    """Agrega o actualiza a alguien en el directorio."""
    urn = urn.strip()
    if not re.fullmatch(r"urn:li:(?:person|organization):[A-Za-z0-9_-]+", urn):
        raise ErrorMencion(
            f"'{urn}' no parece una URN. Debe ser urn:li:person:… o "
            "urn:li:organization:…")
    d = cargar()
    d[nombre.strip()] = urn
    DIRECTORIO.parent.mkdir(parents=True, exist_ok=True)
    DIRECTORIO.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(DIRECTORIO, 0o600)
    except OSError:
        pass


def verificar(urn: str) -> tuple[bool, str]:
    """¿Existe de verdad esa persona u organización? Sin publicar nada.

    Truco: LinkedIn valida las menciones del lado del servidor al crear el post,
    y **también lo hace con `lifecycleState: DRAFT`**. Un borrador no sale al
    feed, así que se crea uno con la mención, se lee la respuesta y se borra.

        URN inventada → 400 INVALID_MENTION_PERSON_URN_ID
        URN real      → 201

    Es la única validación disponible: esta app no puede consultar perfiles
    ajenos (todo lo demás responde 403 partner API).
    """
    from linkedin import API, ErrorLinkedIn, LinkedIn
    import requests

    cli = LinkedIn.desde_keychain()
    yo = cli.quien_soy()
    borrador = None
    try:
        r = requests.post(
            f"{API}/rest/posts", headers=cli._headers(), timeout=30,
            json={"author": yo["urn"],
                  "commentary": f"verificacion @[x]({urn})",
                  "visibility": "CONNECTIONS",
                  "distribution": {"feedDistribution": "MAIN_FEED",
                                   "targetEntities": [],
                                   "thirdPartyDistributionChannels": []},
                  "lifecycleState": "DRAFT",
                  "isReshareDisabledByAuthor": False})
        if r.status_code == 201:
            borrador = r.headers.get("x-restli-id")
            return True, "LinkedIn la reconoce"
        if "INVALID_MENTION" in r.text:
            return False, "LinkedIn dice que esa URN no corresponde a nadie"
        return False, f"LinkedIn respondió {r.status_code}: {r.text[:150]}"
    except Exception as e:
        return False, f"No pude verificarla ({type(e).__name__}): {e}"
    finally:
        if borrador:
            try:
                cli.borrar(borrador)
            except Exception:
                pass   # un borrador huérfano no sale al feed


def expandir(texto: str) -> tuple[str, list[str], list[str]]:
    """Convierte `@Nombre` en la anotación completa usando el directorio.

    Devuelve (texto, mencionados, no_encontrados). Las anotaciones que ya
    vienen completas se respetan tal cual.
    """
    directorio = cargar()
    if not directorio:
        return texto, [], []

    # Se protegen las anotaciones ya completas para no tocarlas dos veces.
    guardadas: list[str] = []
    def _guardar(m):
        guardadas.append(m.group(0))
        return f"\x00{len(guardadas) - 1}\x00"
    texto = ANOTACION.sub(_guardar, texto)

    # El más largo primero: "Andrés Caicedo" antes que "Andrés".
    por_largo = sorted(directorio, key=len, reverse=True)
    mencionados: list[str] = []

    for nombre in por_largo:
        patron = re.compile(r"@" + re.escape(nombre) + r"\b")
        if patron.search(texto):
            texto = patron.sub(f"@[{nombre}]({directorio[nombre]})", texto, count=0)
            mencionados.append(nombre)

    # Lo que quedó con @ y no se pudo resolver: se avisa, no se adivina.
    sin_resolver = [m.group(1) for m in CORTA.finditer(texto)
                    if m.group(1) not in mencionados]

    for i, original in enumerate(guardadas):
        texto = texto.replace(f"\x00{i}\x00", original)
    return texto, mencionados, sorted(set(sin_resolver))


def partir(texto: str) -> list[tuple[bool, str]]:
    """Parte el texto en tramos (es_anotacion, contenido).

    Sirve para escapar el texto normal sin destrozar las anotaciones: los
    caracteres `@ [ ] ( )` son reservados del formato little text, así que
    escaparlos a ciegas convierte una mención en texto literal.
    """
    tramos: list[tuple[bool, str]] = []
    ultimo = 0
    for m in ANOTACION.finditer(texto):
        if m.start() > ultimo:
            tramos.append((False, texto[ultimo:m.start()]))
        tramos.append((True, m.group(0)))
        ultimo = m.end()
    if ultimo < len(texto):
        tramos.append((False, texto[ultimo:]))
    return tramos


def encontradas(texto: str) -> list[tuple[str, str]]:
    """Las menciones ya anotadas en el texto: [(nombre, urn), …]."""
    return [(m.group(1), m.group(2)) for m in ANOTACION.finditer(texto)]
