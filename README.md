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

## Publicación

GitHub Pages con origen **GitHub Actions** (Settings → Pages → Source). El workflow `Publicar sitio` se ejecuta en cada cambio en `main` y además cada noche a las 00:10 (hora de Nicaragua) para retirar las promociones vencidas. Si una compilación falla, el sitio sigue mostrando la última versión publicada.

## Datos que conviene revisar al editar

- **WhatsApp / teléfono:** `50584024868` (enlaces `wa.me` y `tel:` en `index.html`, y `WHATSAPP` en `scripts/build.py`)
- **Correo de afiliaciones:** `afiliaciones@optoservicenic.com` (en `assets/js/main.js`)
- **Horarios y direcciones:** sección `#sucursales` y pie de página en `index.html`
- **Redes sociales:** Instagram `@optoservicenic`, Facebook, TikTok `@optoservice`
- **Dominio:** `CNAME` y el dominio configurado en Settings → Pages
