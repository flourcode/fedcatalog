#!/usr/bin/env python3
"""FedCatalog weekly newsletter draft.

Two outputs:
  drafts/changelog-YYYY-MM-DD.md      every detected change (the machine record)
  drafts/YYYY-MM-DD.html / .md        the newsletter: editorial selection, ~600-800 words
The nightly job copies the newsletter to drafts/latest.html / latest.md.

Run:  python3 src/weekly_draft.py            # last 7 days
      python3 src/weekly_draft.py --days 14
      python3 src/weekly_draft.py --refresh   # fetch the latest FedRAMP changelog first
"""
import json, os, re, sys, datetime, urllib.request, html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build as B

ROOT = B.ROOT; DATA = B.DATA; ORIGIN = B.ORIGIN
CHANGELOG_SRC = 'https://raw.githubusercontent.com/FedRAMP/marketplace-fedramp-gov-data/main/fedramp-status-changelog.json'
AI_RE = re.compile(r'(?<![.\w])(ai|artificial intelligence|gen(erative)? ?ai|llm|claude|chatgpt|gpt|gemini|copilot|agentic|machine learning)\b', re.I)
CYBER_RE = re.compile(r'\b(secur|cyber|threat|zero trust|identity|vulnerab|siem|endpoint|firewall)\w*', re.I)

def load_changelog(refresh):
    path = os.path.join(DATA, 'changelog.json')
    if refresh:
        try: open(path, 'wb').write(urllib.request.urlopen(CHANGELOG_SRC, timeout=60).read()); print('changelog refreshed')
        except Exception as e: print('changelog refresh skipped:', e)
    return json.load(open(path))['data']['certprocessstatuschangelog']

def status_words(s):
    """FedRAMP's changelog uses older labels; show the current terminology."""
    s = s or ''
    if re.search(r'certified|^authorized$|fedramp authorized', s, re.I): return 'FedRAMP Authorized'
    if 'No Status Found' in s: return 'No Status Found'
    if 'Initial Implementation' in s: return 'Initial Implementation'
    if 'In Process' in s: return 'FedRAMP In Process'
    if 'Ready' in s: return 'FedRAMP Ready'
    return s

def num(n): return ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten'][n] if 0 <= n <= 10 else str(n)
def cap(s): return s[:1].upper() + s[1:] if s else s
def join_sentence(bits):
    bits = [b for b in bits if b]
    if not bits: return 'Not much changed in the data.'
    if len(bits) == 1: return cap(bits[0]) + '.'
    return cap(', '.join(bits[:-1]) + ', and ' + bits[-1]) + '.'
def and_list(items):
    items = list(items)
    return items[0] if len(items) == 1 else (', '.join(items[:-1]) + ' and ' + items[-1]) if items else ''
def plural(n, word, words=None): return f'{n} {word if n == 1 else (words or word + "s")}'

def md_to_html(s):
    out = []
    for raw_line in s.split('\n'):
        line = html.escape(raw_line, quote=False)
        line = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2" style="color:#DC4E2B">\1</a>', line)
        line = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line)
        line = re.sub(r'(?<!\*)\*(?!\*)(.+?)\*(?!\*)', r'<em>\1</em>', line)
        if raw_line.startswith('SUBJECT:') or raw_line.startswith('PREVIEW:'): out.append(f'<p style="margin:0 0 4px;color:#6E6E73;font-size:13px">{line}</p>')
        elif raw_line.startswith('## '): out.append(f'<h2 style="font-size:18px;margin:22px 0 8px">{line[3:]}</h2>')
        elif raw_line.startswith('- '): out.append(f'<p style="margin:0 0 10px 14px">&bull; {line[2:]}</p>')
        elif raw_line == '---': out.append('<hr style="border:0;border-top:1px solid #E5E5EA;margin:24px 0">')
        elif raw_line.strip(): out.append(f'<p style="margin:0 0 10px">{line}</p>')
    body = '\n'.join(out).replace('·', '&middot;').replace('—', '&mdash;').replace('–', '&ndash;').replace('’', '&rsquo;').replace('“', '&ldquo;').replace('”', '&rdquo;')
    return '<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><title>FedCatalog weekly draft</title></head><body>\n<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;font-size:15px;line-height:1.5;color:#1D1D1F;max-width:640px">' + body + '</div>\n</body></html>'

