#!/usr/bin/env python3
"""FedCatalog static site generator.

Reads src/data/snapshot.js (built by build_snapshot.py) plus the curated JSON in
src/data, and writes a complete static site to dist/. Every important page is
plain HTML with its content in the initial response; assets/site.js adds
search, filters, the mobile filter sheet, copy buttons and the live
USAspending section.

Run:  python3 src/build.py
"""
import json, re, os, html, shutil, datetime, sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'src'); DATA = os.path.join(SRC, 'data'); DIST = os.path.join(ROOT, 'dist')
ORIGIN = 'https://fedcatalog.com'
SITE = 'FedCatalog'
EMAIL = 'mark@fedcatalog.com'
TODAY = datetime.date.today().isoformat()

# ------------------------------------------------------------------ helpers
def esc(s): return html.escape(str(s if s is not None else ''), quote=True)
def slugify(s): return re.sub(r'^-|-$', '', re.sub(r'[^a-z0-9]+', '-', str(s or '').lower().replace('&', ' and ')))
RE_SUFFIX = re.compile(r",?\s*\b(inc|llc|l\.l\.c|corp|corporation|incorporated|company|co|ltd|lp|plc|pbc|dba .*)\b\.?$", re.I)
def vendor_key(name):
    n = re.sub(r'\s*\(.*?\)\s*', ' ', str(name or '')); n = re.sub(r'[.,]+$', '', n)
    return RE_SUFFIX.sub('', RE_SUFFIX.sub('', n)).strip()
def fmt_date(iso):
    if not iso: return '—'
    try: return datetime.date.fromisoformat(iso[:10]).strftime('%b %-d, %Y')
    except Exception: return iso
def trunc(text, n):
    text = (text or '').strip()
    if len(text) <= n: return text
    cut = text[:n].rsplit(' ', 1)[0].rstrip(',;:—-')
    return cut + '…'
def first_sentence(text):
    m = re.match(r'^(.{20,220}?[.!?])(\s|$)', text or '')
    return m.group(1) if m else trunc(text, 160)
def nfmt(n): return f'{n:,}'
STATUS = {'FedRAMP Authorized': ('authorized', 'Authorized'), 'FedRAMP In Process': ('in-process', 'In process'), 'Agency In Process': ('in-process', 'In process'), 'FedRAMP Ready': ('ready', 'Ready')}
def changelog_family(s):
    """Map a changelog status string to (status_code, status_label, display status)."""
    s = s or ''
    if 'No Status Found' in s: return ('delisted', 'Delisted', 'No longer on the FedRAMP Marketplace')
    if 'In Remediation' in s: return ('authorized', 'Authorized · in remediation', 'FedRAMP Authorized (in remediation)')
    if re.search(r'certified|^authorized$', s, re.I): return ('authorized', 'Authorized', 'FedRAMP Authorized')
    if 'Ready' in s: return ('ready', 'Ready', 'FedRAMP Ready')
    if 'Initial Implementation' in s: return ('initial', 'Initial Implementation', 'Initial Implementation')
    if 'In Process' in s or 'Review' in s: return ('in-process', 'In process', 'FedRAMP In Process')
    return (None, None, None)
RUNS = {'aws': 'AWS', 'aws-gov': 'AWS GovCloud', 'azure': 'Azure', 'azure-gov': 'Azure Government', 'google': 'Google Cloud', 'oci': 'Oracle Cloud'}
RUNS_FAMILY = {'aws': 'aws', 'aws-gov': 'aws', 'azure': 'azure', 'azure-gov': 'azure', 'google': 'google', 'oci': 'oci'}
FAMILY_LABEL = {'aws': 'AWS', 'azure': 'Microsoft Azure', 'google': 'Google Cloud', 'oci': 'Oracle Cloud'}
CLOUD_SLUG = {'aws': 'aws', 'aws-gov': 'aws-govcloud', 'azure': 'azure', 'azure-gov': 'azure-government', 'google': 'google-cloud', 'oci': 'oracle-cloud'}
IMPACT_ORDER = {'High': 4, '20x Moderate': 3, 'Moderate': 3, '20x Low': 2, 'Low': 2, 'LI-SaaS': 1}
IMPACT_HELP = {'High': 'Loss would have severe or catastrophic effect; typical for law enforcement, emergency, financial and health systems', 'Moderate': 'Loss would have serious effect; the most common baseline', 'Low': 'Loss would have limited effect', 'LI-SaaS': 'Low-impact SaaS: tailored baseline for low-risk SaaS that does not store PII beyond login', '20x Low': 'FedRAMP 20x pilot, Low', '20x Moderate': 'FedRAMP 20x pilot, Moderate'}
CAT_DESC = {
  'Artificial Intelligence (AI)': 'Machine learning, generative AI, document intelligence and assistants', 'Cybersecurity & Risk Management': 'Identity, endpoint, network, vulnerability, SIEM and risk',
  'Analytics': 'Business intelligence, dashboards, data science and reporting', 'Data Management': 'Data platforms, warehouses, integration, quality and governance',
  'Development Tools': 'DevSecOps, source control, CI/CD, testing and low-code', 'Operations Management': 'IT operations, service management, monitoring and workflow',
  'Collaboration': 'Meetings, messaging, documents, whiteboards and intranets', 'Communication': 'Email, notifications, voice and video', 'Network Management': 'SD-WAN, CDN, DNS, secure access and edge',
  'Virtual Private Network (VPN)': 'Remote and zero-trust access', 'Content Management System (CMS)': 'Web content, documents, records and forms', 'Customer Relations Management (CRM)': 'Constituent and case management',
  'Customer Service': 'Service desks, ticketing and citizen support', 'Contact Center': 'Voice, chat and omnichannel contact centers', 'Human Resources': 'HR, payroll, talent and workforce management',
  'Education & Training': 'Learning, courses and training delivery', 'Learning Management': 'LMS platforms and course delivery', 'Governance, Risk, and Compliance (GRC)': 'Policy, audit, risk registers and ATO tooling',
  'Legal & Policy': 'Legal operations, policy and records', 'Storage': 'Object and file storage, backup and archive', 'System Administration': 'Endpoint, patch and configuration management',
  'Mobile Device Management (MDM)': 'Device and endpoint management', 'Finance': 'Financial management, budgeting and procurement', 'Accounting': 'Accounting and expense management',
  'Grant Management': 'Grant applications, awards and reporting', 'Health & Wellness': 'Clinical, health and wellness systems', 'Law Enforcement': 'Evidence, records and public-safety tools',
  'Fleet Management': 'Vehicles, telematics and logistics', 'Research': 'Survey, lab and research platforms', 'Marketing & Sales': 'Outreach, campaigns and engagement',
  'Design & Multimedia': 'Design, media and creative tools', 'Construction': 'Construction and facilities management', 'Media': 'Media management and delivery', 'Travel Management': 'Travel booking and expense',
  'Talent Development': 'Skills and career development', 'Talent Management': 'Recruiting and performance'}
CAT_SLUG_OVERRIDE = {'Artificial Intelligence (AI)': 'artificial-intelligence', 'Cybersecurity & Risk Management': 'cybersecurity', 'Content Management System (CMS)': 'content-management', 'Customer Relations Management (CRM)': 'crm', 'Governance, Risk, and Compliance (GRC)': 'grc', 'Virtual Private Network (VPN)': 'vpn', 'Mobile Device Management (MDM)': 'mdm', 'Data Management': 'data-management', 'Analytics': 'analytics'}
POPULAR = ['Artificial Intelligence (AI)', 'Cybersecurity & Risk Management', 'Data Management', 'Analytics', 'Development Tools', 'Network Management', 'Collaboration', 'Governance, Risk, and Compliance (GRC)']

# ------------------------------------------------------------------ data model
def load():
    raw = open(os.path.join(DATA, 'snapshot.js')).read()
    snap = json.loads(raw[raw.index('=') + 1:].rstrip().rstrip(';'))
    products = []
    for p in snap['products']:
        sc, sl = STATUS.get(p['s'], ('ready', p['s']))
        vk = vendor_key(p['v'])
        runs, named = p['r'], p.get('rn', [])
        products.append(dict(id=p['id'], vendor=p['v'], vendor_key=vk, vendor_slug=slugify(vk), name=p['n'], status=p['s'], status_code=sc, status_label=sl, impact=p['i'],
            deployment=p['d'], models=p['m'], functions=[snap['functions'][i] for i in p['f']], agencies=[snap['agencyNames'][i] for i in p['a']], runs=runs, runs_named=named,
            families=sorted({RUNS_FAMILY[r] for r in runs + named}), auth_type=p['t'], auth_date=p['ad'], ready_date=p.get('rd', ''), assessor=p.get('as', ''), sales_email=p.get('se', ''),
            website=(p['w'] if re.match(r'^https?://', p['w'] or '') else ('https://' + p['w'] if p['w'] else '')), desc=p['de'], small=p['sb'], leveraged_by=p['lv']))
    # ---- Status overlay from FedRAMP's status changelog (authoritative timeline; the daily record lags it)
    latest = {}
    for x in sorted(load_changes_all(), key=lambda x: x.get('transition_date') or ''):
        if x.get('product_id') and (x.get('from_status') or '') != (x.get('to_status') or ''): latest[x['product_id']] = x
    by_id_tmp = {p['id']: p for p in products}
    for pid, x in latest.items():
        code, label, display = changelog_family(x['to_status'])
        if not code: continue
        p = by_id_tmp.get(pid)
        if p:
            p['status_event'] = x['transition_date'][:10]
            if code != p['status_code']:
                p['record_status'] = p['status']; p['record_status_event'] = x['to_status']
                p['status_code'], p['status_label'], p['status'] = code, label, display
            if code == 'authorized' and not p.get('auth_date'): p['auth_date'] = x['transition_date'][:10]
        elif code != 'delisted' and x['transition_date'][:10] >= (datetime.date.today() - datetime.timedelta(days=365)).isoformat():
            # Offering known only from the changelog (e.g. Initial Implementation listings): a light record.
            vk = vendor_key(x['csp'])
            products.append(dict(id=pid, vendor=x['csp'], vendor_key=vk, vendor_slug=slugify(vk), name=x['cso'], status=display, status_code=code, status_label=label, impact='',
                deployment='', models=[], functions=[], agencies=[], runs=[], runs_named=[], families=[], auth_type=(x.get('cert_path') or ''), auth_date=(x['transition_date'][:10] if code == 'authorized' else ''),
                ready_date=(x['transition_date'][:10] if code == 'ready' else ''), assessor='', sales_email='', website='', desc='', small='', leveraged_by=0, stub=True, status_event=x['transition_date'][:10]))
    # per-product website overrides (src/data/product_sites.json), keyed by FedRAMP ID
    try: site_overrides = json.load(open(os.path.join(DATA, 'product_sites.json'))).get('sites', {})
    except Exception: site_overrides = {}
    for p in products:
        if p['id'] in site_overrides and site_overrides[p['id']]:
            p['website_fedramp'] = p['website']; p['website'] = site_overrides[p['id']]
    # unique product slugs
    seen = defaultdict(int)
    for p in products: seen[slugify(p['name'])] += 1
    for p in products:
        s = slugify(p['name'])
        p['slug'] = s if seen[s] == 1 else slugify(p['vendor_key'] + ' ' + p['name'])
    dup = defaultdict(int)
    for p in products: dup[p['slug']] += 1
    for p in products:
        if dup[p['slug']] > 1: p['slug'] = p['slug'] + '-' + p['id'].lower()
    by_id = {p['id']: p for p in products}
    vendors = {}
    for p in products:
        v = vendors.setdefault(p['vendor_slug'], dict(slug=p['vendor_slug'], name=p['vendor_key'], products=[], website=''))
        v['products'].append(p)
    # Vendor page URL: curated override if present; otherwise the offering URL whose domain is most common across
    # the vendor's offerings, preferring paths that look like public-sector pages over product pages.
    overrides = {}
    try: overrides = json.load(open(os.path.join(DATA, 'vendor_sites.json'))).get('sites', {})
    except Exception: pass
    for v in vendors.values():
        if v['slug'] in overrides and overrides[v['slug']]: v['website'] = overrides[v['slug']]; continue
        urls = [p['website'] for p in v['products'] if p['website']]
        if not urls: continue
        domains = defaultdict(int)
        for u in urls: domains[re.sub(r'^https?://(www\.)?', '', u).split('/')[0].lower()] += 1
        top = max(domains.items(), key=lambda t: t[1])[0]
        cands = [u for u in urls if re.sub(r'^https?://(www\.)?', '', u).split('/')[0].lower() == top]
        gov = [u for u in cands if re.search(r'gov|federal|public-?sector|government', u, re.I)]
        v['website'] = (gov or cands)[0]
    functions = []
    for name in snap['functions']:
        count = sum(1 for p in products if name in p['functions'] and p['status_code'] != 'delisted')
        if count: functions.append(dict(name=name, slug=CAT_SLUG_OVERRIDE.get(name, slugify(name)), count=count))
    functions.sort(key=lambda f: -f['count'])
    fn_by_name = {f['name']: f for f in functions}
    agencies = []
    for a in snap['agencies']:
        prods = [by_id[i] for i in a['n'] if i in by_id and by_id[i]['status_code'] != 'delisted']
        if not prods: continue
        name = a['s'] or a['p']
        agencies.append(dict(id=a['id'], parent=a['p'], sub=a['s'], name=name, slug=slugify(name), products=prods))
    agencies.sort(key=lambda a: -len(a['products']))
    # unique agency slugs
    dup = defaultdict(int)
    for a in agencies: dup[a['slug']] += 1
    for a in agencies:
        if dup[a['slug']] > 1: a['slug'] = a['slug'] + '-' + a['id'].lower()
    agency_by_name = {}
    for a in agencies: agency_by_name.setdefault(a['name'], a)
    try: listings = json.load(open(os.path.join(DATA, 'marketplace_listings.json'))).get('listings', [])
    except Exception: listings = []
    by_vendor = defaultdict(list)
    for l in listings: by_vendor[l['vendor_slug']].append(l)
    dod = snap.get('dod') or {'rows': [], 'fetched': '', 'source': ''}
    onegov = snap.get('onegov') or {'agreements': [], 'checked': '', 'source': ''}
    return dict(products=products, by_id=by_id, vendors=vendors, functions=functions, fn_by_name=fn_by_name, agencies=agencies, agency_by_name=agency_by_name,
                latest=snap.get('latest', []), meta=snap['meta'], dod=dod, onegov=onegov, listings=listings, listings_by_vendor=by_vendor)

