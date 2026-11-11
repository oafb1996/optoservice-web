#!/usr/bin/env python3
"""Genera el sitio publicable en _site/.

1. Copia los archivos del sitio.
2. Inserta en index.html las fotos de content/fotos-*.json y las promociones de
   content/promociones.json (todo se edita desde Pages CMS).
3. Optimiza cada imagen usada: versiones AVIF y WebP de 480, 800 y 1200 px de
   ancho y un JPEG (o PNG) de respaldo, para que las fotos del celular no pesen.
4. Genera vista-previa.html: avisos (fotos borrosas, sin descripción, muy
   recortadas o sin usar), las promociones con su estado y cada foto recortada
   como se verá en celular, tablet y computadora (no se enlaza desde la página
   ni la indexa Google).
5. Inserta las sucursales (content/sucursales.json) en el inicio, el pie y los datos estructurados.
6. Genera las demás páginas desde paginas/ (terapia-visual.html, 404.html). El encabezado, el pie y la hoja de
   "Agendar cita" se copian de index.html, así hay una sola versión de cada uno.
   Una página con <meta name="borrador"> se publica con noindex y un aviso, fuera del sitemap y sin
   enlaces desde las demás (los enlaces con data-requiere="<página>" se quitan).
7. Genera sitemap.xml con las páginas publicadas.

Uso:  python3 scripts/build.py [--out _site]
"""
import argparse
import hashlib
import html
import json
import math
import re
import shutil
import sys
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageOps, features

try:  # fotos HEIC de iPhone
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent.parent
EXCLUDE = {'paginas', '.git', '.github', '.gitignore', '.pages.yml', 'scripts', 'content', 'docs', '_site', 'README.md', 'MEJORAS.md'}
WIDTHS = (480, 800, 1200)
WHATSAPP = '50584024868'
NICARAGUA = timezone(timedelta(hours=-6))
DOMINIO = 'https://optoservicenic.com'  # el mismo de CNAME, canonical y datos estructurados
# Sucursales: están en el inicio (/#masaya, /#diriomo); los datos están en content/sucursales.json
SUCURSALES = {'masaya': 'Masaya', 'diriomo': 'Diriomo'}
TELEFONO = '+50584024868'
REDES = ['https://instagram.com/optoservicenic', 'https://facebook.com/profile.php?id=100092434450811',
         'https://tiktok.com/@optoservice']
MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
         'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

# Espacios de foto. Cada uno se edita en Pages CMS desde su propio archivo de content/.
#   sizes: ancho mostrado (atributo sizes)   pos: encuadre por defecto   alt: texto alternativo por defecto
#   opcional: si no tiene fotos, el espacio no se muestra (en vez de dejar la foto por defecto)
#   marcos: tamaño real del espacio (ancho, alto) en celular, tablet y computadora, para vista-previa.html
SLOTS = {
    'portada': {'archivo': 'fotos-portada.json', 'lista': 'fotos', 'titulo': 'Portada',
                'sizes': '(max-width: 899px) calc(100vw - 32px), 590px', 'pos': '50% 30%',
                'alt': 'Paciente con lentes en Opto Service',
                'marcos': {'Celular': (358, 448), 'Tablet': (707, 640), 'Computadora': (548, 640)}},
    'examen': {'archivo': 'fotos-examen.json', 'lista': 'fotos', 'titulo': 'Examen visual',
               'sizes': '(max-width: 999px) calc(100vw - 34px), 510px', 'pos': '50% 55%',
               'alt': 'Lentes disponibles en Opto Service',
               'marcos': {'Celular': (356, 267), 'Tablet': (705, 529), 'Computadora': (534, 726)}},
    'nosotros': {'archivo': 'fotos-nosotros.json', 'lista': 'fotos', 'titulo': 'Nosotros',
                 'sizes': '(max-width: 999px) calc(100vw - 32px), 480px', 'pos': '50% 30%',
                 'alt': 'Paciente de Opto Service',
                 'marcos': {'Celular': (358, 448), 'Tablet': (707, 560), 'Computadora': (477, 540)}},
    'masaya': {'archivo': 'fotos-sucursales.json', 'lista': 'masaya', 'titulo': 'Sucursal Masaya',
               'sizes': '(max-width: 767px) calc(100vw - 34px), 600px', 'pos': '50% 50%',
               'alt': 'Sucursal de Opto Service en Masaya', 'opcional': True,
               'marcos': {'Celular': (356, 223), 'Tablet': (343, 215), 'Computadora': (590, 369)}},
    'diriomo': {'archivo': 'fotos-sucursales.json', 'lista': 'diriomo', 'titulo': 'Sucursal Diriomo',
                'sizes': '(max-width: 767px) calc(100vw - 34px), 600px', 'pos': '50% 50%',
                'alt': 'Sucursal de Opto Service en Diriomo', 'opcional': True,
                'marcos': {'Celular': (356, 223), 'Tablet': (343, 215), 'Computadora': (590, 369)}},
}
# Parte de la foto que siempre debe verse (campo "enfoque" del panel)
ENFOQUE = {
    'arriba-izquierda': '15% 20%', 'arriba': '50% 20%', 'arriba-derecha': '85% 20%',
    'izquierda': '15% 50%', 'centro': '50% 50%', 'derecha': '85% 50%',
    'abajo-izquierda': '15% 80%', 'abajo': '50% 80%', 'abajo-derecha': '85% 80%',
}
AVIF = features.check('avif')
# Servicios que se pueden dejar elegidos al abrir "Agendar cita" (deben coincidir con index.html)
SERVICIOS = ['Examen visual completo', 'Terapia visual', 'Optometría pediátrica', 'Lentes oftálmicos',
             'Lentes de contacto', 'Atención oftalmológica']
# Secciones a las que puede llevar el recuadro de una foto (campo "enlace")
SECCIONES = {'#promociones': 'Promociones', '#servicios': 'Servicios', '#examen': 'Examen visual',
             '#nosotros': 'Nosotros', '#senales': '¿Cuándo revisarte?', '#sucursales': 'Sucursales',
             '#faq': 'Preguntas frecuentes', '#empresas': 'Para empresas', '#contacto': 'Contacto'}
