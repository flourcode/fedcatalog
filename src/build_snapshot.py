"""Build a compact snapshot of the FedRAMP Marketplace data for embedding.
Run:  python3 build_snapshot.py  (fetches data.json from the public repo)"""
import json, re, sys, os, urllib.request, datetime

SRC = 'https://raw.githubusercontent.com/FedRAMP/marketplace-fedramp-gov-data/main/data.json'

def load():
    if len(sys.argv) > 1 and not sys.argv[1].startswith('--'): return json.load(open(sys.argv[1]))
    with urllib.request.urlopen(SRC, timeout=60) as r: return json.load(r)

def compact(raw):
    prods = raw['data']['Products']; agencies = raw['data']['Agencies']
    # "runs on": IaaS platforms list the offerings that leverage them
    runs = {}
    PLATFORMS = [(r'^AWS US East/West', 'aws'), (r'^AWS GovCloud', 'aws-gov'), (r'^Azure Commercial', 'azure'), (r'^Azure Government', 'azure-gov'),
                 (r'^Google Services', 'google'), (r'^Oracle Cloud Infrastructure', 'oci')]
    for p in prods:
        for pat, code in PLATFORMS:
            if re.search(pat, p['cso']):
                for dep in p.get('leveraged_systems') or []:
                    if isinstance(dep, dict): runs.setdefault(dep['id'], set()).add(code)
    NAMED = [(r'govcloud', 'aws-gov'), (r'\baws\b|amazon web', 'aws'), (r'azure gov', 'azure-gov'), (r'\bazure\b', 'azure'), (r'google cloud|\bgcp\b|google workspace', 'google'), (r'oracle cloud|\boci\b', 'oci')]
    named = {}
    for p in prods:
        for pat, code in NAMED:
            if re.search(pat, p['cso'], re.I): named.setdefault(p['id'], set()).add(code)
    functions = sorted({f for p in prods for f in (p.get('business_function') or []) if f})
    fidx = {f: i for i, f in enumerate(functions)}
    agency_names = sorted({a for p in prods for a in (p.get('agency_authorizations') or []) if a})
    aidx = {a: i for i, a in enumerate(agency_names)}
    out = []
    for p in prods:
        desc = re.sub(r'\s+', ' ', p.get('service_desc') or '').strip()
        out.append({
            'id': p['id'], 'v': p['csp'], 'n': p['cso'], 's': p['status'], 'i': p['impact_level'],
            'd': p.get('deployment_model') or '', 'm': [x for x in (p.get('service_model') or []) if x],
            'f': [fidx[x] for x in (p.get('business_function') or []) if x],
            'a': [aidx[x] for x in (p.get('agency_authorizations') or []) if x],
            'r': sorted(runs.get(p['id'], [])), 'rn': sorted(named.get(p['id'], set()) - runs.get(p['id'], set())),
            'rd': (p.get('ready_date') or '')[:10] if str(p.get('ready_date','')).startswith('20') else '', 'as': p.get('independent_assessor') or '', 'se': p.get('sales_email') or '',
            't': p.get('auth_type') or '', 'ad': (p.get('auth_date') or '')[:10] if str(p.get('auth_date','')).startswith('20') else '',
            'w': p.get('website') or '', 'de': desc[:700], 'sb': p.get('small_business') or '',
            'lv': len(p.get('leveraged_systems') or []),
        })
    ag = [{'id': a['id'], 'p': a['parent'], 's': a.get('sub') or '', 'n': [x['id'] for x in a.get('auths') or []]} for a in agencies]
    return {'meta': {'last_change': raw['meta'].get('last_change'), 'built': datetime.datetime.utcnow().isoformat() + 'Z', 'source': SRC},
            'functions': functions, 'agencyNames': agency_names, 'products': out, 'agencies': ag, 'latest': raw['data']['Metrics'].get('latest', [])}