def similar(db, p, n=6):
    cands = []
    for x in db['products']:
        if x['id'] == p['id'] or x['vendor_slug'] == p['vendor_slug'] or not set(x['functions']) & set(p['functions']): continue
        s = len(set(x['functions']) & set(p['functions'])) * 3 + (2 if x['impact'] == p['impact'] else 0) + (1 if x['status_code'] == 'authorized' else 0) + min(3, len(x['agencies']) / 10)
        cands.append((s, x))
    cands.sort(key=lambda t: -t[0])
    return [x for _, x in cands[:n]]
def vendor_summary(v):
    ps = [p for p in v['products'] if p['status_code'] != 'delisted'] or v['products']
    fns = defaultdict(int)
    for p in ps:
        for f in p['functions']: fns[f] += 1
    best = max(ps, key=lambda p: IMPACT_ORDER.get(p['impact'], 0))
    if not best['impact']: best = dict(best, impact='—')
    return dict(authorized=sum(1 for p in ps if p['status_code'] == 'authorized'), best=best, runs=sorted({r for p in ps for r in p['runs']}),
                agencies={a for p in ps for a in p['agencies']}, fns=[f for f, _ in sorted(fns.items(), key=lambda t: -t[1])])
def dod_rows_for(db, slug): return [r for r in db['dod']['rows'] if r.get('vendor_slug') == slug]
def onegov_for(db, slug): return [a for a in db['onegov']['agreements'] if a.get('vendor_slug') == slug]

# ------------------------------------------------------------------ URL helpers
def url_product(p): return f'/software/{p["slug"]}/'
def url_vendor(v): return f'/vendors/{v["slug"]}/'
def url_agency(a): return f'/agencies/{a["slug"]}/'
def url_category(f): return f'/categories/{f["slug"]}/'
def url_cloud(code): return f'/cloud/{CLOUD_SLUG[code]}/'

# ------------------------------------------------------------------ components
def monogram(name, cls=''):
    """Decorative single initial of the canonical vendor name. Same letter for every offering from a vendor;
    never an acronym. Exists so rows chunk visually; the text carries the information."""
    m = re.search(r'[A-Za-z0-9]', name or '')
    return f'<div class="mono {cls}" aria-hidden="true">{esc(m.group(0).upper() if m else "·")}</div>'
def status_label(p): return f'<span class="status s-{p["status_code"]}">{esc(p["status_label"])}</span>'
def runs_text(p):
    parts = [esc(RUNS[r]) for r in p['runs']] + [f'<span class="named" title="Named in the offering title; no leveraged-system record">{esc(RUNS[r])}</span>' for r in p['runs_named']]
    return ' · '.join(parts) if parts else '—'
def product_row(p, date=None):
    ag = len(p['agencies'])
    agtxt = date if date else (f'{ag} {"agency" if ag == 1 else "agencies"}' if ag else '—')
    sub = esc(p['vendor_key']) + (' · ' + ' · '.join(esc(f) for f in p['functions'][:2]) if p['functions'] else '')
    attrs = f' data-status="{p["status_code"]}" data-impact="{esc(p["impact"])}" data-family="{" ".join(p["families"])}" data-agencies="{ag}" data-auth="{esc(p["auth_date"] or p["ready_date"])}" data-name="{esc(p["name"].lower())}" data-vendor="{esc(p["vendor_key"].lower())}" data-onegov="{1 if p.get("_onegov") else 0}" data-dod="{esc(" ".join(p.get("_dod", [])))}"'
    return (f'<a class="row" href="{url_product(p)}"{attrs}>{monogram(p["vendor_key"])}<div class="main"><div class="name">{esc(p["name"])}</div><div class="sub">{sub}</div></div>'
            f'<div class="meta"><span class="c-st">{status_label(p)}</span><span class="c-im">{esc(p["impact"])}</span><span class="c-ro">{runs_text(p)}</span><span class="c-ag">{esc(agtxt)}</span></div><span class="chev" aria-hidden="true">›</span></a>')
def rows_block(products, table=True, page_size=None):
    head = '<div class="thead" aria-hidden="true"><span></span><span>Product</span><span>FedRAMP</span><span>Impact</span><span>Runs on</span><span>Agencies</span><span></span></div>' if table else ''
    return f'<div class="rows{" is-table" if table else ""}" data-rows>{head}{"".join(product_row(p) for p in products)}</div>'
def agency_link(a):
    n = len(a['products'])
    return f'<a class="cat" href="{url_agency(a)}"><b>{esc(a["name"])}</b><small>{nfmt(n)} authorized offering{"" if n == 1 else "s"}</small><span class="chev" aria-hidden="true">›</span></a>'
def cat_link(f): return f'<a class="cat" href="{url_category(f)}"><b>{esc(f["name"])}</b><span>{esc(CAT_DESC.get(f["name"], "Cloud services in this category"))}</span><small>{nfmt(f["count"])} offerings</small><span class="chev" aria-hidden="true">›</span></a>'
def crumbs_html(items):
    out = []
    for i, (label, href) in enumerate(items):
        if i: out.append('<span aria-hidden="true">›</span>')
        out.append(f'<a href="{href}">{esc(label)}</a>' if href else f'<span aria-current="page">{esc(label)}</span>')
    return '<nav class="crumbs" aria-label="Breadcrumb">' + ' '.join(out) + '</nav>'
def crumbs_ld(items):
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [dict({"@type": "ListItem", "position": i + 1, "name": label}, **({"item": ORIGIN + href} if href else {})) for i, (label, href) in enumerate(items)]}
def rail_html(base, with_dod=True):
    def group(title, key, opts): return f'<h4>{title}</h4>' + ''.join(f'<button type="button" data-filter="{key}" data-value="{v}" aria-pressed="false"><i></i>{l}</button>' for v, l in opts)
    return ('<div class="rail" data-rail>' + group('Status', 'status', [('authorized', 'Authorized'), ('in-process', 'In process'), ('ready', 'Ready')])
            + group('Impact', 'impact', [('High', 'High'), ('Moderate', 'Moderate'), ('Low', 'Low'), ('LI-SaaS', 'LI-SaaS')])
            + group('Runs on', 'family', [('aws', 'AWS'), ('azure', 'Azure'), ('google', 'Google Cloud')])
            + group('Agency authorizations', 'agencies', [('10', '10 or more'), ('25', '25 or more')])
            + group('Special purchasing', 'onegov', [('1', 'OneGov agreement')])
            + (group('DoD Impact Level (vendor)', 'dod', [('IL4', 'IL4 provisional authorization'), ('IL5', 'IL5 provisional authorization'), ('IL6', 'IL6 provisional authorization')]) if with_dod else '')
            + '<select aria-label="Sort" data-sort><option value="agencies">Sort: most agencies</option><option value="newest">Sort: newest authorization</option><option value="name">Sort: A–Z</option><option value="vendor">Sort: vendor</option></select>'
            + '<button type="button" class="clear" data-clear hidden>Clear filters</button></div>')
def results_page(crumbs, title, sub, products, head_extra=''):
    return (f'<section class="panel">{crumbs_html(crumbs)}<h1 class="h2" style="margin-top:10px">{esc(title)}' + (f'<small>{esc(sub)}</small>' if sub else '') + '</h1>' + head_extra
            + f'<div class="results">{rail_html("")}<div><div class="results-bar"><span class="count" data-count>{nfmt(len(products))} {"result" if len(products) == 1 else "results"}</span>'
            + '<button class="filter-btn" type="button" data-open-sheet>Filters<b data-filter-count></b></button></div>' + rows_block(products)
            + '<p class="note" data-empty hidden>Nothing matches these filters. Clear one or two and try again.</p>'
            + '<p class="note">Filters and sorting apply to the list on this page; nothing is hidden from search engines.</p>' + signup_slot('list') + '</div></div></section>')
def dod_row_html(r, with_vendor, db):
    tone = 'tone-good' if r['status'].startswith('Provisional Authorization') else ('tone-bad' if 'Suspended' in r['status'] else ('tone-warn' if 'IATT' in r['status'] else ''))
    expired = r.get('expires') and r['expires'] < TODAY
    vend = ''
    if with_vendor:
        vend = (f'<a href="/vendors/{r["vendor_slug"]}/" style="text-decoration:none">{esc(r["provider"])}</a>' if r.get('vendor_slug') in db['vendors'] else esc(r['provider'])) + ' · '
    return (f'<li><div class="award-head"><b>{vend}{esc(r["cso"])}</b><span>{esc(r["il"])}{(" " + esc(r["baseline"])) if r.get("baseline") else ""}</span></div>'
            f'<p class="award-meta"><span class="{tone}">{esc(r["status"])}</span> · {esc(", ".join(r["models"]))} · expires {esc(fmt_date(r["expires"]) if r.get("expires") else r.get("expires_text", ""))}{" (past the listed date; verify on the DoD page)" if expired else ""}</p></li>')
def onegov_row_html(a, with_vendor, db):
    expired = a.get('expires') and a['expires'] < TODAY
    vend = ''
    if with_vendor:
        vend = (f'<a href="/vendors/{a["vendor_slug"]}/" style="text-decoration:none">{esc(a["vendor"])}</a>' if a.get('vendor_slug') in db['vendors'] else esc(a['vendor'])) + ' · '
    meta = ' · '.join(esc(x) for x in [a.get('vehicle'), a.get('eligibility'), a.get('includes')] if x) + (f' · {esc(a["flag"])}' if a.get('flag') else '') + (' · past the listed expiry; confirm with GSA' if expired else '')
    links = f'<a class="link" href="https://itvmo.gsa.gov/onegov/?tabName=agreements-tab#{esc(a["anchor"])}" target="_blank" rel="noopener noreferrer" style="color:var(--orange-hover)">GSA agreement page →</a>' + (f' <a class="link" href="{esc(a["press"])}" target="_blank" rel="noopener noreferrer" style="color:var(--orange-hover)">Press release →</a>' if a.get('press') else '')
    return (f'<li><div class="award-head"><b>{vend}{esc(a["title"])}</b><span>{("to " + esc(fmt_date(a["expires"]))) if a.get("expires") else esc(a.get("expires_text", ""))}</span></div>'
            f'<p class="award-desc">{esc(a["discount"])}</p><p class="award-meta">{meta}</p><div class="award-links">{links}</div></li>')
def buy_links(vendor_name, p=None):
    v = esc(vendor_name).replace(' ', '%20')
    out = []
    if p and p.get('website'): out.append(f'<a href="{esc(p["website"])}" target="_blank" rel="noopener noreferrer">Vendor government page<small>Visit →</small></a>')
    out.append(f'<a href="https://aws.amazon.com/marketplace/search/results?searchTerms={v}" target="_blank" rel="noopener noreferrer">AWS Marketplace<small>View →</small></a>')
    out.append(f'<a href="https://azuremarketplace.microsoft.com/en-us/marketplace/apps?search={v}&amp;page=1" target="_blank" rel="noopener noreferrer">Azure Marketplace<small>View →</small></a>')
    out.append(f'<a href="https://console.cloud.google.com/marketplace/browse?q={v}" target="_blank" rel="noopener noreferrer">Google Cloud Marketplace<small>View →</small></a>')
    if p and p.get('id'): out.append(f'<a href="https://www.fedramp.gov/marketplace/products/{esc(p["id"])}/" target="_blank" rel="noopener noreferrer">FedRAMP Marketplace listing<small>View →</small></a>')
    return '<div class="buy">' + ''.join(out) + '</div>'
MARKET_LABEL = {'aws': 'AWS Marketplace', 'azure': 'Azure Marketplace', 'google': 'Google Cloud Marketplace', 'oracle': 'Oracle Cloud Marketplace', 'carahsoft': 'Carahsoft'}
def marketplace_links(vendor_name):
    """Search links: (key, name, description, url). Used only where no exact listing is on file."""
    vq = esc(vendor_name).replace(' ', '%20')
    return [
        ('aws', 'AWS Marketplace', 'Search listings; GovCloud (US) availability is shown on each listing', f'https://aws.amazon.com/marketplace/search/results?searchTerms={vq}'),
        ('azure', 'Azure Marketplace', 'Search listings; Azure Government editions are listed separately', f'https://azuremarketplace.microsoft.com/en-us/marketplace/apps?search={vq}&page=1'),
        ('google', 'Google Cloud Marketplace', 'Search listings', f'https://console.cloud.google.com/marketplace/browse?q={vq}'),
        ('oracle', 'Oracle Cloud Marketplace', 'Browse listings', 'https://cloudmarketplace.oracle.com/marketplace/en_US/homePage.jspx'),
        ('gsa-elib', 'GSA eLibrary', 'MAS contract holders that list the vendor', f'https://www.gsaelibrary.gsa.gov/ElibMain/searchResults.do?searchText={vq}&searchType=allWords'),
        ('gsa-adv', 'GSA Advantage', 'Products and prices on GSA schedules', f'https://www.gsaadvantage.gov/advantage/ws/search/advantage_search?q=0:0{vq}'),
        ('sewp', 'NASA SEWP', 'Provider and contract-holder lookup', 'https://www.sewp.nasa.gov/'),
    ]
