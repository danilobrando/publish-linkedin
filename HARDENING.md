# Hardening

Estado al **31-ago-2026, 20:25**. El repo es público y lo clonaron ~83 personas
el mismo día, así que el hardening dejó de ser opcional.

## Hecho

| | Qué | Dónde |
|---|---|---|
| ✅ | Config por entorno | `PUBLISH_LINKEDIN_{HOME,LOG,JSONL,VENTANA_H,SIMULACRO}` |
| ✅ | Secretos fuera del código | Keychain (macOS) · archivo 0600 (Windows/Linux) |
| ✅ | Anti-CSRF: validación del `state` de OAuth | `auth.py` |
| ✅ | Freno de mano (`confirmar=True`) | `server.py` |
| ✅ | **Idempotencia** por huella de contenido, ventana 24h | `registro.py` |
| ✅ | **Lock** con robo de lock rancio a las 2h | `registro.py` |
| ✅ | Diario jsonl consultable + diario legible | `registro.py` |
| ✅ | **`doctor`** — 9 chequeos con acción por cada fallo | `doctor.py` |
| ✅ | **`fix`** — repara locks rancios y permisos; `--quiet` | `doctor.py` |
| ✅ | **`SIMULACRO`** — las pruebas no pueden tocar la red | `linkedin.py` |
| ✅ | Suite de 24 pruebas, siempre bajo simulacro | `prueba.py` |
| ✅ | Catálogo de 8 errores de LinkedIn traducidos a acción | `linkedin.py` |
| ✅ | Backoff ante 429/5xx respetando `Retry-After` | `linkedin.py` |
| ✅ | Renegociación de versión de API caducada | `linkedin.py` |
| ✅ | `SKILL.md` con AUTO-RECOVERY POLICY | `SKILL.md` |
| ✅ | Vigilante diario + LaunchAgent | `vigilante.sh` |
| ✅ | Repo público, MIT | `github.com/danilobrando/publish-linkedin` |

## Los tres incidentes que originaron esto

Ninguno es hipotético. Los tres pasaron el 31-ago-2026.

1. **Un subagente publicó en el perfil real** usando otro servidor MCP que no
   tenía freno de mano. → Se eliminó ese servidor; el freno aquí es obligatorio.
2. **Una prueba automatizada publicó de verdad.** Redirigir `PUBLISH_LINKEDIN_HOME`
   no basta: el token vive en el Keychain y sigue siendo válido. → `SIMULACRO`.
3. **La versión de API estaba caducada** (`426 NONEXISTENT_VERSION`) y no se supo
   hasta la primera publicación real. → `_renegociar_version()`.

## Falta

- [ ] **Sin `refresh_token`.** Verificado: LinkedIn no lo entrega a esta app, así
      que hay que volver a autorizar cada ~60 días. `auth.py` ya lo guarda si
      algún día llega, y el vigilante avisa 7 días antes. **Mitigado, no resuelto.**
- [ ] Windows y Linux: el código los contempla pero **nadie los ha probado**.
- [ ] Sentinels de última corrida exitosa.
- [ ] `--dry-run` en la CLI (hoy el ensayo solo existe en la herramienta MCP).
- [ ] Rotar el Client Secret — se compartió con ~83 personas el 31-ago.

## Decisión: publicar sin humano

**No.** Hoy `linkedin_publicar` exige `confirmar=True`, lo que significa que
alguien lee cada post antes de que salga. Automatizar esa confirmación requiere
antes: límite diario duro, un juez de calidad que pueda vetar, y una ventana de
retracción automática. La idempotencia y el lock ya están — eran el requisito
mínimo, no la autorización.
