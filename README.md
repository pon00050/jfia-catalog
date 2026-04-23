# jfia-catalog

**[Read the full write-up →](https://ronanwrites.vercel.app/manuals/jfia-catalog-469-articles)**

The only structured index of all 469 articles published in the
[Journal of Forensic & Investigative Accounting (JFIA)](https://jfiaonline.com),
2009–2025.

## What is JFIA?

JFIA is a peer-reviewed academic journal dedicated to forensic accounting research.
Published by the National Association of Certified Valuators and Analysts (NACVA),
it covers fraud detection, earnings manipulation, disclosure timing, insider networks,
and related topics. 469 articles across 46 issues, 2009–2025.

## Dataset

`jfia_catalog.json` — 681 KB, UTF-8 encoded.

### Structure

```json
{
  "scraped_at": "...",
  "total_articles": 469,
  "issues": [
    {
      "volume": 1,
      "issue": 1,
      "period": "2009 Q1",
      "url": "...",
      "is_special_issue": false,
      "articles": [
        {
          "index": 1,
          "title": "Bernard Madoff and the Solo Auditor Red Flag",
          "authors": ["Ross D. Fuerman"],
          "abstract": "...",
          "keywords": ["Madoff", "solo auditor", "fraud"],
          "pdf_url": "https://s3.amazonaws.com/web.nacva.com/JFIA/Issues/JFIA-2009-1_1.pdf"
        }
      ]
    }
  ]
}
```

### Coverage

| Metric | Value |
|--------|-------|
| Total articles | 469 |
| Issues | 46 |
| Date range | 2009–2025 |
| Articles with abstracts | 363 |
| Articles with keywords | 242 |

## Usage

```python
import json

with open("jfia_catalog.json", encoding="utf-8") as f:
    catalog = json.load(f)

# Flatten to list of articles
articles = [
    {**article, "volume": issue["volume"], "issue": issue["issue"], "period": issue["period"]}
    for issue in catalog["issues"]
    for article in issue["articles"]
]

print(f"{len(articles)} articles loaded")

# Search by keyword
query = "earnings management"
matches = [a for a in articles if query.lower() in " ".join(a.get("keywords", [])).lower()]
print(f"{len(matches)} articles matching '{query}'")
```

For richer search and detectlet schema integration, see the
[jfia-forensic](https://github.com/pon00050/jfia-forensic) package:

```bash
uv add git+https://github.com/pon00050/jfia-forensic
```

```python
from jfia_forensic import JFIACatalog
catalog = JFIACatalog.load("jfia_catalog.json")
results = catalog.search("Beneish M-Score", limit=5)
for r in results:
    print(r.title)
```

## Citation Format

When citing a JFIA article:

```
Authors. (Year). Title. Journal of Forensic & Investigative Accounting, Vol(Issue).
Retrieved from: pdf_url
```

Example:
```
Fuerman, R.D. (2009). Bernard Madoff and the Solo Auditor Red Flag.
Journal of Forensic & Investigative Accounting, 1(1).
Retrieved from: https://s3.amazonaws.com/web.nacva.com/JFIA/Issues/JFIA-2009-1_1.pdf
```

## Scraper

`JFIA_metadata_scraper.py` — the script used to build this catalog from NACVA's
website. Run it again to update the catalog when new issues are published.

```bash
pip install requests beautifulsoup4
python JFIA_metadata_scraper.py
```

## License

The catalog metadata (titles, authors, abstracts, keywords) is structured data
derived from publicly accessible JFIA web pages. The PDF content itself is
copyright NACVA. This catalog is provided for research purposes only.
