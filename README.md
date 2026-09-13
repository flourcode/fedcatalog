# FedCatalog — fedcatalog.com

Independent federal software reference. A static website generated from public
data: FedRAMP Marketplace, DoD Cyber Exchange, GSA OneGov and USAspending.

## Hands-off mode (recommended): the site rebuilds itself nightly

Once set up, you never upload again. GitHub rebuilds the site from the sources
every night, verifies it, and commits it; Amplify redeploys on its own. If a
source is unreadable, last night's data is kept. If anything fails, nothing is
published and GitHub emails you. The job downloads about 5 MB a night and
commits only when something changed. The repo's history grows slowly as a
result; if it ever feels heavy (years from now), a developer can squash it in
minutes without affecting the site.

One-time setup, done from GitHub's website:
1. Put the **whole project** in the repo (not just the site): `src/`, `.github/`,
   `README.md`, plus the site files at the root. The full-project zip is laid out
   this way; upload it with GitHub Desktop.
2. Repo → Settings → Actions → General → Workflow permissions → choose
   **Read and write permissions** → Save.
3. Repo → Actions tab → "Nightly rebuild from public sources" → **Run workflow**
   once, and watch it go green. From then on it runs at 09:30 UTC daily.

The only thing the site depends on is FedRAMP's public data, which the job
refreshes nightly along with the FedRAMP changelog. It also re-reads the DoD
Cyber Exchange table (keyless; keeps the previous copy if the page changes) and
checks GSA's OneGov feed for new titles — both secondary, neither can break the
site. USAspending is live in the browser and optional. Marketplace listings,
OneGov details and vendor pages are small hand-maintained files.

**Architectural rule:** FedCatalog must stay understandable and maintainable by
one person. No API credentials, databases, cloud services or extra
infrastructure get added unless Mark specifically approves them. The promise is
"FedCatalog shows what it can verify and labels what it can't," not
completeness.

## Uploading by hand (if you don't use hands-off mode): use GitHub Desktop, not the website

The site is about 1,550 folders. GitHub's web page only lets you upload 100
files at a time, so use the free **GitHub Desktop** app instead (desktop.github.com):

1. In GitHub Desktop: File → Clone repository → pick your repo. It creates a
   folder on your computer.
2. Delete whatever is in that folder, then copy the *contents* of `dist/`
   into it.
3. Back in GitHub Desktop, type a summary like "Update site" and click
   **Commit to main**, then **Push origin**. Amplify redeploys on its own.

That's the entire publishing routine, every time, for any size of site.

## What to upload (the short version)

Everything you need to publish is inside **`dist/`**. Upload the *contents* of
`dist/` to the root of your GitHub repo (so `index.html`, `sitemap.xml`,
`robots.txt`, `404.html`, `CNAME` and the `assets/`, `software/`, `vendors/`…
folders all sit at the top level). Point Amplify at the repo, attach
`fedcatalog.com`, done. Nothing else in this project is needed to run the site.

`src/` is the generator — the machinery that turns the data into those 1,500+
pages. You don't need to touch it; ask for a rebuild when you want fresh data.

## Amplify settings to check once

1. **Domain:** in Amplify → Domain management, add `fedcatalog.com` and keep
   the option that redirects `www.fedcatalog.com` to `fedcatalog.com` (Amplify
   offers this by default). HTTPS is automatic.
2. **404 page:** Amplify → Rewrites and redirects → add a rule:
   Source `/<*>` · Target `/404.html` · Type `404 (Rewrite)`. Without this,
   unknown URLs show Amplify's plain error instead of the site's own page.
3. **Clean URLs:** Amplify serves `/vendors/databricks/` from
   `vendors/databricks/index.html` automatically. No rule needed.

## The one rule: `src/` is the source of truth

The nightly job reads `src/` and regenerates every page at the top level of
the repo. Edit files inside `src/`; never edit generated pages or the copies
in `assets/`, because they are rewritten every night. Where things live:

