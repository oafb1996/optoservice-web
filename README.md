# optoservice-web

Sitio web de **Opto Service** — https://optoservicenic.com (Óptica y Optometría Médica en Masaya y Diriomo, Nicaragua).

Sitio estático de una sola página (HTML + CSS + JavaScript sin dependencias), con el diseño de la propuesta B, "Farmacia de lino": fondo lino, azul marino y turquesa, tipografía Schibsted Grotesk. Las fotos y las promociones se administran desde **Pages CMS**, y un paso de compilación en GitHub Actions las inserta en la página y optimiza las imágenes.

## Administrar fotos y promociones (gerencia)

Panel: **https://app.pagescms.org** → repositorio `optoservice-web`.

- **Promociones del mes**: imagen o flyer, título, precio u oferta, descripción, fecha de vencimiento y mensaje de WhatsApp. Las vencidas desaparecen solas. Si no hay ninguna vigente, la sección y el enlace del menú no se muestran.
- **Fotos** (una opción por sección: *Fotos · Portada*, *Examen visual*, *Nosotros* y *Sucursales*): si una sección tiene más de una foto, rotan en carrusel, y cada sección tiene su propia velocidad. Cada foto puede llevar:
  - un **recuadro de texto** (etiqueta + texto) que cambia junto con la foto, por ejemplo "Terapia visual" en la portada;
  - la **parte que siempre debe verse** (9 posiciones: arriba a la izquierda, arriba, centro, abajo a la derecha, etc.);
  - **cómo llenar el espacio**: *llenar* (recorta los bordes) o *mostrar completa* (sin recortar, con margen color lino).
  - **fechas** *Mostrar desde* / *Mostrar hasta* para fotos de temporada (se activan y retiran solas; el sitio se regenera cada noche);
  - un **enlace en el recuadro**: abrir "Agendar cita" (con un servicio ya elegido, si se quiere) o ir a una sección.
  Las fotos de sucursales son opcionales: si no hay, solo se ve el mapa.
- **Vista previa**: https://optoservicenic.com/vista-previa.html muestra arriba los **avisos** (fotos que pueden verse borrosas, sin descripción, muy recortadas, programadas o vencidas, y fotos subidas que no se usan), luego las **promociones** con su estado (vigente, vencida, oculta) y cada foto recortada tal como se verá en celular, tablet y computadora. Se actualiza en cada publicación, no está enlazada desde la página y Google no la indexa.

Cada cambio guardado se publica solo en 1-2 minutos. Las fotos se pueden subir tal como salen del celular: se reducen y convierten a AVIF y WebP automáticamente. En la página, los carruseles se pueden pausar y se detienen al pasar el mouse o usar el teclado.

## Estructura

```
index.html                  Página (con marcadores donde se insertan fotos y promociones)
content/fotos-*.json        Fotos de cada sección (portada, examen, nosotros, sucursales)  ← lo edita Pages CMS
content/promociones.json    Promociones del mes              ← lo edita Pages CMS
assets/uploads/             Fotos subidas desde el panel
assets/css/styles.css       Estilos
assets/js/main.js           Menú móvil, "Agendar cita" en 3 pasos, FAQ, formulario, carruseles
assets/img/                 Logo e imagen para compartir en redes
assets/fonts/               Fuente Schibsted Grotesk (autoalojada, licencia SIL OFL)
scripts/build.py            Genera el sitio publicable en _site/ (y vista-previa.html)
scripts/chat-mock.py        Simulador del canal web del asistente (para desarrollo y pruebas)
docs/                       Contrato del chat web y borrador de política de privacidad (no se publican)
content/chat.json           Interruptor y datos del asistente de chat       ← lo edita quien programa
assets/js/chat.js           Panel del asistente (se descarga solo al abrirlo)
assets/css/chat.css         Estilos del panel del asistente
.pages.yml                  Formularios del panel de Pages CMS
.github/workflows/          Publicación automática en GitHub Pages
MEJORAS.md                  Checklist de mejoras pendientes
```

## Agendar cita

Los botones "Agendar cita", "Agenda tu examen", "Reserva tu cita" y "Agendar por WhatsApp" (los que llevan `data-agendar` en `index.html`) abren una hoja de 3 pasos: servicio, sucursal y cuándo le viene bien (más el nombre, opcional). Al final se abre WhatsApp con el mensaje ya escrito; no se envía nada hasta que la persona pulsa enviar. Si el navegador no puede mostrar la hoja, los botones abren WhatsApp directamente con el mensaje general.

## Ver en local

```bash
pip install -r scripts/requirements.txt
python3 scripts/build.py
python3 -m http.server 8000 -d _site
# abrir http://localhost:8000
```

Abrir `index.html` sin compilar también funciona: muestra la primera foto por defecto de cada espacio y oculta las promociones.

