# Contrato del canal web del asistente

> **Estado: propuesto por osops, NO implementado.** El widget de la web (`assets/js/chat.js`) ya está construido contra este contrato y probado con el simulador `scripts/chat-mock.py`. Hasta que osops lo despliegue, el chat permanece apagado (`content/chat.json` → `"activo": false`).

Origen: respuesta del asistente de osops tras revisar su código, más los ajustes que pide el lado web (sección "Ajustes pedidos").

## Qué es y qué no es

- El asistente web es el mismo cerebro del chatbot de WhatsApp de osops (modelo Claude de Anthropic, mismas instrucciones del negocio) expuesto como canal web.
- **No hay identidad verificada** (en WhatsApp Meta verifica el teléfono; en la web no). Por eso el canal web **no consulta** órdenes, saldos, pagos, exámenes ni citas, ni crea fichas de pacientes. Solo: información de sucursales, preguntas frecuentes (base de conocimiento), captura de contacto (`dejar_contacto`) y traspaso a una persona por WhatsApp.
- El traspaso apunta al **número del bot** en osops (así la conversación cae en la bandeja con contexto). El número de los botones de la web (8402 4868) es otro y se usa solo como respaldo cuando el servicio no responde.

## URL base y CORS

| | |
|---|---|
| Producción | `https://osops.app/api/web-chat` |
| Desarrollo | `http://localhost:5000/api/web-chat` (CORS permite `http://localhost:*` solo fuera de producción) |
| Simulador | `python3 scripts/chat-mock.py` → `http://127.0.0.1:8771/api/web-chat` |

- Orígenes permitidos: `https://optoservicenic.com` y `https://www.optoservicenic.com`. Métodos `POST, OPTIONS`; cabeceras `Content-Type, Authorization`; **sin cookies** (`credentials: omit`).
- Las cabeceras `Access-Control-Allow-Origin` y `Vary: Origin` van **en todas las respuestas, también en los errores 4xx/5xx**. Sin ellas el navegador oculta el error y el widget solo ve "fallo de red".
- `Access-Control-Expose-Headers: Retry-After`, para poder leer los 429.
- Otro origen: sin `Allow-Origin` (el navegador bloquea); petición sin `Origin`: 403.

## 1) `POST /session` — abrir sesión

Petición:

```json
{ "turnstile_token": "<token de Cloudflare Turnstile>" }
```

`201`:

```json
{
  "session_id": "ws_7f3c9a1e2b4d",
  "token": "<token firmado, opaco>",
  "expires_at": "2026-10-27T18:30:00Z",
  "greeting": "¡Hola! 😊 Soy el asistente virtual de Opto Service. ¿Con cuál sucursal te quieres comunicar: *Masaya* o *Diriomo*?",
  "limits": { "max_message_chars": 500, "max_messages": 30 }
}
```

- El token de Turnstile es de un solo uso y vence a los 5 minutos: el widget lo pide justo antes de llamar. Si responde `403 turnstile_failed`, el widget reintenta **una vez** con un token nuevo.
- El token de sesión **no cambia** durante la sesión; solo se extiende `expires_at`. Si osops lo rota, `/message` debe devolver el token nuevo en el cuerpo.

## 2) `POST /message` — enviar un mensaje

Cabeceras: `Content-Type: application/json`, `Authorization: Bearer <token>`.

```json
{ "session_id": "ws_7f3c9a1e2b4d", "message": "¿A qué hora abren en Masaya?" }
```

`200`:

```json
{
  "reply": { "text": "¡Claro! 🕐 En *Masaya* atendemos de lunes a sábado ...", "format": "whatsapp" },
  "handoff": null,
  "lead_saved": false,
  "remaining_messages": 28,
  "expires_at": "2026-10-27T18:30:00Z"
}
```

`200` con traspaso:

```json
{
  "reply": { "text": "Te paso con una persona del equipo para ayudarte mejor 🙌 ...", "format": "whatsapp" },
  "handoff": { "reason": "pidió_persona", "whatsapp_url": "https://wa.me/505XXXXXXXX?text=Hola%2C%20vengo%20del%20chat%20web%20(ref%20W7F3C)" },
  "lead_saved": false,
  "remaining_messages": 25,
  "expires_at": "..."
}
```

Después de un traspaso, la sesión ya no recibe respuestas del bot (`409 handed_off`).

### Formato de `reply.text`

Solo `*negrita*`, saltos de línea (`\n`) y emojis. Los enlaces van como **URL completas en texto plano** (sin markdown `[texto](url)`). El widget nunca interpreta HTML: construye nodos de texto, convierte `*texto*` en negrita y vuelve clicables únicamente las URL `https://`.

## Errores

```json
{ "error": { "code": "rate_limited", "message": "Texto en español para mostrar" },
  "whatsapp_url": "https://wa.me/..." }
```

`whatsapp_url` aparece cuando conviene ofrecer WhatsApp. Debe empezar con `https://wa.me/` o `https://api.whatsapp.com/`; el widget descarta cualquier otra cosa.