| You want to change | Edit this file (inside `src/`) |
|---|---|
| Home headline or the line under it | `src/templates/site-text.js` |
| Google Analytics ID | `src/templates/analytics.js` |
| Newsletter signup URL | `src/templates/signup.js` |
| A product's "Visit government offering" link | `src/data/product_sites.json` (by FedRAMP ID) |
| A vendor page's "Visit government page" link | `src/data/vendor_sites.json` (by vendor slug) |
| Marketplace listings and seller pages | `src/data/marketplace_listings.json` |
| OneGov agreements | `src/data/onegov.json` |
| DoD / OneGov vendor name matching | `src/data/crosswalk.json` |
| About, Methodology, Privacy, Terms, Contact copy | `src/build.py` (the `ABOUT`, `MARK`, `METHODOLOGY`, `PRIVACY`, `TERMS` blocks near the middle) |
| Your photo | `src/assets/mark.jpg` |

Save, commit with GitHub Desktop, and the next nightly run publishes it. (If
you're not using the nightly job, ask for a rebuild.)

## Changing the words at the top (no rebuild needed)

`assets/site-text.js` holds the header tagline, footer tagline, home headline
and home sub-headline. Edit the text between the quotes, save, and upload that
one file; every page picks it up. The hero itself lives only in `index.html`
if you want to change more than the words. Everything else (product, vendor
and agency pages) is generated from data and never hand-edited.

## Email signup (one file) and the weekly draft

1. Create a newsletter at Beehiiv or Kit and copy its subscribe-page URL.
2. Open `src/templates/signup.js` (with the nightly job) or `assets/signup.js` (without it), paste the URL between the quotes on `formUrl`, save, commit. The signup box appears on the home page, the
   New page and every category page. Empty URL, no box.
3. Each week, open `drafts/latest.html` in the repo on GitHub (the nightly job writes it; it covers the last 14 days) — newly authorized offerings grouped by
   impact level, Ready and In-Process entries, other status changes, DoD
   provisional authorizations expiring within 60 days, and new or expiring
   OneGov agreements, every line linked to its FedCatalog page. Paste the HTML
   into your newsletter, read it over, send. Without the nightly job: `python3 src/weekly_draft.py --refresh` produces the same files.

## Fixing a specific link

Two small files, one line each:

- **A product's "Visit government offering" link** (also the "Vendor direct"
  row): `src/data/product_sites.json`, keyed by the FedRAMP ID shown under the
  product name on the page. Example already in the file: AWS US East/West
  (`AGENCYAMAZONEW`) → aws.amazon.com/government-education/government/.
- **A vendor page's "Visit government page" button:** `src/data/vendor_sites.json`,
  keyed by the vendor's URL slug (the last part of the vendor page address).

Edit the file, save, and the next rebuild uses it (nightly if the job is on,
or ask me).

## Vendor page links

The "Visit government page" button on a vendor page uses `src/data/vendor_sites.json`
when the vendor has an entry there; otherwise the build picks the most common
domain across the vendor's FedRAMP offerings, preferring a public-sector page.
Add an entry for any vendor whose derived link is wrong (a few large vendors are
seeded). It's a one-line edit per vendor; ask for a rebuild afterward.

## Exact marketplace listings

`src/data/marketplace_listings.json` records exact marketplace listings and
seller pages per vendor (AWS, Azure, Google, Oracle). Each entry has the
listing URL, title, publisher, a note, the date checked, and optionally the
FedRAMP IDs it serves (for example, a GovCloud listing). On product pages a
listing tied to that offering appears under "Confirmed buying paths" (✓
verified, or ○ vendor-supplied and reviewed); the vendor's other listings appear
under "<Vendor>'s marketplace listings"; markets with nothing on file show a
search labeled "exact listing not yet verified." Add an entry with
`"source": "vendor"` when a vendor sends it and you've looked at it. Two
minutes per entry, on your schedule; there is no obligation to verify anything.

## Procurement links

Product and vendor pages show "Buying paths": confirmed paths first (a GSA OneGov
agreement, the government page from the FedRAMP record), then "other places to
check" — a search for the vendor on AWS Marketplace, Azure
Marketplace, Google Cloud Marketplace, GSA eLibrary, GSA Advantage and NASA
SEWP. Nothing is verified by hand and nothing needs to be submitted; the
`/buy/` page links to the marketplaces and vehicles themselves.

