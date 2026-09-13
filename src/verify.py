"""Crawl dist/ and check links, titles, descriptions, canonicals, H1s, sitemap, leftovers."""
import os, re, sys, html
from collections import Counter
DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'dist')
pages = {}
for root, _, files in os.walk(DIST):
    for f in files:
        if f.endswith('.html'):
            full = os.path.join(root, f); rel = '/' + os.path.relpath(full, DIST).replace(os.sep, '/')
            pages[rel] = open(full, encoding='utf-8').read()
import posixpath
def exists(path, frm='/index.html'):
    p = path.split('#')[0].split('?')[0]
    if not p: return True
    if not p.startswith('/'): p = posixpath.normpath(posixpath.join(posixpath.dirname(frm), p)); p = p + '/' if path.split('#')[0].split('?')[0].endswith('/') and not p.endswith('/') else p
    if p == '.': p = '/'
    return os.path.isfile(os.path.join(DIST, p.lstrip('/'))) or os.path.isfile(os.path.join(DIST, p.strip('/'), 'index.html'))
problems = Counter(); titles = Counter(); sample = {}
sitemap = set(re.findall(r'<loc>https://fedcatalog\.com(.*?)</loc>', open(os.path.join(DIST, 'sitemap.xml')).read()))
for rel, h in pages.items():
    t = re.search(r'<title>(.*?)</title>', h, re.S); titles[t.group(1) if t else ''] += 1
    if not t or not t.group(1).strip(): problems['missing title'] += 1
    if not re.search(r'<meta name="description" content="[^"]+"', h): problems['missing description'] += 1
    noindex = 'noindex' in h
    canon = re.search(r'<link rel="canonical" href="(.*?)"', h)
    if not canon: problems['missing canonical'] += 1
    elif not canon.group(1).startswith('https://fedcatalog.com/'): problems['bad canonical origin'] += 1
    h1 = len(re.findall(r'<h1[\s>]', h))
    if h1 != 1: problems['h1 count != 1'] += 1; sample.setdefault('h1', rel)
    if '#/' in re.sub(r'https?://[^"\']+', '', h): problems['hash route'] += 1; sample.setdefault('hash', rel)
    if re.search(r'pipe ?team', h, re.I): problems['pipeteam'] += 1; sample.setdefault('pipe', rel)
    if 'federal-software-catalog' in h.lower() or 'localhost' in h: problems['dev host'] += 1
    for href in re.findall(r'href="([^"]+)"', h):
        href = html.unescape(href)
        if href.startswith('http') or href.startswith('mailto:') or href.startswith('#'): continue
        if not exists(href, rel): problems['broken link'] += 1; sample.setdefault('broken', (rel, href))
    page_url = rel.replace('/index.html', '/') if rel.endswith('/index.html') else rel
    if not noindex and page_url != '/404.html' and page_url not in sitemap: problems['indexable page missing from sitemap'] += 1; sample.setdefault('sitemap', rel)
for u in sitemap:
    if not exists(u): problems['sitemap url unresolved'] += 1
dups = {t: c for t, c in titles.items() if c > 1}
print('pages:', len(pages), '| sitemap urls:', len(sitemap))
print('problems:', dict(problems) or 'none')
print('duplicate titles:', dups or 'none')
print('samples:', sample)