def procurement_block(db, p, v):
    def item(name, sub, href, cta, cls=''): return f'<li class="proc {cls}"><div><b>{esc(name)}</b><small>{esc(sub)}</small></div><a href="{esc(href)}" target="_blank" rel="noopener noreferrer">{esc(cta)} →</a></li>'
    onegov = onegov_for(db, v['slug'])
    listings = db['listings_by_vendor'].get(v['slug'], [])
    pid = p.get('id')
    exact = [l for l in listings if pid and pid in (l.get('fedramp_ids') or [])]
    others = [l for l in listings if l not in exact]
    confirmed = []
    if onegov: confirmed.append(item('GSA OneGov agreement', onegov[0]['discount'][:110] + ' · via ' + onegov[0]['vehicle'] + (' · to ' + fmt_date(onegov[0]['expires']) if onegov[0].get('expires') else ''), f'https://itvmo.gsa.gov/onegov/?tabName=agreements-tab#{onegov[0]["anchor"]}', 'GSA agreement', 'is-confirmed'))
    for l in exact: confirmed.append(item(MARKET_LABEL[l['market']] + ': ' + l['title'], ('Vendor-supplied, reviewed' if l.get('source') == 'vendor' else 'Verified listing for this offering') + (' · ' + l['note'] if l.get('note') else '') + ((' · published by ' + l['publisher']) if l.get('publisher') and l['publisher'] != 'per listing' else '') + ' · checked ' + fmt_date(l['checked']), l['url'], 'View listing', 'is-vendor-supplied' if l.get('source') == 'vendor' else 'is-confirmed'))
    if p.get('website'): confirmed.append(item('Vendor direct', ('FedCatalog link; the FedRAMP record lists ' + re.sub(r'^https?://(www\.)?', '', p['website_fedramp']).rstrip('/')) if p.get('website_fedramp') else 'Government sales page from the FedRAMP record', p['website'], 'Visit', 'is-confirmed'))
    vendor_rows = [item((MARKET_LABEL[l['market']] + ': ' if l.get('kind') != 'note' else '') + l['title'], ('Seller page: all listings by the vendor' if l.get('kind') == 'seller' else ('How this vendor is bought' if l.get('kind') == 'note' else 'Vendor’s listing; not matched to this specific offering')) + (' · ' + l['note'] if l.get('note') else '') + ' · checked ' + fmt_date(l['checked']), l['url'], 'View', 'is-vendor') for l in others]
    covered = {l['market'] for l in listings if l.get('kind') != 'note'}
    searches = [item(name, 'Exact listing not yet verified by FedCatalog · ' + sub, href, ('Search ' + name) if v['name'].replace(' ', '%20').lower() in href.lower() else 'Open ' + name) for key, name, sub, href in marketplace_links(v['name']) if key not in covered]
    out = ''
    if confirmed: out += '<h3 class="h3" style="margin-top:8px">Confirmed buying paths</h3><ul class="procs">' + ''.join(confirmed) + '</ul>'
    else: out += '<p class="note" style="margin-top:8px">No confirmed buying path on record for this offering. The FedRAMP record lists no government sales page and GSA lists no OneGov agreement for the vendor.</p>'
    if vendor_rows: out += '<h3 class="h3">' + esc(v['name']) + '’s marketplace listings</h3><ul class="procs">' + ''.join(vendor_rows) + '</ul>'
    if searches: out += '<h3 class="h3">Other places to check</h3><ul class="procs is-quiet">' + ''.join(searches) + '</ul>'
    out += '<p class="note">✓ verified by FedCatalog · ○ vendor-supplied and reviewed · searches are places to look, not matches. FedCatalog shows what it can verify and labels what it can’t. Sell this to government? Send exact marketplace, GSA or SEWP listings to <a href="mailto:mark@fedcatalog.com">mark@fedcatalog.com</a>.</p>'
    return out

def evidence_links(vendor_name):
    v = esc(vendor_name).replace(' ', '%20')
    return ('<div class="buy">'
            f'<a href="https://www.gsaelibrary.gsa.gov/ElibMain/searchResults.do?searchText={v}&amp;searchType=allWords" target="_blank" rel="noopener noreferrer">GSA eLibrary<small>Search MAS contractors →</small></a>'
            '<a href="https://www.sewp.nasa.gov/" target="_blank" rel="noopener noreferrer">NASA SEWP<small>Provider lookup →</small></a>'
            '<a href="https://acrrepo.section508.gov/" target="_blank" rel="noopener noreferrer">Section 508 ACR Repository<small>Search for an ACR →</small></a>'
            f'<a href="https://sam.gov/search/?keywords={v}" target="_blank" rel="noopener noreferrer">SAM.gov entity<small>Search →</small></a></div>')

def correction_link(kind, name, ident, path):
    subject = f'FedCatalog correction: {name}'
    body = (f'Page: {ORIGIN}{path}\n{kind}: {name}' + (f'\nFedRAMP ID: {ident}' if ident else '') + '\n\nWhat needs fixing (delete what does not apply):\n- Federal landing page URL:\n- Exact marketplace listing (AWS / Azure / Google / Oracle):\n- GSA / SEWP / reseller path:\n- Description or category:\n- Something else:\n')
    href = 'mailto:' + EMAIL + '?subject=' + esc(subject).replace(' ', '%20') + '&body=' + esc(body).replace('\n', '%0A').replace(' ', '%20')
    return f'<p class="correct">Something wrong or missing on this page? <a href="{href}">Email me</a> and I’ll fix it by checking the source.</p>'
def signup_slot(context=''):
    return f'<div class="signup" data-signup data-context="{esc(context)}" hidden></div>'

# ------------------------------------------------------------------ layout
def relativize(html_text, path):
    """Turn root-relative links (/vendors/x/) into relative ones (../../vendors/x/) so the
    site works from a subfolder, a GitHub preview, or a file opened from disk. Canonical,
    Open Graph and JSON-LD URLs stay absolute on purpose."""
    depth = len([s for s in path.split('/') if s]) if path != '/404.html' else 0
    prefix = '../' * depth if depth else './'
    def fix(m):
        attr, target = m.group(1), m.group(2)
        if target == '/': return f'{attr}="{prefix}"'
        return f'{attr}="{prefix}{target[1:]}"'
    html_text = re.sub(r'\b(href|src|action)="(/(?!/)[^"]*)"', fix, html_text)
    return html_text.replace('<meta name="fc-base" content="/">', f'<meta name="fc-base" content="{prefix}">')

def layout(db, *, path, title, description, body, noindex=False, jsonld=None, og_type='website', h1_check=True):
    return relativize(_layout(db, path=path, title=title, description=description, body=body, noindex=noindex, jsonld=jsonld, og_type=og_type), path)

def _layout(db, *, path, title, description, body, noindex=False, jsonld=None, og_type='website'):
    canonical = ORIGIN + path
    ld = ''.join(f'<script type="application/ld+json">{json.dumps(j, ensure_ascii=False)}</script>' for j in (jsonld or []))
    robots = '<meta name="robots" content="noindex,follow">' if noindex else ''
    refreshed = fmt_date(db['meta'].get('last_change'))
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{canonical}">
{robots}
<meta property="og:site_name" content="FedCatalog">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{canonical}">
<meta property="og:type" content="{og_type}">
<meta property="og:image" content="{ORIGIN}/assets/fedcatalog-og.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#FFFFFF">
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
<meta name="fc-base" content="/">
<link rel="stylesheet" href="/assets/site.css">
{ld}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="top">
  <div class="top-row">
    <a class="brand" href="/"><b>FedCatalog</b></a>
    <nav class="nav" aria-label="Primary">
      <a href="/agencies/">Agencies</a><a href="/categories/">Browse</a><a href="/buy/">How to buy</a><a href="/new/">New</a>
    </nav>
  </div>
  <div class="searchbar"{' hidden' if path == '/' else ''}>
    <form class="search" action="/search/" method="get" role="search">
      <label for="q" class="sr-only">Search software, a vendor, or describe a need</label>
      <input id="q" name="q" type="search" autocomplete="off" placeholder="Search software, vendors or requirements…">
      <button type="submit">Search</button>
    </form>
  </div>
</header>
<main class="shell" id="main">
{body}
</main>
<footer class="site-footer">
  <nav aria-label="Footer"><a href="/about/">About</a> · <a href="/methodology/">How the data works</a> · <a href="/contact/">Contact</a> · <a href="/privacy/">Privacy</a> · <a href="/terms/">Terms</a></nav>
  <p class="foot-muted">© 2026 FedCatalog · Not affiliated with or endorsed by the U.S. Government.</p>
</footer>
<script src="/assets/site-text.js"></script>
<script src="/assets/signup.js"></script>
<script src="/assets/analytics.js"></script>
<script src="/assets/site.js" defer></script>
</body>
</html>'''

# ------------------------------------------------------------------ pages
def page_home(db):
    P = db['products']; V = db['vendors']
    P = [p for p in P if p['status_code'] != 'delisted']
    authorized = sum(1 for p in P if p['status_code'] == 'authorized')
    popular = [db['fn_by_name'][n] for n in POPULAR if n in db['fn_by_name']]
    home_agencies = [a for a in db['agencies'] if not a['sub'] and a['name'].startswith('Department of')][:8]
    recent = sorted([p for p in P if p['status_code'] == 'authorized' and p.get('auth_date')], key=lambda p: (p.get('status_event') or p['auth_date']), reverse=True)[:5]
    adopted = sorted([p for p in P if p['status_code'] != 'delisted'], key=lambda p: -len(p['agencies']))[:5]
    changes = load_changes()[:5]
    body = f'''
<section class="hero">
  <h1 data-text="heroTitle">Federal Software in One Place</h1>
  <p data-text="heroSub">FedRAMP, DoD, OneGov, GSA, SEWP and marketplaces. Connected.</p>
  <form class="search" action="/search/" method="get" role="search"><label for="hq" class="sr-only">Search</label><input id="hq" name="q" type="search" autocomplete="off" placeholder="Search software, vendors or requirements…"><button type="submit">Search</button></form>
  <p class="cred">Public data · Source-linked · No pay-to-rank · Updated {esc(fmt_date(db['meta'].get('last_change')))} · <a href="/methodology/">How the data works →</a></p>
</section>
<section class="panel"><div class="sec-head"><h2>Browse by agency</h2><a href="/agencies/">See all agencies</a></div><div class="cats">{''.join(agency_link(a) for a in home_agencies)}</div></section>
<section class="panel"><div class="sec-head"><h2>Popular categories</h2><a href="/categories/">See all</a></div><div class="cats">{''.join(cat_link(f) for f in popular)}</div></section>
<section class="panel"><div class="sec-head"><h2>Recently authorized</h2><a href="/fedramp/authorized/?sort=newest">See all</a></div><div class="rows">{''.join(product_row(p, date=fmt_date(p['auth_date']) if p['auth_date'] else None) for p in recent)}</div></section>
<section class="panel"><div class="sec-head"><h2>Most widely authorized</h2><a href="/fedramp/authorized/">See all</a></div><p class="sec-sub">Offerings with the most federal agency authorization or reuse records. A record is not a purchase.</p><div class="rows">{''.join(product_row(p) for p in adopted)}</div></section>
{('<section class="panel"><div class="sec-head"><h2>New and changed</h2><a href="/new/">See all</a></div><ul class="new">' + ''.join(change_row(db, x) for x in changes) + '</ul></section>') if changes else ''}
<section class="panel" style="padding-top:0">{signup_slot('home')}</section>
'''
    ld = [{"@context": "https://schema.org", "@type": "WebSite", "@id": ORIGIN + "/#website", "url": ORIGIN + "/", "name": "FedCatalog", "alternateName": "Federal Software Catalog",
           "potentialAction": {"@type": "SearchAction", "target": {"@type": "EntryPoint", "urlTemplate": ORIGIN + "/search/?q={search_term_string}"}, "query-input": "required name=search_term_string"}},
          {"@context": "https://schema.org", "@type": "Organization", "@id": ORIGIN + "/#organization", "name": "FedCatalog", "url": ORIGIN + "/", "logo": ORIGIN + "/assets/fedcatalog-og.png",
           "description": "An independent reference connecting federal software authorization, government records and buying paths.", "founder": {"@id": ORIGIN + "/about/mark-flournoy/#mark"}}]
    return layout(db, path='/', title='FedCatalog | Federal Software in One Place', description='Search federal software across FedRAMP, DoD, OneGov, GSA, SEWP and cloud marketplaces. Find authorization details, vendors and government buying paths in one place.', body=body, jsonld=ld)

_all_changes = None
def load_changes_all():
    global _all_changes
    if _all_changes is None:
        try: _all_changes = json.load(open(os.path.join(DATA, 'changelog.json')))['data']['certprocessstatuschangelog']
        except Exception: _all_changes = []
    return _all_changes
_changes = None
def load_changes():
    global _changes
    if _changes is None:
        try:
            raw = json.load(open(os.path.join(DATA, 'changelog.json')))['data']['certprocessstatuschangelog']
            _changes = sorted([x for x in raw if x.get('transition_date') and x['transition_date'][:10] <= TODAY], key=lambda x: x['transition_date'], reverse=True)
        except Exception: _changes = []
    return _changes
def change_row(db, x):
    p = db['by_id'].get(x['product_id'])
    tone = 'tone-good' if re.search(r'authori|certified', x['to_status'], re.I) else ('tone-bad' if 'Delisted' in x['to_status'] else 'tone-warn')
    name = f'<a href="{url_product(p)}">{esc(x["cso"])}</a>' if p else esc(x['cso'])
    return f'<li><span class="date">{esc(fmt_date(x["transition_date"]))}</span><div><b>{name} <span class="{tone}">{esc(x["to_status"])}</span></b><small>{esc(x["csp"])}{(" · from " + esc(x["from_status"])) if x.get("from_status") else ""}{(" · " + esc(x["cert_path"]) + " path") if x.get("cert_path") else ""}</small></div></li>'

def recent_events(p, days=120):
    """Changelog entries for this offering in the last `days`, newest first."""
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    ev = [x for x in load_changes() if x.get('product_id') == p['id'] and x['transition_date'][:10] >= cutoff and (x.get('from_status') or '') != (x.get('to_status') or '')]
    return ev
def status_family(s):
    s = s or ''
    if re.search(r'certified|^authorized$|fedramp authorized', s, re.I) and 'Remediation' not in s: return 'authorized'
    if 'No Status Found' in s: return 'none'
    return 'other'
def page_product(db, p):
    v = db['vendors'][p['vendor_slug']]
    events = recent_events(p)
    conflict = bool(p.get('record_status'))
    others = [x for x in v['products'] if x['id'] != p['id']]
    sim = similar(db, p)
    runs = ' · '.join(RUNS[r] for r in p['runs']) if p['runs'] else (' · '.join(RUNS[r] for r in p['runs_named']) if p['runs_named'] else 'Not recorded')
    crumbs = [('FedCatalog', '/'), ('Software', '/software/'), (p['name'], None)]
    agency_chips = ''.join(f'<a class="chip" href="{url_agency(db["agency_by_name"][n])}">{esc(n)}</a>' if n in db['agency_by_name'] else f'<span class="chip muted">{esc(n)}</span>' for n in p['agencies'])
    fact_status_sub = (p['auth_type'] + ' path' + (' · ' + fmt_date(p['auth_date']) if p['auth_date'] else '')) if p['auth_type'] else ('Ready ' + fmt_date(p['ready_date']) if p['ready_date'] else '')
    onegov = onegov_for(db, p['vendor_slug']); dod = dod_rows_for(db, p['vendor_slug'])
    ag = len(p['agencies'])
    stat_ag = f'{ag} federal agency authorization{"" if ag == 1 else "s"}' if ag else 'No agency authorizations on record'
    details = [('Offering', esc(p['name']), 'FedRAMP ID ' + esc(p['id'])),
               ('Status', esc(p['status']), ' · '.join(x for x in [(p['auth_type'] + ' authorization path') if p['auth_type'] else '', ('authorized ' + fmt_date(p['auth_date'])) if p['auth_date'] else '', ('FedRAMP Ready ' + fmt_date(p['ready_date'])) if p['ready_date'] else ''] if x)),
               ('Impact level', esc(p['impact']), IMPACT_HELP.get(p['impact'], '')),
               ('Deployment', esc(p['deployment'] or '—'), ' · '.join(p['models'])),
               ('Runs on', esc(runs), ('From FedRAMP leveraged-system relationships.' + ((' Also named in the title: ' + ', '.join(RUNS[r] for r in p['runs_named'])) if p['runs_named'] else '')) if p['runs'] else ('Named in the offering title; no leveraged-system record' if p['runs_named'] else '')),
               ('Assessor (3PAO)', esc(p['assessor']), '') if p['assessor'] else None,
               ('Leveraged by', f'{nfmt(p["leveraged_by"])} other offerings', 'FedRAMP offerings built on this one') if p['leveraged_by'] else None,
               ('Government sales', f'<a href="mailto:{esc(p["sales_email"])}">{esc(p["sales_email"])}</a>', 'Contact published on the FedRAMP listing') if p['sales_email'] else None,
               ('Data as of', esc(fmt_date(db['meta'].get('last_change'))), 'FedRAMP Marketplace, refreshed daily')]
    matrix = ''.join(f'<li><dt>{t}</dt><dd>{val}{("<small>" + esc(sub) + "</small>") if sub else ""}</dd></li>' for t, val, sub in [d for d in details if d])
    body = f'''
