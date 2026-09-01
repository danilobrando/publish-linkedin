# publish-linkedin

Servidor MCP mínimo para publicar en LinkedIn desde tu Second Brain.

Cinco herramientas. ~1.100 líneas que puedes leer completas. API oficial de
LinkedIn (OAuth 2.0, scope `w_member_social`) — **sin cookies del navegador**,
que es la zona gris de los términos de servicio.

```
tú: "publica esto en LinkedIn"
Claude: [ensayo] esto es lo que saldría. ¿Confirmas?
tú: "sí"
Claude: ✓ Publicado. linkedin.com/feed/update/urn:li:share:…
```

**El post sale en tu perfil personal**, con tu nombre y tu foto.

## La forma más fácil de instalarlo

Abre Claude Code en una carpeta vacía y pídele esto:

```
Instala https://github.com/danilobrando/publish-linkedin siguiendo su README
y guíame hasta que pueda publicar.
```

Él lee las instrucciones de este archivo, hace lo que le toca a él y te dice
exactamente qué te toca a ti. Si prefieres a mano, están los
[cuatro pasos manuales](#instalación-manual-si-prefieres-no-usar-el-agente) más abajo.

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

# 🤖 Si eres Claude Code (o cualquier agente): lee esto primero

El usuario te pidió instalar este repo. **Guíalo hasta que publique**, no solo hasta que
instale. Sigue estos pasos en orden y no te saltes ninguna verificación.

## Reglas que no puedes romper

| | |
|---|---|
| ❌ **Nunca** corras `auth.py credenciales` | Usa `input()` y `getpass()`. Se te cuelga la terminal. **Lo corre el usuario.** |
| ❌ **Nunca** corras `auth.py login` | Abre el navegador y espera un clic humano. **Lo corre el usuario.** |
| ❌ **Nunca** pidas ni recibas el Client Secret por el chat | Va tecleado directo en la terminal del usuario. Si te lo pega, dile que lo rote. |
| ✅ Sí corres | `git clone`, crear el entorno, instalar dependencias, `claude mcp add`, `auth.py estado` |

**Cuando llegues a un paso del usuario:** dale el comando exacto **con ruta absoluta**,
dile que lo corra **en su propia terminal**, y **espera** a que te diga que terminó. No
sigas de largo.

**Antes de empezar, avísale:** *"te voy a pedir permiso para correr `git` y `pip`; apruébalos
o no puedo instalar nada."* Sin eso, el primer comando se bloquea y el usuario no entiende
por qué.

## Paso 1 — Instalar *(lo haces tú)*

Detecta el sistema operativo y usa la rama correcta.

**macOS / Linux:**
```bash
git clone https://github.com/danilobrando/publish-linkedin.git
cd publish-linkedin
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

**Windows:**
```
git clone https://github.com/danilobrando/publish-linkedin.git
cd publish-linkedin
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

> ⚠️ El entorno **tiene que llamarse `.venv`** y estar dentro del repo. El paso 4 depende
> de esa ruta exacta. No uses `uv`, `conda`, ni un entorno global aunque estén disponibles.

> ⚠️ **Clona dentro de la carpeta donde el usuario te abrió**, no en `/tmp` ni en el home.
> Apenas termines, corre `pwd` dentro del repo y **dile al usuario la ruta absoluta**.
> Desde ahí, **todo comando que le entregues al usuario lleva la ruta absoluta completa**
> — él va a correrlos en otra terminal, parada en otro lado. Un `cd publish-linkedin`
> relativo es la causa #1 de que esto falle.

**Verifica antes de seguir** (macOS/Linux · en Windows `.venv\Scripts\python`):
```bash
.venv/bin/python -c "import mcp, requests; print('OK')"
```
Si no imprime `OK`, arregla eso antes de continuar.

## Paso 2 — Credenciales *(lo hace el usuario)*

**Lo normal y lo recomendado es que el usuario cree su propia app.** Es suya, no depende
de nadie, y no se le vence cuando alguien más rote un secreto. Empieza siempre por ahí.

Dile:

> Vas a crear tu propia aplicación de LinkedIn. Toma unos 10 minutos y te queda tuya para
> siempre. Necesitas administrar una **Página de LinkedIn** — si no tienes una, la creas
> gratis en el momento; sirve una página de tu empresa, de tu marca personal, o una de
> prueba.

Llévalo paso a paso por la sección [Crear tu propia app](#crear-tu-propia-app) de este
mismo archivo. **No la resumas: acompáñalo por cada pestaña** y espera confirmación en cada
una. Los dos errores que más pasan son pedir el producto equivocado y escribir mal la
Redirect URL.

Cuando tenga Client ID y Client Secret, sigue abajo.

### Plan B — credenciales prestadas

**Solo** si el usuario no puede crear la app ahora (no administra ninguna página, LinkedIn
no le deja, o se quedó sin tiempo en una clase en vivo). Dile que le pida al instructor su
Client ID y Client Secret, y explícale por qué no es riesgoso:

> Son las credenciales de una **empresa de prueba**, creada justamente para esto — no de
> una compañía real. La app solo sirve para pedir permiso: **el token que se genera es
> tuyo y solo publica en tu perfil.** Nadie puede publicar por ti, ni tú por nadie.

Adviértele también que **es prestado**: si el instructor rota el secreto, tiene que volver
a hacer el paso 2 con credenciales propias. Por eso el camino bueno es el de arriba.

### 2c · Guardar las credenciales — los DOS caminos pasan por aquí

Cuando el usuario ya tenga Client ID y Client Secret —propias o prestadas—, dile que corra
**en su terminal**, dentro de la carpeta del repo:

```bash
.venv/bin/python auth.py credenciales
```

Le va a pedir **Client ID** (se ve al escribir) y **Client Secret** (no se ve, es normal).

**Espera a que te confirme.** Después verifica tú:
```bash
.venv/bin/python auth.py estado
```

| Lo que imprime | Qué significa |
|---|---|
| `✗ Todavía no hay credenciales` | El paso 2c no se completó. **No sigas.** |
| `✓ Credenciales de la app guardadas` + `✗ Falta autenticarte` | Correcto. Sigue al paso 3. |

El código de salida también sirve: `2` si falta algo, `0` si todo está listo.

## Paso 3 — Autorizar *(lo hace el usuario)*

Dile que corra **en su terminal**:

```bash
.venv/bin/python auth.py login
```

Adviértele **antes** de que lo corra:
- Se le abre el navegador con su sesión de LinkedIn. Tiene que darle **Allow**.
- Tiene 2 minutos. Si se pasa, simplemente lo vuelve a correr.

**Espera.** Después verifica tú:
```bash
.venv/bin/python auth.py estado
```
Tiene que salir **el nombre del usuario** y una fecha de vencimiento (~60 días). Si sale
un error, búscalo en la tabla [Cuando algo falle](#cuando-algo-falle) de este archivo y
resuélvelo antes de seguir.

## Paso 4 — Conectar el servidor *(lo haces tú)*

Desde la carpeta del repo:

```bash
claude mcp add publish-linkedin --scope user \
  -e PYTHONPATH=$PWD -- $PWD/.venv/bin/python $PWD/server.py
```

En **Windows** usa rutas absolutas explícitas en vez de `$PWD` (PowerShell: `$PWD` sirve;
`cmd` no). Verifica con `claude mcp list` que aparezca `publish-linkedin ✔ Connected`.

Después dile al usuario, con estas palabras:

> **Cierra y vuelve a abrir Claude Code.** Los servidores MCP se cargan al arrancar. Si no
> reinicias, las herramientas no aparecen y vas a creer que algo salió mal.

## Paso 5 — Primera publicación *(después del reinicio)*

Ya reiniciado, verifica con la herramienta `linkedin_quien_soy`. Debe devolver el nombre
del usuario.

Después dile:

> Pídeme que publique algo. **La primera vez no voy a publicar**: te muestro un ensayo con
> el texto exacto que saldría. Solo publico cuando tú confirmes.

Cuando te pida publicar:
1. Llama `linkedin_publicar` **sin** `confirmar` (o con `confirmar=False`). Muéstrale el ensayo completo.
2. **Espera su confirmación explícita.** No la asumas, no la interpretes de un «dale» ambiguo.
3. Solo entonces vuelve a llamar con `confirmar=True` y dale la URL.

Si se arrepiente, `linkedin_borrar` con el URN que devolviste.

## Si algo falla en cualquier paso

Busca el síntoma en la tabla [Cuando algo falle](#cuando-algo-falle) de este archivo antes
de improvisar. Si no está ahí, dile al usuario qué falló en una frase, sin jerga, y qué
vas a intentar.

---

# Instalación *(manual, si prefieres no usar el agente)*

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

> 🎓 **Lo recomendado es crear tu propia app** — ver
> [Crear tu propia app](#crear-tu-propia-app). Toma ~10 minutos y queda tuya.
>
> **Si estás en un curso y no alcanzas:** pide esas dos credenciales a quien lo dicta.
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
| `linkedin_borrar` | Borra un post — **solo si `confirmar=True`** |
| `linkedin_doctor` | Diagnostica todo. Pásale `reparar=True` para que arregle lo que pueda |

### El freno de mano

`linkedin_publicar` **no publica por defecto**. Sin `confirmar=True` hace un
ensayo y devuelve el texto exacto que saldría, el conteo de caracteres y cómo
queda tras escapar los reservados del formato *little text* de LinkedIn.

Publicar es irreversible y es tu nombre. Un sistema autónomo sin freno no es
autonomía — es un accidente esperando su turno.

## Cuando algo no funcione: el doctor

```bash
.venv/bin/python doctor.py          # 10 chequeos, cada fallo dice qué hacer
.venv/bin/python doctor.py fix      # repara locks rancios y permisos
.venv/bin/python doctor.py --quiet  # solo el veredicto (para scripts)
```

Códigos de salida: `0` todo bien · `1` hay un aviso · `2` algo roto · `64` mal uso.

También está como herramienta MCP: pídele a Claude *"diagnostica mi LinkedIn"*.

### Que te avise antes de que se venza el token

El token dura ~60 días y **LinkedIn no avisa**. Esta app no recibe
`refresh_token` (solo se los dan a apps aprobadas), así que hay que volver a
autorizar. Para no enterarte el día que necesitas publicar:

```bash
./instalar-vigilante.sh        # corre el doctor a diario a las 9:15 (macOS)
./instalar-vigilante.sh quitar
```

En Linux, la misma idea con cron: `15 9 * * * /ruta/al/repo/vigilante.sh`

## Probar sin publicar

```bash
PUBLISH_LINKEDIN_SIMULACRO=1 ...
```

Con esa variable, `publicar` y `borrar` **nunca tocan la red**. La suite la
activa sola:

```bash
.venv/bin/python prueba.py               # 37 pruebas, ninguna contacta a LinkedIn
.venv/bin/python prueba_concurrencia.py  # 8 procesos reales peleando por el lock
```

La segunda va aparte porque necesita procesos de verdad. Verifica que el lock
sea atómico — y está calibrada para **fallar** con la versión anterior, que
dejaba entrar hasta 8 publicadores a la vez.

> Existe por un incidente real: el 31-ago-2026, dos corridas automatizadas
> publicaron de verdad en un perfil real. Redirigir el directorio de datos no
> basta — el token vive en el Keychain y sigue siendo válido.

## Cómo se evita publicar dos veces

Es el fallo más caro de un publicador: no fallar, sino **duplicar en público**.
Hay cuatro controles, y los cuatro fueron necesarios:

| Control | Qué previene |
|---|---|
| Huella del contenido, ventana 24h | Republicar el mismo texto |
| El chequeo corre **dentro** del lock | Que dos procesos lo pasen a la vez |
| Lock atómico (`O_CREAT\|O_EXCL`) | Que dos procesos tomen el lock a la vez |
| Se registra `INTENTO` **antes** de llamar | Que un timeout deje el post vivo sin rastro |

Y ante un `5xx` de LinkedIn **no se reintenta a propósito**: un 5xx no dice si
el post se creó o no. El mensaje te lo dice y te manda a revisar tu perfil.

Si borras un post, su huella se libera y puedes volver a publicarlo corregido.

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

**Este es el camino recomendado.** Toma ~10 minutos y la app queda tuya.

### Primero: la Página

LinkedIn no deja crear una app sin asociarle una **Página**. Si no administras ninguna,
créala gratis en **[linkedin.com/company/setup/new](https://www.linkedin.com/company/setup/new)**.
Sirve tu empresa, tu marca personal, o una página de prueba — da igual: **la página no es
donde sale el post.** El post sale en tu perfil personal. La página solo figura como
"editor" de la app en el portal. Es papeleo.

### Después: la app

Ve a **[linkedin.com/developers/apps](https://www.linkedin.com/developers/apps)**
→ *Create app*. Asóciala a tu página. Un *super admin* de esa página tiene que aprobar la
verificación con un enlace — si la página es tuya, eres tú y es un clic.

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

## Estado y pendientes

Versión `0.1.0`. Ver `HARDENING.md` para el detalle.

Lo que falta y conviene saber antes de confiar en esto:

- **Windows y Linux están escritos pero sin probar.** El código los contempla;
  nadie los ha corrido de verdad.
- **No hay `refresh_token`**: reautorizar cada ~60 días es obligatorio.
- Publicar sin humano **no está soportado a propósito**. `confirmar=True` es
  siempre de una persona.

MIT.
