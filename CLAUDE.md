# Instrucciones para el agente

Si el usuario te pidió instalar o configurar este repo:

**Lee `README.md` completo y sigue la sección «🤖 Si eres Claude Code».**

Ahí está el runbook paso a paso, incluyendo las dos cosas que **no puedes hacer tú**:

- `auth.py credenciales` → usa `input()` y `getpass()`. Se te cuelga. Lo corre el usuario.
- `auth.py login` → abre el navegador y espera un clic humano. Lo corre el usuario.

Nunca pidas ni recibas el Client Secret por el chat.

Guía al usuario hasta que **publique**, no solo hasta que instale.