MIN_ANCHO = 1000  # px: con menos, la foto puede verse borrosa en computadora
MIN_VISIBLE = .5  # fracción de la foto que debe verse en cada pantalla antes de avisar
PROMO_SIZES = '(max-width: 599px) calc(100vw - 32px), 300px'
WA_GENERAL = f'https://wa.me/{WHATSAPP}?text=' + urllib.parse.quote('¡Hola Opto Service! Quiero agendar un examen visual. ¿Me ayudan con la cita?', safe='')
WA_CHAT = f'https://wa.me/{WHATSAPP}?text=' + urllib.parse.quote('¡Hola Opto Service! Quisiera hablar con una persona del equipo.', safe='')
CHAT_ICON = ('<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" '
             'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.2A8 8 0 1 1 21 12z"/></svg>')

warnings = []


def warn(msg):
    warnings.append(msg)
    print(f'AVISO: {msg}', file=sys.stderr)


def attr(value):
    return html.escape(str(value), quote=True)


def text(value):
    return str(value).strip() if value is not None else ''


def slug(name):
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-') or 'imagen'


def parse_date(value, where):
    value = text(value)
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        warn(f'fecha no válida "{value}" en {where}; se ignora')
        return None


class Optimizer:
    """Genera versiones livianas de cada imagen y devuelve cómo referenciarlas."""

    def __init__(self, out):
        self.dir = out / 'assets' / 'opt'
        self.dir.mkdir(parents=True, exist_ok=True)
        self.cache = {}

    def __call__(self, ref):
        rel = urllib.parse.unquote(text(ref)).lstrip('/')
        if rel not in self.cache:
            self.cache[rel] = self._process(rel)
        return self.cache[rel]

    def _process(self, rel):
        try:  # solo imágenes dentro de assets/ (sin ../ ni rutas fuera del sitio)
            src = (ROOT / rel).resolve()
            found = bool(rel) and src.is_file() and (ROOT / 'assets') in src.parents
        except (OSError, ValueError):  # nombre demasiado largo o con caracteres no válidos
            found = False
        if not found:
            warn(f'no se encontró la imagen "{rel[:120]}"')
            return None
        try:
            im = ImageOps.exif_transpose(Image.open(src))
            im.load()
        except Exception as e:  # formato no soportado o archivo dañado
            warn(f'no se pudo abrir la imagen "{rel}": {e}')
            return None

        if im.mode in ('I', 'I;16', 'I;16L', 'I;16B'):  # 16 bits por canal: pasar a 8 bits sin recortar
            im = im.point(lambda v: v * (1 / 256)).convert('L')
        alpha = im.mode in ('RGBA', 'LA') or (im.mode == 'P' and 'transparency' in im.info)
        im = im.convert('RGBA' if alpha else 'RGB')
        w, h = im.size
        base = f'{slug(src.stem)}-{hashlib.sha1(src.read_bytes()).hexdigest()[:8]}'

        srcset, avif = [], []
        for tw in sorted({min(t, w) for t in WIDTHS}):
            resized = im.resize((tw, round(h * tw / w)), Image.LANCZOS)
            name = f'{base}-{tw}.webp'
            resized.save(self.dir / name, 'WEBP', quality=78, method=5)
            srcset.append(f'assets/opt/{name} {tw}w')
            if AVIF:  # entre 20 y 30 % más liviano que WebP con la misma calidad
                name = f'{base}-{tw}.avif'
                resized.save(self.dir / name, 'AVIF', quality=50, speed=6)
                avif.append(f'assets/opt/{name} {tw}w')

        fw = min(WIDTHS[-1], w)
        fh = round(h * fw / w)
        fallback = im.resize((fw, fh), Image.LANCZOS)
        if alpha:
            name = f'{base}.png'
            fallback.save(self.dir / name, 'PNG', optimize=True)
        else:
            name = f'{base}.jpg'
            fallback.save(self.dir / name, 'JPEG', quality=80, optimize=True, progressive=True)
        return {'src': f'assets/opt/{name}', 'srcset': ', '.join(srcset), 'avif': ', '.join(avif),
                'width': fw, 'height': fh, 'orig_w': w, 'orig_h': h, 'rel': rel}


def picture(img, sizes, attrs, lazy=False):
    """<picture> con AVIF (si se generó) y WebP; lazy=True deja las direcciones en data-* para cargarlas después."""
    pre = 'data-' if lazy else ''
    source = (f'<source type="image/avif" {pre}srcset="{attr(img["avif"])}" sizes="{sizes}">' if img.get('avif') else '')
    return (f'<picture>{source}<img {pre}src="{attr(img["src"])}" {pre}srcset="{attr(img["srcset"])}" sizes="{sizes}" '
            f'width="{img["width"]}" height="{img["height"]}" {attrs}></picture>')


def replace_block(page, name, lines):
    pattern = re.compile(r'^( *)<!--%s-->\n.*?^ *<!--/%s-->' % (re.escape(name), re.escape(name)), re.S | re.M)
    match = pattern.search(page)
    if not match:
        sys.exit(f'ERROR: falta el marcador <!--{name}--> en index.html')
    ind = match.group(1)
    body = ''.join(f'{ind}{line}\n' for line in lines)
    return page[:match.start()] + f'{ind}<!--{name}-->\n{body}{ind}<!--/{name}-->' + page[match.end():]


def slide_items(slot, items, optimize, today):
    """Fotos de un espacio con todo lo necesario para mostrarlas.

    Devuelve todas las fotos válidas; las que están fuera de sus fechas llevan 'estado' para
    que la vista previa las liste, pero no se muestran en la página.
    """
    cfg = SLOTS[slot]
    out = []
    for n, item in enumerate(items if isinstance(items, list) else [], 1):
        if not isinstance(item, dict) or not text(item.get('imagen')):
            continue
        img = optimize(item['imagen'])
        if not img:
            continue
        where = f'{cfg["titulo"]}, foto {n}'
        enfoque = text(item.get('enfoque'))
        if enfoque and enfoque not in ENFOQUE:
            warn(f'enfoque "{enfoque}" no válido en {where}; se usa el encuadre por defecto')
        desde = parse_date(item.get('desde'), where)
        hasta = parse_date(item.get('hasta'), where)
        estado = ''
        if desde and today < desde:
            estado = f'programada: se muestra desde el {fecha(desde)}'
        elif hasta and today > hasta:
            estado = f'vencida: se dejó de mostrar después del {fecha(hasta)}'
        enlace = text(item.get('enlace'))
        if enlace and not (enlace in SECCIONES or enlace == 'agendar'
                           or (enlace.startswith('agendar:') and enlace[8:] in SERVICIOS)):
            warn(f'enlace "{enlace}" no válido en {where}; el recuadro queda sin enlace')
            enlace = ''
        out.append({
            'n': n, 'img': img, 'estado': estado, 'desde': desde, 'hasta': hasta,
            'alt': text(item.get('descripcion')) or cfg['alt'],
            'sin_descripcion': not text(item.get('descripcion')),
            'pos': ENFOQUE.get(enfoque, cfg['pos']),
            'completa': text(item.get('ajuste')) == 'completa',
            'etiqueta': text(item.get('etiqueta')),
            'texto': text(item.get('texto')),
            'enlace': enlace,
        })
    return out


