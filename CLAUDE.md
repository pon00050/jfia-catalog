# CLAUDE.md — jfia-catalog

469 JFIA forensic accounting articles — structured metadata catalog.

## Ecosystem

Part of the Korean forensic accounting toolkit.
- Hub: `../forensic-accounting-toolkit/` | [GitHub](https://github.com/pon00050/forensic-accounting-toolkit)
- Task board: https://github.com/users/pon00050/projects/1
- Role: Foundation library (data artifact)
- Depends on: `requests`, `beautifulsoup4` (scraper only; not needed to read the catalog)
- Consumed by: jfia-forensic (enrichment pipeline reads jfia_catalog.json)

## Architecture

Standalone scraper → JSON catalog. No installable package, no pyproject.toml.

```
JFIA_metadata_scraper.py   — Scrapes NACVA website for JFIA article metadata
jfia_catalog.json          — 469 articles across 46 issues (2009–2025)
README.md                  — Dataset documentation
tests/test_catalog.py      — Schema validation (JSON exists, parses, required fields present)
```

### JSON structure

`jfia_catalog.json` is a single dict, not a flat list:
```json
{
  "scraped_at": "ISO-8601 timestamp",
  "total_articles": 469,
  "issues": [
    {
      "volume": 1, "issue": 1, "period": "January-June 2009",
      "contentid": 490, "url": "...", "is_special_issue": false,
      "articles": [
        {
          "index": 1,
          "title": "...",
          "authors": ["Author Name"],
          "abstract": "...",
          "keywords": ["keyword"],
          "pdf_url": "..."
        }
      ]
    }
  ]
}
```

To iterate articles across all issues: `[a for issue in d["issues"] for a in issue["articles"]]`

## How to Run

```bash
# Re-scrape (requires internet, takes ~10 min)
python JFIA_metadata_scraper.py
```

Output overwrites `jfia_catalog.json`.

## Known Gaps

| Gap | Why | Status |
|-----|-----|--------|
| 106/469 articles (22.6%) missing abstracts | HTML layout variation across 17-year archive (4+ layouts) | Unblocked — scraper improvement |
| 227/469 articles (48.4%) missing keywords | Same cause | Unblocked — scraper improvement |
| 51/469 articles (10.9%) missing authors | Same cause | Unblocked — scraper improvement |
| `ISSUES` list is hardcoded — no automated discovery of new volumes | Manual update required when Vol.18+ appears | By design |

## How to Run Tests

```bash
# Schema validation (no network, no deps beyond stdlib)
pytest tests/ -v
```

## Conventions

- This is a data artifact, not an installable Python package
- `jfia_catalog.json` is committed (it's the deliverable)
- Scraper dependencies: `pip install requests beautifulsoup4` (or install from requirements.txt)
- Tests validate the committed JSON only — they do not run the scraper


---

**Working notes** (regulatory analysis, legal compliance research, or anything else not appropriate for this public repo) belong in the gitignored working directory of the coordination hub. Engineering docs (API patterns, test strategies, run logs) stay here.
