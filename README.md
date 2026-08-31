# publish-linkedin

Servidor MCP mínimo para publicar en LinkedIn desde tu Second Brain.

Cuatro herramientas. ~490 líneas que puedes leer completas. API oficial de
LinkedIn (OAuth 2.0, scope `w_member_social`) — **sin cookies del navegador**,
que es la zona gris de los términos de servicio.

```
tú: "publica esto en LinkedIn"
Claude: [ensayo] esto es lo que saldría. ¿Confirmas?
tú: "sí"
Claude: ✓ Publicado. linkedin.com/feed/update/urn:li:share:…
```

**El post sale en tu perfil personal**, con tu nombre y tu foto.

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

# Instalación

Cuatro pasos. Solo necesitas **Python 3.11 o más nuevo**.

## 1 · Clonar e instalar

```bash
git clone https://github.com/danilobrando/publish-linkedin.git
cd publish-linkedin
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

En **Windows**, las dos últimas líneas son:

```
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

> Si ya tienes [uv](https://github.com/astral-sh/uv), sirve igual y es más rápido:
> `uv venv --python 3.12 && uv pip install -r requirements.txt`.
> **No hace falta instalarlo solo para esto** — probado con `venv` y `pip` normales.

## 2 · Guardar las credenciales de la app

```bash
.venv/bin/python auth.py credenciales
```

*(en Windows: `.venv\Scripts\python auth.py credenciales` — y así en todos los que siguen)*

Te pide un **Client ID** y un **Client Secret**, que identifican a la
aplicación que pide permiso — no a ti.

> 🎓 **Si estás en un curso:** pide esas dos credenciales a quien lo dicta.
> Una misma aplicación puede servir a todo el salón: cada persona autoriza
> por su lado y publica en su propio perfil. **No van en este repo.**
>
> **Si vas por tu cuenta:** necesitas crear tu propia app.
> Ver [Crear tu propia app](#crear-tu-propia-app) abajo.

Se piden por teclado a propósito: pasarlas como argumento las dejaría en el
historial del shell.

- **macOS** → van al Keychain.
- **Windows y Linux** → a `~/.config/publish-linkedin/`, con permisos 0600.

## 3 · Autenticarte

```bash
.venv/bin/python auth.py login
```

Se abre el navegador **con tu sesión de LinkedIn**. Le das **Allow**. Eso
crea un token que es tuyo y solo publica en tu perfil.

```bash
.venv/bin/python auth.py estado
```

Debe decir tu nombre y hasta cuándo dura el token (~60 días).

> ⚠️ **El token vence y no avisa.** Cuando falle dentro de dos meses, el
> mensaje te va a decir la fecha exacta y qué correr. No es un bug.

## 4 · Conectarlo a Claude Code

```bash
claude mcp add publish-linkedin --scope user \
  -e PYTHONPATH=$PWD -- $PWD/.venv/bin/python $PWD/server.py
```

> ⚠️ **Cierra y vuelve a abrir Claude Code.** Los servidores MCP se cargan al
> arrancar; si no reinicias, no aparecen y vas a creer que te equivocaste.

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

### Si compartes una app con varias personas

Es válido y es como funciona OAuth: la app pide permiso, cada persona lo
concede por separado, y cada token solo sirve para quien lo autorizó. **Nadie
puede publicar en el perfil de otro.** Dicho eso, dos cosas que conviene saber:

- El Client Secret **es una contraseña de la app**. Quien lo administra debe
  poder rotarlo (pestaña `Auth` del portal, un clic) y hacerlo cuando el grupo
  deje de necesitarlo.
- LinkedIn limita por app además de por persona. Si mucha gente publica en el
  mismo minuto, van a ver un `429`. El mensaje lo explica y dice cuánto esperar.

## Cuando algo falle

| Síntoma | Qué pasó |
|---|---|
| `Todavía no hay credenciales` | Falta el paso 2 |
| `No hay token` / `El token venció` | Corre `auth.py login` otra vez |
| El navegador dice `redirect_uri` inválido | La app no tiene registrada `http://localhost:8765/callback` |
| `429` | Límite de LinkedIn. Espera lo que diga el mensaje |
| `401` / `403` al publicar | Token vencido, o falta el producto `Share on LinkedIn` en la app |
| `426 NONEXISTENT_VERSION` | LinkedIn retiró la versión de API. El código la renegocia solo y reintenta una vez |
| Claude no ve las herramientas | No reiniciaste Claude Code después del paso 4 |

---

## Crear tu propia app

Solo si quieres tu propia aplicación en vez de usar una compartida.

Ve a **[linkedin.com/developers/apps](https://www.linkedin.com/developers/apps)**
→ *Create app*.

> ⚠️ **LinkedIn te va a exigir una Página de LinkedIn.** No se puede crear una
> app sin asociarle una, y un *super admin* de esa página tiene que aprobar la
> verificación con un enlace. Si administras alguna, úsala. Si no, este es el
> punto donde conviene pedir prestadas las credenciales de una app existente
> en vez de crear una página solo para esto.
>
> **La Página no es donde sale el post.** El post sale en tu perfil personal.
> La página solo figura como "editor" de la app en el portal. Es papeleo.

**Pestaña `Products`** — pide estos dos. Ambos son **aprobación instantánea**:

| Producto | Para qué |
|---|---|
| `Share on LinkedIn` | Publicar. Es el que importa. |
| `Sign In with LinkedIn using OpenID Connect` | Saber quién eres al autenticar. |

No pidas *Community Management API* ni *Ad Library*: esos sí requieren revisión
humana de LinkedIn y tardan días. **No los necesitas para publicar.**

**Pestaña `Auth`**:

1. Copia el **Client ID** y el **Client Secret**.
2. En *OAuth 2.0 settings → Redirect URLs*, agrega exactamente:
   ```
   http://localhost:8765/callback
   ```
   Sin `https`, sin barra al final, con ese puerto. Un carácter de más y el
   login falla con un error que no explica nada.

## Archivos

| Archivo | Qué es |
|---|---|
| `linkedin.py` | Cliente HTTP + almacén de secretos + escapado |
| `auth.py` | Flujo OAuth (`credenciales` · `login` · `estado`) |
| `server.py` | Servidor MCP con las cuatro herramientas |

## Pendiente

Ver `HARDENING.md`. Lo más importante que falta: idempotencia (evitar publicar
dos veces el mismo texto) y aviso antes de que venza el token.

MIT.