def fecha(d):
    return f'{d.day} de {MESES[d.month - 1]} de {d.year}'


def enlace_texto(enlace):
    if enlace == 'agendar':
        return 'abre "Agendar cita"'
    if enlace.startswith('agendar:'):
        return f'abre "Agendar cita" con {enlace[8:]} elegido'
    return f'lleva a la sección {SECCIONES.get(enlace, enlace)}'


def badge_html(item):
    if not item['etiqueta'] and not item['texto']:
        return ''
    inner = ''
    if item['etiqueta']:
        inner += f'<div class="eyebrow">{html.escape(item["etiqueta"])}</div>'
    if item['texto']:
        inner += f'<div class="photo-badge-text">{html.escape(item["texto"])}</div>'
    enlace = item['enlace']
    if not enlace:
        return f'<div class="photo-badge">{inner}</div>'
    arrow = '<span class="photo-badge-arrow" aria-hidden="true">→</span>'
    if enlace.startswith('agendar'):
        servicio = enlace[8:]
        data = f' data-servicio="{attr(servicio)}"' if servicio else ''
        return (f'<a class="photo-badge is-link" href="{attr(WA_GENERAL)}" target="_blank" rel="noopener" '
                f'data-agendar{data}>{inner}{arrow}</a>')
    return f'<a class="photo-badge is-link" href="{enlace}">{inner}{arrow}</a>'


def render_slides(slot, items):
    cfg = SLOTS[slot]
    out = []
    for i, item in enumerate(items):
        first = i == 0
        cls = 'slide' + (' is-active' if first else '') + (' is-full' if item['completa'] else '')
        attrs = f'alt="{attr(item["alt"])}" style="object-position:{item["pos"]}"'
        if first:
            attrs += ' fetchpriority="high"' if slot == 'portada' else ' loading="lazy"'
        attrs += ' decoding="async"'
        # solo la primera se carga de entrada; las demás cuando el carrusel llega a ellas
        out.append(f'<div class="{cls}">' + picture(item['img'], cfg['sizes'], attrs, lazy=not first) + badge_html(item) + '</div>')
    return out


def visible_fraction(img, frame):
    """Qué parte de la foto se ve al llenar un marco (object-fit: cover)."""
    iw, ih = img['orig_w'], img['orig_h']
    fw, fh = frame
    scale = max(fw / iw, fh / ih)
    return (fw * fh) / (iw * ih * scale * scale)


def collect_notices(fotos, promos_raw, optimize, today):
    """Avisos para quien administra las fotos: lo que conviene revisar antes de compartir la página."""
    notices = []  # (nivel, dónde, mensaje) — nivel: 'revisar' o 'info'
    for slot, cfg in SLOTS.items():
        for item in fotos.get(slot) or []:
            where = f'{cfg["titulo"]} · foto {item["n"]}'
            img = item['img']
            if item['estado']:
                notices.append(('info', where, f'{item["estado"].capitalize()}.'))
            if img['orig_w'] < MIN_ANCHO:
                notices.append(('revisar', where, f'La foto mide {img["orig_w"]} px de ancho y puede verse borrosa en computadora. '
                                                  f'Lo ideal es subirla de 1200 px o más.'))
            if item['sin_descripcion']:
                notices.append(('revisar', where, 'No tiene descripción. Ayuda a personas con discapacidad visual y a Google.'))
            if not item['completa']:
                cortes = [f'{label} ({round(visible_fraction(img, frame) * 100)} %)'
                          for label, frame in cfg['marcos'].items() if visible_fraction(img, frame) < MIN_VISIBLE]
                if cortes:
                    notices.append(('revisar', where, 'Se recorta mucho; se ve menos de la mitad de la foto en ' + ', '.join(cortes)
                                    + '. Revisa abajo que no se corte lo importante, o usa "Mostrar completa".'))
    for i, p in enumerate(promos_raw if isinstance(promos_raw, list) else [], 1):
        if isinstance(p, dict) and text(p.get('imagen')):
            img = optimize(p['imagen'])
            if img and img['orig_w'] < 800:
                notices.append(('revisar', f'Promoción {i}', f'El flyer mide {img["orig_w"]} px de ancho y puede verse borroso.'))
    # Fotos subidas al panel que no se usan en ninguna sección ni promoción
    used = set()
    for f in (ROOT / 'content').glob('*.json'):
        for m in re.findall(r'assets/uploads/[^"\\]+', f.read_text(encoding='utf-8')):
            used.add(urllib.parse.unquote(m))
    uploads = ROOT / 'assets' / 'uploads'
    for f in sorted(uploads.iterdir()) if uploads.is_dir() else []:
        if f.is_file() and not f.name.startswith('.') and f'assets/uploads/{f.name}' not in used:
            notices.append(('info', 'Fotos subidas', f'"{f.name}" está subida pero no se usa en ninguna sección ni promoción.'))
    for w in warnings:
        notices.append(('revisar', 'Publicación', w[0].upper() + w[1:] + '.'))
    return notices


def promo_states(items, optimize, today):
    """Todas las promociones del panel con su estado, para la vista previa."""
    out = []
    for i, p in enumerate(items if isinstance(items, list) else [], 1):
        if not isinstance(p, dict):
            continue
        vence = parse_date(p.get('vence'), f'la promoción {i}')
        titulo = text(p.get('titulo'))
        img = optimize(p['imagen']) if text(p.get('imagen')) else None
        if p.get('activa') is False:
            estado, nivel = 'Oculta ("Mostrar en la web" desmarcado)', 'off'
        elif not img and not titulo:
            estado, nivel = 'No se muestra: le falta imagen y título', 'off'
        elif vence and vence < today:
            estado, nivel = f'Vencida el {fecha(vence)}', 'off'
        elif vence:
            dias = (vence - today).days
            estado = f'Vigente hasta el {fecha(vence)}' + (' (vence hoy)' if dias == 0 else f' (quedan {dias} días)')
            nivel = 'on'
        else:
            estado, nivel = 'Vigente, sin fecha de fin', 'on'
        out.append({'n': i, 'titulo': titulo, 'precio': text(p.get('precio')), 'desc': text(p.get('descripcion')),
                    'img': img, 'estado': estado, 'nivel': nivel})
    return out


