"""Comprueba el sitio generado: python -m unittest discover -s scripts -p 'test_*.py'."""
import json
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


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
        self.assertEqual(urls, canonical)
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
        self.assertIn('Óptica y optometría en Masaya y Diriomo</h1>', self.text)

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


if __name__ == '__main__':
    unittest.main()