## Google Analytics (one file, once)

Open `src/templates/analytics.js` (with the nightly job) or `assets/analytics.js` (without it) and paste your GA4 measurement ID (it looks like
`G-XXXXXXXXXX`) between the quotes on the first line:

```
var FEDCATALOG_GA_ID = "G-XXXXXXXXXX";
```

That's it. Every page loads this file, so all 1,500+ pages are tracked, plus
search terms and outbound clicks as events. Leave the quotes empty to turn it
off. The file honors browser "Do Not Track" and Global Privacy Control, and the
Privacy page already describes this use. When I regenerate the site, I keep
your ID in place — but check the file after any rebuild.

## Email

The site uses `mark@fedcatalog.com` on the Contact, Privacy and Terms pages
and in the vendor-update form. **That address does not exist until you set up
email for the domain** (for example, an email-forwarding rule in your domain
registrar, or a mailbox). Do that before launch, or the contact form will
address mail to nowhere.

## After launch: Google Search Console

1. Add `fedcatalog.com` as a **Domain property** (verify with the DNS record
   Google gives you; add it in Route 53).
2. Submit `https://fedcatalog.com/sitemap.xml`.
3. Use *URL inspection* on the homepage, one vendor page, one product page, one
   category and one agency page; confirm "URL is on Google" or "can be indexed".
4. Watch *Pages* under Indexing over the following weeks. Do not request
   indexing page by page; the sitemap does that job.
5. Add the site to Bing Webmaster Tools and submit the same sitemap.

## Keeping data fresh

FedRAMP publishes new data daily and the site is rebuilt from it. To refresh:

```
python3 src/build_snapshot.py --refresh     # fetch FedRAMP, re-parse DoD table, check OneGov feed
python3 src/build.py                        # regenerate dist/
python3 src/verify.py                       # crawl dist/ and check links, titles, canonicals
```

Then upload the new `dist/` contents. Monthly is plenty; the "Data refreshed"
date in the footer and on each page shows what the build used. Vendor pages'
"Government purchasing" section is always live from USAspending regardless.

`src/data/onegov.json` is curated by hand; `--refresh` prints any agreement
titles in GSA's feed that aren't in the file yet. `src/data/crosswalk.json`
maps DoD and OneGov provider names to FedRAMP vendor names when the automatic
match fails.

## Site structure

```
/                          home
/software/                 all offerings A–Z         /software/<offering>/
/vendors/                  all vendors A–Z           /vendors/<vendor>/
/agencies/                 agencies                  /agencies/<agency>/
/categories/               browse                    /categories/<category>/
/fedramp/authorized|in-process|ready/               status pages
/fedramp/high|moderate|low|li-saas/                 impact pages
/cloud/aws|aws-govcloud|azure|azure-government|google-cloud|oracle-cloud/
/dod/  /dod/il2|il4|il5|il6/                         DoD Impact Level
/onegov/                   GSA OneGov agreements
/new/                      FedRAMP status changes
/about/  /about/mark-flournoy/  /methodology/  /privacy/  /terms/  /contact/
/search/?q=                search (noindex; JavaScript renders results)
```

Every indexable page has a unique title and description, an absolute canonical,
Open Graph tags, BreadcrumbList JSON-LD, one H1, and its content in the HTML.
Filtered views (`?status=…`) are the same page filtered in the browser; they
add `noindex` dynamically and canonicalize to the parent. Comparison pages are
not mass-generated; "X vs Y" searches point to both vendor pages.

## Editorial rules baked into the build

No ratings, no rankings, no scores, no pay-to-rank, no vendor logos. Exact
source status strings are preserved (FedRAMP Authorized / Ready / In Process;
DoD PA / PA-C / IATT / Suspended). "Runs on" (FedRAMP relationship) is distinct
from "sold on a marketplace" (search link). USAspending figures are shown as a
floor and split into vendor-direct vs reseller/prime. Every figure names its
source and date.
