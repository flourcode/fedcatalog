# FedCatalog — handoff notes

For whoever maintains this next: Mark, a developer, or an AI assistant given
this folder. Everything here is plain files; there is no server, database,
account or API key anywhere in the project.

## What the site is
A static website (plain HTML/CSS/JS) generated from public data about federal
software: FedRAMP Marketplace, the DoD Cyber Exchange list, GSA OneGov, and
live USAspending lookups in the browser. About 1,550 pages. Hosted by pointing
AWS Amplify at the GitHub repo; Amplify serves whatever is at the repo root.

## How it's built
`src/build.py` reads `src/data/snapshot.js` (a compact copy of FedRAMP's data,
produced by `src/build_snapshot.py`) plus the curated JSON files in `src/data`,
and writes the whole site to `dist/`. `src/verify.py` crawls the output and
fails on broken links, duplicate titles, missing canonicals or H1s.
`.github/workflows/nightly.yml` runs those three every night, copies `dist/`
to the repo root, commits if anything changed, and writes the newsletter draft
to `drafts/latest.html`. Amplify redeploys on the commit.

Rule: `src/` is the only thing anyone edits. The root is generated.

## Where each kind of change lives
See the table in README.md ("The one rule"). Short version: text in
`src/templates/*.js` and the copy blocks in `src/build.py`; facts in
`src/data/*.json`; the photo in `src/assets/`.

## Editorial rules the code enforces
No rankings, ratings, scores, sponsored placement or vendor edits to data.
Exact source status strings are preserved (FedRAMP Authorized/Ready/In
Process; DoD PA/PA-C/IATT/Suspended). "Runs on" (a FedRAMP relationship) is
kept distinct from "sold on a marketplace" (a search link unless an exact
listing is on file). USAspending figures are labeled a floor and split into
vendor-direct vs reseller. Every figure names its source and date. Keep these.

## If FedRAMP changes its data format
`data.json` is FedRAMP's "legacy" file. If it stops updating or changes shape,
`build_snapshot.py` is the only file that reads it (the `compact()` function).
The nightly job will fail and email; the site keeps serving the last good
version indefinitely. Point `SRC` at the replacement file and adjust field
names in `compact()`.

## Local rebuild (optional; the job does this nightly)
    python3 src/build_snapshot.py --refresh
    python3 src/build.py
    python3 src/verify.py
Requires Python 3 and `pip install pillow` (for the share image).

## Contacts and accounts to keep alive
Domain: fedcatalog.com (Route 53). Hosting: AWS Amplify. Email:
mark@fedcatalog.com (forwarding at the registrar). Newsletter: Kit.
Analytics: Google Analytics, ID in `src/templates/analytics.js`.