def render_preview(fotos, promos, notices, today):
    """vista-previa.html: avisos, promociones y cada foto recortada en el tamaño real de su espacio."""
    css = (
        "body{margin:0;padding:24px 16px 64px;background:#f2ede8;color:#14213d;font:16px/1.5 'Schibsted Grotesk',system-ui,sans-serif}"
        ".pv-wrap{max-width:1400px;margin:0 auto}h1{font-size:32px;line-height:1.1;letter-spacing:-.03em;margin:0}"
        "h2{margin:48px 0 4px;font-size:24px;letter-spacing:-.02em}.pv-note{color:#3a4254;max-width:760px;margin:12px 0 0}"
        ".pv-toc{display:flex;flex-wrap:wrap;gap:8px 16px;margin-top:16px;font-weight:600}.pv-toc a{color:#0a6e70}"
        ".pv-photo{margin-top:20px;padding:16px;background:#fff;border:1px solid #ddd4c9;border-radius:10px}"
        ".pv-photo.is-off{opacity:.6}"
        ".pv-meta{font-size:14px;color:#565c6b;margin-bottom:12px}.pv-meta b{color:#14213d}"
        ".pv-frames{display:flex;flex-wrap:wrap;gap:20px;align-items:flex-start}"
        ".pv-frame figcaption{font:600 12px/1.2 'Schibsted Grotesk',sans-serif;letter-spacing:.14em;text-transform:uppercase;color:#565c6b;margin-bottom:6px}"
        ".pv-box{position:relative;overflow:hidden;border-radius:10px;background:#e5ddd3;outline:1px dashed #8a8f9c}"
        ".pv-box img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}"
        ".pv-box.is-full img{object-fit:contain;background:#f2ede8}.pv-empty{color:#565c6b;font-style:italic}"
        ".pv-tag{display:inline-block;padding:3px 8px;border-radius:4px;font:600 12px/1.3 'Schibsted Grotesk',sans-serif;letter-spacing:.06em}"
        ".pv-tag.on{background:#06cacb;color:#14213d}.pv-tag.off{background:#ebe5de;color:#565c6b}.pv-tag.warn{background:#fdf1f1;color:#7a1515;border:1px solid #a42323}"
        ".pv-notices{margin-top:16px;padding:0;list-style:none;background:#fff;border:1px solid #ddd4c9;border-radius:10px}"
        ".pv-notices li{display:flex;gap:12px;align-items:flex-start;padding:12px 16px;border-top:1px solid #ddd4c9}.pv-notices li:first-child{border-top:0}"
        ".pv-notices .pv-where{flex:none;width:190px;font-weight:600}.pv-ok{margin-top:16px;padding:14px 16px;background:#fff;border:1px solid #ddd4c9;border-radius:10px}"
        ".pv-promos{display:flex;flex-wrap:wrap;gap:16px;margin-top:16px}.pv-promo{width:260px;background:#fff;border:1px solid #ddd4c9;border-radius:10px;overflow:hidden}"
        ".pv-promo.is-off{opacity:.6}.pv-promo .pv-flyer{aspect-ratio:4/5;background:#f2ede8}.pv-promo .pv-flyer img{display:block;width:100%;height:100%;object-fit:contain}"
        ".pv-promo .pv-body{padding:12px 14px;font-size:14px}.pv-promo h3{margin:6px 0 2px;font-size:17px;line-height:1.25}"
        "@media (max-width:640px){.pv-notices li{flex-direction:column;gap:2px}.pv-notices .pv-where{width:auto}}"
    )
    revisar = sum(1 for n in notices if n[0] == 'revisar')
    out = ['<!DOCTYPE html>', '<html lang="es"><head><meta charset="utf-8">',
           '<meta name="viewport" content="width=device-width, initial-scale=1">',
           '<meta name="robots" content="noindex, nofollow">',
           '<title>Vista previa de fotos — Opto Service</title>',
           '<link rel="icon" href="favicon.ico" sizes="48x48">',
           '<link rel="stylesheet" href="assets/css/styles.css">',
           f'<style>{css}</style></head><body><div class="pv-wrap">',
           '<h1>Vista previa de fotos y promociones</h1>',
           '<p class="pv-note">Revisa aquí lo que subes al panel antes de compartir la página. Cada foto aparece recortada como se ve en '
           'celular, tablet y computadora (a la mitad de su tamaño real). Si una cara o un detalle importante queda cortado, cambia '
           '<b>Parte de la foto que siempre debe verse</b> en el panel, o elige <b>Mostrar completa</b> en <b>Cómo llenar el espacio</b>. '
           f'Generada el {fecha(today)}; se actualiza 1-2 minutos después de cada cambio.</p>',
           '<nav class="pv-toc"><a href="#avisos">Avisos' + (f' ({revisar} por revisar)' if revisar else '') + '</a>'
           '<a href="#promos">Promociones</a>'
           + ''.join(f'<a href="#pv-{slot}">{html.escape(cfg["titulo"])}</a>' for slot, cfg in SLOTS.items()) + '</nav>']

    out.append('<h2 id="avisos">Avisos</h2>')
    if notices:
        out.append('<ul class="pv-notices">')
        for nivel, where, msg in sorted(notices, key=lambda n: n[0] != 'revisar'):
            tag = '<span class="pv-tag warn">Revisar</span>' if nivel == 'revisar' else '<span class="pv-tag off">Info</span>'
            out.append(f'<li>{tag}<span class="pv-where">{html.escape(where)}</span><span>{html.escape(msg)}</span></li>')
        out.append('</ul>')
    else:
        out.append('<p class="pv-ok">Todo en orden: ninguna foto ni promoción necesita revisión.</p>')

    out.append('<h2 id="promos">Promociones</h2>')
    if not promos:
        out.append('<p class="pv-empty">No hay promociones cargadas. La sección y el enlace del menú no se muestran.</p>')
    else:
        out.append('<div class="pv-promos">')
        for p in promos:
            flyer = (f'<div class="pv-flyer"><img src="{attr(p["img"]["src"])}" alt="" loading="lazy"></div>' if p['img']
                     else '<div class="pv-flyer"></div>')
            out.append(f'<div class="pv-promo{" is-off" if p["nivel"] == "off" else ""}">{flyer}<div class="pv-body">'
                       f'<span class="pv-tag {p["nivel"]}">{html.escape(p["estado"])}</span>'
                       f'<h3>{html.escape(p["titulo"] or "(sin título)")}</h3>'
                       + (f'<div><b>{html.escape(p["precio"])}</b></div>' if p['precio'] else '')
                       + (f'<div>{html.escape(p["desc"])}</div>' if p['desc'] else '')
                       + '</div></div>')
        out.append('</div>')

    for slot, cfg in SLOTS.items():
        items = fotos.get(slot) or []
        visibles = [i for i in items if not i['estado']]
        out.append(f'<h2 id="pv-{slot}">{html.escape(cfg["titulo"])}</h2>')
        if not items:
            out.append('<p class="pv-empty">Sin fotos' + (': este espacio no se muestra en la página.' if cfg.get('opcional') else '.') + '</p>')
            continue
        if not visibles:
            out.append('<p class="pv-empty">Ninguna foto está dentro de sus fechas: '
                       + ('este espacio no se muestra en la página.' if cfg.get('opcional') else 'se muestra la foto por defecto.') + '</p>')
        for item in items:
            img = item['img']
            ajuste = 'mostrar completa' if item['completa'] else 'llenar el espacio'
            estado = (f'<span class="pv-tag off">{html.escape(item["estado"].capitalize())}</span> ' if item['estado']
                      else '<span class="pv-tag on">Se muestra</span> ')
            out.append(f'<div class="pv-photo{" is-off" if item["estado"] else ""}">')
            out.append(f'<div class="pv-meta">{estado}<b>Foto {item["n"]}</b> · {html.escape(item["alt"])} · {img["orig_w"]}×{img["orig_h"]} px · '
                       f'encuadre {item["pos"]} · {ajuste} · <code>{html.escape(img["rel"].rsplit("/", 1)[-1])}</code></div>')
            out.append('<div class="pv-frames">')
            for label, (w, h) in cfg['marcos'].items():
                cls = 'pv-box is-full' if item['completa'] else 'pv-box'
                out.append(f'<figure class="pv-frame" style="margin:0"><figcaption>{label} · {w}×{h}</figcaption>'
                           f'<div class="{cls}" style="width:{w // 2}px;height:{h // 2}px">'
                           f'<img src="{attr(img["src"])}" alt="" loading="lazy" style="object-position:{item["pos"]}">'
                           f'</div></figure>')
            out.append('</div>')
            if item['etiqueta'] or item['texto']:
                link = f' · el recuadro {enlace_texto(item["enlace"])}' if item['enlace'] else ''
                out.append(f'<div class="pv-meta" style="margin:12px 0 0">Recuadro sobre la foto: <b>{html.escape(item["etiqueta"])}</b> '
                           f'{html.escape(item["texto"])}{html.escape(link)}</div>')
            out.append('</div>')
    out.append('</div></body></html>')
    return '\n'.join(out) + '\n'


