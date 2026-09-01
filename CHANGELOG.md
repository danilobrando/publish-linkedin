# Cambios

## 0.3.0 — 2026-08-31

### Mencionar personas y organizaciones

Escribes `@Nombre` y sale una etiqueta real, que notifica. También páginas de
empresa. Dos herramientas nuevas: `linkedin_menciones` y
`linkedin_mencion_guardar`.

**El límite honesto:** LinkedIn no le deja a esta app averiguar la URN de nadie.
Verificado — `/v2/people?q=search` da 404, `vanityName`, `connections` y
`organizations` dan 403 «partner API», y solo `/v2/userinfo` responde 200.
Resolverlas exige el Marketing Developer Platform, que es una solicitud de
negocio con revisión humana. Así que la URN se captura a mano una vez por
persona; el README trae el procedimiento.

**Verificación sin ensuciar el feed:** LinkedIn valida las menciones del lado
del servidor incluso con `lifecycleState: DRAFT`. `linkedin_mencion_guardar`
crea un borrador con la mención, lee la respuesta y lo borra. Una URN inventada
da `400 INVALID_MENTION_PERSON_URN_ID`; una real, `201`. Ese mismo experimento
es lo que prueba que la mención se resuelve contra una persona real y no se
manda como texto literal.

**El bug que había que evitar:** `@ [ ] ( )` son reservados del formato little
text. Escaparlos a ciegas convertía la etiqueta en texto plano — corchetes a la
vista y sin notificar a nadie. Ahora el texto se parte en tramos y solo se
escapa lo que no es anotación.

56 pruebas.

## 0.2.0 — 2026-08-31

### Adjuntos

`linkedin_publicar` acepta `adjunto` y `titulo`: una imagen (`.jpg .png .gif`,
10 MB) o un documento (`.pdf .pptx .docx`, 100 MB) por post. El PDF sale como
documento navegable en el feed.

La subida son dos llamadas antes de crear el post (`initializeUpload` y un PUT
del binario). El archivo se valida antes de subir nada, y el adjunto entra en la
huella de idempotencia — el mismo texto con otra imagen es otro post.

Verificado contra la API real: subida de PNG y PDF, y un post de cada tipo,
publicados y **borrados de inmediato**. Los PDF devuelven un URN de tipo
`urn:li:ugcPost:` en vez de `urn:li:share:`; `limpiar_urn` ya lo contemplaba.

46 pruebas.

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
