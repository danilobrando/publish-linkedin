# publish-linkedin

Servidor MCP mínimo para publicar en LinkedIn desde tu Second Brain.

Cuatro herramientas. ~470 líneas que puedes leer completas. API oficial de
LinkedIn (OAuth 2.0, scope `w_member_social`) — **sin cookies del navegador**,
que es la zona gris de los términos de servicio.

```
tú: "publica esto en LinkedIn"
Claude: [ensayo] esto es lo que saldría. ¿Confirmas?
tú: "sí"
Claude: ✓ Publicado. linkedin.com/feed/update/urn:li:share:…
```

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

---

# Instalación, de cero

Son cinco pasos. El primero es el único que puede trabarte.

## 1 · Crear la app en LinkedIn Developer

Ve a **[linkedin.com/developers/apps](https://www.linkedin.com/developers/apps)**
y dale *Create app*.

> ⚠️ **La trampa #1: LinkedIn te va a exigir una Página de Empresa.**
> No se puede crear una app sin asociarle una. Si no tienes una,
> [créala primero](https://www.linkedin.com/company/setup/new/) — puede ser
> mínima, con tu nombre, y sirve. Tienes que ser **administrador** de esa
> página: después de crear la app, LinkedIn te pide *verificarla* con un
> enlace que solo un admin puede aprobar. Sin ese clic, la app no sirve.

Una vez creada:

**Pestaña `Products`** — pide acceso a estos dos. Ambos son **aprobación
instantánea**, no hay que esperar a nadie:

| Producto | Para qué |
|---|---|
| `Share on LinkedIn` | Publicar. Es el que importa. |
| `Sign In with LinkedIn using OpenID Connect` | Saber quién eres al autenticar. |

> No pidas *Community Management API* ni *Ad Library*: esos sí requieren
> revisión humana de LinkedIn y pueden tardar días. **No los necesitas para
> publicar.**

**Pestaña `Auth`**:

1. Copia el **Client ID** y el **Client Secret**.
2. En *OAuth 2.0 settings → Redirect URLs*, agrega exactamente:
   ```
   http://localhost:8765/callback
   ```

> ⚠️ **La trampa #2: esa URL tiene que ser idéntica.** Sin `https`, sin barra
> al final, con ese puerto. Un carácter de más y el login falla con un error
> que no explica nada.

> 🔒 **El Client Secret es una contraseña.** No lo pegues en un chat, no lo
> subas a git, no lo muestres en una pantalla compartida. Si se te escapa,
> vuelve a la pestaña `Auth` y genera uno nuevo.

## 2 · Instalar

Necesitas **Python 3.11+** y [uv](https://github.com/astral-sh/uv).

```bash
git clone https://github.com/danilobrando/publish-linkedin.git
cd publish-linkedin
uv venv --python 3.12
uv pip install -r requirements.txt
```

## 3 · Guardar las credenciales

```bash
.venv/bin/python auth.py credenciales
```

Te pide el Client ID y el Secret por teclado (el secret no se ve mientras
escribes, y así no queda en el historial del shell).

- **macOS** → van al Keychain.
- **Windows y Linux** → a `~/.config/publish-linkedin/`, con permisos 0600.

## 4 · Autenticarte

```bash
.venv/bin/python auth.py login
```

Se abre el navegador. Le das **Allow**. Vuelve solo.

```bash
.venv/bin/python auth.py estado
```

Debe decir el nombre de tu cuenta y hasta cuándo dura el token (~60 días).

> ⚠️ **La trampa #3: el token vence y no avisa.** Cuando falle dentro de dos
> meses, el mensaje te va a decir la fecha exacta y qué correr. No es un bug.

## 5 · Conectarlo a Claude Code

```bash
claude mcp add publish-linkedin --scope user \
  -e PYTHONPATH=$PWD -- $PWD/.venv/bin/python $PWD/server.py
```

**Cierra y vuelve a abrir Claude Code.** Los servidores MCP se cargan al
arrancar; si no reinicias, no aparecen.

Verifica pidiéndole a Claude: *"¿cuál es mi estado de LinkedIn?"*

---

## Las cuatro herramientas

| Herramienta | Qué hace |
|---|---|
| `linkedin_estado` | ¿Hay token? ¿Hasta cuándo? ¿Qué permisos? |
| `linkedin_quien_soy` | Confirma contra LinkedIn en qué cuenta se publicaría |
| `linkedin_publicar` | Publica — **solo si `confirmar=True`** |
| `linkedin_borrar` | Borra un post publicado. El botón de deshacer. |

### El freno de mano

`linkedin_publicar` **no publica por defecto**. Sin `confirmar=True` hace un
ensayo y devuelve el texto exacto que saldría, el conteo de caracteres y cómo
queda tras escapar los reservados del formato *little text* de LinkedIn.

Publicar es irreversible y es tu nombre. Un sistema autónomo sin freno no es
autonomía — es un accidente esperando su turno.

## Seguridad

- Secretos y token en el Keychain (macOS) o en archivos 0600 (Windows/Linux).
  **Nunca en un archivo de configuración legible.**
- El `state` de OAuth se valida al volver del navegador (anti-CSRF).
- Toda publicación —ensayo, fallo o real— queda en el diario de auditoría:
  `~/.config/publish-linkedin/publicaciones.log` (override: `PUBLISH_LINKEDIN_LOG`).

## Cuando algo falle

| Síntoma | Qué pasó |
|---|---|
| `Faltan credenciales de la app` | No corriste el paso 3 |
| `No hay token` / `El token venció` | Corre `auth.py login` otra vez |
| El navegador dice `redirect_uri` inválido | Trampa #2: la URL no coincide con la de la pestaña `Auth` |
| `403` al publicar | Falta el producto `Share on LinkedIn` en la pestaña `Products` |
| `426 NONEXISTENT_VERSION` | LinkedIn retiró la versión de API. El código la renegocia solo y reintenta una vez |
| Claude no ve las herramientas | No reiniciaste Claude Code después del paso 5 |

## Archivos

| Archivo | Qué es |
|---|---|
| `linkedin.py` | Cliente HTTP + almacén de secretos + escapado |
| `auth.py` | Flujo OAuth (`credenciales` · `login` · `estado`) |
| `server.py` | Servidor MCP con las cuatro herramientas |

## Pendiente

Ver `HARDENING.md` — esto es el mínimo que publica, no el estándar de
conector completo. Lo más importante que falta: idempotencia (evitar publicar
dos veces el mismo texto) y aviso antes de que venza el token.

MIT.
