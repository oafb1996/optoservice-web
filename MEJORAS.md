# Checklist de mejoras — optoservicenic.com

Surge de la revisión integral del sitio (octubre 2026). Se marca cada punto al publicarlo.

## Nuevas funciones

- [x] **Promociones del mes**: sección propia, administrable desde Pages CMS, con fecha de vencimiento (se ocultan solas) y botón de WhatsApp por promoción.
- [x] **Carruseles de fotos** en portada, servicios, examen y nosotros, administrables desde Pages CMS.
- [x] **Optimización automática de imágenes** subidas desde el panel (WebP en varios tamaños), para que las fotos del celular no hagan lenta la web.
- [ ] Conectar Pages CMS al repositorio e invitar a administración y gerencia *(lo hace el dueño de la cuenta; ver README)*.

## 🔴 Prioridad alta

- [x] Quitar el ícono 🔇 de Instagram de las fotos (recortado). *Pendiente: reemplazarlas por las fotos originales cuando estén disponibles.*
- [x] Mostrar de inmediato el texto de la portada en móvil (sin animación de entrada) para mejorar la velocidad percibida.
- [x] Reducir el peso de las fotos (WebP, varios tamaños, carga diferida de las que están más abajo).
- [ ] Formulario de empresas confiable: enviarlo por WhatsApp o con un servicio como Web3Forms/Formspree.

## 🟠 Importante

- [x] Contraste de colores: etiquetas turquesa sobre fondos claros, botones de WhatsApp y textos pequeños.
- [ ] Datos estructurados de "Óptica" (LocalBusiness) para las dos sucursales.
- [ ] `sitemap.xml` y `robots.txt`.
- [ ] Alta en Google Search Console.
- [ ] Enlazar la web desde el perfil de Google Business.
- [ ] Mapas con el pin exacto de cada sucursal (desde Google Business).
- [ ] Elementos de confianza: quién atiende (nombre, título, foto), reseñas de pacientes, fotos reales de las sucursales.

## 🟡 Conversión y contenido

- [ ] Botón de WhatsApp en cada sucursal con mensaje para Masaya / Diriomo.
- [ ] Que cada servicio abra WhatsApp con un mensaje sobre ese servicio.
- [ ] Más preguntas frecuentes: precio del examen, formas de pago, convenios o seguros, tiempo de entrega de los lentes.
- [x] Variar la frase "De todas las edades": se conserva en el recuadro grande de la portada y en las preguntas frecuentes.
- [x] Año del pie de página automático.
- [ ] Medir visitas y clics a WhatsApp (Cloudflare Web Analytics o GoatCounter).

## 🔧 Técnicos

- [x] Al saltar desde el menú, la etiqueta de cada sección ya no queda tapada por la barra superior.
- [x] Etiqueta `<main>` y tamaño declarado de las imágenes.
- [x] Logo liviano (antes 1543 px para mostrarse a 82 px).
- [x] Imagen para compartir en WhatsApp/Facebook en formato 1200×630.
- [ ] Contraste del borde de los campos del formulario de empresas (1,3:1; las pautas de accesibilidad piden 3:1). En el chat ya está corregido.

## 💬 Asistente de chat en la web (chatbot de osops)

Contrato con osops en `docs/contrato-chat-web.md`. El widget está listo y **apagado** hasta que el backend exista.

- [x] Widget de la web: burbuja en escritorio, botón "Asistente" en la barra del móvil, panel accesible, carga diferida (no cuesta velocidad), Turnstile, manejo de errores y traspaso a WhatsApp.
- [x] Probado con un simulador del contrato (`scripts/chat-mock.py`) en escritorio y en móviles de 320 a 430 px, y con axe (accesibilidad) con el panel abierto.
- [ ] Backend en osops: rutas `/session` y `/message`, tablas, límites, CORS, Turnstile y tope de gasto (estimado 3-4 días).
- [ ] Cuenta de Cloudflare y widget de Turnstile (la clave secreta va en Render; a la web solo llega la *site key*).
- [ ] Revisar con asesoría legal y publicar la política de privacidad (`docs/politica-privacidad-borrador.md`).
- [ ] Activar en `content/chat.json` y probar de punta a punta contra osops.
