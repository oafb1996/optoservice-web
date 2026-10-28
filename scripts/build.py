#!/usr/bin/env python3
"""Genera el sitio publicable en _site/.

1. Copia los archivos del sitio.
2. Inserta en index.html las fotos de content/fotos.json y las promociones de
   content/promociones.json (ambos se editan desde Pages CMS).
3. Optimiza cada imagen usada: versiones WebP de 480, 800 y 1200 px de ancho y
   un JPEG (o PNG) de respaldo, para que las fotos del celular no pesen.

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

# Espacios de foto: ancho mostrado (atributo sizes), encuadre y texto alternativo por defecto
SLOTS = {
    'portada': {'sizes': '(max-width: 879px) calc(100vw - 36px), 470px', 'pos': '50% 28%',
                'alt': 'Paciente con lentes en Opto Service'},
    'servicios': {'sizes': '(max-width: 879px) calc(100vw - 44px), 380px', 'pos': '50% 45%',
                  'alt': 'Lentes disponibles en Opto Service'},
    'examen': {'sizes': '(max-width: 879px) calc(100vw - 44px), 440px', 'pos': '50% 32%',
               'alt': 'Paciente de Opto Service con sus lentes'},
    'nosotros': {'sizes': '(max-width: 879px) calc(100vw - 44px), 460px', 'pos': '50% 30%',
                 'alt': 'Paciente de Opto Service'},
}
ENFOQUE = {'arriba': '50% 22%', 'centro': '50% 50%', 'abajo': '50% 80%'}
PROMO_SIZES = '(max-width: 879px) 82vw, 360px'
WA_GENERAL = f'https://wa.me/{WHATSAPP}?text=' + urllib.parse.quote('¡Hola Opto Service! Quiero agendar un examen visual. ¿Me ayudan con la cita?', safe='')
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


def render_slides(slot, items, optimize):
    cfg = SLOTS[slot]
    out = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict) or not text(item.get('imagen')):
            continue
        img = optimize(item['imagen'])
        if not img:
            continue
        first = not out
        alt = text(item.get('descripcion')) or cfg['alt']
        pos = ENFOQUE.get(text(item.get('enfoque')), cfg['pos'])
        parts = ['<img class="slide is-active"' if first else '<img class="slide"']
        if first:
            parts.append(f'src="{attr(img["src"])}" srcset="{attr(img["srcset"])}"')
        else:  # se cargan cuando el carrusel llega a ellas
            parts.append(f'data-src="{attr(img["src"])}" data-srcset="{attr(img["srcset"])}"')
        parts.append(f'sizes="{cfg["sizes"]}" width="{img["width"]}" height="{img["height"]}"')
        parts.append(f'alt="{attr(alt)}" style="object-position:{pos}"')
        if first:
            parts.append('fetchpriority="high"' if slot == 'portada' else 'loading="lazy"')
        parts.append('decoding="async">')
        out.append(' '.join(parts))
    return out


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
        card.append(f'    <a class="promo-cta" href="{attr(wa)}" target="_blank" rel="noopener"{label}>Quiero esta promoción →</a>')
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
    conf = {'apiUrl': api, 'turnstileSiteKey': site_key, 'whatsappUrl': WA_GENERAL}
    if privacy:
        conf['privacyUrl'] = privacy
    timeout = cfg.get('timeoutMs')
    if isinstance(timeout, (int, float)) and not isinstance(timeout, bool) and 1000 <= timeout <= 120000:
        conf['timeoutMs'] = int(timeout)  # solo para pruebas
    wa = attr(WA_GENERAL)
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

    fotos = load_json('fotos.json')
    segundos = fotos.get('segundos')
    if isinstance(segundos, bool) or not isinstance(segundos, (int, float)) or not math.isfinite(segundos):
        segundos = 5
    interval = int(min(max(segundos, 3), 20) * 1000)
    page = re.sub(r'data-interval="\d+"', f'data-interval="{interval}"', page)
    for slot in SLOTS:
        slides = render_slides(slot, fotos.get(slot), optimize)
        if slides:
            page = replace_block(page, f'fotos:{slot}', slides)
        else:
            warn(f'"{slot}" no tiene fotos válidas; se deja la foto por defecto')

    cards = render_promos(load_json('promociones.json').get('promociones'), optimize, today)
    page = replace_block(page, 'promociones', cards)
    if cards:
        page = page.replace('data-promos hidden', 'data-promos').replace(' data-promo-link hidden', ' data-promo-link')

    chat = render_chat(load_json('chat.json'))
    if chat:
        for name, lines in chat.items():
            page = replace_block(page, name, lines)

    (out / 'index.html').write_text(page, encoding='utf-8')
    print(f'Sitio generado en {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}: '
          f'{len(optimize.cache)} imágenes optimizadas, {sum(1 for c in cards if c.startswith("<article"))} promociones vigentes'
          + (', asistente de chat ACTIVO' if chat else '')
          + (f', {len(warnings)} avisos' if warnings else ''))


if __name__ == '__main__':
    main()