def render_promos(items, optimize, today):
    cards = []
    for i, p in enumerate(items if isinstance(items, list) else [], 1):
        if not isinstance(p, dict) or p.get('activa') is False:
            continue
        vence = parse_date(p.get('vence'), f'la promoción {i}')
        if vence and vence < today:
            continue
        titulo, precio, desc = text(p.get('titulo')), text(p.get('precio')), text(p.get('descripcion'))
        img = optimize(p['imagen']) if text(p.get('imagen')) else None
        if not img and not titulo:
            warn(f'la promoción {i} no tiene imagen ni título; no se muestra')
            continue

        mensaje = text(p.get('mensaje')) or (
            f'¡Hola Opto Service! Me interesa la promoción: {titulo}' if titulo
            else '¡Hola Opto Service! Me interesa una promoción que vi en su página web.')
        wa = f'https://wa.me/{WHATSAPP}?text={urllib.parse.quote(mensaje, safe="")}'

        card = ['<article class="promo-card"' + (f' data-vence="{vence.isoformat()}">' if vence else '>')]
        if img:
            card.append('  <div class="promo-media">' + picture(
                img, PROMO_SIZES, f'alt="{attr(titulo or "Promoción de Opto Service")}" loading="lazy" decoding="async"') + '</div>')
        card.append('  <div class="promo-body">')
        if precio:
            card.append(f'    <div class="promo-price">{html.escape(precio)}</div>')
        if titulo:
            card.append(f'    <h3 class="promo-title">{html.escape(titulo)}</h3>')
        if desc:
            card.append(f'    <p class="promo-text">{html.escape(desc).replace(chr(10), "<br>")}</p>')
        if vence:
            card.append(f'    <div class="promo-date">Válida hasta el {vence.day} de {MESES[vence.month - 1]}</div>')
        label = f' aria-label="Quiero esta promoción: {attr(titulo)}"' if titulo else ''
        card.append(f'    <a class="promo-cta" href="{attr(wa)}" target="_blank" rel="noopener"{label}>Quiero esta promoción</a>')
        card.append('  </div>')
        card.append('</article>')
        cards.extend(card)
    return cards


def render_chat(cfg):
    """Lanzadores y configuración del asistente de chat.

    Devuelve None (y no se agrega nada a la página) si content/chat.json no lo activa
    o si algún dato es dudoso: ante la duda, el chat queda apagado.
    """
    if cfg.get('activo') is not True:
        return None
    api = text(cfg.get('apiUrl')).rstrip('/')
    https_ok = re.fullmatch(r'https://[A-Za-z0-9.-]+(:\d+)?(/[A-Za-z0-9._~/-]*)?', api)
    local_ok = re.fullmatch(r'http://(localhost|127\.0\.0\.1)(:\d+)?(/[A-Za-z0-9._~/-]*)?', api)
    if not (https_ok or local_ok):
        warn('content/chat.json: "apiUrl" debe empezar con https://; el asistente queda apagado')
        return None
    site_key = text(cfg.get('turnstileSiteKey'))
    if site_key and not re.fullmatch(r'[0-9A-Za-z_-]{10,64}', site_key):
        warn('content/chat.json: "turnstileSiteKey" no es válida; el asistente queda apagado')
        return None
    if not site_key and not local_ok:
        warn('content/chat.json: falta "turnstileSiteKey"; el asistente queda apagado')
        return None
    privacy = text(cfg.get('privacidadUrl'))
    if privacy and not re.fullmatch(r'(https://[^\s"<>\']+|/[A-Za-z0-9._~/#-]*)', privacy):
        warn('content/chat.json: "privacidadUrl" no es válida; se omite el enlace')
        privacy = ''
    conf = {'apiUrl': api, 'turnstileSiteKey': site_key, 'whatsappUrl': WA_CHAT}
    if privacy:
        conf['privacyUrl'] = privacy
    timeout = cfg.get('timeoutMs')
    if isinstance(timeout, (int, float)) and not isinstance(timeout, bool) and 1000 <= timeout <= 120000:
        conf['timeoutMs'] = int(timeout)  # solo para pruebas
    wa = attr(WA_CHAT)
    return {
        'chat-launcher': [f'<button type="button" class="chat-launcher" data-chat-open data-chat-fallback="{wa}" '
                          f'aria-haspopup="dialog" aria-label="Abrir el asistente virtual">{CHAT_ICON}<span>Asistente</span></button>'],
        'chat-bar': [f'<button type="button" class="chat-bar-btn" data-chat-open data-chat-fallback="{wa}" '
                     f'aria-haspopup="dialog">{CHAT_ICON}Asistente</button>'],
        'chat-config': ['<script type="application/json" id="chat-config">'
                        + json.dumps(conf, ensure_ascii=False).replace('<', '\\u003c') + '</script>'],
    }