def main():
    days = 7; refresh = '--refresh' in sys.argv
    if '--days' in sys.argv: days = int(sys.argv[sys.argv.index('--days') + 1])
    today = datetime.date.today(); since = today - datetime.timedelta(days=days)
    db = B.load()
    raw = [x for x in load_changelog(refresh) if x.get('transition_date') and since.isoformat() <= x['transition_date'][:10] <= today.isoformat()]
    raw = [x for x in raw if (x.get('from_status') or '') != (x.get('to_status') or '')]   # drop only true re-records; sideways moves stay
    raw.sort(key=lambda x: x['transition_date'], reverse=True)

    def prod(x): return db['by_id'].get(x['product_id'])
    def url(x): p = prod(x); return (ORIGIN + B.url_product(p)) if p else None
    def imp(x): p = prod(x); return p['impact'] if p else ''
    def vendor_weight(x):
        p = prod(x)
        if not p: return 0
        v = db['vendors'].get(p['vendor_slug']); s = B.vendor_summary(v) if v else None
        return (len(s['agencies']) if s else 0) + (10 if B.onegov_for(db, p['vendor_slug']) else 0) + (10 if B.dod_rows_for(db, p['vendor_slug']) else 0) + (len(v['products']) if v else 0)
    def is_ai(x): p = prod(x); return bool(AI_RE.search(x['cso'] + ' ' + x['csp'])) or bool(p and 'Artificial Intelligence (AI)' in p['functions'])
    def is_cyber(x): p = prod(x); return bool(CYBER_RE.search(x['cso'] + ' ' + ' '.join(p['functions'] if p else [])))

    authorized = [x for x in raw if status_words(x['to_status']) == 'FedRAMP Authorized' and status_words(x.get('from_status')) != 'FedRAMP Authorized']
    inproc = [x for x in raw if status_words(x['to_status']) in ('FedRAMP In Process', 'Initial Implementation', 'FedRAMP Ready') and status_words(x.get('from_status')) != status_words(x['to_status'])]
    delisted = [x for x in raw if status_words(x['to_status']) == 'No Status Found' and status_words(x.get('from_status')) == 'FedRAMP Authorized']
    other = [x for x in raw if x not in authorized and x not in inproc and x not in delisted]
    soon = today + datetime.timedelta(days=60)
    og_expiring = sorted([a for a in db['onegov']['agreements'] if a.get('expires') and today.isoformat() <= a['expires'] <= soon.isoformat()], key=lambda a: a['expires'])
    og_new = []; prev = os.path.join(DATA, 'onegov.prev.json')
    if os.path.exists(prev):
        seen = {a['title'] for a in json.load(open(prev))['agreements']}; og_new = [a for a in db['onegov']['agreements'] if a['title'] not in seen]
    dod_expiring = sorted([r for r in db['dod']['rows'] if r.get('expires') and r['status'].startswith('Provisional') and today.isoformat() <= r['expires'] <= soon.isoformat()], key=lambda r: r['expires'])
    dod_new = []; prevd = os.path.join(DATA, 'dod_il.prev.json')
    if os.path.exists(prevd):
        seen = {(r['provider'], r['cso']) for r in json.load(open(prevd))['rows']}; dod_new = [r for r in db['dod']['rows'] if (r['provider'], r['cso']) not in seen]

    # ---- editorial selection
    watching = sorted(inproc, key=lambda x: vendor_weight(x) + (15 if is_ai(x) else 0), reverse=True)[:8]
    short = []
    for x in sorted(authorized, key=lambda x: -vendor_weight(x))[:2]:
        short.append((f'**{x["cso"]}** from {x["csp"]} reached FedRAMP Authorized at the {imp(x) or "listed"} impact level' + (' (previously In Process).' if 'In Process' in (x.get('from_status') or '') else '.'), url(x)))
    if delisted:
        short.append((f'**{plural(len(delisted), "offering")}** previously shown as Authorized now appear as No Status Found in the current FedRAMP data, including {and_list(x["cso"] for x in delisted[:3])}. That happens for several reasons; treat it as a prompt to check the record, not an explanation.', ORIGIN + '/new/'))
    for r in dod_new[:1]: short.append((f'**{r["cso"]}** ({r["provider"]}) appeared on the DoD Cyber Exchange list at {r["il"]} as {r["status"]}.', ORIGIN + '/dod/'))
    for a in og_new[:1]: short.append((f'GSA added a OneGov agreement for **{a["vendor"]}**: {a["discount"]}.', ORIGIN + '/onegov/'))
    if og_expiring: short.append((f'**{plural(len(og_expiring), "OneGov agreement")}** ({and_list(a["vendor"] for a in og_expiring[:4])}) currently show an expiration date within 60 days. That is the date GSA publishes, not necessarily the end of the offer; anyone relying on one should check the agreement.', ORIGIN + '/onegov/'))
    for x in [w for w in watching if vendor_weight(w) >= 20 or is_ai(w)][:1]:
        if len(short) < 5: short.append((f'**{x["cso"]}** from {x["csp"]} entered {status_words(x["to_status"])}. Not authorized yet, but on the path.', url(x)))
    short = short[:5]

    # ---- "one thing I noticed", only when a pattern exists
    note = None
    ai_items = [x for x in authorized + inproc if is_ai(x)]
    ai_og = [a for a in og_expiring if AI_RE.search(a['title'])]
    cyber_auth = [x for x in authorized if is_cyber(x)]
    if len(ai_items) >= 2 or (ai_items and ai_og):
        names = and_list(sorted({x['cso'] for x in ai_items})[:3])
        note = (f'AI is showing up at more than one point in the federal software lifecycle at once. {names} moved in the FedRAMP process this week'
                + (f', while the OneGov agreements for {and_list(a["vendor"] for a in ai_og)} are approaching their currently published expiration dates' if ai_og else '')
                + '. Those are separate things: authorization status and procurement path aren’t the same. Seeing them side by side is why FedCatalog exists.')
    elif len(delisted) >= 5:
        note = f'{cap(num(len(delisted)))} offerings dropped off the current Authorized list in one week, which is more than usual. FedRAMP doesn’t publish a reason in the data, so I won’t guess at one. If you rely on any of them, the current record is the place to look.'
    elif len(cyber_auth) >= 3:
        note = f'{cap(num(len(cyber_auth)))} of this week’s new authorizations are security products ({", ".join(x["cso"] for x in cyber_auth[:3])}). Cyber keeps being the category where the FedRAMP pipeline is busiest.'

    # ---- newsletter
    send_date = today + datetime.timedelta(days=(1 - today.weekday()) % 7)   # next Tuesday, or today if it is one
    preview_bits = []
    if authorized: preview_bits.append(plural(len(authorized), 'new FedRAMP authorization'))
    if delisted: preview_bits.append(plural(len(delisted), 'delisting'))
    if og_expiring: preview_bits.append('OneGov agreements nearing expiration')
    if dod_new: preview_bits.append(plural(len(dod_new), 'new DoD listing'))
    if not preview_bits: preview_bits.append('a quiet week in the FedRAMP data')
    opening_bits = []
    if authorized: opening_bits.append(f'{num(len(authorized))} offering{"s" if len(authorized) != 1 else ""} reached FedRAMP Authorized')
    if delisted: opening_bits.append(f'{num(len(delisted))} familiar product{"s" if len(delisted) != 1 else ""} dropped off the current list')
    if og_expiring: opening_bits.append(f'{num(len(og_expiring))} OneGov agreement{"s" if len(og_expiring) != 1 else ""} {"are" if len(og_expiring) != 1 else "is"} coming up on {"their" if len(og_expiring) != 1 else "its"} published expiration date')
    opening = ('A fair amount moved this week. ' if len(raw) >= 15 else 'A quieter week. ') + join_sentence(opening_bits) + ' Here are the things I thought were worth knowing.'

    L = [f'SUBJECT: Federal software changes worth knowing — {send_date.strftime("%b %-d")}', 'PREVIEW: ' + cap(join_sentence(preview_bits)), '', opening, '']
    if short:
        L.append('## The short version')
        for text, u in short: L.append(f'- {text}' + (f' [View →]({u})' if u else ''))
        L.append('')
    if authorized:
        L.append('## Newly authorized')
        for x in (authorized if len(authorized) <= 10 else sorted(authorized, key=lambda x: -vendor_weight(x))[:10]):
            prev_s = status_words(x.get('from_status'))
            L.append(f'**{x["csp"]} — {x["cso"]}**  ')
            L.append(f'FedRAMP {imp(x)} · Authorized {B.fmt_date(x["transition_date"])}'.replace('FedRAMP  ·', 'FedRAMP ·') + (f' · Previously {prev_s.replace("FedRAMP ", "")}' if prev_s and prev_s != 'FedRAMP Authorized' else '') + (f' · [View in FedCatalog →]({url(x)})' if url(x) else ''))
            L.append('')
        if len(authorized) > 10: L += [f'…and {len(authorized) - 10} more on the [New page]({ORIGIN}/new/).', '']
    if watching:
        L += ['## Worth watching', 'A few names entered or moved further into the FedRAMP process this week. None of these is authorized yet.', '']
        for x in watching:
            L.append(f'**{x["cso"]} — {x["csp"]}**  ')
            L.append(f'{status_words(x["to_status"])}' + (f' · {imp(x)}' if imp(x) else '') + f' · {B.fmt_date(x["transition_date"])}' + (f' · [View →]({url(x)})' if url(x) else ''))
            L.append('')
        L += [f'[See all new and changed records →]({ORIGIN}/new/)', '']
    if delisted:
        L += ['## No longer on the current Authorized list', f'{cap(num(len(delisted)))} offering{"s" if len(delisted) != 1 else ""} that {"were" if len(delisted) != 1 else "was"} previously shown as Authorized now appear{"" if len(delisted) != 1 else "s"} as No Status Found in the current FedRAMP data. That can happen for several reasons, so treat this as a signal to check the current record rather than an explanation of why it changed.', '']
        for x in sorted(delisted, key=lambda x: -vendor_weight(x))[:6]:
            L.append(f'**{x["cso"]} — {x["csp"]}**  '); L.append('Previously FedRAMP Authorized · now No Status Found' + (f' · [View →]({url(x)})' if url(x) else '')); L.append('')
        if len(delisted) > 6: L += [f'[See all status changes →]({ORIGIN}/new/)', '']
    if og_new or og_expiring or dod_new or dod_expiring:
        L.append('## On the buying side')
        for a in og_new: L += [f'GSA added a OneGov agreement: **{a["vendor"]} — {a["title"]}**. {a["discount"]}. [Agreement →](https://itvmo.gsa.gov/onegov/?tabName=agreements-tab#{a["anchor"]})', '']
        if og_expiring:
            L += [f'{cap(num(len(og_expiring)))} OneGov agreement{"s" if len(og_expiring) != 1 else ""} currently show{"" if len(og_expiring) != 1 else "s"} an expiration date within the next 60 days:', '']
            for a in og_expiring: L.append(f'**{a["vendor"]} — {a["title"]}** · {B.fmt_date(a["expires"])}  ')
            L += ['', 'That doesn’t necessarily mean the offers disappear the next day. It means that is the expiration date currently published by GSA, so anyone relying on one of these paths should check the agreement.', '', f'[View the OneGov agreements →]({ORIGIN}/onegov/)', '']
        for r in dod_new: L += [f'New on the DoD Cyber Exchange list: **{r["cso"]}** ({r["provider"]}) — {r["il"]} · {r["status"]}. [DoD listings →]({ORIGIN}/dod/)', '']
        if dod_expiring: L += ['DoD provisional authorizations with a published expiration inside 60 days: ' + '; '.join(f'**{r["cso"]}** ({B.fmt_date(r["expires"])})' for r in dod_expiring[:5]) + f'. [DoD listings →]({ORIGIN}/dod/)', '']
    if note: L += ['## One thing I noticed', '*Draft note from the data. Keep, edit or delete before sending.*', '', note, '']
    # ---- the roll: everyone who moved but wasn't featured above, so nobody is left out
    featured = {x['product_id'] for x in (authorized if len(authorized) <= 10 else sorted(authorized, key=lambda x: -vendor_weight(x))[:10])} | {x['product_id'] for x in watching} | {x['product_id'] for x in sorted(delisted, key=lambda x: -vendor_weight(x))[:6]}
    roll = []
    def names(lst): return ', '.join(f'{x["cso"]} ({x["csp"]})' for x in lst)
    rest_auth = [x for x in authorized if x['product_id'] not in featured]
    if rest_auth: roll.append(f'Also authorized: {names(rest_auth)}.')
    for label, code in [('Also entered In Process', 'FedRAMP In Process'), ('Also reached FedRAMP Ready', 'FedRAMP Ready'), ('Also entered Initial Implementation', 'Initial Implementation')]:
        rest = [x for x in inproc if status_words(x['to_status']) == code and x['product_id'] not in featured]
        if rest: roll.append(f'{label}: {names(rest)}.')
    rest_del = [x for x in delisted if x['product_id'] not in featured]
    if rest_del: roll.append(f'Also now No Status Found: {names(rest_del)}.')
    if other: roll.append('Other status changes: ' + ', '.join(f'{x["cso"]} ({x.get("from_status") or "—"} → {x["to_status"]})' for x in other) + '.')
    if roll:
        L += ['## Also this week', 'Everything else that moved in the FedRAMP data, so nobody is left out:', ''] + [r + '  ' for r in roll] + ['', '*FedRAMP’s public data can trail a vendor’s announcement by a few days; anything that lands after this issue will be in the next one.*', '']
    L += ['**Want everything?**  ', f'FedCatalog tracks the full changelog, including Initial Implementation records, status changes and newly authorized offerings. [See everything that changed →]({ORIGIN}/new/)', '',
          '---', '**FedCatalog**  ', 'Federal Software in One Place  ', f'[Search FedCatalog]({ORIGIN}/) · [New & changed]({ORIGIN}/new/) · [How the data works]({ORIGIN}/methodology/)', '', 'Questions or corrections? Just reply to this email.', '', '— Mark']
    newsletter = '\n'.join(L)

    # ---- the machine changelog: everything
    C = [f'# Full changelog · {since} to {today}', '']
    for x in raw: C.append(f'- {x["transition_date"][:10]} · {x["csp"]} — {x["cso"]}' + (f' · {imp(x)}' if imp(x) else '') + f' · {status_words(x.get("from_status")) or "—"} → {status_words(x["to_status"])}' + (f' · {url(x)}' if url(x) else ''))

    os.makedirs(os.path.join(ROOT, 'drafts'), exist_ok=True)
    base = os.path.join(ROOT, 'drafts', today.isoformat())
    open(base + '.md', 'w', encoding='utf-8').write(newsletter); open(base + '.html', 'w', encoding='utf-8').write(md_to_html(newsletter))
    open(os.path.join(ROOT, 'drafts', f'changelog-{today.isoformat()}.md'), 'w', encoding='utf-8').write('\n'.join(C))
    words = len(re.sub(r'\[.*?\]\(.*?\)', '', newsletter).split())
    print(f'{len(authorized)} authorized · {len(inproc)} in process/initial · {len(delisted)} delisted · {len(other)} other · {len(og_expiring)} OneGov expiring · note: {"yes" if note else "none"} · ~{words} words')
    print('wrote', base + '.md', base + '.html', 'and the changelog')

if __name__ == '__main__':
    main()
