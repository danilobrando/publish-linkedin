# Cambios

## 0.1.0 — 2026-08-31

Primera versión con hardening completo. Nació el mismo día para una clase en
vivo y pasó por una revisión de 8 expertos (5 de hardening, 3 de producto) con
refutación adversarial: 58 hallazgos, 31 sobrevivieron y se corrigieron.

### Lo que hace

Cinco herramientas MCP para publicar en LinkedIn desde Claude Code:
`linkedin_estado`, `linkedin_quien_soy`, `linkedin_publicar`, `linkedin_borrar`,
`linkedin_doctor`. API oficial con OAuth 2.0, sin cookies del navegador.

### Cómo evita publicar dos veces

Cuatro controles, los cuatro necesarios: huella del contenido con ventana de
24h, chequeo dentro del lock, lock atómico (`O_CREAT|O_EXCL`), y escritura
anticipada del `INTENTO` antes de llamar a LinkedIn. Más un techo de 10 posts
diarios por si un agente entra en bucle.

Ante un `5xx` **no se reintenta a propósito**: un 5xx no dice si el post se creó.

### Los tres incidentes que originaron los controles

Ninguno hipotético; los tres del 31-ago-2026.

1. Un agente publicó en un perfil real usando otro servidor MCP sin freno.
2. Una prueba automatizada publicó de verdad: redirigir el directorio de datos
   no aísla nada porque el token vive en el Keychain. → `PUBLISH_LINKEDIN_SIMULACRO`.
3. La versión de API estaba caducada y no se supo hasta publicar. → renegociación
   automática.

### Se sabe que falta

- Windows y Linux están escritos pero **sin probar**.
- LinkedIn no entrega `refresh_token` a esta app: hay que reautorizar cada ~60
  días. El vigilante avisa 7 días antes.
- Publicar sin humano no está soportado a propósito.
