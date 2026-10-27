# optoservice-web

Sitio web de **Opto Service** — https://optoservicenic.com (Óptica y Optometría Médica en Masaya y Diriomo, Nicaragua).

Sitio estático de una sola página (HTML + CSS + JavaScript sin dependencias). Las fotos y las promociones se administran desde **Pages CMS**, y un paso de compilación en GitHub Actions las inserta en la página y optimiza las imágenes.

## Administrar fotos y promociones (gerencia)

Panel: **https://app.pagescms.org** → repositorio `optoservice-web`.

- **Promociones del mes**: imagen o flyer, título, precio u oferta, descripción, fecha de vencimiento y mensaje de WhatsApp. Las vencidas desaparecen solas. Si no hay ninguna vigente, la sección y el enlace del menú no se muestran.
- **Fotos de la página**: una lista de fotos para cada espacio (portada, servicios, examen, nosotros). Si un espacio tiene más de una, rotan en carrusel. También se elige cada cuántos segundos cambian.

Cada cambio guardado se publica solo en 1-2 minutos. Las fotos se pueden subir tal como salen del celular: se reducen y convierten a WebP automáticamente.

## Estructura

```
index.html                  Página (con marcadores donde se insertan fotos y promociones)
content/fotos.json          Fotos de cada carrusel           ← lo edita Pages CMS
content/promociones.json    Promociones del mes              ← lo edita Pages CMS
assets/uploads/             Fotos subidas desde el panel
assets/css/styles.css       Estilos
assets/js/main.js           Menú móvil, FAQ, formulario, carruseles, animaciones
assets/img/                 Logo e imagen para compartir en redes
assets/fonts/               Fuente Parkinsans (autoalojada)
scripts/build.py            Genera el sitio publicable en _site/
scripts/chat-mock.py        Simulador del canal web del asistente (para desarrollo y pruebas)
docs/                       Contrato del chat web y borrador de política de privacidad (no se publican)
content/chat.json           Interruptor y datos del asistente de chat       ← lo edita quien programa
assets/js/chat.js           Panel del asistente (se descarga solo al abrirlo)
assets/css/chat.css         Estilos del panel del asistente
.pages.yml                  Formularios del panel de Pages CMS
.github/workflows/          Publicación automática en GitHub Pages
MEJORAS.md                  Checklist de mejoras pendientes
```

## Ver en local

```bash
pip install -r scripts/requirements.txt
python3 scripts/build.py
python3 -m http.server 8000 -d _site
# abrir http://localhost:8000
```

Abrir `index.html` sin compilar también funciona: muestra la primera foto por defecto de cada espacio y oculta las promociones.

Para probar cómo se vería la página otro día (vencimiento de promociones): `python3 scripts/build.py --hoy 2026-12-01`.

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
- Aparece una burbuja "Asistente" en escritorio y un tercer botón en la barra inferior del móvil. El código del panel se descarga solo cuando alguien lo abre.
- Antes de activarlo: publicar la política de privacidad (`docs/politica-privacidad-borrador.md` es un borrador para revisión legal) y tener el backend de osops en producción.
- El contrato entre la web y osops está en `docs/contrato-chat-web.md`. Para desarrollar sin osops: `python3 scripts/chat-mock.py` y, en una copia de pruebas, `apiUrl` apuntando a `http://127.0.0.1:8771/api/web-chat`.

## Publicación

GitHub Pages con origen **GitHub Actions** (Settings → Pages → Source). El workflow `Publicar sitio` se ejecuta en cada cambio en `main` y además cada noche a las 00:10 (hora de Nicaragua) para retirar las promociones vencidas. Si una compilación falla, el sitio sigue mostrando la última versión publicada.

## Datos que conviene revisar al editar

- **WhatsApp / teléfono:** `50584024868` (enlaces `wa.me` y `tel:` en `index.html`, y `WHATSAPP` en `scripts/build.py`)
- **Formulario de empresas:** se envía con [Web3Forms](https://web3forms.com). La clave pública está en `data-access-key` del `<form data-afil-form>` en `index.html`; el correo de destino se cambia desde el panel de Web3Forms (hoy `afiliaciones@optoservicenic.com`).
- **Horarios y direcciones:** sección `#sucursales` y pie de página en `index.html`
- **Redes sociales:** Instagram `@optoservicenic`, Facebook, TikTok `@optoservice`
- **Dominio:** `CNAME` y el dominio configurado en Settings → Pages
