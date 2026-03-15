# CLAUDE.md — jfia-catalog

469 JFIA forensic accounting articles — structured metadata catalog.

## Ecosystem

Part of the Korean forensic accounting toolkit.
- Hub: `../forensic-accounting-toolkit/` | [GitHub](https://github.com/pon00050/forensic-accounting-toolkit)
- Task board: https://github.com/users/pon00050/projects/1
- Role: Foundation library (data artifact)
- Depends on: none
- Consumed by: jfia-forensic (enrichment pipeline reads jfia_catalog.json)

## Architecture

Standalone scraper → JSON catalog. No installable package, no pyproject.toml.

```
JFIA_metadata_scraper.py   — Scrapes kci.go.kr for JFIA article metadata
jfia_catalog.json          — 469 articles with title, authors, year, abstract, keywords
README.md                  — Dataset documentation
```

## How to Run

```bash
# Re-scrape (requires internet, takes ~10 min)
python JFIA_metadata_scraper.py
```

Output overwrites `jfia_catalog.json`.

## Conventions

- This is a data artifact, not an installable Python package
- `jfia_catalog.json` is committed (it's the deliverable)
- No tests — the scraper is run manually and output is inspected
