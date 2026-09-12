/* FedCatalog analytics.
   Paste your Google Analytics 4 measurement ID (looks like G-XXXXXXXXXX) between the
   quotes below. Leave it empty to disable analytics site-wide. This file is loaded by
   every page, so you only ever change it here. */
var FEDCATALOG_GA_ID = "";

(function () {
  if (!FEDCATALOG_GA_ID || !/^G-[A-Z0-9]+$/.test(FEDCATALOG_GA_ID)) return;
  if (navigator.doNotTrack === '1' || navigator.globalPrivacyControl) return;   // honor browser privacy signals
  var s = document.createElement('script');
  s.async = true; s.src = 'https://www.googletagmanager.com/gtag/js?id=' + FEDCATALOG_GA_ID;
  document.head.appendChild(s);
  window.dataLayer = window.dataLayer || [];
  function gtag() { window.dataLayer.push(arguments); }
  window.gtag = gtag;
  gtag('js', new Date());
  gtag('config', FEDCATALOG_GA_ID, { anonymize_ip: true, send_page_view: true });
  /* A few useful events beyond page views. */
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[href]'); if (!a) return;
    var href = a.getAttribute('href') || '';
    if (/^https?:\/\//.test(href) && a.host !== location.host) gtag('event', 'outbound_click', { link_url: href, link_text: (a.textContent || '').trim().slice(0, 80), page_path: location.pathname });
  });
  document.addEventListener('submit', function (e) {
    var f = e.target; if (f && f.getAttribute('role') === 'search') { var q = (f.querySelector('input[name=q]') || {}).value || ''; if (q) gtag('event', 'search', { search_term: q.slice(0, 100) }); }
  });
})();