def enrich(snap):
    """Attach DoD IL rows and OneGov agreements. Both live in /data as curated JSON;
    refresh_sources() below tries to update them from the source pages."""
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    dod = json.load(open(os.path.join(here, 'data', 'dod_il.json')))
    onegov = json.load(open(os.path.join(here, 'data', 'onegov.json')))
    cw = json.load(open(os.path.join(here, 'data', 'crosswalk.json')))
    def vkey(n):
        n = re.sub(r'\s*\(.*?\)\s*', ' ', n); n = re.sub(r'[.,]+$', '', n)
        suf = re.compile(r",?\s*\b(inc|llc|l\.l\.c|corp|corporation|incorporated|company|co|ltd|lp|plc|pbc)\b\.?$", re.I)
        return suf.sub('', suf.sub('', n)).strip()
    def slug(s): return re.sub(r'^-|-$', '', re.sub(r'[^a-z0-9]+', '-', s.lower().replace('&', ' and ')))
    vendor_slugs = {slug(vkey(p['v'])) for p in snap['products']}
    def resolve(name, table):
        target = table.get(name.lower())
        s = slug(vkey(target)) if target else slug(vkey(name))
        return s if s in vendor_slugs else None
    for r in dod['rows']: r['vendor_slug'] = resolve(r['provider'], cw['dod'])
    for a in onegov['agreements']: a['vendor_slug'] = resolve(a['vendor'], cw['onegov'])
    snap['dod'] = {'source': dod['source'], 'fetched': dod['fetched'], 'rows': dod['rows']}
    snap['onegov'] = {'source': onegov['source'], 'checked': onegov['checked'], 'agreements': onegov['agreements']}
    return snap

def refresh_sources():
    """Best-effort: re-parse the DoD CSO table from public.cyber.mil. If the page
    layout changes and nothing parses, the previous data/dod_il.json is kept."""
    import os, html
    here = os.path.dirname(os.path.abspath(__file__))
    import shutil
    for name in ['dod_il.json', 'onegov.json']:
        src_path = os.path.join(here, 'data', name)
        if os.path.exists(src_path): shutil.copy(src_path, os.path.join(here, 'data', name.replace('.json', '.prev.json')))
    try:
        req = urllib.request.Request('https://public.cyber.mil/dccs/cso/', headers={'User-Agent': 'Mozilla/5.0 (catalog-build)'})
        page = urllib.request.urlopen(req, timeout=60).read().decode('utf-8', 'ignore')
        rows = []
        for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', page, re.S):
            cells = [html.unescape(re.sub(r'<[^>]+>', ' ', c)).strip() for c in re.findall(r'<td[^>]*>(.*?)</td>', tr, re.S)]
            cells = [re.sub(r'\s+', ' ', c) for c in cells]
            if len(cells) < 6 or not re.match(r'IL\d', cells[2]): continue
            lvl, base = (cells[2].split(' ') + [''])[:2]
            m = re.match(r'(\d+)/(\d+)/(\d{4})$', cells[5])
            rows.append({'provider': cells[0], 'cso': cells[1], 'il': lvl, 'baseline': base, 'models': [s.strip() for s in cells[3].split(';')], 'status': cells[4],
                         'expires': f'{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}' if m else None, 'expires_text': cells[5]})
        if len(rows) >= 40:
            json.dump({'source': 'https://public.cyber.mil/dccs/cso/', 'fetched': datetime.date.today().isoformat(), 'rows': rows}, open(os.path.join(here, 'data', 'dod_il.json'), 'w'), indent=1)
            print('DoD IL refreshed:', len(rows), 'rows')
        else:
            print('DoD IL: page parsed', len(rows), 'rows; keeping previous file')
    except Exception as e:
        print('DoD IL refresh skipped:', e)
    # OneGov: only report whether the feed lists agreements we don't have (curation stays manual).
    try:
        feed = urllib.request.urlopen('https://itvmo.gsa.gov/agreements-feed.xml', timeout=30).read().decode('utf-8', 'ignore')
        titles = set(html.unescape(t) for t in re.findall(r'<title>(.*?)</title>', feed)[1:])
        have = set(a['title'] for a in json.load(open(os.path.join(here, 'data', 'onegov.json')))['agreements'])
        new = [t for t in titles if t not in have]
        print('OneGov feed titles not yet curated:', new if new else 'none')
    except Exception as e:
        print('OneGov feed check skipped:', e)

if __name__ == '__main__':
    if '--refresh' in sys.argv: refresh_sources()
    snap = enrich(compact(load()))
    js = 'window.FSC_SNAPSHOT = ' + json.dumps(snap, separators=(',', ':'), ensure_ascii=False) + ';'
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'snapshot.js')
    open(out, 'w').write(js)
    print('products', len(snap['products']), 'agencies', len(snap['agencies']), 'bytes', len(js.encode()))
