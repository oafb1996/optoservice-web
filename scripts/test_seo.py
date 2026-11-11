"""Comprueba el sitio generado: python -m unittest discover -s scripts -p 'test_*.py'."""
import json
import re
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit


ROOT = Path(__file__).resolve().parent.parent


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.tags = []
        self.structured = []
        self.script = None
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.append((tag, attrs))
        if tag == 'script' and attrs.get('type') == 'application/ld+json':
            self.script = ''

    def handle_data(self, data):
        if self.script is not None:
            self.script += data

    def handle_endtag(self, tag):
        if tag == 'script' and self.script is not None:
            self.structured.append(json.loads(self.script))
            self.script = None


class PublishedSEO(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.site = Path(cls.temp.name) / 'site'
        subprocess.run([sys.executable, str(ROOT / 'scripts/build.py'), '--out', str(cls.site)],
                       cwd=ROOT, check=True)
        cls.text = (cls.site / 'index.html').read_text()
        cls.page = Page(cls.text)

    def test_sitemap_lists_only_canonical_page(self):
        canonical = [a['href'] for tag, a in self.page.tags
                     if tag == 'link' and a.get('rel') == 'canonical']
        self.assertEqual(canonical, ['https://optoservicenic.com/'])
        sitemap = ET.parse(self.site / 'sitemap.xml')
        urls = [node.text for node in sitemap.findall('.//{*}loc')]
        # El inicio y cada página publicada (sin noindex); nunca borradores, 404 ni vista previa
        expected = []
        for path in sorted(self.site.glob('*.html'), key=lambda f: f.name != 'index.html'):
            page = Page(path.read_text())
            if any('noindex' in a.get('content', '') for tag, a in page.tags if tag == 'meta'):
                continue
            expected += [a['href'] for tag, a in page.tags if tag == 'link' and a.get('rel') == 'canonical']
        self.assertEqual(urls[0], canonical[0])
        self.assertEqual(urls, expected)
        robots = (self.site / 'robots.txt').read_text()
        self.assertIn('Sitemap: https://optoservicenic.com/sitemap.xml', robots)
        self.assertNotIn('Disallow:', robots)

    def test_preview_is_noindex_but_home_is_indexable(self):
        preview = Page((self.site / 'vista-previa.html').read_text())
        self.assertTrue(any(a.get('name') == 'robots' and 'noindex' in a.get('content', '')
                            for tag, a in preview.tags if tag == 'meta'))
        self.assertFalse(any('noindex' in a.get('content', '')
                             for tag, a in self.page.tags if tag == 'meta'))

    def test_local_navigation_resolves(self):
        ids = [a['id'] for _, a in self.page.tags if 'id' in a]
        self.assertEqual(len(ids), len(set(ids)), 'IDs duplicados')
        for tag, attrs in self.page.tags:
            if tag != 'a':
                continue
            href = attrs.get('href', '')
            if href.startswith('#') and len(href) > 1:
                self.assertIn(unquote(href[1:]), ids, href)
        self.assertIn('masaya', ids)
        self.assertIn('diriomo', ids)
        self.assertEqual(sum(tag == 'h1' for tag, _ in self.page.tags), 1)
        self.assertIn('Óptica y Optometría en Masaya y Diriomo</h1>', self.text)

    def test_local_businesses_match_visible_content(self):
        self.assertEqual(len(self.page.structured), 1)
        graph = self.page.structured[0]['@graph']
        organizations = [n for n in graph if n['@type'] == 'Organization']
        self.assertEqual(len(organizations), 1)
        branches = [n for n in graph if n['@type'] == 'Optician']
        self.assertEqual({n['address']['addressLocality'] for n in branches}, {'Masaya', 'Diriomo'})
        for branch in branches:
            self.assertIn(branch['address']['streetAddress'], self.text)
            self.assertEqual(branch['telephone'], organizations[0]['telephone'])
            self.assertEqual(branch['parentOrganization']['@id'], organizations[0]['@id'])
            self.assertEqual(branch['@id'], branch['url'])
            self.assertIn(urlsplit(branch['url']).fragment,
                          [a.get('id') for _, a in self.page.tags])
            self.assertIn('previa cita', branch['description'])
            # La atención dominical no tiene horario fijo: no declararla abierta 24h.
            self.assertNotIn('Sunday', json.dumps(branch['openingHoursSpecification']))
            self.assertNotIn('aggregateRating', branch)
        by_city = {n['address']['addressLocality']: n for n in branches}
        self.assertEqual(by_city['Masaya']['openingHoursSpecification'][1]['opens'], '08:30')
        self.assertEqual(by_city['Masaya']['openingHoursSpecification'][1]['closes'], '15:00')
        self.assertEqual(by_city['Diriomo']['openingHoursSpecification'][1]['opens'], '08:00')
        self.assertEqual(by_city['Diriomo']['openingHoursSpecification'][1]['closes'], '14:00')



class OtherPages(unittest.TestCase):
    """Páginas fuera del inicio (paginas/*.html): encabezado y pie compartidos, borradores y 404."""

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.site = Path(cls.temp.name) / 'site'
        subprocess.run([sys.executable, str(ROOT / 'scripts/build.py'), '--out', str(cls.site)],
                       cwd=ROOT, check=True, capture_output=True)
        cls.pages = {f.name: Page(f.read_text()) for f in cls.site.glob('*.html') if f.name != 'vista-previa.html'}

    @staticmethod
    def meta(page, name):
        return next((a.get('content', '') for tag, a in page.tags if tag == 'meta' and a.get('name') == name), None)

    def test_each_page_has_title_h1_and_shared_layout(self):
        self.assertIn('404.html', self.pages)
        self.assertIn('terapia-visual.html', self.pages)
        self.assertIn('empresas.html', self.pages)
        self.assertTrue(any(tag == 'form' and 'data-afil-form' in a for tag, a in self.pages['empresas.html'].tags))
        self.assertFalse(any(tag == 'form' and 'data-afil-form' in a for tag, a in self.pages['index.html'].tags))
        for name, page in self.pages.items():
            with self.subTest(name):
                self.assertEqual(sum(tag == 'h1' for tag, _ in page.tags), 1)
                self.assertTrue(any(tag == 'header' for tag, _ in page.tags))
                self.assertTrue(any(tag == 'footer' for tag, _ in page.tags))
                self.assertTrue(any(tag == 'dialog' for tag, _ in page.tags), 'falta la hoja de Agendar cita')

    def test_links_between_pages_resolve(self):
        ids = {name: {a['id'] for _, a in page.tags if 'id' in a} for name, page in self.pages.items()}
        for name, page in self.pages.items():
            for tag, a in page.tags:
                ref = a.get('href') if tag in ('a', 'link') else a.get('src') if tag in ('img', 'script') else None
                if not ref or not ref.startswith('/') or ref.startswith('//'):
                    continue
                path, _, fragment = unquote(ref.split('?')[0]).partition('#')
                target = 'index.html' if path == '/' else path.lstrip('/')
                if not (self.site / target).is_file():
                    target += '.html'
                with self.subTest(page=name, ref=ref):
                    self.assertTrue((self.site / target).is_file())
                    if fragment:
                        self.assertIn(fragment, ids[target])
            if name != 'index.html':  # fuera del inicio, ningún enlace a una sección suelta (#servicios)
                local = [a['href'] for tag, a in page.tags if tag == 'a' and a.get('href', '').startswith('#')]
                for href in local:
                    self.assertIn(href[1:], ids[name], f'{name}: {href}')

    def test_drafts_are_noindex_unlinked_and_out_of_sitemap(self):
        sitemap = (self.site / 'sitemap.xml').read_text()
        for name, page in self.pages.items():
            source = (ROOT / 'paginas' / name)
            if not source.is_file() or '<meta name="borrador"' not in source.read_text():
                continue
            slug = name[:-5]
            with self.subTest(name):
                self.assertIn('noindex', self.meta(page, 'robots') or '')
                self.assertTrue(any('draft-banner' in a.get('class', '') for _, a in page.tags))
                self.assertNotIn(f'/{slug}<', sitemap)
                for other_name, other in self.pages.items():
                    if other_name != name:
                        hrefs = [a.get('href', '') for tag, a in other.tags if tag == 'a']
                        self.assertNotIn(f'/{slug}', hrefs, f'{other_name} enlaza al borrador')

    def test_not_found_page_is_noindex(self):
        self.assertIn('noindex', self.meta(self.pages['404.html'], 'robots') or '')

    def test_branch_data_comes_from_content(self):
        data = json.loads((ROOT / 'content/sucursales.json').read_text())
        home = Page((self.site / 'index.html').read_text())
        branches = {n['url'].split('#')[1]: n for n in home.structured[0]['@graph'] if n['@type'] == 'Optician'}
        self.assertEqual(set(branches), set(data))
        for sid, suc in data.items():
            with self.subTest(sid):
                self.assertEqual(branches[sid]['address']['streetAddress'], suc['direccion'] + '.')
                saturday = branches[sid]['openingHoursSpecification'][1]
                self.assertEqual((saturday['opens'], saturday['closes']), (suc['sabado']['abre'], suc['sabado']['cierra']))
                reviews = [a for tag, a in home.tags if tag == 'a' and a.get('data-resena') == sid]
                self.assertEqual([a['href'] for a in reviews], [suc['resenas']] if suc['resenas'] else [])


    def test_whatsapp_messages_say_they_come_from_the_web(self):
        for name in self.pages:
            text = (self.site / name).read_text()
            for encoded in re.findall(r'wa\.me/\d+\?text=([^"&\s<]+)', text):
                with self.subTest(page=name, message=unquote(encoded)[:60]):
                    self.assertIn('página web', unquote(encoded))

    def test_no_analytics_while_privacy_policy_is_a_draft(self):
        source = ROOT / 'paginas' / 'privacidad.html'
        if source.is_file() and '<meta name="borrador"' not in source.read_text():
            self.skipTest('la política está publicada')
        for name in self.pages:
            with self.subTest(name):
                text = (self.site / name).read_text()
                self.assertNotIn('googletagmanager', text)
                self.assertNotIn('medicion.js', text)


class Helpers(unittest.TestCase):
    """Funciones de scripts/build.py que no dependen del contenido actual."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / 'scripts'))
        import build
        cls.build = build

    def test_tag_whatsapp_adds_origin_once(self):
        link = 'https://wa.me/50584024868?text=' + quote('¡Hola Opto Service! Quiero una cita.', safe='')
        once = self.build.tag_whatsapp(f'<a href="{link}">')
        self.assertIn(quote('¡Hola Opto Service! Vengo de la página web. Quiero una cita.', safe=''), once)
        self.assertEqual(self.build.tag_whatsapp(once), once)
        other = 'https://wa.me/50584024868?text=' + quote('Me interesa la promo', safe='')
        self.assertIn(quote('¡Hola Opto Service! Vengo de la página web. Me interesa la promo', safe=''),
                      self.build.tag_whatsapp(other))

    def test_analytics_has_no_ad_signals_and_is_deferred(self):
        snippet = self.build.render_analytics('G-TEST1234')
        self.assertIn('allow_google_signals:false', snippet)
        self.assertIn('allow_ad_personalization_signals:false', snippet)
        self.assertIn('<script async src="https://www.googletagmanager.com/gtag/js?id=G-TEST1234">', snippet)
        self.assertIn('<script src="/assets/js/medicion.js" defer>', snippet)

    def test_tracking_script_sends_no_personal_or_health_data(self):
        code = (ROOT / 'assets/js/medicion.js').read_text().split('(function', 1)[1]  # sin el comentario inicial
        for forbidden in ('name="servicio"', 'name="nombre"', 'elements.nombre', 'mensaje', 'correo', 'FormData'):
            self.assertNotIn(forbidden, code)


if __name__ == '__main__':
    unittest.main()