<section class="panel narrow">
  {crumbs_html(crumbs)}
  <div class="phead" style="margin-top:16px">
    {monogram(p['vendor_key'])}
    <div><h1>{esc(p['name'])}</h1><p class="vend"><a href="{url_vendor(v)}">{esc(p['vendor_key'])}</a></p></div>
    <p class="one">{esc(first_sentence(p['desc']) if p['desc'] else 'FedRAMP lists this offering at the ' + p['status_label'] + ' stage; no description has been published yet.')}</p>
    <div class="stat">{status_label(p)}{('<span>' + esc(p['impact']) + '</span>') if p['impact'] else ''}<span>{esc(stat_ag)}</span></div>
    {(f'<p class="caution"><b>FedRAMP’s two files disagree about this offering.</b> FedRAMP’s status changelog recorded <b>{esc(p.get("record_status_event", ""))}</b> on {esc(fmt_date(p.get("status_event")))}, which FedCatalog shows as the current status. FedRAMP’s daily data record (refreshed {esc(fmt_date(db["meta"].get("last_change")))}) still shows <b>{esc(p["record_status"])}</b>; it usually trails the changelog by a week or two. Verify on the <a href="https://www.fedramp.gov/marketplace/products/{esc(p["id"])}/" target="_blank" rel="noopener noreferrer">FedRAMP Marketplace</a> before relying on either.</p>') if conflict else ''}
    {(f'<p class="caution"><b>Listed from FedRAMP’s status changelog.</b> FedRAMP recorded this offering as <b>{esc(p["status"])}</b> on {esc(fmt_date(p.get("status_event")))}{(" (" + esc(p["auth_type"]) + " path)") if p.get("auth_type") else ""}. FedRAMP’s daily data record has no entry for it yet, so category, impact level, hosting and agency details are not available. They will appear here when FedRAMP publishes them.</p>') if p.get('stub') else ''}
    {(f'<p class="caution"><b>No longer on the FedRAMP Marketplace.</b> FedRAMP’s status changelog recorded this offering as No Status Found on {esc(fmt_date(p.get("status_event")))}. FedRAMP does not publish a reason. This page is kept for reference; the offering is excluded from FedCatalog’s lists and counts.</p>') if p['status_code'] == 'delisted' and not conflict else ''}
    <div class="cta">{(f'<a class="primary" href="{esc(p["website"])}" target="_blank" rel="noopener noreferrer">Visit government offering</a>') if p['website'] else ''}<a href="#buy">How to buy</a><button class="copy" type="button" data-copy="{esc(copy_summary(p, runs))}">Copy summary</button></div>
  </div>
  <div class="facts">
    <div class="fact"><small>FedRAMP</small><b>{status_label(p)}</b><span>{esc(fact_status_sub)}</span></div>
    <div class="fact"><small>Impact</small><b>{esc(p['impact'] or '—')}</b><span>{esc(p['deployment'] or ('Not yet published' if p.get('stub') else ''))}</span></div>
    <div class="fact"><small>Runs on</small><b>{runs_text(p)}</b><span>{'FedRAMP record' if p['runs'] else ('From the offering title' if p['runs_named'] else 'Not recorded by FedRAMP')}</span></div>
    <div class="fact"><small>Agency authorizations</small><b>{ag}</b><span>{('Leveraged by ' + nfmt(p['leveraged_by']) + ' offerings') if p['leveraged_by'] else 'ATO or reuse on record'}</span></div>
  </div>
  <p class="prov">Source: FedRAMP Marketplace · refreshed {esc(fmt_date(db['meta'].get('last_change')))}{(' · DoD status: DoD Cyber Exchange · checked ' + esc(fmt_date(db['dod'].get('fetched')))) if dod else ''}{(' · OneGov: GSA ITVMO · checked ' + esc(fmt_date(db['onegov'].get('checked')))) if onegov else ''} · <a href="/methodology/">How the data works</a></p>
  <div class="section" id="buy"><h2>How to buy</h2><p class="sec-sub">Confirmed paths come from GSA and the FedRAMP record; searches are places to look.</p>{procurement_block(db, p, v)}<p class="note"><a href="https://www.fedramp.gov/marketplace/products/{esc(p['id'])}/" target="_blank" rel="noopener noreferrer">FedRAMP Marketplace listing ↗</a> · <a href="https://acrrepo.section508.gov/" target="_blank" rel="noopener noreferrer">Section 508 ACR Repository ↗</a> · <a href="https://sam.gov/search/?keywords={esc(p['vendor_key']).replace(' ', '%20')}" target="_blank" rel="noopener noreferrer">SAM.gov ↗</a></p></div>

  {(f'<div class="section"><h2>Government footprint</h2><p class="prose">{ag} {"agency has" if ag == 1 else "agencies have"} an authorization or reuse on record for this offering.</p><div class="chips">{agency_chips}</div></div>') if ag else ''}
  <div class="section"><h2>What it does</h2><p class="prose">{esc(trunc(p['desc'], 700)) if p['desc'] else 'FedRAMP has not published a description for this offering yet.'}</p><div class="chips">{''.join(f'<a class="chip" href="{url_category(db["fn_by_name"][f])}">{esc(f)}</a>' for f in p['functions'] if f in db['fn_by_name'])}</div></div>
  <div class="section"><h2>Authorization details</h2><dl class="matrix"><ul>{matrix}</ul></dl><p class="note">An authorization belongs to this specific offering and boundary; the vendor’s other offerings are listed separately. Source: FedRAMP Marketplace · refreshed {esc(fmt_date(db['meta'].get('last_change')))}.</p>
  {(f'<h3 class="h3">DoD Impact Level listings for {esc(v["name"])}</h3><ul class="awards">{"".join(dod_row_html(r, False, db) for r in dod)}</ul><p class="note">DoD listings name their own offering; they are not automatically the same boundary as this FedRAMP offering. <a href="/dod/">All DoD listings</a>.</p>') if dod else ''}</div>
  {(f'<div class="section"><h2>Other offerings from {esc(v["name"])}</h2><div class="rows">{"".join(product_row(x) for x in others[:8])}</div></div>') if others else ''}
  {(f'<div class="section"><h2>Similar software</h2><div class="rows">{"".join(product_row(x) for x in sim)}</div></div>') if sim else ''}
  {correction_link('Offering', p['name'] + ' (' + p['vendor_key'] + ')', p['id'], url_product(p))}
</section>'''
    dupname = sum(1 for x in db['products'] if x['name'] == p['name']) > 1
    title = f'{p["name"]}{(" (" + p["impact"] + ", " + p["id"] + ")") if dupname else ""}: FedRAMP, Agencies & Procurement | FedCatalog'
    desc = f'{p["name"]} by {p["vendor_key"]}: {p["status"]}' + (f' at the {p["impact"]} impact level' if p['impact'] else '') + f', {ag} agency authorization record{"" if ag == 1 else "s"}, runs on {runs.lower() if runs != "Not recorded" else "unrecorded platforms"}, and where to buy it.'
    return layout(db, path=url_product(p), title=title, description=desc[:300], body=body, jsonld=[crumbs_ld(crumbs)])
def copy_summary(p, runs):
    return '\n'.join(x for x in [f'{p["vendor_key"]} — {p["name"]}', f'{p["status"]} · {p["impact"]} · {p["deployment"]}', f'Runs on: {runs}', f'Agency authorizations: {len(p["agencies"])}', 'Categories: ' + ', '.join(p['functions']), f'Gov offering: {p["website"]}' if p['website'] else '', f'FedCatalog: {ORIGIN}{url_product(p)}'] if x)

def page_vendor(db, v):
    s = vendor_summary(v); onegov = onegov_for(db, v['slug']); dod = dod_rows_for(db, v['slug'])
    crumbs = [('FedCatalog', '/'), ('Vendors', '/vendors/'), (v['name'], None)]
    dod_pa = sorted({r['il'] for r in dod if r['status'].startswith('Provisional Authorization')})
    stat = f'<span>{s["authorized"]} authorized</span><span>up to {esc(s["best"]["impact"])}</span><span>{len(s["agencies"])} {"agency" if len(s["agencies"]) == 1 else "agencies"}</span>' + (f'<span>DoD {"/".join(dod_pa)}</span>' if dod_pa else '') + ('<span class="tone-accent">OneGov agreement</span>' if onegov else '')
    comps = defaultdict(int)
    for p in v['products']:
        for x in similar(db, p, 12):
            if x['vendor_slug'] != v['slug']: comps[x['vendor_slug']] += 1
    comp_vendors = [db['vendors'][sl] for sl, _ in sorted(comps.items(), key=lambda t: -t[1])[:8] if sl in db['vendors']]
    body = f'''
<section class="panel narrow">
  {crumbs_html(crumbs)}
  <div class="phead" style="margin-top:16px">
    {monogram(v['name'])}
    <div><h1>{esc(v['name'])}</h1><p class="vend">{len(v['products'])} FedRAMP offering{'' if len(v['products']) == 1 else 's'}</p></div>
    <div class="stat">{stat}</div>
    <div class="cta">{(f'<a class="primary" href="{esc(v["website"])}" target="_blank" rel="noopener noreferrer">Visit government page</a>') if v['website'] else ''}</div>
  </div>
  <p class="prov">Sources: FedRAMP Marketplace · refreshed {esc(fmt_date(db['meta'].get('last_change')))}{(' · DoD Cyber Exchange · checked ' + esc(fmt_date(db['dod'].get('fetched')))) if dod else ''}{(' · GSA OneGov · checked ' + esc(fmt_date(db['onegov'].get('checked')))) if onegov else ''} · USAspending.gov · fetched live · <a href="/methodology/">How the data works</a></p>
  {(f'<div class="section" id="onegov"><h2>Special federal purchasing</h2><p class="prose">GSA has negotiated a government-wide OneGov agreement with this vendor. Agencies still follow their normal FAR 8.4 ordering procedures.</p><ul class="awards">{"".join(onegov_row_html(a, False, db) for a in onegov)}</ul><p class="source">Source: GSA ITVMO OneGov · checked {esc(fmt_date(db["onegov"].get("checked")))} · <a href="/onegov/">all agreements</a></p></div>') if onegov else ''}
  {(f'<div class="section" id="dod"><h2>DoD Impact Level</h2><p class="prose">Listings on the DoD Cyber Exchange for this vendor, with the exact DoD status. These are separate from FedRAMP and belong to the named DoD offering.</p><ul class="awards">{"".join(dod_row_html(r, False, db) for r in dod)}</ul><p class="source">Source: DoD Cyber Exchange, Current Authorized CSOs · fetched {esc(fmt_date(db["dod"].get("fetched")))} · <a href="/dod/">all listings</a></p></div>') if dod else ''}
  <div class="section"><h2>Offerings</h2><div class="rows">{''.join(product_row(x) for x in sorted(v['products'], key=lambda p: -len(p['agencies'])))}</div></div>
  <div class="section" data-purchasing data-vendor="{esc(v['name'])}" data-terms="{esc(json.dumps(spend_terms(v)))}" data-fedramp-agencies="{len(s['agencies'])}"><h2>Government purchasing (observed)</h2><p class="note">Federal award records that mention this vendor load here from USAspending.gov when the page opens. <noscript>This section needs JavaScript; the underlying data is public at USAspending.gov.</noscript></p></div>
  <div class="section" id="buy"><h2>How to buy</h2><p class="sec-sub">Confirmed paths come from GSA and the FedRAMP record; searches are places to look.</p>{procurement_block(db, {'website': v['website']}, v)}</div>
  <div class="section"><h2>Categories</h2><div class="chips">{''.join(f'<a class="chip" href="{url_category(db["fn_by_name"][f])}">{esc(f)}</a>' for f in s['fns'] if f in db['fn_by_name'])}</div></div>
  {(f'<div class="section"><h2>Compare</h2><div class="chips">{"".join(f"<a class=" + chr(34) + "chip" + chr(34) + f" href=" + chr(34) + f"/search/?q={esc(v['name'])}%20vs%20{esc(c['name'])}" + chr(34) + f">{esc(v['name'])} vs {esc(c['name'])}</a>" for c in comp_vendors)}</div></div>') if comp_vendors else ''}
  {correction_link('Vendor', v['name'], '', url_vendor(v))}