Para probar cómo se vería la página otro día (vencimiento de promociones): `python3 scripts/build.py --hoy 2026-12-01`.

## SEO local

Las dos sucursales permanecen en el inicio. Se pueden compartir enlaces directos:

- Masaya: `https://optoservicenic.com/#masaya`
- Diriomo: `https://optoservicenic.com/#diriomo`

`index.html` contiene datos estructurados JSON-LD de la organización y las dos
ópticas. Si cambian teléfono, dirección u horarios, actualizar tanto el contenido
visible como esos datos. El domingo se describe como atención previa cita, sin
inventar un horario fijo. No se incluyen coordenadas ni valoraciones sin verificar.

El build genera `_site/sitemap.xml` a partir de la URL canónica del inicio y copia
`robots.txt`. Los anclajes no son páginas independientes y no se agregan al sitemap.
`vista-previa.html` queda fuera del sitemap y conserva `noindex`; se permite su
rastreo para que los buscadores puedan leer esa directiva.

Comprobar la salida real del build y sus enlaces:

```bash
python3 -m unittest discover -s scripts -p 'test_*.py'
```

Después de publicar, verificar el dominio en Google Search Console, enviar
`https://optoservicenic.com/sitemap.xml` e inspeccionar la URL del inicio. Revisar
también los datos estructurados en `https://validator.schema.org/`.
Esto facilita el rastreo; no garantiza indexación ni posiciones.

Pendientes fuera del código: reclamar/verificar los perfiles de Google de cada
sucursal, confirmar sus pines, subir fotos reales y obtener sus enlaces de reseñas.
Pueden enlazar al inicio o al anclaje de su sede. No hace falta crear páginas de
sucursal para completar esos pasos. No se agregó analítica: requiere definir la
medición, configurar la propiedad y revisar la política de privacidad primero.

## Asistente de chat (apagado hasta que osops esté listo)

La web trae un widget de chat que habla con el canal web del asistente de osops (el chatbot de WhatsApp). Está **apagado por defecto**: mientras `content/chat.json` diga `"activo": false`, no se agrega ni una línea a la página.

Para activarlo, cuando el backend esté desplegado, editar `content/chat.json`:

```json
{
  "activo": true,
  "apiUrl": "https://osops.app/api/web-chat",
  "turnstileSiteKey": "<site key pública de Cloudflare Turnstile>",
  "privacidadUrl": "/privacidad.html"
}
```

- Si algún dato es dudoso (URL que no sea `https://`, falta la clave de Turnstile, etc.), el chat **se queda apagado** y la compilación lo avisa.
- Aparece un botón "Asistente" encima del de WhatsApp en escritorio y un tercer botón en la barra inferior del móvil. El código del panel se descarga solo cuando alguien lo abre.
- Antes de activarlo: publicar la política de privacidad (`docs/politica-privacidad-borrador.md` es un borrador para revisión legal) y tener el backend de osops en producción.
- El contrato entre la web y osops está en `docs/contrato-chat-web.md`. Para desarrollar sin osops: `python3 scripts/chat-mock.py` y, en una copia de pruebas, `apiUrl` apuntando a `http://127.0.0.1:8771/api/web-chat`.

## Publicación

GitHub Pages con origen **GitHub Actions** (Settings → Pages → Source). El workflow `Publicar sitio` se ejecuta en cada cambio en `main` y además cada noche a las 00:10 (hora de Nicaragua) para retirar las promociones vencidas. Si una compilación falla, el sitio sigue mostrando la última versión publicada.

Cada script y hoja de estilos se publica con una huella de su contenido (`main.js?v=a1b2c3d4`, hecho por `scripts/build.py`), para que los navegadores no sigan usando una versión vieja guardada en memoria (GitHub Pages permite guardarla 10 minutos). La página lleva además `<meta name="build">` con un identificador de la versión publicada.

## Datos que conviene revisar al editar

- **WhatsApp / teléfono:** `50584024868` (enlaces `wa.me` y `tel:` en `index.html`, y `WHATSAPP` en `scripts/build.py`)
- **Formulario de empresas:** se envía con [Web3Forms](https://web3forms.com). La clave pública está en `data-access-key` del `<form data-afil-form>` en `index.html`; el correo de destino lo define Web3Forms al crear la clave. **Hoy es un correo de pruebas**: cuando el buzón `afiliaciones@optoservicenic.com` esté listo, crear otra clave con ese correo y reemplazarla en `index.html`.
- **Horarios y direcciones:** sección `#sucursales` y pie de página en `index.html`
- **Redes sociales:** Instagram `@optoservicenic`, Facebook, TikTok `@optoservice`
- **Dominio:** `CNAME` y el dominio configurado en Settings → Pages
