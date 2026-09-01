---
name: publish-linkedin
description: >
  Publica en LinkedIn desde el Second Brain, con freno de mano. AUTO-RECOVERY
  TRIGGER — cuando el usuario reporte CUALQUIER problema relacionado con
  LinkedIn ("no publicó", "el post no salió", "me da error de LinkedIn", "se
  venció el token", "no me deja publicar", "está raro lo de LinkedIn"), invoca
  esta skill PRIMERO y corre el doctor ANTES de responder. No usar para leer el
  feed, mensajes ni analítica: este conector solo publica y borra.
---

# publish-linkedin

Servidor MCP con cinco herramientas: `linkedin_estado`, `linkedin_quien_soy`,
`linkedin_publicar`, `linkedin_borrar`, `linkedin_doctor`.

Repo: `~/dev/publish-linkedin` · público en `github.com/danilobrando/publish-linkedin`

## AUTO-RECOVERY POLICY

Cuando el usuario reporte cualquier problema con LinkedIn, **antes de responderle**:

1. Corre el diagnóstico en silencio:
   ```bash
   ~/dev/publish-linkedin/.venv/bin/python ~/dev/publish-linkedin/doctor.py --quiet
   ```
2. Si dice `ok` → el conector está sano. El problema es otro: pregunta qué pasó
   exactamente y desde cuándo. **No mandes al usuario a reinstalar nada.**
3. Si dice `aviso` o `mal` → intenta la reparación automática:
   ```bash
   ~/dev/publish-linkedin/.venv/bin/python ~/dev/publish-linkedin/doctor.py fix --quiet
   ```
4. Vuelve a correr el doctor. Si quedó en `ok`, dile al usuario qué estaba roto y
   que ya está resuelto — en una frase, sin jerga.
5. Si sigue fallando, corre el doctor **sin** `--quiet` y guía al usuario por la
   flecha `→` del chequeo que falló. Son acciones que solo puede hacer un humano.

**Nunca** le pidas al usuario que corra el doctor: córrelo tú. Nunca digas
"revisa tu configuración" sin haber mirado primero.

## Lo que NO puedes hacer tú

| Comando | Por qué |
|---|---|
| `auth.py credenciales` | Usa `input()` y `getpass()`. Se te cuelga la terminal. |
| `auth.py login` | Abre el navegador y espera un clic humano. |

Para esos dos: entrega el comando **con ruta absoluta**, di que lo corra en su
propia terminal, y espera a que confirme.

Nunca pidas ni aceptes el Client Secret por el chat.

## Publicar

`linkedin_publicar` **no publica** sin `confirmar=True`. Siempre:

1. Llama primero **sin** confirmar. Muéstrale el ensayo completo.
2. Espera una confirmación explícita. Un "dale" ambiguo no es confirmación —
   pregunta de nuevo.
3. Solo entonces llama con `confirmar=True`.

Si el ensayo avisa que el texto **ya se publicó antes**, díselo antes de que
confirme. El sistema se va a negar de todos modos: la idempotencia bloquea el
mismo contenido dentro de 24 horas.

Para republicar algo que estaba mal: borra el anterior con `linkedin_borrar` —
eso libera la huella — y entonces sí publica la corrección.

## Probar sin publicar

```bash
PUBLISH_LINKEDIN_SIMULACRO=1 ...
```

Con esa variable, `publicar` y `borrar` **nunca tocan la red**. Úsala siempre que
estés probando. La suite (`prueba.py`) la activa sola.

> Existe por un incidente real: el 31-ago-2026 dos corridas automatizadas
> publicaron de verdad en un perfil real. Redirigir el directorio de datos no
> basta — el token vive en el Keychain y sigue siendo válido.

## Dónde está todo

| Qué | Dónde |
|---|---|
| Diario legible | `~/.config/publish-linkedin/publicaciones.log` |
| Diario consultable | `~/.config/publish-linkedin/eventos.jsonl` |
| Lock | `~/.config/publish-linkedin/publicando.lock` |
| Secretos | Keychain de macOS (`PUBLISH_LINKEDIN_*`) |