</section>'''
    n = len(v['products'])
    title = f'{v["name"]} Federal Software, FedRAMP & Procurement | FedCatalog'
    desc = f'{v["name"]}: {n} FedRAMP offering{"" if n == 1 else "s"} ({s["authorized"]} authorized, up to {s["best"]["impact"]}), {len(s["agencies"])} agency authorization record{"" if len(s["agencies"]) == 1 else "s"}' + (', a GSA OneGov agreement' if onegov else '') + (', DoD ' + '/'.join(dod_pa) + ' listings' if dod_pa else '') + ', observed federal awards and procurement links.'
    return layout(db, path=url_vendor(v), title=title, description=desc[:300], body=body, jsonld=[crumbs_ld(crumbs)])
AMBIGUOUS = {'box', 'elastic', 'monday', 'notion', 'asana', 'slack', 'zoom', 'medallia', 'workday', 'unison', 'sprout', 'sage', 'ivanti', 'planet', 'granicus'}
def spend_terms(v):
    key = v['name'].strip()
    if len(key) <= 3 or key.lower() in AMBIGUOUS:
        names = []
        for p in v['products']:
            n = re.sub(r'\s+-\s+.*$', '', re.sub(r'\s*\(.*?\)\s*', ' ', p['name'])).strip()
            if len(n) > 3 and n not in names: names.append(n)
        return names[:3] or [key]
    return [key]

def page_list(db, *, path, crumbs, title, sub, products, meta_title, meta_desc, head_extra=''):
    return layout(db, path=path, title=meta_title, description=meta_desc, body=results_page(crumbs, title, sub, products, head_extra), jsonld=[crumbs_ld(crumbs)])

def page_agency(db, a):
    crumbs = [('FedCatalog', '/'), ('Agencies', '/agencies/'), (a['name'], None)]
    fn = defaultdict(int)
    for p in a['products']:
        for f in p['functions']: fn[f] += 1
    top = sorted(fn.items(), key=lambda t: -t[1])[:6]
    head = ('<p class="sec-sub" style="margin:-2px 0 12px">See the software with authorization records at this agency, then filter by category, impact level and cloud environment.</p><div class="chips" style="margin:-4px 0 12px">' + ''.join(f'<a class="chip" href="{url_category(db["fn_by_name"][f])}">{esc(f)} · {c}</a>' for f, c in top if f in db['fn_by_name']) + '</div>'
            + f'<p class="note" style="margin:0 0 12px"><a href="https://www.fedramp.gov/marketplace/agencies/{esc(a["id"])}/" target="_blank" rel="noopener noreferrer">This agency on the FedRAMP Marketplace ↗</a></p>')
    n = len(a['products'])
    return page_list(db, path=url_agency(a), crumbs=crumbs, title=a['name'], sub=f'{nfmt(n)} authorized offerings' + (f' · part of {a["parent"]}' if a['sub'] else ''), products=sorted(a['products'], key=lambda p: -len(p['agencies'])),
                     meta_title=f'{a["name"]} Authorized Software | FedCatalog', meta_desc=f'{n} cloud service offerings with a FedRAMP authorization or reuse record at {a["name"]}, with impact levels, hosting platforms and procurement links.', head_extra=head)
def page_category(db, f):
    crumbs = [('FedCatalog', '/'), ('Browse', '/categories/'), (f['name'], None)]
    products = sorted([p for p in db['products'] if f['name'] in p['functions'] and p['status_code'] != 'delisted'], key=lambda p: -len(p['agencies']))
    short = f['name'].replace(' (AI)', '').replace(' (CMS)', '').replace(' (CRM)', '').replace(' (GRC)', '').replace(' (VPN)', '').replace(' (MDM)', '')
    return page_list(db, path=url_category(f), crumbs=crumbs, title=f['name'], sub=CAT_DESC.get(f['name'], ''), products=products,
                     meta_title=f'Federal {short} Software | FedCatalog', meta_desc=f'{len(products)} FedRAMP cloud offerings in {f["name"]}: {CAT_DESC.get(f["name"], "").lower()}. Status, impact level, agency adoption, hosting platform and procurement links for each.')

def page_static(db, path, title, meta_title, meta_desc, body_html, noindex=False, jsonld=None):
    return layout(db, path=path, title=meta_title, description=meta_desc, body=f'<section class="panel narrow"><article class="doc">{body_html}</article></section>', noindex=noindex, jsonld=jsonld)

# ------------------------------------------------------------------ static copy
ABOUT = '''
<div class="about">
<div>
<h1>Hi, I’m Mark.</h1>
<p>I spent six years supporting Federal Partner Sales at AWS after sales roles at F5, Red Hat, Western Digital, and STEC. Before that I spent 20 years in the Marines.</p>
<p>I’ve been the seller, the partner guy, and the person on the government side trying to work out what we could actually buy and where.</p>
<p>Federal software information is scattered across FedRAMP, the DoD Cyber Exchange, GSA, USAspending and the cloud marketplaces, and none of them talk to each other. FedCatalog puts the useful parts in one place: what a product is, whether it’s authorized, where it runs, and the ways government can buy it.</p>
<p>I don’t rank vendors, sell placement, or decide which product is “best.” The facts come from public sources, and every page says where they came from.</p>
<p>There’s no company behind this. It’s just me. If something is wrong or missing, email me at <a href="mailto:mark@fedcatalog.com">mark@fedcatalog.com</a>.</p>
<p><a href="https://www.linkedin.com/in/markflournoy/" target="_blank" rel="noopener noreferrer">LinkedIn →</a> · <a href="/methodology/">How the data works →</a></p>
</div>
<figure class="photo"><img src="/assets/mark.jpg" alt="Mark Flournoy" width="640" height="640"><figcaption>That’s me. I’m friendlier in person than the photograph suggests.</figcaption></figure>
</div>'''
MARK = '''
<div class="about">
<div>
<h1>Mark Flournoy</h1>
<p class="lede">I build and maintain FedCatalog.</p>
<p>Six years supporting Federal Partner Sales at AWS, sales roles at F5, Red Hat, Western Digital and STEC before that, and 20 years in the Marines before any of it. I’ve sat on both sides of the federal buying table, which is mostly why this site exists.</p>
<p><a class="btn-link" href="https://www.linkedin.com/in/markflournoy/" target="_blank" rel="noopener noreferrer">LinkedIn →</a></p>
<p><a href="/about/">About FedCatalog</a> · <a href="/contact/">Contact</a></p>
</div>
<figure class="photo"><img src="/assets/mark.jpg" alt="Mark Flournoy" width="640" height="640"></figure>
</div>'''
METHODOLOGY = '''
<h1>Data Sources &amp; Methodology</h1>
<p class="lede">FedCatalog is designed around a simple rule: show what the public evidence supports and label everything else clearly.</p>
<p><strong>FedCatalog doesn’t rank vendors, sell placement, or decide what software is “best.”</strong> It organizes public information so buyers and sellers can understand the path from authorization to procurement.</p>
<p><strong>Nothing here is edited by vendors.</strong> Authorization, agency records and federal spending data come from public government sources; procurement links open searches on the marketplaces and vehicles themselves.</p>
<p>Independence is shown structurally rather than claimed: no sponsored ranking, no “best vendors” lists, no preferred marketplace, every important fact linked to its source, a date on the data, this methodology in the open, corrections encouraged, and a real name on the <a href="/about/">About page</a>.</p>
<h2>FedRAMP Marketplace</h2>
<p><strong>Source:</strong> the FedRAMP Marketplace public data published by GSA (<a href="https://www.fedramp.gov/marketplace/" target="_blank" rel="noopener noreferrer">fedramp.gov/marketplace</a>), which FedRAMP republishes as machine-readable files updated daily.</p>
<p><strong>Imported:</strong> vendor, offering name, status (Authorized, Ready, In Process), impact level, authorization path and dates, deployment and service model, business categories, agency authorization and reuse records, description, website, assessor, published sales contact, and which offerings leverage which authorized platforms.</p>
<p><strong>Refresh:</strong> daily. Each page shows the date of the data it was built from.</p>
<p><strong>Two files, one lag:</strong> FedRAMP publishes a daily data record and a separate status changelog. The changelog usually runs ahead of the record by a week or two, in both directions: a new authorization can appear in the changelog while the record still says In Process, and a delisting can appear in the changelog while the record still says Authorized. FedCatalog treats the changelog as the current status (the FedRAMP Marketplace itself follows it: delisted offerings return a 404 there), lists the offering’s recent changelog events under Authorization details, and puts a visible notice on the page whenever the two files disagree. Offerings that FedRAMP has recorded in the changelog within the last year but not yet in the daily record — including Initial Implementation listings, which FedRAMP began publishing in July 2026 — appear as light records with what is known. Delisted offerings keep a reference page but are excluded from lists and counts.</p>
<p><strong>Meaning:</strong> an authorization belongs to the specific offering and security boundary listed, not to the vendor or to the vendor’s other products. Agency authorization records show that an agency issued or reused an authorization; they do not by themselves show that the agency purchased or deployed the product.</p>
<p><strong>Runs on:</strong> FedRAMP records which authorized infrastructure platform an offering leverages. FedCatalog shows that relationship as “runs on.” Where a platform is only named in the offering’s title and no relationship is on record, it is shown with a dashed underline and labeled as such. Running on a cloud is not the same as being sold in that cloud’s marketplace.</p>
<h2>DoD Cyber Exchange</h2>
<p><strong>Source:</strong> the “Current Authorized CSOs” table on the DoD Cyber Exchange (<a href="https://public.cyber.mil/dccs/cso/" target="_blank" rel="noopener noreferrer">public.cyber.mil</a>).</p>
<p><strong>Meaning:</strong> FedCatalog preserves the exact DoD status string: Provisional Authorization, Provisional Authorization to Connect (PA-C), IATT – Not Authorized for Operational Use, or Suspended. These are never rewritten into a FedCatalog score. A Provisional Authorization is not an agency ATO. Where the listed expiration date has passed, the site says so and asks you to verify on the DoD page. A DoD listing may describe a different offering or boundary from the vendor’s FedRAMP listing; FedCatalog links DoD rows to vendors, not to specific FedRAMP offerings.</p>
<h2>GSA OneGov</h2>
<p><strong>Source:</strong> GSA’s IT Vendor Management Office list of current OneGov agreements (<a href="https://itvmo.gsa.gov/onegov/" target="_blank" rel="noopener noreferrer">itvmo.gsa.gov/onegov</a>), curated by hand and checked against GSA’s feed for new agreements.</p>
<p><strong>Meaning:</strong> discount, expiry, vehicle, eligibility and included products are shown as GSA publishes them. Agreements are linked to vendors only where the match is clear. Ordering details are behind a government login; agencies still follow their ordinary FAR 8.4 ordering procedures, and pricing and eligibility should be confirmed with GSA. Expiry dates matter and are shown.</p>
<h2>USAspending</h2>
<p><strong>Source:</strong> the USAspending.gov API, queried live when a vendor page opens, for federal prime contract records (award types A–D) whose recipient name or award description mentions the vendor or, for short or ambiguous names, its offering names. The search terms used are printed on the page.</p>
<p><strong>Meaning:</strong> these figures are an observed floor, not a vendor revenue estimate. Most software is bought through resellers whose award descriptions may not name the software vendor; many descriptions are generic; name matching can undercount or occasionally match the wrong thing; and obligations are not bookings or revenue. FedCatalog therefore shows, separately: obligations on awards that mention the vendor; the portion paid directly to the vendor entity; who received the money (vendor direct versus reseller or prime); and the number of buying departments, next to the number of FedRAMP authorization records, because approved is not the same as purchased.</p>
<h2>GSA eLibrary, NASA SEWP, Section 508 ACR Repository, SAM.gov</h2>
<p>Until records from these sources are joined directly to FedCatalog data, the links on product and vendor pages open searches or lookup pages. They do not mean FedCatalog has confirmed that a product is available on a vehicle or has an accessibility conformance report.</p>
<h2 id="procurement">Procurement links</h2>
<p>Each offering’s “Buying paths” section shows, in order: confirmed paths (the GSA OneGov agreement, exact marketplace listings matched to this FedRAMP offering, and the vendor’s government sales page from the FedRAMP record); the vendor’s other marketplace listings and seller pages, which are the vendor’s own but not matched to a specific boundary; and searches for the vendor on marketplaces and vehicles where no listing is on file yet. A listing is recorded only after opening it on the marketplace and confirming the publisher, or after a vendor supplies it and FedCatalog reviews it (labeled vendor-supplied); it is tied to a FedRAMP offering only when the listing clearly serves that boundary, such as a GovCloud listing. Where nothing is on file the page says “exact listing not yet verified.” Commercial and government editions can differ; confirm the edition and boundary on the listing itself.</p>
<h2>Cloud marketplaces</h2>
<p>AWS Marketplace, Azure Marketplace and Google Cloud Marketplace links open a search for the vendor on each marketplace. Listing availability, editions, terms and private offers are confirmed there.</p>
<h2>Corrections</h2>
<p>Anyone can <a href="/contact/">submit a correction</a>. Public-source facts are corrected by re-checking the source. Vendor-supplied links are reviewed before publication.</p>
<h2>Editorial policy</h2>
<ul>
<li>No pay-to-rank. No vendor is placed or ranked because it sponsors the site.</li>
<li>No star ratings, reviews, or any “federal readiness” score.</li>
<li>Facts come from public sources, not vendor claims.</li>
<li>Comparisons show factual differences and never declare a winner.</li>
<li>Corrections are welcomed and acknowledged.</li>
</ul>
<p>FedCatalog is maintained by <a href="/about/">Mark Flournoy</a>.</p>'''
PRIVACY = '''
<h1>Privacy</h1>
<p class="lede">Plain English, because there isn’t much to say.</p>
<p>FedCatalog does not require an account.</p>
<p>FedCatalog does not sell personal information.</p>
<p>Searches performed in the catalog run in your browser and are not intentionally stored by FedCatalog.</p>
<p>The site’s hosting provider may maintain ordinary technical logs such as IP address, browser information and requested URLs.</p>
<p>If you email FedCatalog or submit a listing correction, the information you provide may be retained as necessary to review the request and respond.</p>
<p>FedCatalog links to third-party sites including government sources, software vendors and cloud marketplaces. Those sites have their own privacy practices. Vendor pages request public award data from USAspending.gov directly from your browser; that request is subject to USAspending’s own policies.</p>
<p>FedCatalog uses Google Analytics to understand which pages are read and which searches are run, with IP anonymization enabled. Google may set cookies for that purpose and processes the data under its own policies. FedCatalog respects browser “Do Not Track” and Global Privacy Control signals, in which case analytics does not load. No advertising or cross-site tracking is used.</p>
<p><strong>Last updated:</strong> September 2026 · <a href="mailto:mark@fedcatalog.com">mark@fedcatalog.com</a></p>'''
TERMS = '''
<h1>Terms of Use</h1>
<p class="lede">FedCatalog is an independent reference. It is not a government agency and is not affiliated with or endorsed by GSA, FedRAMP, the Department of Defense, AWS, Microsoft, Google or any software vendor listed in the catalog.</p>
<h2>Informational use</h2>
<p>FedCatalog is provided for informational and reference purposes. It is not procurement, legal, compliance or security advice, and it does not determine whether any product is suitable for a particular requirement.</p>
<h2>Accuracy</h2>
<p>The catalog is assembled from public sources that change daily. FedCatalog does not guarantee that any information is complete, current or error-free. Verify critical information with the authoritative source, which every page names, before relying on it.</p>
<h2>External links</h2>
<p>Links to government, vendor and marketplace sites are provided for convenience and do not imply endorsement. Marketplace and contract-vehicle links open searches; they do not confirm availability.</p>
<h2>Trademarks</h2>
<p>Vendor and product names and trademarks remain the property of their respective owners and are used only to identify the offerings described.</p>
<h2>Limitation of liability</h2>
<p>To the extent permitted by law, FedCatalog and its author are not liable for any loss arising from use of, or reliance on, the site or its content.</p>
<h2>Changes</h2>
<p>FedCatalog may correct, update or remove content at any time. These terms may be updated; the date below reflects the current version.</p>
<p><strong>Effective:</strong> September 2026 · <a href="mailto:mark@fedcatalog.com">mark@fedcatalog.com</a></p>'''
def CONTACT():
    return f"""
<h1>Contact</h1>
<h2>General questions</h2>
<p><a href="mailto:{EMAIL}">{EMAIL}</a></p>
<h2>Corrections</h2>
<p>If a FedRAMP, DoD or OneGov fact looks wrong, email the page link and what you believe is incorrect. Public-source facts are corrected by re-checking the source; FedCatalog does not edit authorization, agency or spending data by hand.</p>
<h2>Vendors</h2>
<p>FedCatalog links to a search for your company on each marketplace and vehicle rather than to individual listings, so there is nothing to submit. If your FedRAMP record’s website is wrong or missing, correct it with FedRAMP; FedCatalog picks up the change on its next refresh.</p>"""

# ------------------------------------------------------------------ assets
def write(path, content):
    full = os.path.join(DIST, path.lstrip('/'))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, 'w', encoding='utf-8') as f: f.write(content)
def write_page(path, html_text):
    write(path.rstrip('/') + '/index.html' if path != '/' else 'index.html', html_text)

def build_assets(db):
    css = open(os.path.join(SRC, 'templates', 'site.css')).read()
    css += '''