def load_json(name):
    path = ROOT / 'content' / name
    try:
        raw = path.read_text(encoding='utf-8')
    except FileNotFoundError:
        warn(f'no existe content/{name}')
        return {}
    if not raw.strip():  # Pages CMS deja el archivo vacío al borrar el último elemento de la lista
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        sys.exit(f'ERROR: content/{name} no es un JSON válido: {e}')
    if not isinstance(data, dict):
        warn(f'content/{name} no tiene el formato esperado; se ignora')
        return {}
    return data


def version_assets(out, pages):
    """Agrega a cada script y estilo una huella de su contenido (archivo.js?v=a1b2c3d4).

    GitHub Pages deja que el navegador guarde los archivos 10 minutos (los celulares, a
    veces más). Sin huella, un visitante podía ver la página nueva con el script viejo.
    Con huella, cualquier cambio cambia la dirección y se descarga de inmediato.
    El orden importa: main.js contiene la dirección de chat.js, y chat.js la de chat.css.
    """
    def stamp(path):
        return hashlib.sha1(path.read_bytes()).hexdigest()[:8]

    def point(path, reference, target):
        text = path.read_text(encoding='utf-8')
        if reference not in text:
            warn(f'{path.name}: no se encontró {reference}; no se le puso versión')
            return
        path.write_text(text.replace(reference, f'{reference[:-1]}?v={stamp(target)}{reference[-1]}'), encoding='utf-8')

    assets = out / 'assets'
    point(assets / 'js' / 'chat.js', "'/assets/css/chat.css'", assets / 'css' / 'chat.css')
    point(assets / 'js' / 'main.js', "'/assets/js/chat.js'", assets / 'js' / 'chat.js')
    stamps = {'css/styles.css': stamp(assets / 'css' / 'styles.css'), 'js/main.js': stamp(assets / 'js' / 'main.js')}
    result = {}
    for name, page in pages.items():
        for rel, st in stamps.items():
            pattern = r'((?:href|src)="/?assets/%s)"' % re.escape(rel)
            if len(re.findall(pattern, page)) != 1:
                warn(f'{name}: no se encontró assets/{rel}; no se le puso versión')
                continue
            page = re.sub(pattern, r'\1?v=%s"' % st, page)
        build_id = hashlib.sha1((page + stamps['js/main.js']).encode()).hexdigest()[:8]
        result[name] = page.replace('<meta name="theme-color"', f'<meta name="build" content="{build_id}">\n<meta name="theme-color"', 1)
    return result


# ===== Sucursales, equipo y páginas =====

def hora(value, where):
    """'08:30' -> (datetime.time, '8:30am'); None si no es una hora válida."""
    m = re.fullmatch(r'([01]?\d|2[0-3]):([0-5]\d)', text(value))
    if not m:
        warn(f'hora no válida "{text(value)}" en {where}')
        return None
    h, mi = int(m.group(1)), m.group(2)
    return f'{h:02d}:{mi}', f'{(h - 1) % 12 + 1}:{mi}{"am" if h < 12 else "pm"}'


