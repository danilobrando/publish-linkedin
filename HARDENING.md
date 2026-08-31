# Hardening pendiente

Lo que hay hoy es **el mínimo que publica**, construido contra reloj para la
sesión de cierre de SB Cohorte II (31-ago-2026). Es un subconjunto estricto
del estándar de conectores (`~/.claude/specs/connector-standard.md`): nada de
lo escrito se bota, falta lo de abajo.

## Ya cumple

- [x] Config por entorno (`PUBLISH_LINKEDIN_LOG`, `PUBLISH_LINKEDIN_HOME`)
- [x] Secretos fuera del código (Keychain en macOS · archivo 0600 en Windows/Linux)
- [x] Diario de auditoría de toda publicación
- [x] Anti-CSRF: validación del `state` de OAuth
- [x] Freno de mano (ensayo por defecto, `confirmar=True` para publicar)
- [x] Repo con git

## Falta — P0 (antes de dejarlo correr solo)

- [ ] **`doctor`** — 8 chequeos: Keychain, vigencia del token, permiso
      `w_member_social`, red, producto Share on LinkedIn activo, redirect URI,
      diario escribible, dependencias.
- [ ] **`fix`** — auto-reparación con `--quiet`, para la política de
      AUTO-RECOVERY del SKILL.md.
- [ ] **Refresh de token.** Hoy el token dura ~60 días y expira sin aviso.
      LinkedIn da `refresh_token` solo a apps aprobadas — verificar si la app
      califica; si no, alarma a los 7 días de vencer.
- [ ] **Lock + robo de lock rancio (2h)** — sin esto, dos ejecuciones
      simultáneas publican el mismo post dos veces.
- [ ] **Idempotencia.** Hash del texto en el diario; rechazar republicar el
      mismo contenido dentro de 24h. Es el fallo más caro: duplicar en
      público.
- [ ] **Borrar las credenciales en texto plano** del `.mcp.json` heredado de
      la configuración anterior (quedan con permisos 644). Ya están en el
      almacén seguro. El riesgo es local, no publicado — pero aparece en
      pantalla si alguna vez compartes ese archivo.

## Falta — P1

- [ ] Sentinels + jsonl estructurado
- [ ] Reintento con backoff ante 429 (LinkedIn limita por app y por miembro)
- [ ] `--dry-run` y `--quiet` en la CLI, no solo en la herramienta MCP
- [ ] Catálogo de errores de LinkedIn (equivalente al catálogo AADSTS de
      `ingest-outlook`)
- [ ] SKILL.md con AUTO-RECOVERY POLICY
- [ ] LaunchAgent para la publicación programada
- [ ] Review de 5 expertos (Charity, Aaron, Simon, Allspaw, Filippo) → P0+P1
- [ ] Review de productización (Adam, Mitchell, Mike)
- [x] Repo `danilobrando/publish-linkedin`, MIT — público desde el 31-ago-2026
      para la cohorte. Ojo: público adelanta el hardening de abajo.

## Decisión pendiente

**¿Publicar sin humano, alguna vez?** Hoy exige `confirmar=True`, lo que
significa que un humano lee cada post antes de que salga. Es la postura
correcta para arrancar. Automatizar el `confirmar` requiere primero:
idempotencia, límite diario duro, y un juez de calidad que pueda vetar.
No antes.
