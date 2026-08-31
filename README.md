# publish-linkedin

Servidor MCP mínimo para publicar en LinkedIn desde tu Second Brain.

Tres herramientas. ~400 líneas legibles. API oficial de LinkedIn (OAuth 2.0,
scope `w_member_social`) — **sin cookies del navegador**, que es la zona gris
de los términos de servicio.

## Por qué existe

Existe `southleft/linkedin-mcp`: 87 herramientas, MIT, buen trabajo. Se
descartó por tres razones concretas:

| | |
|---|---|
| Mantenimiento | Último commit 25-mar-2026 · `Development Status :: 3 - Alpha` |
| Superficie | 87 herramientas para usar 3 |
| Riesgo de ToS | Depende de `linkedin-api` (scraping de cookies) para media API |

La regla es la de siempre: **si necesitas tres herramientas, escribe tres
herramientas.** Un repo que no puedes leer completo es un repo en el que
confías a ciegas.

## Instalación

```bash
uv venv --python 3.12 && uv pip install "mcp[cli]>=1.2" requests
python auth.py importar   # credenciales de la app → Keychain
python auth.py login      # navegador → Allow → token en Keychain
python auth.py estado     # verificar
```

Registro en Claude Code:

```bash
claude mcp add publish-linkedin --scope user \
  -e PYTHONPATH=$PWD -- $PWD/.venv/bin/python $PWD/server.py
```

Requisito en LinkedIn Developer: producto **Share on LinkedIn** activo y
`http://localhost:8765/callback` en las Redirect URLs.

## Herramientas

| Herramienta | Qué hace |
|---|---|
| `linkedin_estado` | ¿Hay token? ¿Hasta cuándo? ¿Qué permisos? |
| `linkedin_quien_soy` | Confirma contra LinkedIn en qué cuenta se publicaría |
| `linkedin_publicar` | Publica — **solo si `confirmar=True`** |

### El freno de mano

`linkedin_publicar` **no publica por defecto**. Sin `confirmar=True` hace un
ensayo y devuelve el texto exacto que saldría, el conteo de caracteres y cómo
queda tras escapar los reservados del formato *little text* de LinkedIn.

Publicar es irreversible y es tu nombre. Un sistema autónomo sin freno no es
autonomía — es un accidente esperando su turno.

## Seguridad

- Secretos y token en el **Keychain de macOS**, nunca en archivos de texto.
- El `state` de OAuth se valida al volver del navegador (anti-CSRF).
- Toda publicación —ensayo, fallo o real— queda en el diario de auditoría:
  `~/.config/publish-linkedin/publicaciones.log` (override: `PUBLISH_LINKEDIN_LOG`).

## Archivos

| Archivo | Qué es |
|---|---|
| `linkedin.py` | Cliente HTTP + Keychain + escapado |
| `auth.py` | Flujo OAuth (`importar` · `login` · `estado`) |
| `server.py` | Servidor MCP con las 3 herramientas |

## Pendiente

Ver `HARDENING.md` — esto es el mínimo que publica, no el estándar de
conector completo.

MIT.