def load_sucursales():
    """Datos de cada sucursal (content/sucursales.json), validados. Sin datos válidos, la compilación se detiene."""
    data = load_json('sucursales.json')
    out = {}
    for sid, nombre in SUCURSALES.items():
        raw = data.get(sid) if isinstance(data.get(sid), dict) else {}
        where = f'content/sucursales.json ({nombre})'
        s = {'id': sid, 'nombre': nombre, 'url': f'{DOMINIO}/#{sid}'}
        for campo in ('direccion', 'localidad', 'departamento', 'mapa'):
            s[campo] = text(raw.get(campo))
            if not s[campo]:
                sys.exit(f'ERROR: falta "{campo}" en {where}')
        s['como_llegar'] = text(raw.get('como_llegar'))
        s['horario'] = []
        for campo, dias, etiqueta in (('lunes_viernes', ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'], 'Lunes a Viernes'),
                                      ('sabado', ['Saturday'], 'Sábado')):
            rango = raw.get(campo) if isinstance(raw.get(campo), dict) else {}
            abre, cierra = hora(rango.get('abre'), f'{where}, {etiqueta}'), hora(rango.get('cierra'), f'{where}, {etiqueta}')
            if not abre or not cierra:
                sys.exit(f'ERROR: horario de {etiqueta} incompleto en {where}')
            s['horario'].append({'etiqueta': etiqueta, 'dias': dias, 'abre': abre, 'cierra': cierra})
        s['geo'] = None
        lat, lon = text(raw.get('latitud')), text(raw.get('longitud'))
        if lat or lon:
            try:
                la, lo = float(lat), float(lon)
                if not (10 <= la <= 15.5 and -88 <= lo <= -82.5):  # Nicaragua
                    raise ValueError
                s['geo'] = (la, lo)
            except ValueError:
                warn(f'coordenadas no válidas en {where}; se omiten')
        s['resenas'] = text(raw.get('resenas'))
        if s['resenas'] and not re.fullmatch(r'https://[^\s"<>\']+', s['resenas']):
            warn(f'enlace de reseñas no válido en {where}; se omite')
            s['resenas'] = ''
        s['lugar'] = f'{s["localidad"]}, {s["departamento"]}' if s['localidad'] != s['departamento'] else s['localidad']
        s['mapa_src'] = 'https://maps.google.com/maps?q=' + urllib.parse.quote(s['mapa'], safe='') + '&z=15&output=embed'
        s['direcciones'] = 'https://www.google.com/maps/dir/?api=1&destination=' + urllib.parse.quote(s['mapa'], safe='')
        out[sid] = s
    return out


def horario_dl(s):
    lines = [f'<dt>{h["etiqueta"]}</dt><dd>{h["abre"][1]} – {h["cierra"][1]}</dd>' for h in s['horario']]
    return lines + ['<dt>Domingo</dt><dd>Previa cita</dd>']


def horario_texto(s):
    partes = [f'{h["etiqueta"].lower() if i else h["etiqueta"]}, de {h["abre"][1]} a {h["cierra"][1]}'
              for i, h in enumerate(s['horario'])]
    return '; '.join(partes) + '. Los domingos atendemos previa cita.'


def optician(s):
    """Datos para Google de una sucursal. El @id y la url son el ancla de su tarjeta en el inicio."""
    node = {
        '@type': 'Optician',
        '@id': s['url'],
        'name': f'Opto Service — {s["nombre"]}',
        'url': s['url'],
        'parentOrganization': {'@id': f'{DOMINIO}/#organizacion'},
        'telephone': TELEFONO,
        'address': {'@type': 'PostalAddress', 'streetAddress': f'{s["direccion"]}.', 'addressLocality': s['localidad'],
                    'addressRegion': s['departamento'], 'addressCountry': 'NI'},
        'openingHoursSpecification': [
            {'@type': 'OpeningHoursSpecification', 'dayOfWeek': h['dias'] if len(h['dias']) > 1 else h['dias'][0],
             'opens': h['abre'][0], 'closes': h['cierra'][0]} for h in s['horario']],
        'description': 'Los domingos atendemos previa cita.',
    }
    if s['geo']:
        node['geo'] = {'@type': 'GeoCoordinates', 'latitude': s['geo'][0], 'longitude': s['geo'][1]}
    return node


def jsonld(nodes):
    organization = {
        '@type': 'Organization', '@id': f'{DOMINIO}/#organizacion', 'name': 'Opto Service', 'url': f'{DOMINIO}/',
        'logo': f'{DOMINIO}/assets/img/logo-opto-service.png', 'telephone': TELEFONO, 'sameAs': REDES,
    }
    graph = {'@context': 'https://schema.org', '@graph': [organization] + nodes}
    return json.dumps(graph, ensure_ascii=False, indent=2).replace('<', '\\u003c')


def render_branch_card(s):
    """Mapa y datos de la tarjeta de una sucursal en el inicio."""
    return ([f'<iframe class="branch-map" src="{attr(s["mapa_src"])}" loading="lazy" referrerpolicy="no-referrer-when-downgrade" '
             f'title="Mapa de la sucursal de {s["nombre"]}"></iframe>',
             '<div class="branch-body">',
             f'  <div class="branch-head"><h3>{s["nombre"]}</h3><span class="eyebrow is-teal">Óptica y optometría médica</span></div>',
             f'  <p class="branch-addr">{html.escape(s["direccion"])}.</p>']
            + ([f'  <p class="branch-ref">{html.escape(s["como_llegar"])}</p>'] if s['como_llegar'] else [])
            + ['  <dl class="hours">']
            + [f'    {line}' for line in horario_dl(s)]
            + ['  </dl>',
               '  <div class="branch-actions">',
               f'    <a class="btn btn-outline btn-sm" href="{attr(s["direcciones"])}" target="_blank" rel="noopener" data-direcciones="{s["id"]}">'
               f'Cómo llegar<span class="sr-only"> a la sucursal de {s["nombre"]}</span></a>']
            + ([f'    <a class="btn btn-outline btn-sm" href="{attr(s["resenas"])}" target="_blank" rel="noopener" data-resena="{s["id"]}">'
                f'Déjanos tu reseña en Google<span class="sr-only"> sobre la sucursal de {s["nombre"]}</span></a>'] if s['resenas'] else [])
            + ['  </div>',
               '</div>'])


def render_footer_branches(sucs):
    return [f'<p><strong><a href="#{s["id"]}">{s["nombre"]}</a></strong><br>{html.escape(s["direccion"])}.</p>' for s in sucs.values()]


def render_team(items, optimize):
    """Tarjetas del equipo (content/equipo.json). Sin personas con nombre, no se muestra nada."""
    cards = []
    for i, p in enumerate(items if isinstance(items, list) else [], 1):
        if not isinstance(p, dict) or p.get('activo') is False:
            continue
        nombre, titulo, especialidad = text(p.get('nombre')), text(p.get('titulo')), text(p.get('especialidad'))
        if not nombre:
            warn(f'la persona {i} del equipo no tiene nombre; no se muestra')
            continue
        img = optimize(p['foto']) if text(p.get('foto')) else None
        card = ['  <article class="member">']
        if img:
            card.append('    <div class="member-photo">' + picture(
                img, '(max-width: 599px) 40vw, 160px',
                f'alt="{attr(nombre)}" loading="lazy" decoding="async" style="object-position:50% 25%"') + '</div>')
        card.append(f'    <h3>{html.escape(nombre)}</h3>')
        if titulo:
            card.append(f'    <p class="member-title">{html.escape(titulo)}</p>')
        if especialidad:
            card.append(f'    <p>{html.escape(especialidad)}</p>')
        card.append('  </article>')
        cards.extend(card)
    if not cards:
        return []
    return ['<div class="team-head eyebrow">Nuestro equipo</div>', '<div class="team">'] + cards + ['</div>']


def extract_block(page, name):
    match = re.search(r'<!--%s-->\n(.*?)^ *<!--/%s-->' % (re.escape(name), re.escape(name)), page, re.S | re.M)
    if not match:
        sys.exit(f'ERROR: falta el marcador <!--{name}--> en index.html')
    return match.group(1)


def absolutize(fragment):
    """Enlaces de index.html para usarlos en otra página: #seccion -> /#seccion y assets/... -> /assets/..."""
    fragment = fragment.replace('href="#top"', 'href="/"')
    fragment = re.sub(r'href="#([A-Za-z][\w-]*)"', r'href="/#\1"', fragment)
    return re.sub(r'\b(href|src)="(?![a-z][a-z0-9+.-]*:|/|#)', r'\1="/', fragment)


def fill_common(page, comunes, name):
    for block, content in comunes.items():
        pattern = re.compile(r'^( *)<!--%s-->\n *<!--/%s-->\n' % (block, block), re.M)
        if not pattern.search(page):
            sys.exit(f'ERROR: falta el marcador <!--{block}--> vacío en paginas/{name}')
        page = pattern.sub(lambda m: content, page, count=1)
    return page


def mark_draft(page):
    """Páginas en borrador: noindex y aviso visible. Devuelve (página, motivo o None)."""
    match = re.search(r'<meta name="borrador" content="([^"]*)">\n?', page)
    if not match:
        return page, None
    motivo = match.group(1) or 'Borrador'
    page = page.replace(match.group(0), '<meta name="robots" content="noindex, nofollow">\n', 1)
    page = page.replace('<main>', '<main>\n  <div class="draft-banner" role="note"><strong>Borrador:</strong> '
                        f'{html.escape(motivo)}. Esta página no aparece en Google ni está enlazada; no la compartas todavía.</div>', 1)
    return page, motivo


def drop_links(page, drafts):
    """Quita los enlaces hacia páginas en borrador: el <a> o <span> que lleva data-requiere="<página>"."""
    for name in drafts:
        page = re.sub(r'<(a|span) [^>]*data-requiere="%s"[^>]*>.*?</\1>' % re.escape(name), '', page, flags=re.S)
    return page


def write_sitemap(out, pages):
    """sitemap.xml con la URL canónica de cada página publicable (sin noindex).

    Los anclajes (#masaya) no son páginas distintas. La vista previa y los borradores quedan
    fuera y conservan su meta noindex (no bloquearlos en robots.txt: el buscador necesita leer
    esa directiva).
    """
    urls = []
    for name, page in pages.items():
        if re.search(r'<meta name="robots" content="[^"]*noindex', page):
            continue
        canonical = re.search(r'<link rel="canonical" href="([^"]+)">', page)
        if not canonical:
            raise ValueError(f'{name} debe declarar su URL canónica para el sitemap')
        urls.append(html.unescape(canonical.group(1)))
    namespace = 'http://www.sitemaps.org/schemas/sitemap/0.9'
    ET.register_namespace('', namespace)
    sitemap = ET.Element(f'{{{namespace}}}urlset')
    for loc in urls:
        ET.SubElement(ET.SubElement(sitemap, f'{{{namespace}}}url'), f'{{{namespace}}}loc').text = loc
    ET.ElementTree(sitemap).write(out / 'sitemap.xml', encoding='utf-8', xml_declaration=True)


def apply_slot(page, slot, slides):
    """Pone las fotos de un espacio (y su velocidad) en una página que tiene su marcador."""
    visibles, interval, cfg = slides[slot]
    page = re.sub(r'(data-carousel="%s" data-interval=")\d+"' % slot, r'\g<1>%d"' % interval, page)
    if visibles:
        page = replace_block(page, f'fotos:{slot}', render_slides(slot, visibles))
        page = re.sub(r'(data-carousel="%s"[^>]*?) hidden>' % slot, r'\1>', page)
    elif cfg.get('opcional'):
        page = replace_block(page, f'fotos:{slot}', [])
    return page


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--out', default='_site', help='carpeta de salida (por defecto _site)')
    parser.add_argument('--hoy', help='fecha AAAA-MM-DD para probar el vencimiento de promociones')
    args = parser.parse_args()
    out = (ROOT / args.out).resolve()
    today = date.fromisoformat(args.hoy) if args.hoy else datetime.now(NICARAGUA).date()

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for item in ROOT.iterdir():
        if item.name in EXCLUDE or item.resolve() == out:
            continue
        if item.is_dir():
            shutil.copytree(item, out / item.name)
        else:
            shutil.copy2(item, out / item.name)

    optimize = Optimizer(out)
    page = (ROOT / 'index.html').read_text(encoding='utf-8')

    # Fotos de cada espacio
    fotos, slides = {}, {}
    for slot, cfg in SLOTS.items():
        data = load_json(cfg['archivo'])
        items = slide_items(slot, data.get(cfg['lista']), optimize, today)
        fotos[slot] = items
        visibles = [i for i in items if not i['estado']]  # dentro de sus fechas
        segundos = data.get('segundos')
        if isinstance(segundos, bool) or not isinstance(segundos, (int, float)) or not math.isfinite(segundos):
            segundos = 5
        slides[slot] = (visibles, int(min(max(segundos, 3), 20) * 1000), cfg)
        if not visibles and not cfg.get('opcional'):
            warn(f'"{cfg["titulo"]}" no tiene fotos para hoy; se deja la foto por defecto')
        page = apply_slot(page, slot, slides)

    # Promociones
    promos_raw = load_json('promociones.json').get('promociones')
    cards = render_promos(promos_raw, optimize, today)
    page = replace_block(page, 'promociones', cards)
    if cards:
        page = page.replace('data-promos hidden', 'data-promos').replace(' data-promo-link hidden', ' data-promo-link')

    # Asistente de chat
    chat = render_chat(load_json('chat.json'))
    if chat:
        for name, lines in chat.items():
            page = replace_block(page, name, lines)

    # Sucursales, equipo y datos estructurados
    sucs = load_sucursales()
    for sid, suc in sucs.items():
        page = replace_block(page, f'sucursal:{sid}', render_branch_card(suc))
    page = replace_block(page, 'pie:sucursales', render_footer_branches(sucs))
    page = replace_block(page, 'equipo', render_team(load_json('equipo.json').get('equipo'), optimize))
    page = replace_block(page, 'datos-estructurados', ['<script type="application/ld+json">',
                                                       jsonld([optician(s) for s in sucs.values()]), '</script>'])

    # Demás páginas: comparten encabezado, pie y recursos con el inicio
    comunes = {name: absolutize(extract_block(page, name)) for name in ('comun:recursos', 'comun:cabecera', 'comun:pie')}
    pages, drafts = {'index.html': page}, []
    for src in sorted((ROOT / 'paginas').glob('*.html')):
        other, motivo = mark_draft(src.read_text(encoding='utf-8'))
        if motivo:
            drafts.append(src.stem)
            warn(f'{src.name} está en borrador ({motivo}): se publica con noindex y sin enlaces')
        pages[src.name] = fill_common(other, comunes, src.name)
    pages = {name: drop_links(p, drafts) for name, p in pages.items()}

    notices = collect_notices(fotos, promos_raw, optimize, today)
    (out / 'vista-previa.html').write_text(
        render_preview(fotos, promo_states(promos_raw, optimize, today), notices, today), encoding='utf-8')

    write_sitemap(out, pages)

    for name, p in version_assets(out, pages).items():
        (out / name).write_text(p, encoding='utf-8')
    print(f'Sitio generado en {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}: '
          f'{len(pages)} páginas ({len(drafts)} en borrador), '
          f'{len(optimize.cache)} imágenes optimizadas, {sum(1 for c in cards if c.startswith("<article"))} promociones vigentes'
          + (', asistente de chat ACTIVO' if chat else '')
          + (f', {len(warnings)} avisos' if warnings else ''))

if __name__ == '__main__':
    main()
