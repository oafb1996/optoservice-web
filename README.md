# optoservice-web

Sitio web de **Opto Service** — Óptica y Optometría Médica en Masaya y Diriomo, Nicaragua.

Sitio estático de una sola página (HTML + CSS + JavaScript sin dependencias). No requiere compilación.

## Estructura

```
index.html                 Página principal
favicon.svg                Ícono del sitio
assets/css/styles.css      Estilos (fuente, variables responsivas, efectos)
assets/js/main.js          Menú móvil, FAQ, formulario de afiliación y animaciones
assets/img/                Logo y fotografías
assets/fonts/              Fuente Parkinsans (autoalojada)
```

## Ver en local

```bash
python3 -m http.server 8000
# abrir http://localhost:8000
```

## Datos que conviene revisar al editar

- **WhatsApp / teléfono:** `50584024868` (enlaces `wa.me` y `tel:` en `index.html`)
- **Correo de afiliaciones:** `afiliaciones@optoservice.com` (en `assets/js/main.js`)
- **Horarios y direcciones:** sección `#sucursales` y pie de página en `index.html`
- **Redes sociales:** Instagram `@optoservicenic`, Facebook, TikTok `@optoservice`

## Publicación

Al ser estático, se puede publicar con GitHub Pages (Settings → Pages → rama `main`, carpeta `/`),
Netlify, Vercel o cualquier hosting. El archivo `.nojekyll` evita que GitHub Pages procese el sitio con Jekyll.
