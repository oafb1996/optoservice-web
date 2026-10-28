# Política de privacidad — BORRADOR

> ⚠️ **Borrador para revisión. No publicar sin que lo revise una persona con conocimiento legal.**
> No es asesoría legal. Revisen qué exige la normativa de protección de datos personales de Nicaragua (la Ley 787 es la referencia; verifiquen su alcance y requisitos vigentes) y completen todo lo marcado como **[COMPLETAR]**.
> Está escrito según lo que hace hoy la web y lo que describió osops para el chat. Si algo cambia (analítica, otro proveedor, otro plazo), hay que actualizarlo.

**Última actualización:** [COMPLETAR fecha]

## 1. Quiénes somos

**Opto Service** — Óptica y Optometría Médica, con sucursales en Masaya y Diriomo, Nicaragua.
Responsable del tratamiento: [COMPLETAR razón social y número RUC].
Dirección: [COMPLETAR]. Correo de contacto para temas de privacidad: [COMPLETAR, por ejemplo privacidad@optoservicenic.com].

## 2. Qué datos recogemos y para qué

### Al usar el asistente virtual (chat de la página)

- **Los mensajes que escribes** y las respuestas del asistente, para poder atenderte y mejorar el servicio.
- **Un identificador aleatorio de sesión** y las fechas de la conversación.
- **Un código derivado de tu dirección IP** (no la dirección en claro), para evitar abusos del servicio.
- **Tu nombre y teléfono, solo si tú nos los das** para que una persona del equipo te contacte.

El asistente es una **inteligencia artificial**. No lo uses para compartir datos médicos ni de pago. No puede consultar tu historial ni tus pagos desde la página web.

### Al llenar el formulario "Para empresas"

Nombre de la empresa, persona de contacto, correo, teléfono y mensaje. Los usamos solo para responder a tu solicitud de afiliación.

### Al escribirnos por WhatsApp, llamarnos o seguirnos en redes

Lo que nos compartas en esos canales se rige además por las políticas de WhatsApp (Meta), Instagram, Facebook y TikTok.

### Datos que recoge el navegador sin que escribas nada

- Para el chat se guarda en tu navegador (almacenamiento de sesión) la conversación en curso; se borra al cerrar la pestaña.
- [COMPLETAR si se agrega analítica de visitas: qué herramienta, qué mide y si usa cookies.]
- Los mapas de las sucursales los carga Google Maps, que puede recoger datos técnicos de tu visita según su propia política.

## 3. Con quién compartimos los datos

Solo con proveedores que necesitamos para ofrecer el servicio, que actúan por nuestra cuenta:

| Proveedor | Para qué |
|---|---|
| Anthropic | modelo de inteligencia artificial que genera las respuestas del asistente |
| Render y Neon | alojamiento del sistema del asistente y su base de datos |
| Cloudflare | verificación anti-bots (Turnstile) al abrir el chat |
| Web3Forms | entrega por correo del formulario "Para empresas" |
| Meta (WhatsApp) | cuando continúas la conversación por WhatsApp |
| Google | mapas de las sucursales |
| GitHub | alojamiento de la página web |

[COMPLETAR/CONFIRMAR con osops la lista exacta de proveedores y los países donde se procesan los datos.]

No vendemos tus datos ni los usamos para publicidad de terceros.

## 4. Cuánto tiempo los conservamos

- Conversaciones del chat web: **90 días** [CONFIRMAR con osops], salvo que nos hayas pedido ser contactado, en cuyo caso conservamos tus datos de contacto el tiempo necesario para atenderte.
- Solicitudes de afiliación: [COMPLETAR].

## 5. Tus derechos

Puedes pedirnos acceso a tus datos, rectificarlos, que los eliminemos u oponerte a su uso, escribiendo a [COMPLETAR correo]. Respondemos en un plazo de [COMPLETAR].

## 6. Menores de edad

El asistente y el formulario están dirigidos a personas adultas. Si eres menor, usa el chat acompañado de tu madre, padre o tutor. [REVISAR con asesoría legal.]

## 7. Seguridad

Usamos conexiones cifradas (HTTPS), verificación anti-bots, límites de uso y acceso restringido a los datos. Ningún sistema es 100 % seguro, por eso te pedimos no compartir datos sensibles en el chat.

## 8. Cambios en esta política

Si la cambiamos, publicaremos la nueva versión en esta página con su fecha.

## 9. Contacto

[COMPLETAR correo y teléfono]

---

### Para quien publique esto (nota interna, borrar antes de publicar)

1. Completar los [COMPLETAR] y revisar con asesoría legal.
2. Crear la página `privacidad.html` en el sitio (puedo hacerlo con el mismo diseño de la web).
3. Poner `"privacidadUrl": "/privacidad.html"` en `content/chat.json` y enlazar la política desde el pie de página.
