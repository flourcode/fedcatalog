#!/usr/bin/env python3
"""Draft the weekly FedCatalog email from public data.

Run:  python3 src/weekly_draft.py            # last 7 days, from src/data
      python3 src/weekly_draft.py --days 14
      python3 src/weekly_draft.py --refresh   # fetch the latest FedRAMP changelog first

Writes drafts/YYYY-MM-DD.md and .html. Paste the HTML into Beehiiv/Kit, read it
over, send. Every line links to the FedCatalog page and names its source.
"""
import json, os, re, sys, datetime, urllib.request, html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build as B

ROOT = B.ROOT; DATA = B.DATA
ORIGIN = B.ORIGIN
CHANGELOG_SRC = 'https://raw.githubusercontent.com/FedRAMP/marketplace-fedramp-gov-data/main/fedramp-status-changelog.json'

def load_changelog(refresh):
    path = os.path.join(DATA, 'changelog.json')
    if refresh:
        try:
            raw = urllib.request.urlopen(CHANGELOG_SRC, timeout=60).read()
            open(path, 'wb').write(raw); print('changelog refreshed')
        except Exception as e: print('changelog refresh skipped:', e)
    return json.load(open(path))['data']['certprocessstatuschangelog']

def main():
    days = 7; refresh = '--refresh' in sys.argv
    if '--days' in sys.argv: days = int(sys.argv[sys.argv.index('--days') + 1])
    today = datetime.date.today(); since = today - datetime.timedelta(days=days)
    db = B.load()
    changes = [x for x in load_changelog(refresh) if x.get('transition_date') and since.isoformat() <= x['transition_date'][:10] <= today.isoformat() and x.get('from_status') != x.get('to_status')]   # skip re-recorded, unchanged statuses
    changes.sort(key=lambda x: x['transition_date'], reverse=True)
    def link(x):
        p = db['by_id'].get(x['product_id'])
        return (ORIGIN + B.url_product(p)) if p else None
    def imp(x):
        p = db['by_id'].get(x['product_id']); return p['impact'] if p else ''
    authorized = [x for x in changes if re.search(r'authori|certified', x['to_status'], re.I)]
    ready = [x for x in changes if x['to_status'] == 'FedRAMP Ready']
    inproc = [x for x in changes if 'In Process' in x['to_status']]
    other = [x for x in changes if x not in authorized and x not in ready and x not in inproc]
    # DoD: provisional authorizations expiring within 60 days, and changes vs the previous file if kept
    dod = db['dod']['rows']
    soon = today + datetime.timedelta(days=60)
    expiring = sorted([r for r in dod if r.get('expires') and r['status'].startswith('Provisional') and today.isoformat() <= r['expires'] <= soon.isoformat()], key=lambda r: r['expires'])
    prev_dod = os.path.join(DATA, 'dod_il.prev.json'); dod_new = []
    if os.path.exists(prev_dod):
        prev = {(r['provider'], r['cso']) for r in json.load(open(prev_dod))['rows']}
        dod_new = [r for r in dod if (r['provider'], r['cso']) not in prev]
    prev_og = os.path.join(DATA, 'onegov.prev.json'); og_new = []
    if os.path.exists(prev_og):
        prev = {a['title'] for a in json.load(open(prev_og))['agreements']}
        og_new = [a for a in db['onegov']['agreements'] if a['title'] not in prev]
    og_expiring = sorted([a for a in db['onegov']['agreements'] if a.get('expires') and today.isoformat() <= a['expires'] <= soon.isoformat()], key=lambda a: a['expires'])

    # ---- markdown
    md = [f'# What changed in federal software · week of {today.strftime("%b %-d, %Y")}', '', f'Changes recorded {since.strftime("%b %-d")}–{today.strftime("%b %-d")}. Every item links to its FedCatalog page; sources are the FedRAMP Marketplace changelog, the DoD Cyber Exchange list and GSA’s OneGov page.', '']
    def item(x):
        u = link(x); name = f'[{x["cso"]}]({u})' if u else x['cso']
        extra = f' · {imp(x)}' if imp(x) else ''
        return f'- **{name}** — {x["csp"]}{extra} · now {x["to_status"]}' + (f' (from {x["from_status"]})' if x.get('from_status') else '') + f' · {x["transition_date"][:10]}'
    sections = [('Newly authorized', authorized, 'FedRAMP Authorized this week'), ('FedRAMP Ready', ready, 'Assessed and ready for an agency sponsor'), ('Entered In Process', inproc, 'The earliest public signal that an offering is on its way'), ('Other status changes', other, '')]
    for title, lst, sub in sections:
        if not lst: continue
        md += [f'## {title} ({len(lst)})', (sub + '\n') if sub else '']
        by_imp = {}
        for x in lst: by_imp.setdefault(imp(x) or 'Unlisted', []).append(x)
        for level in ['High', '20x Moderate', 'Moderate', '20x Low', 'Low', 'LI-SaaS', 'Unlisted', '']:
            if level in by_imp and by_imp[level]:
                if title == 'Newly authorized' and len(by_imp) > 1: md.append(f'**{level}**')
                md += [item(x) for x in by_imp[level]]
        md.append('')
    if not any(lst for _, lst, _ in sections): md += ['No FedRAMP status changes were recorded this week.', '']
    if dod_new or expiring:
        md += ['## DoD Impact Level', '']
        for r in dod_new: md.append(f'- **New on the DoD list:** {r["cso"]} ({r["provider"]}) — {r["il"]} · {r["status"]}' + (f' · [vendor page]({ORIGIN}/vendors/{r["vendor_slug"]}/#dod)' if r.get('vendor_slug') in db['vendors'] else ''))
        for r in expiring: md.append(f'- **Expires {B.fmt_date(r["expires"])}:** {r["cso"]} ({r["provider"]}) — {r["il"]} Provisional Authorization' + (f' · [vendor page]({ORIGIN}/vendors/{r["vendor_slug"]}/#dod)' if r.get('vendor_slug') in db['vendors'] else ''))
        md.append('')
    if og_new or og_expiring:
        md += ['## OneGov', '']
        for a in og_new: md.append(f'- **New agreement:** {a["vendor"]} — {a["title"]} · {a["discount"]} · [{ORIGIN}/onegov/]({ORIGIN}/onegov/)')
        for a in og_expiring: md.append(f'- **Expires {B.fmt_date(a["expires"])}:** {a["vendor"]} — {a["title"]} · [agreement](https://itvmo.gsa.gov/onegov/?tabName=agreements-tab#{a["anchor"]})')
        md.append('')
    md += ['---', f'Browse everything at [{ORIGIN}]({ORIGIN}) · [New and changed]({ORIGIN}/new/) · [How the data works]({ORIGIN}/methodology/)', '', 'FedCatalog is built by Mark Flournoy from public government data. No pay-to-rank. Reply to this email with corrections.']
    text = '\n'.join(md)
    # ---- html (simple conversion)
    def md_to_html(s):
        out = []
        for line in s.split('\n'):
            line = html.escape(line, quote=False)
            line = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', line)
            line = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line)
            if line.startswith('# '): out.append(f'<h1 style="font-size:22px;margin:0 0 8px">{line[2:]}</h1>')
            elif line.startswith('## '): out.append(f'<h2 style="font-size:17px;margin:20px 0 6px">{line[3:]}</h2>')
            elif line.startswith('- '): out.append(f'<p style="margin:0 0 6px 12px">• {line[2:]}</p>')
            elif line == '---': out.append('<hr style="border:0;border-top:1px solid #E5E5EA;margin:20px 0">')
            elif line.strip(): out.append(f'<p style="margin:0 0 8px">{line}</p>')
        body = '\n'.join(out).replace('·', '&middot;').replace('—', '&mdash;').replace('–', '&ndash;').replace('’', '&rsquo;').replace('“', '&ldquo;').replace('”', '&rdquo;')
        return '<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><title>FedCatalog weekly draft</title></head><body>\n<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;font-size:15px;line-height:1.5;color:#1D1D1F;max-width:640px">' + body + '</div>\n</body></html>'
    os.makedirs(os.path.join(ROOT, 'drafts'), exist_ok=True)
    base = os.path.join(ROOT, 'drafts', today.isoformat())
    open(base + '.md', 'w', encoding='utf-8').write(text); open(base + '.html', 'w', encoding='utf-8').write(md_to_html(text))
    print(f'{len(authorized)} authorized · {len(ready)} ready · {len(inproc)} in process · {len(other)} other · {len(expiring)} DoD PAs expiring within 60 days · {len(og_expiring)} OneGov expiring')
    print('wrote', base + '.md', 'and .html')

if __name__ == '__main__':
    main()