| HTTP | `code` | Cuándo | Qué hace el widget |
|---|---|---|---|
| 400 | `invalid_request` | cuerpo inválido o mensaje vacío | quita el mensaje, lo devuelve al cuadro y muestra el texto |
| 401 | `invalid_token` / `session_expired` | token ausente, mal firmado o vencido | abre una sesión nueva, avisa y **reenvía el mensaje una sola vez** |
| 403 | `origin_not_allowed` | `Origin` no permitido | error genérico + WhatsApp |
| 403 | `turnstile_failed` | Turnstile no validó | un reintento con token nuevo; luego error con "Reintentar" |
| 409 | `busy` | ya hay una respuesta en curso | avisa y devuelve el texto al cuadro (el widget no deja enviar mientras espera) |
| 409 | `handed_off` | la sesión ya pasó a WhatsApp | bloquea el cuadro y ofrece WhatsApp |
| 413 | `message_too_long` | más de 500 caracteres | el cuadro ya limita a `max_message_chars` |
| 429 | `rate_limited` | límite por sesión o por IP (`Retry-After` en segundos) | muestra el mensaje y cuánto esperar |
| 503 | `bot_unavailable` | asistente apagado, tope diario de gasto o sin clave de IA | mensaje + botón de WhatsApp |
| 500 | `internal_error` | error del servidor | mensaje + WhatsApp |

Sin respuesta en 45 s (`timeoutMs`), el widget muestra "tardó demasiado" y ofrece reintentar.

## Límites propuestos

| Concepto | Límite |
|---|---|
| Tamaño del mensaje | 500 caracteres |
| Mensajes por sesión | 30 |
| Mensajes por IP | 60 por hora |
| Sesiones nuevas por IP | 10 por hora |
| Vida de la sesión | 30 min, se renueva con cada mensaje, máximo 2 h |
| Gasto diario del modelo | tope en US$ configurable (propuesta: 2); al pasarlo, `503` con enlace a WhatsApp |

Sin streaming: respuesta completa. El historial vive en el servidor; **nunca** se acepta el historial enviado por el navegador. El widget solo envía el mensaje nuevo y guarda `session_id`, token y transcripción en `sessionStorage` (se borra al cerrar la pestaña).

## Seguridad y privacidad

- La web es estática: **no hay secretos en el navegador**. Solo se publican la URL de la API y la *site key* pública de Turnstile.
- Servidor: Turnstile en `/session`, token de sesión firmado con HMAC, límites por sesión/IP, CORS con lista de orígenes, tope de gasto, modelo fijo (Haiku) para web, sin herramientas de datos personales.
- Datos que guardaría osops: id de sesión aleatorio, mensajes, fechas, **hash** de la IP y, solo si la persona los da, nombre y teléfono. Retención propuesta: 90 días.
- El widget muestra siempre: "Asistente virtual con IA. No compartas datos médicos ni de pago. Guardamos la conversación para atenderte." con enlace a la política de privacidad (ver `docs/politica-privacidad-borrador.md`).

## Configuración

- osops (Render → Environment): `TURNSTILE_SECRET_KEY`, `WEB_CHAT_TOKEN_SECRET`, `WEB_CHAT_ALLOWED_ORIGINS`, `WEB_CHAT_DAILY_USD_CAP`, opcional `WEB_CHAT_ANTHROPIC_API_KEY`. En osops, página Chatbot: interruptor "Canal web" y número de WhatsApp del traspaso.
- Web (`content/chat.json`): `activo`, `apiUrl`, `turnstileSiteKey`, `privacidadUrl`. Ver README.
- Turnstile: la *site key* debe autorizar `optoservicenic.com`, `www.optoservicenic.com` y `localhost` para pruebas.

## Ajustes pedidos por el lado web

1. CORS (`Allow-Origin`, `Vary`) también en los errores 4xx/5xx.
2. `Access-Control-Expose-Headers: Retry-After`.
3. El token no rota; si lo hace, `/message` lo devuelve en el cuerpo.
4. Turnstile: token de un solo uso (5 min); el widget lo pide justo antes de `/session` y reintenta una vez ante `turnstile_failed`.
5. Enlaces en `reply.text` como URL completas en texto plano.
6. `409 busy`: el widget no permite enviar mientras espera; debería ser raro.
7. Registrar la duración de cada respuesta; la primera tras un rato inactivo puede tardar por el arranque en frío de la base de datos.
8. Alta de Turnstile con los dominios del punto "Configuración".

## Probar sin osops

```bash
python3 scripts/chat-mock.py            # simulador en http://127.0.0.1:8771
```

En `content/chat.json` de una copia de pruebas: `{"activo": true, "apiUrl": "http://127.0.0.1:8771/api/web-chat", "turnstileSiteKey": ""}` (la API `http://` solo se acepta para `localhost`/`127.0.0.1`). Frases que activan escenarios: `persona`, `/503`, `/500`, `/429`, `/expirar`, `/contacto`, `/xss`, `/lento`, `/largo`, `/ultimos`, `horario` (ver el encabezado de `scripts/chat-mock.py`).

Contra el backend real, el mismo contrato se puede verificar con `curl`:

```bash
curl -s -X POST https://osops.app/api/web-chat/session \
  -H "Origin: https://optoservicenic.com" -H "Content-Type: application/json" \
  -d '{"turnstile_token":"<token>"}'
```