/* ---------- Static-site additions ---------- */
.skip { position: absolute; left: -999px; top: 8px; background: var(--text); color: #fff; padding: 8px 12px; border-radius: 8px; z-index: 100; }
.skip:focus { left: 8px; }
.searchbar[hidden] { display: none; }
.doc h1 { font-size: 34px; font-weight: 700; letter-spacing: -.03em; line-height: 1.1; margin: 10px 0 14px; }
.doc h2 { font-size: 22px; font-weight: 700; letter-spacing: -.02em; margin: 30px 0 8px; }
.doc p { font-size: 16px; line-height: 1.6; margin: 0 0 12px; max-width: 66ch; }
.doc p.lede { font-size: 18px; color: var(--secondary); }
.doc ul { margin: 0 0 12px 20px; list-style: disc; } .doc li { margin: 4px 0; line-height: 1.55; }
.doc a { color: var(--orange-hover); }
.about { display: grid; grid-template-columns: 1fr; gap: 24px; align-items: start; }
.about .photo { margin: 0; max-width: 150px; }
.about .photo img { display: block; width: 100%; height: auto; border-radius: 14px; filter: grayscale(1); box-shadow: 0 1px 2px rgba(0,0,0,.06), 0 10px 30px rgba(0,0,0,.10); }
.about .photo figcaption { margin-top: 10px; font-size: 13px; color: var(--secondary); line-height: 1.45; }
@media (min-width: 720px) { .about { grid-template-columns: minmax(0, 1fr) 140px; gap: 40px; } .about .photo { max-width: none; } }
.btn-link { display: inline-flex; align-items: center; min-height: 44px; padding: 0 16px; border-radius: 11px; background: var(--orange); color: #fff !important; text-decoration: none; font-weight: 600; }
.foot-grid { display: grid; gap: 16px; grid-template-columns: 1fr; font-size: 14px; line-height: 1.6; }
.foot-grid a { text-decoration: none; color: var(--text); } .foot-grid a:hover { color: var(--orange-hover); }
.foot-muted { color: var(--secondary); font-size: 13px; }
.site-footer p.foot-muted { margin-top: 16px; }
.site-footer p.foot-muted a { color: var(--text); }
.az { display: grid; grid-template-columns: 1fr; }
.az a { display: grid; grid-template-columns: 1fr auto; gap: 4px 12px; padding: 12px 0; border-bottom: 1px solid var(--separator); text-decoration: none; align-items: center; }
.az a b { font-size: 16px; font-weight: 600; } .az a small { grid-column: 1; font-size: 13px; color: var(--secondary); } .az a span { grid-column: 2; grid-row: 1 / span 2; color: var(--tertiary); font-size: 18px; }
.az a:hover b { color: var(--orange-hover); }
.letters { display: flex; flex-wrap: wrap; gap: 4px; margin: 10px 0 16px; } .letters a { min-width: 32px; min-height: 32px; display: inline-flex; align-items: center; justify-content: center; border: 1px solid var(--separator-2); border-radius: 8px; text-decoration: none; font-size: 13px; font-weight: 600; }
.procs { border-top: 1px solid var(--separator); }
.proc { display: grid; grid-template-columns: 1fr auto; gap: 12px; align-items: center; padding: 12px 0; border-bottom: 1px solid var(--separator); }
.proc.is-confirmed { background: var(--canvas); border-radius: 10px; padding: 12px 14px; border-bottom: 0; margin-bottom: 6px; }
.proc.is-confirmed b::before { content: "✓ "; color: var(--authorized); }
.proc.is-vendor b::before { content: "● "; color: var(--secondary); }
.proc.is-vendor-supplied { background: var(--canvas); border-radius: 10px; padding: 12px 14px; border-bottom: 0; margin-bottom: 6px; }
.proc.is-vendor-supplied b::before { content: "○ "; color: var(--secondary); }
.procs.is-quiet .proc b { font-weight: 500; } .procs.is-quiet .proc a { color: var(--secondary); } .procs.is-quiet .proc a:hover { color: var(--orange-hover); }
.proc b { display: block; font-size: 15px; font-weight: 600; } .proc small { display: block; font-size: 13px; color: var(--secondary); line-height: 1.4; }
.proc a { font-size: 14px; font-weight: 600; text-decoration: none; color: var(--orange-hover); white-space: nowrap; }
.pillars { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; max-width: 800px; margin: 14px auto 0; }
.pillars a { display: block; padding: 8px 10px; border: 1px solid var(--separator); border-radius: 10px; text-decoration: none; text-align: left; min-width: 0; }
.pillars a small { display: block; font-size: 10px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: var(--secondary); }
.pillars a.is-key { border-color: var(--separator-2); } .pillars a.is-key small { color: var(--orange); } .pillars a b { display: block; font-size: 13px; font-weight: 600; margin-top: 1px; line-height: 1.25; }
.pillars a:hover { border-color: var(--text); }
.pillars a.is-key:hover { border-color: var(--orange); }
@media (min-width: 720px) { .pillars a { padding: 12px 14px; } .pillars a b { font-size: 15px; } }
.hero .kicker { font-size: 13px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: var(--orange-hover); margin-bottom: 10px; }
.hero .counts { margin-top: 10px; font-size: 14px; color: var(--secondary); }
.hero .cred { max-width: 800px; margin: 12px auto 0; font-size: 13px; color: var(--secondary); line-height: 1.5; }
.hero .cred a { font-weight: 600; color: var(--orange); text-decoration: none; white-space: nowrap; }
.hero .quick { display: flex; flex-wrap: wrap; justify-content: center; gap: 4px 0; margin-top: 12px; font-size: 13px; max-width: none; }
.hero .quick a { color: var(--secondary); text-decoration: none; font-weight: 500; padding: 4px 0; min-height: 0; border: 0; border-radius: 0; }
.hero .quick a + a::before { content: "·"; color: var(--tertiary); margin: 0 10px; }
.hero .quick a:hover { color: var(--orange); }
.signup { margin-top: 24px; padding: 18px; border: 1px solid var(--separator); border-radius: 14px; background: var(--canvas); }
.signup h2 { font-size: 18px; font-weight: 700; letter-spacing: -.02em; margin: 0 0 4px; }
.signup p { font-size: 14px; color: var(--secondary); line-height: 1.5; margin: 0 0 12px; max-width: 66ch; }
.signup form { display: flex; gap: 8px; flex-wrap: wrap; }
.signup input { flex: 1 1 220px; min-height: 44px; padding: 0 12px; border: 1px solid var(--separator-2); border-radius: 10px; background: var(--page); font: inherit; }
.signup input:focus-visible { outline: none; border-color: var(--orange); box-shadow: 0 0 0 4px var(--orange-soft); }
.signup button { min-height: 44px; padding: 0 16px; border: 0; border-radius: 10px; background: var(--orange); color: #fff; font-weight: 600; cursor: pointer; }
.signup button:hover { background: var(--orange-hover); }
.signup small { display: block; margin-top: 8px; font-size: 12px; color: var(--secondary); }
.caution { grid-column: 1 / -1; margin-top: 4px; padding: 12px 14px; border: 1px solid #E8C9A0; background: #FFF7EA; border-radius: 12px; font-size: 14px; line-height: 1.5; color: var(--text); }
.caution a { color: var(--orange-hover); }
.agency-hits { margin: 0 0 18px; } .agency-hits .cat { border-top: 1px solid var(--separator); }
.lost { text-align: center; padding-top: 48px; }
.lost .shrug { font-size: 56px; line-height: 1; color: var(--secondary); margin: 0 0 18px; font-family: -apple-system, "Segoe UI", Roboto, sans-serif; }
.lost h1 { font-size: 32px; font-weight: 700; letter-spacing: -.03em; margin: 0 0 10px; }
.lost p { color: var(--secondary); max-width: 48ch; margin: 0 auto; font-size: 16px; }
.lost .search { max-width: 560px; margin: 22px auto 0; }
.lost .links { margin-top: 18px; font-size: 14px; } .lost .links a { color: var(--text); text-decoration: none; font-weight: 500; } .lost .links a:hover { color: var(--orange-hover); }
@media (min-width: 720px) { .lost { padding-top: 80px; } .lost .shrug { font-size: 72px; } .lost h1 { font-size: 40px; } }
.correct { margin-top: 36px; padding-top: 16px; border-top: 1px solid var(--separator); font-size: 13px; color: var(--secondary); } .correct a { color: var(--orange-hover); }
.prov { margin-top: 10px; font-size: 13px; color: var(--secondary); line-height: 1.5; } .prov a { color: var(--orange-hover); }
.builtby { border-top: 1px solid var(--separator); padding-top: 22px; } .builtby h2 { font-size: 22px; font-weight: 700; letter-spacing: -.02em; } .builtby p { margin-top: 8px; font-size: 16px; line-height: 1.55; max-width: 66ch; color: var(--secondary); } .builtby a { color: var(--orange-hover); font-weight: 600; text-decoration: none; }
.hero .try a { color: var(--text); font-weight: 600; text-decoration: none; } .hero .try a:hover { color: var(--orange-hover); }
@media (min-width: 720px) { .foot-grid { grid-template-columns: 1fr auto; } .az { grid-template-columns: 1fr 1fr; gap: 0 32px; } }
'''
    write('assets/site.css', css)
    write('assets/site.js', open(os.path.join(SRC, 'templates', 'site.js')).read())
    shutil.copy(os.path.join(SRC, 'assets', 'mark.jpg'), os.path.join(DIST, 'assets', 'mark.jpg'))
    write('assets/analytics.js', open(os.path.join(SRC, 'templates', 'analytics.js')).read())
    write('assets/site-text.js', open(os.path.join(SRC, 'templates', 'site-text.js')).read())
    write('assets/signup.js', open(os.path.join(SRC, 'templates', 'signup.js')).read())
    # search index (compact)
    idx = [dict(id=p['id'], u=url_product(p), n=p['name'], v=p['vendor_key'], vs=p['vendor_slug'], f=p['functions'], s=p['status_code'], sl=p['status_label'], i=p['impact'], fam=p['families'], r=p['runs'], rn=p['runs_named'], a=len(p['agencies']), d=trunc(p['desc'], 140), dod=p.get('_dod', []), og=1 if p.get('_onegov') else 0) for p in db['products']]
    vend = [dict(n=v['name'], u=url_vendor(v), c=len(v['products']), dod=[dict(il=r['il'], st=r['status'], cso=r['cso']) for r in dod_rows_for(db, v['slug'])], og=1 if onegov_for(db, v['slug']) else 0) for v in db['vendors'].values()]
    ags = [dict(n=a['name'], p=a['parent'] if a['sub'] else '', u=url_agency(a), c=len(a['products'])) for a in db['agencies']]
    write('assets/search-index.json', json.dumps({'products': idx, 'vendors': vend, 'agencies': ags, 'functions': [f['name'] for f in db['functions']], 'catUrls': {f['name']: url_category(f) for f in db['functions']}}, ensure_ascii=False, separators=(',', ':')))
    # favicon + touch icon + OG image
    write('assets/favicon.svg', '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#1D1D1F"/><text x="32" y="41" text-anchor="middle" font-family="-apple-system,Inter,Segoe UI,sans-serif" font-size="28" font-weight="700" fill="#FFFFFF">FC</text><rect x="14" y="48" width="36" height="4" rx="2" fill="#F25F3A"/></svg>')
    try:
        from PIL import Image, ImageDraw, ImageFont
        def font(size):
            for cand in ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf']:
                if os.path.exists(cand): return ImageFont.truetype(cand, size)
            return ImageFont.load_default()
        def fontr(size):
            for cand in ['/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']:
                if os.path.exists(cand): return ImageFont.truetype(cand, size)
            return ImageFont.load_default()
        def fontb(size):
            for cand in ['/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf']:
                if os.path.exists(cand): return ImageFont.truetype(cand, size)
            return ImageFont.load_default()
        def mark(size):
            """The FC mark: charcoal rounded square, white FC, orange bar. Same design as the favicon."""
            m = Image.new('RGBA', (size, size), (0, 0, 0, 0)); md = ImageDraw.Draw(m)
            md.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * .22), fill='#1D1D1F')
            md.text((size / 2, size * .46), 'FC', font=fontb(int(size * .44)), fill='#FFFFFF', anchor='mm')
            md.rounded_rectangle([size * .22, size * .74, size * .78, size * .80], radius=int(size * .03), fill='#F25F3A')
            return m
        # Open Graph image 1200x630
        img = Image.new('RGB', (1200, 630), '#FFFFFF'); d = ImageDraw.Draw(img)
        d.rectangle([0, 0, 1200, 10], fill='#F25F3A')
        img.paste(mark(96), (80, 96), mark(96))
        d.text((196, 118), 'FedCatalog', font=fontb(56), fill='#1D1D1F')
        d.text((80, 262), 'Federal Software', font=fontb(88), fill='#1D1D1F')
        d.text((80, 362), 'in One Place', font=fontb(88), fill='#1D1D1F')
        d.text((80, 490), 'FedRAMP, DoD, OneGov, GSA, SEWP and marketplaces. Connected.', font=fontr(30), fill='#6E6E73')
        d.text((80, 560), 'fedcatalog.com', font=fontr(26), fill='#6E6E73')
        os.makedirs(os.path.join(DIST, 'assets'), exist_ok=True)
        img.save(os.path.join(DIST, 'assets', 'fedcatalog-og.png'))
        mark(180).convert('RGB').save(os.path.join(DIST, 'assets', 'apple-touch-icon.png'))
        # Brand kit for social profiles (not linked from the site)
        kit = os.path.join(ROOT, 'brand'); os.makedirs(kit, exist_ok=True)
        for s in (1024, 512, 400): mark(s).save(os.path.join(kit, f'fedcatalog-mark-{s}.png'))
        for s in (1024, 512, 400):
            sq = Image.new('RGB', (s, s), '#FFFFFF'); sq.paste(mark(int(s * .72)), (int(s * .14), int(s * .14)), mark(int(s * .72))); sq.save(os.path.join(kit, f'fedcatalog-mark-{s}-on-white.png'))
        banner = Image.new('RGB', (1584, 396), '#FFFFFF'); bd = ImageDraw.Draw(banner)
        bd.rectangle([0, 0, 1584, 8], fill='#F25F3A'); banner.paste(mark(120), (96, 128), mark(120))
        bd.text((248, 138), 'FedCatalog', font=fontb(64), fill='#1D1D1F'); bd.text((248, 224), 'Federal Software in One Place  ·  fedcatalog.com', font=fontr(30), fill='#6E6E73')
        banner.save(os.path.join(kit, 'fedcatalog-linkedin-banner-1584x396.png'))
        shutil.copy(os.path.join(DIST, 'assets', 'fedcatalog-og.png'), os.path.join(kit, 'fedcatalog-social-1200x630.png'))
        shutil.copy(os.path.join(DIST, 'assets', 'favicon.svg'), os.path.join(kit, 'fedcatalog-mark.svg'))
    except Exception as e:
        print('image assets skipped:', e)

# ------------------------------------------------------------------ build
def build():
    db = load()
    # tag products with vendor-level onegov/dod for row data attributes
    for p in db['products']:
        p['_onegov'] = bool(onegov_for(db, p['vendor_slug']))
        p['_dod'] = sorted({r['il'] for r in dod_rows_for(db, p['vendor_slug']) if r['status'].startswith('Provisional Authorization')})
    if os.path.exists(DIST): shutil.rmtree(DIST)
    os.makedirs(DIST)
    build_assets(db)
    urls = []
    def add(path, html_text, indexable=True):
        write_page(path, html_text)
        if indexable: urls.append(path)
    add('/', page_home(db))
    for p in db['products']: add(url_product(p), page_product(db, p))
    for v in db['vendors'].values(): add(url_vendor(v), page_vendor(db, v))
    for a in db['agencies']: add(url_agency(a), page_agency(db, a))
    for f in db['functions']: add(url_category(f), page_category(db, f))
    # indexes
    P = sorted([p for p in db['products'] if p['status_code'] != 'delisted'], key=lambda p: p['name'].lower())
    add('/software/', page_list(db, path='/software/', crumbs=[('FedCatalog', '/'), ('Software', None)], title='All software', sub=f'{nfmt(len(P))} FedRAMP cloud service offerings, A–Z. Filter by status, impact, platform and more.', products=P,
        meta_title='All Federal Software Offerings, A–Z | FedCatalog', meta_desc=f'Every FedRAMP cloud service offering ({nfmt(len(P))}) with status, impact level, hosting platform, agency adoption and procurement links.'))
    vs = sorted(db['vendors'].values(), key=lambda v: v['name'].lower())
    letters = sorted({v['name'][0].upper() if v['name'][0].isalpha() else '#' for v in vs})
    az = ''.join(f'<h2 id="v-{esc(L if L != "#" else "num")}" class="h3" style="margin-top:26px">{esc(L)}</h2><div class="az">' + ''.join(vendor_az(db, v) for v in vs if (v['name'][0].upper() if v['name'][0].isalpha() else '#') == L) + '</div>' for L in letters)
    add('/vendors/', layout(db, path='/vendors/', title='Federal Software Vendors, A–Z | FedCatalog', description=f'{nfmt(len(vs))} vendors with FedRAMP cloud service offerings: number of offerings, highest impact level, agency authorization records, DoD Impact Level and OneGov indicators.',
        body=f'<section class="panel narrow">{crumbs_html([("FedCatalog", "/"), ("Vendors", None)])}<h1 class="h2" style="margin-top:10px">Vendors<small>{nfmt(len(vs))} vendors with FedRAMP offerings</small></h1><div class="letters">' + ''.join(f'<a href="#v-{esc(L if L != "#" else "num")}">{esc(L)}</a>' for L in letters) + f'</div>{az}</section>', jsonld=[crumbs_ld([("FedCatalog", "/"), ("Vendors", None)])]))
    ags = db['agencies']
    add('/agencies/', layout(db, path='/agencies/', title='Federal Agencies and Their Authorized Software | FedCatalog', description=f'{nfmt(len(ags))} federal agencies and components with FedRAMP authorization or reuse records, and the software each has authorized.',
        body=f'<section class="panel narrow">{crumbs_html([("FedCatalog", "/"), ("Agencies", None)])}<h1 class="h2" style="margin-top:10px">Agencies<small>Software each agency has authorized, from the FedRAMP Marketplace</small></h1><ul class="list">' + ''.join(f'<li><a href="{url_agency(a)}">{esc(a["name"])}{(" · " + esc(a["parent"])) if a["sub"] else ""}</a><span>{nfmt(len(a["products"]))} authorizations</span></li>' for a in ags) + '</ul></section>', jsonld=[crumbs_ld([("FedCatalog", "/"), ("Agencies", None)])]))
    add('/categories/', layout(db, path='/categories/', title='Browse Federal Software by Category | FedCatalog', description=f'{len(db["functions"])} categories of FedRAMP cloud services, plus browsing by cloud platform, FedRAMP status and impact level, DoD Impact Level, OneGov and agency.',
        body=f'<section class="panel">{crumbs_html([("FedCatalog", "/"), ("Browse", None)])}<h1 class="h2" style="margin-top:10px">Browse</h1><div class="cats" style="margin-bottom:8px">'
        + f'<a class="cat" href="/software/"><b>All software</b><span>Every FedRAMP offering, A–Z, with filters</span><small>{nfmt(sum(1 for p in db["products"] if p["status_code"] != "delisted"))} offerings</small><span class="chev" aria-hidden="true">›</span></a>'
        + f'<a class="cat" href="/vendors/"><b>Vendors</b><span>Every vendor with a FedRAMP offering, A–Z</span><small>{nfmt(len(db["vendors"]))} vendors</small><span class="chev" aria-hidden="true">›</span></a>'
        + f'<a class="cat" href="/agencies/"><b>Agencies</b><span>What each agency has authorized</span><small>{nfmt(len(db["agencies"]))} agencies</small><span class="chev" aria-hidden="true">›</span></a>'
        + f'<a class="cat" href="/buy/"><b>How to buy</b><span>OneGov, marketplaces, GSA, SEWP and vendor direct</span><small>Buying paths</small><span class="chev" aria-hidden="true">›</span></a>'
        + '</div><h2 class="h3">By category</h2><div class="cats">' + ''.join(cat_link(f) for f in db['functions']) + '</div><h2 class="h3">Other ways to browse</h2><div class="quick" style="justify-content:flex-start">'
        + ''.join(f'<a href="{url_cloud(c)}">Runs on {esc(RUNS[c])}</a>' for c in RUNS) + '<a href="/fedramp/authorized/">Authorized</a><a href="/fedramp/in-process/">In process</a><a href="/fedramp/ready/">Ready</a><a href="/fedramp/initial-implementation/">Initial Implementation</a><a href="/fedramp/high/">High</a><a href="/fedramp/moderate/">Moderate</a><a href="/fedramp/low/">Low</a><a href="/fedramp/li-saas/">LI-SaaS</a><a href="/agencies/">By agency</a><a href="/onegov/">OneGov agreements</a><a href="/dod/">DoD Impact Level</a></div></section>', jsonld=[crumbs_ld([("FedCatalog", "/"), ("Browse", None)])]))
    # status / impact
    for code, label in [('authorized', 'FedRAMP Authorized'), ('in-process', 'In process'), ('ready', 'FedRAMP Ready'), ('initial', 'Initial Implementation')]:
        prods = sorted([p for p in db['products'] if p['status_code'] == code], key=lambda p: -len(p['agencies']))
        slug = 'initial-implementation' if code == 'initial' else code
        add(f'/fedramp/{slug}/', page_list(db, path=f'/fedramp/{slug}/', crumbs=[('FedCatalog', '/'), ('FedRAMP', '/categories/'), (label, None)], title=label, sub=f'{nfmt(len(prods))} offerings' + (' · Listed by FedRAMP since July 2026 for providers early in implementation; not authorized' if code == 'initial' else ''), products=prods,
            meta_title=f'{label} Cloud Software | FedCatalog', meta_desc=f'{nfmt(len(prods))} cloud service offerings with FedRAMP status “{label}”, with impact level, hosting platform, agency adoption and procurement links.'))
    for level in ['High', 'Moderate', 'Low', 'LI-SaaS']:
        prods = sorted([p for p in db['products'] if (p['impact'] == level or p['impact'] == '20x ' + level) and p['status_code'] != 'delisted'], key=lambda p: -len(p['agencies']))
        add(f'/fedramp/{level.lower()}/', page_list(db, path=f'/fedramp/{level.lower()}/', crumbs=[('FedCatalog', '/'), ('FedRAMP', '/categories/'), (f'{level} impact', None)], title=f'FedRAMP {level}', sub=IMPACT_HELP.get(level, ''), products=prods,
            meta_title=f'FedRAMP {level} Software and Cloud Services | FedCatalog', meta_desc=f'{nfmt(len(prods))} FedRAMP offerings at the {level} impact level: status, hosting platform, agency authorization records and how to buy each.'))
    for code, label in RUNS.items():
        prods = sorted([p for p in db['products'] if (code in p['runs'] or code in p['runs_named']) and p['status_code'] != 'delisted'], key=lambda p: -len(p['agencies']))
        add(url_cloud(code), page_list(db, path=url_cloud(code), crumbs=[('FedCatalog', '/'), ('Browse', '/categories/'), (label, None)], title=f'Runs on {label}', sub='FedRAMP records the offering as built on this platform’s authorization boundary. Being sold on that cloud’s marketplace is separate.', products=prods,
            meta_title=f'FedRAMP Software Running on {label} | FedCatalog', meta_desc=f'{nfmt(len(prods))} FedRAMP cloud service offerings that leverage {label}’s authorization boundary, with status, impact level, agency adoption and procurement links.'))
    # DoD
    rows = db['dod']['rows']
    def dod_page(path, level):
        lst = sorted([r for r in rows if not level or r['il'] == level], key=lambda r: (r['provider'].lower(), r['cso'].lower()))
        tabs = ''.join(f'<a href="{"/dod/" if not v else "/dod/" + v.lower() + "/"}"{" style=" + chr(34) + "border-color:var(--text);font-weight:600" + chr(34) if level == v else ""}>{l} · {len([r for r in rows if not v or r["il"] == v])}</a>' for v, l in [('', 'All'), ('IL2', 'IL2'), ('IL4', 'IL4'), ('IL5', 'IL5'), ('IL6', 'IL6')])
        crumbs = [('FedCatalog', '/'), ('Browse', '/categories/'), ('DoD Impact Level' if not level else f'DoD {level}', None)]
        body = (f'<section class="panel narrow">{crumbs_html(crumbs)}<h1 class="h2" style="margin-top:10px">DoD {level + " " if level else ""}Impact Level authorizations<small>Cloud service offerings on the DoD Cyber Exchange list, with the exact DoD status. A Provisional Authorization is not an ATO; IATT means not authorized for operational use.</small></h1>'
                f'<div class="quick" style="justify-content:flex-start;margin:0 0 14px">{tabs}</div><ul class="awards">' + ''.join(dod_row_html(r, True, db) for r in lst) + f'</ul><p class="source">Source: DoD Cyber Exchange, Current Authorized CSOs · fetched {esc(fmt_date(db["dod"].get("fetched")))} · <a href="{esc(db["dod"].get("source", ""))}" target="_blank" rel="noopener noreferrer">public.cyber.mil</a></p></section>')
        t = f'DoD {level} Cloud Services & Software | FedCatalog' if level else 'DoD Impact Level Authorized Cloud Services | FedCatalog'
        d = f'{len(lst)} cloud service offerings listed by the DoD Cyber Exchange{(" at " + level) if level else ""}, with the exact DoD status (Provisional Authorization, PA-C, IATT, Suspended) and expiration.'
        return layout(db, path=path, title=t, description=d, body=body, jsonld=[crumbs_ld(crumbs)])
    add('/dod/', dod_page('/dod/', ''))
    for lvl in ['IL2', 'IL4', 'IL5', 'IL6']: add(f'/dod/{lvl.lower()}/', dod_page(f'/dod/{lvl.lower()}/', lvl))
    # OneGov
    ag = db['onegov']['agreements']
    crumbs = [('FedCatalog', '/'), ('Browse', '/categories/'), ('OneGov', None)]
    add('/onegov/', layout(db, path='/onegov/', title='GSA OneGov Software Agreements | FedCatalog', description=f'All {len(ag)} current GSA OneGov agreements: vendor, discount, expiry, contract vehicle, eligibility and included products, as published by GSA’s ITVMO.',
        body=f'<section class="panel narrow">{crumbs_html(crumbs)}<h1 class="h2" style="margin-top:10px">OneGov agreements<small>GSA-negotiated, government-wide pricing. {len(ag)} agreements as published by GSA’s ITVMO. Ordering details are behind a government login; agencies still follow FAR 8.4 ordering procedures.</small></h1><ul class="awards">' + ''.join(onegov_row_html(a, True, db) for a in ag) + f'</ul><p class="source">Source: GSA ITVMO OneGov current agreements · checked {esc(fmt_date(db["onegov"].get("checked")))} · <a href="{esc(db["onegov"].get("source", ""))}" target="_blank" rel="noopener noreferrer">itvmo.gsa.gov</a></p></section>', jsonld=[crumbs_ld(crumbs)]))
    # Buy
    onegov_vendor_slugs = {a['vendor_slug'] for a in db['onegov']['agreements'] if a.get('vendor_slug')}
    onegov_products = sorted([p for p in db['products'] if p['vendor_slug'] in onegov_vendor_slugs], key=lambda p: -len(p['agencies']))
    direct = sum(1 for p in db['products'] if p['website'])
    def card(name, desc, href, small, external=False):
        ext = ' target="_blank" rel="noopener noreferrer"' if external else ''
        return f'<a class="cat" href="{href}"{ext}><b>{esc(name)}</b><span>{esc(desc)}</span><small>{esc(small)}</small><span class="chev" aria-hidden="true">›</span></a>'
    buy_body = (f'<section class="panel narrow">{crumbs_html([("FedCatalog", "/"), ("How to buy", None)])}<h1 class="h2" style="margin-top:10px">Where government buys software<small>The places federal software is actually bought. Authorization tells you what you may use; these are where you buy it. Every product page links to a search for its vendor on each one.</small></h1>'
        '<h2 class="h3">Government-wide pricing</h2><div class="cats">'
        + card('GSA OneGov agreements', 'Pricing negotiated by GSA for the whole government, ordered through MAS and designated vehicles', '/onegov/', f'{len(db["onegov"]["agreements"])} agreements · {len(onegov_products)} FedRAMP offerings from OneGov vendors')
        + card('Vendor direct', 'Government sales pages published on the FedRAMP record', '/software/', f'{direct} offerings list a government page')
        + '</div><h2 class="h3">Cloud marketplaces</h2><div class="cats">'
        + card('AWS Marketplace', 'Software and SaaS billed through AWS. Listings show whether they are available in AWS GovCloud (US) regions', 'https://aws.amazon.com/marketplace', 'aws.amazon.com/marketplace ↗', True)
        + card('AWS Marketplace in GovCloud', 'How AWS Marketplace works inside AWS GovCloud (US)', 'https://docs.aws.amazon.com/govcloud-us/latest/UserGuide/govcloud-marketplace.html', 'AWS GovCloud user guide ↗', True)
        + card('Azure Marketplace', 'Microsoft’s catalog; Azure Government offers are listed separately from commercial', 'https://azuremarketplace.microsoft.com/en-us/marketplace/apps', 'azuremarketplace.microsoft.com ↗', True)
        + card('Google Cloud Marketplace', 'Software deployable and billed through Google Cloud', 'https://console.cloud.google.com/marketplace', 'console.cloud.google.com/marketplace ↗', True)
        + card('Oracle Cloud Marketplace', 'Applications and services for Oracle Cloud Infrastructure, including OCI Government regions', 'https://cloudmarketplace.oracle.com/marketplace/en_US/homePage.jspx', 'cloudmarketplace.oracle.com ↗', True)
        + '</div>' + (f'<p class="note" style="margin-top:10px">Exact listings on file: ' + ', '.join(f"{MARKET_LABEL[m]} {n}" for m, n in sorted(((m, sum(1 for l in db['listings'] if l['market'] == m)) for m in MARKET_LABEL), key=lambda t: -t[1]) if n) + ' — matched to a vendor or a specific FedRAMP offering. Everything else links to a clearly labeled search.</p>' if db['listings'] else '')
        + '<h2 class="h3">Contract vehicles</h2><div class="cats">'
        + card('GSA Multiple Award Schedule', 'IT products, software licenses (SIN 511210) and cloud (SIN 518210C) through GSA contract holders', 'https://www.gsaelibrary.gsa.gov/ElibMain/home.do', 'GSA eLibrary ↗', True)
        + card('GSA Advantage', 'Products and prices from GSA schedule holders, with CDM-tagged cybersecurity tools', 'https://www.gsaadvantage.gov/', 'gsaadvantage.gov ↗', True)
        + card('NASA SEWP', 'Government-wide IT vehicle; provider lookup shows which contract holders carry a vendor. SEWP VI expected November 2026', 'https://www.sewp.nasa.gov/', 'sewp.nasa.gov ↗', True)
        + card('CISA CDM Approved Products List', 'Cybersecurity products approved against CISA CDM requirements', 'https://www.cisa.gov/resources-tools/programs/continuous-diagnostics-and-mitigation-cdm-program/program-approved-products-list-apl', 'cisa.gov ↗', True)
        + f'</div><h2 class="h3" style="margin-top:28px">Useful intersections</h2><div class="cats">'
        + card('OneGov vendors’ FedRAMP offerings', 'Offerings from vendors with a GSA OneGov agreement; filter by impact level', '/buy/onegov-software/', f'{len(onegov_products)} offerings')
        + card('DoD IL5 cloud services', 'Offerings on the DoD Cyber Exchange at IL5, with exact status', '/dod/il5/', f'{len([r for r in db["dod"]["rows"] if r["il"] == "IL5"])} listings')
        + card('FedRAMP High on AWS GovCloud', 'High-impact offerings that leverage the AWS GovCloud boundary', '/cloud/aws-govcloud/?impact=High', f'{len([p for p in db["products"] if "aws-gov" in p["runs"] and p["impact"] == "High"])} offerings')
        + '</div><p class="note" style="margin-top:14px">FedCatalog shows what it can verify and labels what it can’t. Exact listings are added as they are checked or supplied by vendors and reviewed; everything else is a clearly labeled search. <a href="/methodology/#procurement">Methodology</a>.</p></section>')
    add('/buy/', layout(db, path='/buy/', title='Where Government Buys Software: Marketplaces, OneGov, GSA, SEWP | FedCatalog', description='The places federal software is bought — GSA OneGov, vendor direct, AWS, Azure and Google Cloud marketplaces, GSA MAS, GSA Advantage, NASA SEWP and the CDM APL — with direct links and useful intersections.', body=buy_body, jsonld=[crumbs_ld([("FedCatalog", "/"), ("How to buy", None)])]))
    add('/buy/onegov-software/', page_list(db, path='/buy/onegov-software/', crumbs=[('FedCatalog', '/'), ('How to buy', '/buy/'), ('OneGov vendors’ FedRAMP offerings', None)], title='FedRAMP offerings from OneGov vendors', sub='Cloud service offerings whose vendor holds a current GSA OneGov agreement. The agreement may cover a subset of these products; confirm scope on the GSA agreement page.', products=onegov_products,
        meta_title='FedRAMP Software from GSA OneGov Vendors | FedCatalog', meta_desc=f'{len(onegov_products)} FedRAMP cloud offerings from the {len(onegov_vendor_slugs)} vendors with current GSA OneGov agreements, with impact level, agency adoption and procurement paths.'))
    # New
    ch = load_changes()[:120]
    add('/new/', layout(db, path='/new/', title='New and Changed FedRAMP Authorizations | FedCatalog', description='The latest FedRAMP status changes: newly authorized, ready, in process and delisted cloud service offerings, as recorded by the FedRAMP PMO.',
        body=f'<section class="panel narrow">{crumbs_html([("FedCatalog", "/"), ("New", None)])}<h1 class="h2" style="margin-top:10px">New and changed<small>Status changes on the FedRAMP Marketplace, newest first. Last {len(ch)} changes as recorded by the FedRAMP PMO.</small></h1>{signup_slot('new')}<ul class="new">' + ''.join(change_row(db, x) for x in ch) + f'</ul><p class="source">Source: FedRAMP status changelog · built {esc(fmt_date(TODAY))}</p></section>', jsonld=[crumbs_ld([("FedCatalog", "/"), ("New", None)])]))
    # static pages
    add('/about/', page_static(db, '/about/', 'About', 'About FedCatalog | FedCatalog', 'Who built FedCatalog and why: one person putting scattered federal software information in one place, from public sources.', ABOUT))
    mark_ld = {"@context": "https://schema.org", "@type": "ProfilePage", "mainEntity": {"@type": "Person", "@id": ORIGIN + "/about/mark-flournoy/#mark", "name": "Mark Flournoy", "url": ORIGIN + "/about/mark-flournoy/",
               "description": "Builds and maintains FedCatalog. Six years supporting Federal Partner Sales at AWS; earlier sales roles at F5, Red Hat, Western Digital and STEC; 20 years in the U.S. Marines.", "image": ORIGIN + "/assets/mark.jpg", "sameAs": ["https://www.linkedin.com/in/markflournoy/"], "worksFor": {"@id": ORIGIN + "/#organization"}}}
    add('/about/mark-flournoy/', page_static(db, '/about/mark-flournoy/', 'Mark Flournoy', 'Mark Flournoy | FedCatalog', 'Mark Flournoy builds and maintains FedCatalog. Six years supporting Federal Partner Sales at AWS, earlier sales roles at F5, Red Hat, Western Digital and STEC, and 20 years in the Marines.', MARK, jsonld=[mark_ld]))
    add('/methodology/', page_static(db, '/methodology/', 'Methodology', 'Data Sources & Methodology | FedCatalog', 'Where every FedCatalog figure comes from: FedRAMP Marketplace, DoD Cyber Exchange, GSA OneGov, USAspending and procurement sources, what each means, and the editorial policy.', METHODOLOGY))
    add('/privacy/', page_static(db, '/privacy/', 'Privacy', 'Privacy | FedCatalog', 'FedCatalog’s privacy practices in plain English: no accounts, no sale of personal information, no tracking cookies.', PRIVACY))
    add('/terms/', page_static(db, '/terms/', 'Terms', 'Terms of Use | FedCatalog', 'Terms of use for FedCatalog, an independent federal software reference: informational use, accuracy, external links, trademarks and liability.', TERMS))
    add('/contact/', page_static(db, '/contact/', 'Contact', 'Contact FedCatalog | FedCatalog', 'Questions, corrections and vendor listing updates for FedCatalog.', CONTACT()))
    # search page (noindex)
    write_page('/search/', layout(db, path='/search/', title='Search | FedCatalog', description='Search FedCatalog by software, vendor or need.', noindex=True,
        body='<section class="panel"><h1 class="h2" data-search-title>Search</h1><div class="results">' + rail_html('') + '<div><div class="results-bar"><span class="count" data-count></span><button class="filter-btn" type="button" data-open-sheet>Filters<b data-filter-count></b></button></div><div data-search-results><p class="note">Type a product, vendor or need in the search box. Try “FedRAMP High cybersecurity”, “zero trust on AWS” or “Databricks vs Snowflake”.</p></div></div></div></section>'))
    # 404
    write('404.html', _layout(db, path='/404.html', title='Page not found | FedCatalog', description='That page does not exist.', noindex=True,
        body='''<section class="panel narrow lost"><p class="shrug" aria-hidden="true">¯\\_(ツ)_/¯</p><h1>Oops. That page doesn’t exist.</h1><p>The link may be old, the offering may have been delisted, or the address has a typo. Nothing here is broken; you just wandered off the map.</p>
<form class="search" action="/search/" method="get" role="search"><label for="lq" class="sr-only">Search</label><input id="lq" name="q" type="search" autocomplete="off" placeholder="Search software, vendors or requirements…"><button type="submit">Search</button></form>
<p class="links"><a href="/software/">Browse software</a> · <a href="/vendors/">Vendors</a> · <a href="/agencies/">Agencies</a> · <a href="/buy/">How to buy</a> · <a href="/">Home</a></p></section>'''))
    # sitemap, robots, CNAME
    lastmod = (db['meta'].get('last_change') or TODAY)[:10]
    write('sitemap.xml', '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + ''.join(f'  <url><loc>{ORIGIN}{u}</loc><lastmod>{lastmod}</lastmod></url>\n' for u in urls) + '</urlset>\n')
    write('robots.txt', f'User-agent: *\nAllow: /\n\nSitemap: {ORIGIN}/sitemap.xml\n')
    write('CNAME', 'fedcatalog.com\n')
    print('built', len(urls), 'indexable pages into', DIST)
    return urls
def vendor_az(db, v):
    s = vendor_summary(v)
    flags = []
    if onegov_for(db, v['slug']): flags.append('OneGov')
    pa = sorted({r['il'] for r in dod_rows_for(db, v['slug']) if r['status'].startswith('Provisional Authorization')})
    if pa: flags.append('DoD ' + '/'.join(pa))
    n = len(v['products'])
    return f'<a href="{url_vendor(v)}"><b>{esc(v["name"])}</b><small>{n} offering{"" if n == 1 else "s"} · up to {esc(s["best"]["impact"])} · {len(s["agencies"])} agenc{"y" if len(s["agencies"]) == 1 else "ies"}{(" · " + " · ".join(flags)) if flags else ""}</small><span aria-hidden="true">›</span></a>'

if __name__ == '__main__':
    build()
