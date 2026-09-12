/* FedCatalog site.js — progressive enhancement over static HTML.
   1. Filters and sorting on list pages (DOM rows carry data-* attributes)
   2. Mobile filter sheet
   3. Search page (loads /assets/search-index.json on demand)
   4. Copy buttons, contact form (mailto), current-nav highlight
   5. Vendor pages: live "Government purchasing (observed)" from USAspending */
(function () {
  'use strict';
  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));
  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) { if (v === null || v === undefined || v === false) continue; if (k === 'class') node.className = v; else if (k === 'text') node.textContent = v; else if (k.startsWith('on')) node.addEventListener(k.slice(2), v); else node.setAttribute(k, v); }
    for (const c of [].concat(children || [])) { if (c === null || c === undefined || c === false) continue; node.append(typeof c === 'string' ? document.createTextNode(c) : c); }
    return node;
  }
  const clear = n => { while (n.firstChild) n.removeChild(n.firstChild); };
  const fmt = new Intl.NumberFormat('en-US');
  const RUNS = { aws: 'AWS', 'aws-gov': 'AWS GovCloud', azure: 'Azure', 'azure-gov': 'Azure Government', google: 'Google Cloud', oci: 'Oracle Cloud' };
  const FAMILY_LABEL = { aws: 'AWS', azure: 'Microsoft Azure', google: 'Google Cloud', oci: 'Oracle Cloud' };

  /* ---------- 1. Filters on list pages ---------- */
  const FILTER_KEYS = ['status', 'impact', 'family', 'agencies', 'onegov', 'dod'];
  function readParams() { const q = new URLSearchParams(location.search); const s = {}; for (const k of FILTER_KEYS.concat(['sort'])) if (q.get(k)) s[k] = q.get(k); return s; }
  function writeParams(state) {
    const q = new URLSearchParams(location.search);
    for (const k of FILTER_KEYS.concat(['sort'])) q.delete(k);
    for (const [k, v] of Object.entries(state)) if (v && !(k === 'sort' && v === 'agencies')) q.set(k, v);
    const s = q.toString();
    history.replaceState(null, '', location.pathname + (s ? '?' + s : '') + location.hash);
  }
  function rowMatches(row, state) {
    const d = row.dataset;
    if (state.status && d.status !== state.status) return false;
    if (state.impact && !(d.impact === state.impact || (state.impact === 'Moderate' && d.impact === '20x Moderate') || (state.impact === 'Low' && d.impact === '20x Low'))) return false;
    if (state.family && !(d.family || '').split(' ').includes(state.family)) return false;
    if (state.agencies && Number(d.agencies || 0) < Number(state.agencies)) return false;
    if (state.onegov && d.onegov !== '1') return false;
    if (state.dod && !(d.dod || '').split(' ').includes(state.dod)) return false;
    return true;
  }
  function applyFilters(section, state) {
    const rail = $('[data-rail]', section); if (!rail) return;
    for (const b of $$('button[data-filter]', rail)) b.setAttribute('aria-pressed', String(state[b.dataset.filter] === b.dataset.value));
    const sort = $('[data-sort]', rail); if (sort) sort.value = state.sort || 'agencies';
    const active = FILTER_KEYS.filter(k => state[k]).length;
    const clearBtn = $('[data-clear]', rail); if (clearBtn) clearBtn.hidden = !active;
    const countBadge = $('[data-filter-count]', section); if (countBadge) countBadge.textContent = active ? ' (' + active + ')' : '';
    const list = $('[data-rows]', section); if (!list) return;
    const rows = $$('.row', list);
    let shown = 0;
    for (const r of rows) { const ok = rowMatches(r, state); r.hidden = !ok; if (ok) shown++; }
    const key = state.sort || 'agencies';
    const sorted = rows.slice().sort((a, b) => {
      if (key === 'newest') return (b.dataset.auth || '').localeCompare(a.dataset.auth || '');
      if (key === 'name') return (a.dataset.name || '').localeCompare(b.dataset.name || '');
      if (key === 'vendor') return (a.dataset.vendor || '').localeCompare(b.dataset.vendor || '') || (a.dataset.name || '').localeCompare(b.dataset.name || '');
      return Number(b.dataset.agencies || 0) - Number(a.dataset.agencies || 0);
    });
    for (const r of sorted) list.append(r);
    const count = $('[data-count]', section); if (count) count.textContent = fmt.format(shown) + (shown === 1 ? ' result' : ' results');
    const empty = $('[data-empty]', section); if (empty) empty.hidden = shown > 0;
    /* query-string variants are not separate pages for search engines */
    let robots = $('meta[name="robots"]');
    if (active || (state.sort && state.sort !== 'agencies')) { if (!robots) { robots = el('meta', { name: 'robots', content: 'noindex,follow' }); document.head.append(robots); } }
    else if (robots && robots.dataset.dynamic) robots.remove();
    if (robots && !robots.dataset.dynamic && (active)) robots.dataset.dynamic = '1';
  }
  function bindRail(section, rail, getState, setState) {
    for (const b of $$('button[data-filter]', rail)) b.addEventListener('click', () => { const s = Object.assign({}, getState()); if (s[b.dataset.filter] === b.dataset.value) delete s[b.dataset.filter]; else s[b.dataset.filter] = b.dataset.value; setState(s); });
    const sort = $('[data-sort]', rail); if (sort) sort.addEventListener('change', () => { const s = Object.assign({}, getState()); s.sort = sort.value; setState(s); });
    const clearBtn = $('[data-clear]', rail); if (clearBtn) clearBtn.addEventListener('click', () => { const s = getState(); setState(s.sort ? { sort: s.sort } : {}); });
  }
  function setupList(section) {
    const rail = $('[data-rail]', section); if (!rail) return;
    let state = readParams();
    const render = () => { applyFilters(section, state); if (section.dataset.searchPage) renderSearch(state); };
    const setState = (s) => { state = s; writeParams(state); render(); };
    bindRail(section, rail, () => state, setState);
    const open = $('[data-open-sheet]', section);
    if (open) open.addEventListener('click', () => {
      const sheet = el('div', { class: 'sheet', role: 'dialog', 'aria-label': 'Filters' });
      const close = () => sheet.remove();
      const copy = rail.cloneNode(true);
      sheet.append(el('div', { class: 'back', onclick: close }), el('div', { class: 'body' }, [el('div', { class: 'grab' }), copy, el('button', { class: 'btn done', type: 'button', text: 'Done', onclick: close })]));
      bindRail(section, copy, () => state, (s) => { setState(s); for (const b of $$('button[data-filter]', copy)) b.setAttribute('aria-pressed', String(state[b.dataset.filter] === b.dataset.value)); const cb = $('[data-clear]', copy); if (cb) cb.hidden = !FILTER_KEYS.filter(k => state[k]).length; });
      document.body.append(sheet);
    });
    section._render = render;
    render();
  }

  /* ---------- 3. Search ---------- */
  const SYN = [
    [/\b(gen ?ai|generative|llm|large language|chat ?bot|copilot|assistant|summari[sz]\w*|foundation model|machine learning|\bml\b|\bai\b|nlp|computer vision)\b/, ['Artificial Intelligence (AI)']],
    [/\b(siem|soar|\bsoc\b|endpoint|edr|xdr|zero[ -]trust|ztna|firewall|threat|vulnerab\w*|phishing|identity|iam|sso|mfa|secur\w*|cyber\w*|encryption|pki|dlp|attack surface|pen ?test)\b/, ['Cybersecurity & Risk Management']],
    [/\b(data (lake|warehouse|platform|cloud|catalog)|lakehouse|analytics?|business intelligence|\bbi\b|dashboards?|etl|data pipeline|database|sql)\b/, ['Analytics', 'Data Management']],
    [/\b(observab\w*|monitoring|apm|logs?|logging|incident|itsm|itom|aiops|service desk|help ?desk|ticketing)\b/, ['Operations Management', 'System Administration']],
    [/\b(video|meeting|webinar|chat|messag\w*|email|collab\w*|whiteboard|intranet)\b/, ['Collaboration', 'Communication']],
    [/\b(cms|website|web content|content management|documents?|records?|e-?sign\w*|forms?|pdf|workflow)\b/, ['Content Management System (CMS)']],
    [/\b(crm|constituent|case management|citizen service|311)\b/, ['Customer Relations Management (CRM)', 'Customer Service']],
    [/\b(contact center|call center|ivr|omnichannel)\b/, ['Contact Center']],
    [/\b(\bhr\b|payroll|workforce|talent|recruit\w*|onboarding|learning|lms|training|e-?learning)\b/, ['Human Resources', 'Education & Training', 'Learning Management']],
    [/\b(grc|compliance|risk|audit|policy|governance|ato|oscal)\b/, ['Governance, Risk, and Compliance (GRC)', 'Legal & Policy']],
    [/\b(devops|devsecops|ci\/?cd|source code|developer|git|apis?|low[ -]code|no[ -]code|app dev\w*|testing|qa)\b/, ['Development Tools']],
    [/\b(backup|storage|archiv\w*|file (share|transfer)|object storage|disaster recovery)\b/, ['Storage']],
    [/\b(network\w*|sd-?wan|cdn|dns|vpn|sase|load balanc\w*|edge)\b/, ['Network Management', 'Virtual Private Network (VPN)']],
    [/\b(mdm|mobile device|uem|device management)\b/, ['Mobile Device Management (MDM)']],
    [/\b(grants?)\b/, ['Grant Management']],
    [/\b(finance|financial|accounting|erp|procure\w*|invoic\w*|budget\w*|expense)\b/, ['Finance', 'Accounting']],
    [/\b(health|medical|ehr|telehealth|clinical|patient)\b/, ['Health & Wellness']],
    [/\b(law enforcement|body ?cam\w*|evidence|police|investigat\w*)\b/, ['Law Enforcement']],
    [/\b(fleet|vehicle|telematics)\b/, ['Fleet Management']],
    [/\b(travel)\b/, ['Travel Management']],
    [/\b(research|survey|lab)\b/, ['Research']],
    [/\b(marketing|outreach|campaign|social media)\b/, ['Marketing & Sales']],
  ];
  const STOP = new Set(['i', 'a', 'an', 'the', 'need', 'for', 'to', 'of', 'and', 'or', 'with', 'that', 'can', 'use', 'my', 'our', 'we', 'tool', 'tools', 'software', 'product', 'products', 'platform', 'solution', 'ready', 'want', 'looking', 'in', 'on', 'is', 'what', 'something', 'internal', 'government', 'federal', 'agency', 'gov']);
  function interpret(query) {
    const q = query.toLowerCase().trim(), filters = {};
    if (/\bhigh\b/.test(q)) filters.impact = 'High'; else if (/\bmoderate\b/.test(q)) filters.impact = 'Moderate'; else if (/\bli-?saas\b/.test(q)) filters.impact = 'LI-SaaS'; else if (/\blow\b/.test(q)) filters.impact = 'Low';
    if (/\b(authori[sz]ed|certified)\b/.test(q)) filters.status = 'authorized'; else if (/\bin[ -]process\b/.test(q)) filters.status = 'in-process';
    if (/\baws\b|\bgovcloud\b/.test(q) && !/^aws$/.test(q)) filters.family = 'aws';
    if (/\bazure\b/.test(q) && !/^azure$/.test(q)) filters.family = 'azure';
    if (/\bgcp\b|\bgoogle cloud\b|\bon google\b/.test(q)) filters.family = 'google';
    const il = q.match(/\bil ?([2456])\b/); if (il) filters.dod = 'IL' + il[1];
    if (/\bonegov\b/.test(q)) filters.onegov = '1';
    const functions = new Set(), covered = new Set();
    for (const [re, fns] of SYN) { const m = q.match(new RegExp(re.source, 'gi')); if (!m) continue; for (const f of fns) functions.add(f); for (const hit of m) for (const t of hit.toLowerCase().split(/[^a-z0-9+#.]+/)) if (t) covered.add(t); }
    const terms = q.replace(/\b(fedramp|high|moderate|low|li-?saas|authori[sz]ed|certified|in[ -]process|on aws|aws|azure|gcp|google|govcloud|il ?[2456]|dod|onegov|marketplace)\b/g, ' ').split(/[^a-z0-9+#.]+/).filter(t => t.length > 1 && !STOP.has(t) && !covered.has(t));
    return { filters, functions: Array.from(functions), terms, soft: Array.from(covered).filter(t => t.length > 2 && !STOP.has(t)) };
  }
  let INDEX = null;
  const BASE = (document.querySelector('meta[name="fc-base"]') || {}).content || '/';
  async function loadIndex() { if (!INDEX) { const r = await fetch(BASE + 'assets/search-index.json'); INDEX = await r.json(); } return INDEX; }
  function vendorKey(name) { return String(name || '').replace(/\s*\(.*?\)\s*/g, ' ').replace(/[.,]+$/, '').replace(/,?\s*\b(inc|llc|corp|corporation|incorporated|company|co|ltd|lp|plc|pbc)\b\.?$/i, '').trim(); }
  function findVendor(text) { const key = vendorKey(text).toLowerCase(); if (!key) return null; const hits = INDEX.vendors.filter(v => v.n.toLowerCase() === key); if (hits.length) return hits[0]; const part = INDEX.vendors.filter(v => v.n.toLowerCase().includes(key) || key.includes(v.n.toLowerCase())); return part.sort((a, b) => a.n.length - b.n.length)[0] || null; }
  function search(q, extra) {
    const it = interpret(q), f = Object.assign({}, it.filters, extra), out = [];
    for (const p of INDEX.products) {
      if (f.impact && p.i !== f.impact && !(f.impact === 'Moderate' && p.i === '20x Moderate') && !(f.impact === 'Low' && p.i === '20x Low')) continue;
      if (f.status && p.s !== f.status) continue;
      if (f.family && !p.fam.includes(f.family)) continue;
      if (f.agencies && p.a < Number(f.agencies)) continue;
      if (f.dod && !(p.dod || []).includes(f.dod)) continue;
      if (f.onegov && !p.og) continue;
      let score = 0; const vend = p.v.toLowerCase(), name = p.n.toLowerCase(), text = (p.v + ' ' + p.n + ' ' + p.d).toLowerCase();
      for (const t of it.terms) { if (vend.includes(t)) score += vend === t ? 30 : 12; else if (name.includes(t)) score += 8; else if (text.includes(t)) score += 2; else score -= 6; }
      for (const t of it.soft) { if (name.includes(t)) score += 6; else if (text.includes(t)) score += 3; }
      score += it.functions.filter(x => p.f.includes(x)).length * 5;
      if (!it.terms.length && !it.functions.length) score = 1;
      if (score <= 0) continue;
      score += p.s === 'authorized' ? 1 : 0; score += p.a > 5 ? 1 : 0;
      out.push({ p, score });
    }
    out.sort((a, b) => b.score - a.score || b.p.a - a.p.a);
    return { it, results: out.map(x => x.p) };
  }
  function mono(name) { const words = String(name || '?').replace(/[^A-Za-z0-9 ]/g, ' ').split(/\s+/).filter(Boolean); const text = (words.length >= 2 ? words[0][0] + words[1][0] : (words[0] || '?').slice(0, 2)).toUpperCase(); let h = 0; for (const ch of String(name || '')) h = (h * 31 + ch.charCodeAt(0)) >>> 0; return el('div', { class: 'mono m' + (h % 6), 'aria-hidden': 'true', text }); }
  function rowFromIndex(p) {
    const runs = []; p.r.forEach((r, i) => { if (i) runs.push(' · '); runs.push(RUNS[r]); }); p.rn.forEach(r => { if (runs.length) runs.push(' · '); runs.push(el('span', { class: 'named', text: RUNS[r] })); });
    return el('a', { class: 'row', href: BASE + p.u.replace(/^\//, ''), 'data-status': p.s, 'data-impact': p.i, 'data-family': p.fam.join(' '), 'data-agencies': String(p.a), 'data-name': p.n.toLowerCase(), 'data-vendor': p.v.toLowerCase() }, [
      mono(p.v), el('div', { class: 'main' }, [el('div', { class: 'name', text: p.n }), el('div', { class: 'sub', text: p.v + (p.f.length ? ' · ' + p.f.slice(0, 2).join(' · ') : '') })]),
      el('div', { class: 'meta' }, [el('span', { class: 'c-st' }, el('span', { class: 'status s-' + p.s, text: p.sl })), el('span', { class: 'c-im', text: p.i }), el('span', { class: 'c-ro' }, runs.length ? runs : ['—']), el('span', { class: 'c-ag', text: p.a ? p.a + (p.a === 1 ? ' agency' : ' agencies') : '—' })]),
      el('span', { class: 'chev', 'aria-hidden': 'true', text: '›' })]);
  }
  async function renderSearch(state) {
    const q = new URLSearchParams(location.search).get('q') || '';
    const section = $('[data-search-page]'); const out = $('[data-search-results]', section); const title = $('[data-search-title]');
    const input = $('#q'); if (input && !input.value) input.value = q;
    if (!q.trim()) return;
    await loadIndex();
    const vs = q.match(/^(.+?)\s+(?:vs\.?|versus)\s+(.+)$/i);
    const { it, results } = search(q, {});
    clear(out);
    title.textContent = results.length ? '“' + q + '”' : 'Nothing matches “' + q + '”';
    const read = []; if (it.functions.length) read.push(it.functions.join(', ')); if (it.filters.impact) read.push('impact ' + it.filters.impact); if (it.filters.status) read.push(it.filters.status.replace('-', ' ')); if (it.filters.family) read.push('runs on ' + FAMILY_LABEL[it.filters.family]); if (it.filters.dod) read.push('vendor with DoD ' + it.filters.dod + ' provisional authorization'); if (it.filters.onegov) read.push('OneGov vendor');
    if (read.length) title.append(el('small', { text: 'Read as ' + read.join(' · ') }));
    if (vs) { const a = findVendor(vs[1]), b = findVendor(vs[2]); if (a && b) out.append(el('p', { class: 'note', style: 'margin-bottom:12px' }, ['Compare: ', el('a', { href: BASE + a.u.replace(/^\//, ''), text: a.n }), ' and ', el('a', { href: BASE + b.u.replace(/^\//, ''), text: b.n }), ' — open each vendor page for offerings, impact levels, agency records and purchasing options side by side.'])); }
    const vendor = !/\s(on|for|with)\s/.test(q) ? findVendor(q) : null;
    if (vendor) out.append(el('p', { class: 'note', style: 'margin-bottom:12px' }, [vendor.n.toLowerCase() === q.trim().toLowerCase() ? 'Vendor page: ' : 'Did you mean the vendor ', el('a', { href: BASE + vendor.u.replace(/^\//, ''), text: vendor.n }), vendor.n.toLowerCase() === q.trim().toLowerCase() ? ' →' : '?']));
    if (vendor && it.filters.dod) {
      const rows = (vendor.dod || []).filter(r => r.il === it.filters.dod);
      out.append(el('p', { class: 'note', style: 'margin-bottom:12px' }, rows.length ? ['On the DoD Cyber Exchange list, ' + vendor.n + ' at ' + it.filters.dod + ': ' + rows.map(r => r.cso + ' — ' + r.st).join('; ') + '. ', el('a', { href: BASE + vendor.u.replace(/^\//, '') + '#dod', text: 'Details on the vendor page →' })] : ['The DoD Cyber Exchange list has no ' + it.filters.dod + ' entry for ' + vendor.n + '. ', el('a', { href: BASE + 'dod/' + it.filters.dod.toLowerCase() + '/', text: 'See all ' + it.filters.dod + ' listings →' })]));
    }
    if (vendor && it.filters.onegov && !vendor.og) out.append(el('p', { class: 'note', style: 'margin-bottom:12px' }, ['GSA lists no current OneGov agreement for ' + vendor.n + '. ', el('a', { href: BASE + 'onegov/', text: 'See all OneGov agreements →' })]));
    if (!results.length) { out.append(el('p', { class: 'note', text: 'No offerings match the filters read from your search. Try fewer words, a category, or describe the need differently.' })); return; }
    const list = el('div', { class: 'rows is-table', 'data-rows': '' });
    list.append(el('div', { class: 'thead', 'aria-hidden': 'true' }, ['', 'Product', 'FedRAMP', 'Impact', 'Runs on', 'Agencies', ''].map(t => el('span', { text: t }))));
    let shown = 0; const PAGE = 40;
    const more = el('div', { class: 'more' }); const btn = el('button', { class: 'btn alt', type: 'button', onclick: () => draw() });
    function draw() { for (const p of results.slice(shown, shown + PAGE)) list.append(rowFromIndex(p)); shown = Math.min(results.length, shown + PAGE); clear(more); if (shown < results.length) { btn.textContent = 'Show ' + Math.min(PAGE, results.length - shown) + ' more'; more.append(btn); } applyFilters(section, state || readParams()); }
    out.append(list, more); draw();
    document.title = '“' + q + '” — Search | FedCatalog';
  }

  /* ---------- 5. USAspending purchasing (vendor pages) ---------- */
  const USA = 'https://api.usaspending.gov/api/v2', TYPES = ['A', 'B', 'C', 'D'];
  async function usa(path, body) { for (let a = 0; a <= 2; a++) { const r = await fetch(USA + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }); if ((r.status === 429 || r.status === 503) && a < 2) { await new Promise(x => setTimeout(x, 800 * (a + 1))); continue; } if (!r.ok) throw new Error('USAspending HTTP ' + r.status); return r.json(); } }
  function fyNow() { const d = new Date(); return d.getMonth() >= 9 ? d.getFullYear() + 1 : d.getFullYear(); }
  function compact(v) { const a = Math.abs(v); if (a >= 1e9) return '$' + (v / 1e9).toFixed(a >= 1e10 ? 0 : 1) + 'B'; if (a >= 1e6) return '$' + (v / 1e6).toFixed(a >= 1e8 ? 0 : 1) + 'M'; if (a >= 1e3) return '$' + (v / 1e3).toFixed(0) + 'K'; return '$' + v.toFixed(0); }
  const RE_SUF = /,?\s*(L\.?L\.?C\.?|INC\.?|CORP\.?|CORPORATION|INCORPORATED|COMPANY|CO\.?|LTD\.?|L\.?P\.?|P\.?C\.?|HOLDINGS?|GROUP)\.?(?=\s*,|\s*$)/gi;
  function tidy(raw) { const up = String(raw || '').toUpperCase().replace(/\s+&\s+/g, ' AND ').replace(RE_SUF, '').replace(/[.,]+$/, '').trim(); return up.split(' ').map(w => w.length <= 3 && /^[A-Z]+$/.test(w) ? w : w.toLowerCase().replace(/^([a-z])/, m => m.toUpperCase())).join(' '); }
  async function purchasing(section) {
    const vendorName = section.dataset.vendor, terms = JSON.parse(section.dataset.terms || '[]'), fedramp = Number(section.dataset.fedrampAgencies || 0);
    const last = fyNow(), first = last - 4, window = { start_date: (first - 1) + '-10-01', end_date: last + '-09-30' }, label = 'FY' + String(first).slice(2) + '–FY' + String(last).slice(2) + ' to date';
    const f = { award_type_codes: TYPES, time_period: [window], keywords: terms }, fd = { award_type_codes: TYPES, time_period: [window], recipient_search_text: [terms[0]] };
    try {
      const [time, byRec, byAg, top, direct] = await Promise.all([
        usa('/search/spending_over_time/', { group: 'fiscal_year', filters: f }), usa('/search/spending_by_category/recipient/', { filters: f, limit: 10, page: 1 }), usa('/search/spending_by_category/awarding_agency/', { filters: f, limit: 8, page: 1 }),
        usa('/search/spending_by_award/', { filters: f, fields: ['Award ID', 'Recipient Name', 'Award Amount', 'Awarding Agency', 'Awarding Sub Agency', 'Description', 'End Date', 'generated_internal_id'], limit: 6, page: 1, sort: 'Award Amount', order: 'desc' }), usa('/search/spending_over_time/', { group: 'fiscal_year', filters: fd })]);
      const series = time.results.map(r => ({ fy: Number(r.time_period.fiscal_year), amount: r.aggregated_amount || 0 })).sort((a, b) => a.fy - b.fy);
      const total = series.reduce((s, x) => s + x.amount, 0), directTotal = direct.results.reduce((s, r) => s + (r.aggregated_amount || 0), 0);
      const vt = tidy(vendorName).toLowerCase();
      const recs = byRec.results.filter(r => r.name && r.name !== 'MULTIPLE RECIPIENTS').map(r => ({ name: tidy(r.name), amount: r.amount, direct: tidy(r.name).toLowerCase().includes(vt) || vt.includes(tidy(r.name).toLowerCase()) }));
      const ags = byAg.results.map(r => ({ name: r.name, amount: r.amount }));
      clear(section);
      section.append(el('h2', { text: 'Government purchasing (observed)' }));
      if (!total) { section.append(el('p', { class: 'prose', text: 'No federal contract awards in ' + label + ' mention ' + terms.map(t => '“' + t + '”').join(' or ') + '. Orders that name only a reseller, or no product at all, are not captured.' })); return; }
      const max = Math.max(...series.map(x => x.amount), 1);
      section.append(
        el('p', { class: 'prose', text: 'Federal contract obligations on awards whose description or recipient mentions ' + terms.map(t => '“' + t + '”').join(' or ') + ', ' + label + '. This is a floor: many software orders name only the reseller.' }),
        el('div', { class: 'facts', style: 'margin-top:14px' }, [
          el('div', { class: 'fact' }, [el('small', { text: 'On awards mentioning the vendor' }), el('b', { text: compact(total) }), el('span', { text: label })]),
          el('div', { class: 'fact' }, [el('small', { text: 'Paid directly to the vendor' }), el('b', { text: compact(directTotal) }), el('span', { text: 'recipient or parent name matches' })]),
          el('div', { class: 'fact' }, [el('small', { text: 'Agencies buying' }), el('b', { text: String(ags.length) + (ags.length >= 8 ? '+' : '') }), el('span', { text: 'departments with obligations' })]),
          el('div', { class: 'fact' }, [el('small', { text: 'FedRAMP authorization records' }), el('b', { text: String(fedramp) }), el('span', { text: 'approved is not the same as purchased' })])]),
        el('div', { class: 'bars' }, series.map(x => el('div', { class: 'bar' + (x.fy === fyNow() ? ' is-partial' : '') }, [el('em', { text: compact(x.amount) }), el('i', { style: 'height:' + Math.max(2, x.amount / max * 100).toFixed(0) + '%' }), el('span', { text: 'FY' + String(x.fy).slice(2) })]))),
        recs.length ? el('h3', { class: 'h3', text: 'Who received the money' }) : null,
        recs.length ? el('ul', { class: 'lines' }, [...recs.filter(r => r.direct), ...recs.filter(r => !r.direct)].map(r => el('li', {}, [el('span', {}, [r.name, ' ', el('small', { class: r.direct ? 'tone-good' : '', text: r.direct ? 'vendor direct' : 'reseller / prime' })]), el('b', { text: compact(r.amount) })]))) : null,
        ags.length ? el('h3', { class: 'h3', text: 'Top buying departments' }) : null,
        ags.length ? el('ul', { class: 'lines' }, ags.map(a => el('li', {}, [el('span', { text: a.name }), el('b', { text: compact(a.amount) })]))) : null,
        top.results.length ? el('h3', { class: 'h3', text: 'Largest awards mentioning the vendor' }) : null,
        top.results.length ? el('ul', { class: 'awards' }, top.results.map(a => el('li', {}, [el('div', { class: 'award-head' }, [el('b', { text: tidy(a['Recipient Name']) }), el('span', { text: compact(a['Award Amount'] || 0) })]), el('p', { class: 'award-desc', text: String(a.Description || '').toLowerCase().replace(/\b([a-z])/g, m => m.toUpperCase()).slice(0, 140) }), el('p', { class: 'award-meta', text: [a['Award ID'], /defense/i.test(a['Awarding Agency'] || '') && a['Awarding Sub Agency'] ? a['Awarding Sub Agency'] : a['Awarding Agency'], a['End Date'] ? 'ends ' + a['End Date'] : null].filter(Boolean).join(' · ') }), el('div', { class: 'award-links' }, el('a', { class: 'link', href: 'https://www.usaspending.gov/award/' + encodeURIComponent(a.generated_internal_id), target: '_blank', rel: 'noopener noreferrer', text: 'USAspending →', style: 'color:var(--orange-hover)' }))]))) : null,
        el('p', { class: 'source', text: 'USAspending.gov · prime contracts (A–D) · obligations by action date · keyword match on award text and recipient names · fetched ' + new Date().toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }) }));
    } catch (e) { const n = $('.note', section); if (n) n.textContent = 'Couldn’t reach USAspending.gov right now (' + e.message + '). The data is public at usaspending.gov.'; }
  }

  /* ---------- 4. Small behaviours ---------- */
  function renderSignup() {
    const cfg = window.FEDCATALOG_SIGNUP; if (!cfg || !/^https?:\/\//.test(cfg.formUrl || '')) return;
    for (const slot of $$('[data-signup]')) {
      const ctx = slot.dataset.context, h1 = document.querySelector('h1');
      const heading = ctx === 'list' && h1 ? 'New ' + h1.childNodes[0].textContent.trim() + ' authorizations, weekly' : cfg.heading;
      const input = el('input', { type: 'email', name: 'email', placeholder: 'you@agency.gov', 'aria-label': 'Email address', required: 'required' });
      const form = el('form', { onsubmit: (e) => { e.preventDefault(); const u = cfg.formUrl + (cfg.formUrl.includes('?') ? '&' : '?') + 'email=' + encodeURIComponent(input.value.trim()); if (window.gtag) gtag('event', 'sign_up', { method: 'newsletter', page_path: location.pathname }); window.open(u, '_blank', 'noopener'); } }, [input, el('button', { type: 'submit', text: cfg.button || 'Subscribe' })]);
      clear(slot); slot.append(el('h2', { text: heading }), el('p', { text: cfg.blurb }), form, el('small', { text: 'Opens the subscribe page in a new tab. No spam; unsubscribe anytime.' })); slot.hidden = false;
    }
  }
  function setup() {
    renderSignup();
    if (window.FEDCATALOG_TEXT) for (const n of $$('[data-text]')) { const t = window.FEDCATALOG_TEXT[n.dataset.text]; if (typeof t === 'string' && t.trim() && n.textContent.trim() !== t.trim()) n.textContent = t; }
    const here = location.pathname;
    for (const a of $$('.nav a')) { const h = new URL(a.getAttribute('href'), location.href).pathname; if (h !== '/' && (here === h || here.startsWith(h) || (/\/categories\/$/.test(h) && /\/(categories|cloud|fedramp|dod|onegov)\//.test(here)))) a.classList.add('is-current'); }
    for (const b of $$('[data-copy]')) b.addEventListener('click', async () => { try { await navigator.clipboard.writeText(b.dataset.copy); b.classList.add('is-copied'); b.textContent = 'Copied'; setTimeout(() => { b.classList.remove('is-copied'); b.textContent = 'Copy summary'; }, 1400); } catch (_) { window.prompt('Copy this:', b.dataset.copy); } });
    const form = $('[data-contact-form]');
    if (form) {
      const q = new URLSearchParams(location.search); if (q.get('product')) { const f = $('#f-id'); if (f) f.value = q.get('product'); }
      form.addEventListener('submit', (e) => { e.preventDefault(); const d = Object.fromEntries(new FormData(form).entries()); const body = ['Vendor: ' + (d.vendor || ''), 'Product: ' + (d.product || ''), 'FedRAMP ID: ' + (d.id || ''), 'Government offering URL: ' + (d.gov || ''), 'AWS Marketplace listing: ' + (d.aws || ''), 'Azure Marketplace listing: ' + (d.azure || ''), 'Google Cloud Marketplace listing: ' + (d.google || ''), 'Other URL: ' + (d.other || ''), 'Notes: ' + (d.notes || ''), 'Contact: ' + (d.email || '')].join('\n'); location.href = 'mailto:catalog@fedcatalog.com?subject=' + encodeURIComponent('FedCatalog update: ' + (d.vendor || '') + ' — ' + (d.product || '')) + '&body=' + encodeURIComponent(body); });
    }
    for (const s of $$('section')) { if ($('[data-rail]', s)) { if ($('[data-search-results]', s)) { s.dataset.searchPage = '1'; } setupList(s); } }
    const sp = $('[data-search-page]'); if (sp) renderSearch(readParams());
    const purch = $('[data-purchasing]'); if (purch) purchasing(purch);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', setup); else setup();
})();
