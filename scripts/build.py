#!/usr/bin/env python3
"""Genera el sitio publicable en _site/.

1. Copia los archivos del sitio.
2. Inserta en index.html las fotos de content/fotos-*.json y las promociones de
   content/promociones.json (todo se edita desde Pages CMS).
3. Optimiza cada imagen usada: versiones WebP de 480, 800 y 1200 px de ancho y
   un JPEG (o PNG) de respaldo, para que las fotos del celular no pesen.
4. Genera vista-previa.html: cada foto recortada como se verá en celular,
   tablet y computadora (no se enlaza desde la página ni la indexa Google).

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
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageOps

try:  # fotos HEIC de iPhone
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent.parent
EXCLUDE = {'.git', '.github', '.gitignore', '.pages.yml', 'scripts', 'content', 'docs', '_site', 'README.md', 'MEJORAS.md'}
WIDTHS = (480, 800, 1200)
WHATSAPP = '50584024868'
NICARAGUA = timezone(timedelta(hours=-6))
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

        srcset = []
        for tw in sorted({min(t, w) for t in WIDTHS}):
            name = f'{base}-{tw}.webp'
            im.resize((tw, round(h * tw / w)), Image.LANCZOS).save(self.dir / name, 'WEBP', quality=78, method=5)
            srcset.append(f'assets/opt/{name} {tw}w')

        fw = min(WIDTHS[-1], w)
        fh = round(h * fw / w)
        fallback = im.resize((fw, fh), Image.LANCZOS)
        if alpha:
            name = f'{base}.png'
            fallback.save(self.dir / name, 'PNG', optimize=True)
        else:
            name = f'{base}.jpg'
            fallback.save(self.dir / name, 'JPEG', quality=80, optimize=True, progressive=True)
        return {'src': f'assets/opt/{name}', 'srcset': ', '.join(srcset), 'width': fw, 'height': fh}


def replace_block(page, name, lines):
    pattern = re.compile(r'^( *)<!--%s-->\n.*?^ *<!--/%s-->' % (re.escape(name), re.escape(name)), re.S | re.M)
    match = pattern.search(page)
    if not match:
        sys.exit(f'ERROR: falta el marcador <!--{name}--> en index.html')
    ind = match.group(1)
    body = ''.join(f'{ind}{line}\n' for line in lines)
    return page[:match.start()] + f'{ind}<!--{name}-->\n{body}{ind}<!--/{name}-->' + page[match.end():]


def slide_items(slot, items, optimize):
    """Fotos válidas de un espacio, con todo lo necesario para mostrarlas."""
    cfg = SLOTS[slot]
    out = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict) or not text(item.get('imagen')):
            continue
        img = optimize(item['imagen'])
        if not img:
            continue
        enfoque = text(item.get('enfoque'))
        if enfoque and enfoque not in ENFOQUE:
            warn(f'enfoque "{enfoque}" no válido en {cfg["titulo"]}; se usa el encuadre por defecto')
        out.append({
            'img': img,
            'alt': text(item.get('descripcion')) or cfg['alt'],
            'pos': ENFOQUE.get(enfoque, cfg['pos']),
            'completa': text(item.get('ajuste')) == 'completa',
            'etiqueta': text(item.get('etiqueta')),
            'texto': text(item.get('texto')),
        })
    return out


def badge_html(item):
    if not item['etiqueta'] and not item['texto']:
        return ''
    parts = ['<div class="photo-badge">']
    if item['etiqueta']:
        parts.append(f'<div class="eyebrow">{html.escape(item["etiqueta"])}</div>')
    if item['texto']:
        parts.append(f'<div class="photo-badge-text">{html.escape(item["texto"])}</div>')
    parts.append('</div>')
    return ''.join(parts)


def render_slides(slot, items):
    cfg = SLOTS[slot]
    out = []
    for i, item in enumerate(items):
        first = i == 0
        img = item['img']
        cls = 'slide' + (' is-active' if first else '') + (' is-full' if item['completa'] else '')
        parts = ['<img']
        if first:
            parts.append(f'src="{attr(img["src"])}" srcset="{attr(img["srcset"])}"')
        else:  # se cargan cuando el carrusel llega a ellas
            parts.append(f'data-src="{attr(img["src"])}" data-srcset="{attr(img["srcset"])}"')
        parts.append(f'sizes="{cfg["sizes"]}" width="{img["width"]}" height="{img["height"]}"')
        parts.append(f'alt="{attr(item["alt"])}" style="object-position:{item["pos"]}"')
        if first:
            parts.append('fetchpriority="high"' if slot == 'portada' else 'loading="lazy"')
        parts.append('decoding="async">')
        out.append(f'<div class="{cls}">' + ' '.join(parts) + badge_html(item) + '</div>')
    return out


def render_preview(fotos, today):
    """vista-previa.html: cada foto recortada en el tamaño real de su espacio."""
    css = (
        "body{margin:0;padding:24px 16px 64px;background:#f2ede8;color:#14213d;font:16px/1.5 'Schibsted Grotesk',system-ui,sans-serif}"
        ".pv-wrap{max-width:1400px;margin:0 auto}h1{font-size:32px;line-height:1.1;letter-spacing:-.03em;margin:0}"
        "h2{margin:48px 0 4px;font-size:24px;letter-spacing:-.02em}.pv-note{color:#3a4254;max-width:760px;margin:12px 0 0}"
        ".pv-photo{margin-top:20px;padding:16px;background:#fff;border:1px solid #ddd4c9;border-radius:10px}"
        ".pv-meta{font-size:14px;color:#565c6b;margin-bottom:12px}.pv-meta b{color:#14213d}"
        ".pv-frames{display:flex;flex-wrap:wrap;gap:20px;align-items:flex-start}"
        ".pv-frame figcaption{font:600 12px/1.2 'Schibsted Grotesk',sans-serif;letter-spacing:.14em;text-transform:uppercase;color:#565c6b;margin-bottom:6px}"
        ".pv-box{position:relative;overflow:hidden;border-radius:10px;background:#e5ddd3;outline:1px dashed #8a8f9c}"
        ".pv-box img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}"
        ".pv-box.is-full img{object-fit:contain;background:#f2ede8}.pv-empty{color:#565c6b;font-style:italic}"
    )
    out = ['<!DOCTYPE html>', '<html lang="es"><head><meta charset="utf-8">',
           '<meta name="viewport" content="width=device-width, initial-scale=1">',
           '<meta name="robots" content="noindex, nofollow">',
           '<title>Vista previa de fotos — Opto Service</title>',
           '<link rel="stylesheet" href="assets/css/styles.css">',
           f'<style>{css}</style></head><body><div class="pv-wrap">',
           '<h1>Vista previa de fotos</h1>',
           '<p class="pv-note">Así se recorta cada foto en celular, tablet y computadora (a la mitad de su tamaño real). '
           'Si una cara o un detalle importante queda cortado, cambia el campo <b>Parte de la foto que siempre debe verse</b> '
           'en el panel, o elige <b>Mostrar completa</b> en <b>Cómo llenar el espacio</b>. '
           f'Generada el {today.day} de {MESES[today.month - 1]} de {today.year}.</p>']
    for slot, cfg in SLOTS.items():
        items = fotos.get(slot) or []
        out.append(f'<h2>{html.escape(cfg["titulo"])}</h2>')
        if not items:
            out.append('<p class="pv-empty">Sin fotos' + (': este espacio no se muestra en la página.' if cfg.get('opcional') else '.') + '</p>')
            continue
        for n, item in enumerate(items, 1):
            img = item['img']
            name = img['src'].rsplit('/', 1)[-1]
            ajuste = 'mostrar completa' if item['completa'] else 'llenar el espacio'
            out.append('<div class="pv-photo">')
            out.append(f'<div class="pv-meta"><b>Foto {n}</b> · {html.escape(item["alt"])} · encuadre {item["pos"]} · {ajuste} · <code>{html.escape(name)}</code></div>')
            out.append('<div class="pv-frames">')
            for label, (w, h) in cfg['marcos'].items():
                cls = 'pv-box is-full' if item['completa'] else 'pv-box'
                out.append(f'<figure class="pv-frame" style="margin:0"><figcaption>{label} · {w}×{h}</figcaption>'
                           f'<div class="{cls}" style="width:{w // 2}px;height:{h // 2}px">'
                           f'<img src="{attr(img["src"])}" alt="" loading="lazy" style="object-position:{item["pos"]}">'
                           f'</div></figure>')
            out.append('</div>')
            if item['etiqueta'] or item['texto']:
                out.append(f'<div class="pv-meta" style="margin:12px 0 0">Recuadro sobre la foto: <b>{html.escape(item["etiqueta"])}</b> {html.escape(item["texto"])}</div>')
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
            card.append(
                f'  <div class="promo-media"><img src="{attr(img["src"])}" srcset="{attr(img["srcset"])}" '
                f'sizes="{PROMO_SIZES}" width="{img["width"]}" height="{img["height"]}" '
                f'alt="{attr(titulo or "Promoción de Opto Service")}" loading="lazy" decoding="async"></div>')
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


def version_assets(out, page):
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
    point(assets / 'js' / 'chat.js', "'assets/css/chat.css'", assets / 'css' / 'chat.css')
    point(assets / 'js' / 'main.js', "'assets/js/chat.js'", assets / 'js' / 'chat.js')
    for reference, target in (('href="assets/css/styles.css"', assets / 'css' / 'styles.css'),
                              ('src="assets/js/main.js"', assets / 'js' / 'main.js')):
        if page.count(reference) != 1:
            warn(f'index.html: no se encontró {reference}; no se le puso versión')
            continue
        page = page.replace(reference, f'{reference[:-1]}?v={stamp(target)}"')
    build_id = hashlib.sha1((page + stamp(assets / 'js' / 'main.js')).encode()).hexdigest()[:8]
    return page.replace('<meta name="theme-color"', f'<meta name="build" content="{build_id}">\n<meta name="theme-color"', 1)


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

    fotos = {}
    for slot, cfg in SLOTS.items():
        data = load_json(cfg['archivo'])
        items = slide_items(slot, data.get(cfg['lista']), optimize)
        fotos[slot] = items
        segundos = data.get('segundos')
        if isinstance(segundos, bool) or not isinstance(segundos, (int, float)) or not math.isfinite(segundos):
            segundos = 5
        interval = int(min(max(segundos, 3), 20) * 1000)
        page = re.sub(r'(data-carousel="%s" data-interval=")\d+"' % slot, r'\g<1>%d"' % interval, page)
        if items:
            page = replace_block(page, f'fotos:{slot}', render_slides(slot, items))
            page = re.sub(r'(data-carousel="%s"[^>]*?) hidden>' % slot, r'\1>', page)
        elif cfg.get('opcional'):
            page = replace_block(page, f'fotos:{slot}', [])
        else:
            warn(f'"{cfg["titulo"]}" no tiene fotos válidas; se deja la foto por defecto')
    (out / 'vista-previa.html').write_text(render_preview(fotos, today), encoding='utf-8')

    cards = render_promos(load_json('promociones.json').get('promociones'), optimize, today)
    page = replace_block(page, 'promociones', cards)
    if cards:
        page = page.replace('data-promos hidden', 'data-promos').replace(' data-promo-link hidden', ' data-promo-link')

    chat = render_chat(load_json('chat.json'))
    if chat:
        for name, lines in chat.items():
            page = replace_block(page, name, lines)

    page = version_assets(out, page)
    (out / 'index.html').write_text(page, encoding='utf-8')
    print(f'Sitio generado en {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}: '
          f'{len(optimize.cache)} imágenes optimizadas, {sum(1 for c in cards if c.startswith("<article"))} promociones vigentes'
          + (', asistente de chat ACTIVO' if chat else '')
          + (f', {len(warnings)} avisos' if warnings else ''))


if __name__ == '__main__':
    main()
