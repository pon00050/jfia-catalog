"""
JFIA Metadata Scraper
=====================
Scrapes article metadata (title, authors, abstract, keywords, PDF URL) from
all 46 issues of the Journal of Forensic and Investigative Accounting (2009-2025).

No PDFs are downloaded -- only the freely-accessible metadata on each issue page.

Output: jfia_data/jfia_catalog.json

Usage:
    python jfia_data/JFIA_metadata_scraper.py
"""

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

# ---------- Issue metadata (hardcoded from NACVA website exploration) ----------

ISSUES = [
    # (contentid, volume, issue_num, period)
    # Volume 1 (2009)
    (490, 1, 1, "January-June 2009"),
    (489, 1, 2, "July-December 2009"),
    # Volume 2 (2010)
    (479, 2, 1, "January-June 2010"),
    (478, 2, 2, "July-December 2010"),
    # Volume 3 (2011)
    (477, 3, 1, "January-June 2011"),
    (1174, 3, 2, "July-December 2011"),
    # Volume 4 (2012)
    (471, 4, 1, "January-June 2012"),
    (470, 4, 2, "July-December 2012"),
    # Volume 5 (2013)
    (469, 5, 1, "January-June 2013"),
    (468, 5, 2, "July-December 2013"),
    # Volume 6 (2014)
    (391, 6, 1, "January-June 2014"),
    (320, 6, 2, "July-December 2014"),
    # Volume 7 (2015)
    (319, 7, 1, "January-June 2015"),
    (318, 7, 2, "July-December 2015"),
    # Volume 8 (2016)
    (316, 8, 1, "January-June 2016"),
    (315, 8, 2, "July-December 2016"),
    (334, 8, 3, "Special Issue 2016"),
    # Volume 9 (2017)
    (335, 9, 1, "January-June 2017"),
    (373, 9, 2, "July-December 2017"),
    # Volume 10 (2018)
    (406, 10, 1, "January-June 2018"),
    (493, 10, 2, "July-December 2018"),
    (553, 10, 3, "Special Issue 2018"),
    # Volume 11 (2019)
    (568, 11, 1, "January-June 2019"),
    (588, 11, 2, "July-December 2019"),
    (631, 11, 3, "Special Issue 2019"),
    # Volume 12 (2020)
    (683, 12, 1, "January-June 2020"),
    (697, 12, 2, "July-December 2020"),
    (711, 12, 3, "Special Issue 2020"),
    # Volume 13 (2021)
    (744, 13, 1, "January-June 2021"),
    (812, 13, 2, "July-December 2021"),
    # Volume 14 (2022)
    (950, 14, 1, "January-June 2022"),
    (960, 14, 2, "July-December 2022"),
    # Volume 15 (2023)
    (993, 15, 1, "January-June 2023"),
    (1038, 15, 2, "July-December 2023"),
    # Volume 16 (2024)
    (1059, 16, 1, "January-June 2024"),
    (1086, 16, 2, "July-December 2024"),
    (1127, 16, 3, "Special Issue 2024"),
    (1137, 16, 4, "Special Issue 2 2024"),
    # Volume 17 (2025)
    (1153, 17, 1, "January-June 2025"),
    (1208, 17, 2, "Special Issue 2025"),
    (1226, 17, 3, "Special Issue 2 2025"),
    (1276, 17, 4, "Special Issue 3 2025"),
    (1310, 17, 5, "Special Issue 4 2025"),
    (1328, 17, 6, "Special Issue 5 2025"),
    (1431, 17, 7, "Special Issue 6 2025"),
    (1515, 17, 8, "July-December 2025"),
]

BASE_URL = "https://www.nacva.com/content.asp?contentid={}"
OUTPUT_DIR = Path(__file__).parent
OUTPUT_FILE = OUTPUT_DIR / "jfia_catalog.json"
DELAY = 3.0  # seconds between requests (polite to avoid rate-limiting)


def is_jfia_pdf_link(href):
    """Check if a URL points to a JFIA PDF."""
    h = href.lower()
    return ('s3' in h and 'jfia' in h) or ('nacva.com' in h and 'jfia' in h)


def extract_title_from_strong(strong_tag):
    """Extract article title from a <strong> tag that contains a PDF link."""
    full_text = strong_tag.get_text(strip=True)
    # Remove "| Full Article (PDF)" or "| Full Article PDF" suffix
    title = re.split(r'\s*\|\s*Full\s+Article', full_text)[0].strip()
    title = title.rstrip('|').strip()
    return title


def extract_pdf_url(strong_tag):
    """Extract the S3 PDF URL from a <strong> tag."""
    link = strong_tag.find('a', href=True)
    if link and is_jfia_pdf_link(link['href']):
        return link['href']
    return None


def get_walk_start(element):
    """Determine the correct starting element for sibling-walking.

    Two HTML layouts exist across JFIA's 17-year archive:
    - Newer (flat): <strong>Title <a>PDF</a></strong> <br> <em>Author</em> ...
      -> walk siblings of the <strong> itself
    - Older (div-wrapped): <div><strong>Title <a>PDF</a></strong></div> <div>Author</div> ...
      -> walk siblings of the parent <div>
    """
    if element is None:
        return None
    ns = element.next_sibling
    while ns and isinstance(ns, NavigableString) and not ns.strip():
        ns = ns.next_sibling
    if ns is not None:
        return element  # flat format
    parent = element.parent
    if parent and parent.name in ('div', 'p', 'span'):
        return parent  # div-wrapped format
    return element


def find_title_near_link(link_element):
    """Find the article title near a PDF link element.

    Handles multiple HTML formats:
    1. <strong>Title | <a>PDF</a></strong>  — title is in the same strong
    2. <strong>Title</strong> <a>PDF</a>     — title in preceding strong sibling
    3. <strong>Title</strong><strong>| <a>PDF</a></strong> — title in preceding strong
    4. <div><strong>Title</strong></div><div><a>PDF</a></div> — title in preceding div
    """
    # Check parent strong for title text
    parent = link_element.parent
    if isinstance(parent, Tag) and parent.name == 'strong':
        full_text = parent.get_text(strip=True)
        title = re.split(r'\s*\|\s*Full\s+Article', full_text)[0].strip().rstrip('|').strip()
        if title and len(title) > 5:
            return title, parent

    # Walk backwards from link to find title
    search_from = parent if isinstance(parent, Tag) and parent.name in ('strong', 'div') else link_element
    current = search_from
    for _ in range(10):
        current = current.previous_sibling
        if current is None:
            # Try parent's previous sibling
            if search_from.parent:
                current = search_from.parent.previous_sibling
                search_from = search_from.parent
                if current is None:
                    break
                continue
            break
        if isinstance(current, NavigableString):
            text = current.strip()
            if text and text != '|' and len(text) > 5:
                return text, current
            continue
        if isinstance(current, Tag):
            if current.name == 'strong':
                text = current.get_text(strip=True)
                text = re.split(r'\s*\|\s*Full\s+Article', text)[0].strip().rstrip('|').strip()
                if text and len(text) > 5 and not re.match(r'^(Abstract|Keywords?|Key\s*Words?|Data|Table of|Volume|Back)', text, re.I):
                    return text, current
            elif current.name == 'div':
                strong_child = current.find('strong')
                if strong_child:
                    text = strong_child.get_text(strip=True)
                    if text and len(text) > 5 and not re.match(r'^(Abstract|Keywords?|Key\s*Words?|Data)', text, re.I):
                        return text, current

    return "", link_element


def parse_issue_page(soup, contentid):
    """Parse a single JFIA issue page and extract all articles.

    Uses a link-first approach: find all PDF links, then discover
    title/authors/abstract/keywords relative to each link.
    """
    articles = []

    # Find ALL <a> tags with JFIA PDF URLs
    pdf_links = []
    for a in soup.find_all('a', href=True):
        if is_jfia_pdf_link(a['href']):
            pdf_links.append(a)

    if not pdf_links:
        return articles

    for idx, pdf_link in enumerate(pdf_links):
        pdf_url = pdf_link['href']
        title, title_element = find_title_near_link(pdf_link)

        if not title:
            continue

        # Determine walk start: the title element (or its parent div)
        walk_start = get_walk_start(title_element if isinstance(title_element, Tag) else pdf_link)

        authors = []
        abstract = ""
        keywords = []
        found_abstract = False
        found_keywords = False
        abstract_parts = []

        # Find next article's title element for boundary detection
        next_title_el = None
        if idx + 1 < len(pdf_links):
            _, next_title_el = find_title_near_link(pdf_links[idx + 1])
        next_title_walk = get_walk_start(next_title_el) if isinstance(next_title_el, Tag) else None

        current = walk_start
        while True:
            current = current.next_sibling
            if current is None:
                break

            # Stop at boundaries
            if next_title_el and (current is next_title_el or current is next_title_walk):
                break
            if isinstance(current, Tag) and current.name == 'hr':
                break

            # Get text content
            if isinstance(current, NavigableString):
                text = str(current).strip()
            elif isinstance(current, Tag):
                text = current.get_text(strip=True)
            else:
                continue

            if not text:
                continue

            # Skip nav links
            if 'back to top' in text.lower():
                continue

            # Check if element contains a JFIA PDF link (= next article boundary)
            if isinstance(current, Tag):
                inner_link = current.find('a', href=True)
                if inner_link and is_jfia_pdf_link(inner_link.get('href', '')):
                    if current is not walk_start:
                        break

            # Detect Abstract/Keywords markers
            # Markers may be in a <strong> child or in the div text directly
            marker_text = text
            if isinstance(current, Tag):
                strong_child = current.find('strong')
                if strong_child:
                    marker_text = strong_child.get_text(strip=True)

            if re.match(r'^Abstract\s*:', marker_text):
                found_abstract = True
                found_keywords = False
                after = re.sub(r'^Abstract\s*:\s*', '', text).strip()
                if after:
                    abstract_parts.append(after)
                continue

            if re.match(r'^Key\s*[Ww]ords?\s*:', marker_text):
                found_keywords = True
                found_abstract = False
                abstract = ' '.join(abstract_parts).strip()
                abstract_parts = []
                kw_text = re.sub(r'^Key\s*[Ww]ords?\s*:\s*', '', text).strip()
                if kw_text:
                    if ';' in kw_text:
                        keywords = [k.strip() for k in kw_text.split(';') if k.strip()]
                    else:
                        keywords = [k.strip() for k in kw_text.split(',') if k.strip()]
                    found_keywords = False
                continue

            if marker_text.startswith('Data:'):
                continue

            # Author detection: short text before abstract, not a marker
            if not found_abstract and not found_keywords:
                if len(text) < 60 and not re.match(r'^(Abstract|Key|Data|Volume|Table of)', text):
                    authors.append(text)
                continue

            # Collect abstract text
            if found_abstract:
                abstract_parts.append(text)

            # Collect keywords (if not captured inline)
            if found_keywords:
                if ';' in text:
                    keywords = [k.strip() for k in text.split(';') if k.strip()]
                else:
                    keywords = [k.strip() for k in text.split(',') if k.strip()]
                found_keywords = False

        # Finalize abstract if not terminated by Keywords
        if abstract_parts and not abstract:
            abstract = ' '.join(abstract_parts).strip()

        abstract = re.sub(r'\s*Back to Top\s*', '', abstract).strip()

        if title:
            articles.append({
                "index": idx + 1,
                "title": title,
                "authors": authors,
                "abstract": abstract,
                "keywords": keywords,
                "pdf_url": pdf_url or "",
            })

    return articles


def fetch_with_retry(session, url, max_retries=3, base_delay=5.0):
    """Fetch a URL with exponential backoff retry."""
    for attempt in range(max_retries):
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            return resp
        except Exception as e:
            if attempt < max_retries - 1:
                wait = base_delay * (2 ** attempt)
                print(f"    Retry {attempt+1}/{max_retries} in {wait:.0f}s...")
                time.sleep(wait)
            else:
                raise


def merge_articles(existing_articles, new_articles):
    """Merge new articles into existing, deduplicating by pdf_url.

    If a new article has the same pdf_url as an existing one, the new version
    wins only if it has more metadata (longer abstract, more authors, etc.).
    Articles without pdf_url are deduped by title similarity.

    Returns (merged_list, added_count, updated_count).
    """
    # Index existing articles by pdf_url and by normalized title
    by_url = {}
    by_title = {}
    for art in existing_articles:
        if art.get("pdf_url"):
            by_url[art["pdf_url"]] = art
        title_key = re.sub(r'\s+', ' ', art.get("title", "")).strip().lower()
        if title_key:
            by_title[title_key] = art

    added = 0
    updated = 0

    for new_art in new_articles:
        pdf_url = new_art.get("pdf_url", "")
        title_key = re.sub(r'\s+', ' ', new_art.get("title", "")).strip().lower()

        existing = by_url.get(pdf_url) if pdf_url else by_title.get(title_key)

        if existing is None:
            # Genuinely new article
            existing_articles.append(new_art)
            if pdf_url:
                by_url[pdf_url] = new_art
            if title_key:
                by_title[title_key] = new_art
            added += 1
        else:
            # Article exists -- update if new version has richer metadata
            new_score = _metadata_score(new_art)
            old_score = _metadata_score(existing)
            if new_score > old_score:
                existing.update(new_art)
                updated += 1

    return existing_articles, added, updated


def _metadata_score(article):
    """Score how complete an article's metadata is (higher = more complete)."""
    score = 0
    score += len(article.get("abstract", ""))
    score += len(article.get("authors", [])) * 20
    score += len(article.get("keywords", [])) * 10
    score += 50 if article.get("pdf_url") else 0
    return score


def scrape_all():
    """Scrape all JFIA issues and build the catalog.

    Supports resuming with article-level deduplication:
    - Issues already in the catalog are skipped entirely.
    - To re-scrape a specific issue, delete it from the JSON first,
      or use --force to re-scrape all and merge at the article level.
    """
    # Load existing catalog if present (resume mode)
    existing_issues = {}
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            old_catalog = json.load(f)
        for iss in old_catalog.get("issues", []):
            existing_issues[iss["contentid"]] = iss
        print(f"Resume mode: {len(existing_issues)} issues already scraped")

    catalog = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "total_articles": 0,
        "issues": [],
    }

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })

    total_articles = 0
    errors = []
    skipped = 0
    total_added = 0
    total_updated = 0

    for i, (contentid, volume, issue_num, period) in enumerate(ISSUES):
        # Skip if already scraped
        if contentid in existing_issues:
            catalog["issues"].append(existing_issues[contentid])
            total_articles += len(existing_issues[contentid]["articles"])
            skipped += 1
            continue

        url = BASE_URL.format(contentid)
        print(f"[{i+1}/{len(ISSUES)}] Vol.{volume} Issue {issue_num} ({period})")

        try:
            resp = fetch_with_retry(session, url)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, 'html.parser')
            new_articles = parse_issue_page(soup, contentid)

            is_special = 'special' in period.lower()

            # Check if we have a partial version of this issue to merge with
            if contentid in existing_issues:
                old_arts = existing_issues[contentid]["articles"]
                merged, added, updated = merge_articles(old_arts, new_articles)
                articles = merged
                total_added += added
                total_updated += updated
                print(f"    -> merged: {added} new, {updated} updated, {len(articles)} total")
            else:
                articles = new_articles
                total_added += len(articles)
                print(f"    -> {len(articles)} articles found")

            issue_data = {
                "volume": volume,
                "issue": issue_num,
                "period": period,
                "contentid": contentid,
                "url": url,
                "is_special_issue": is_special,
                "articles": articles,
            }
            catalog["issues"].append(issue_data)
            total_articles += len(articles)

        except Exception as e:
            error_msg = f"Vol.{volume} Issue {issue_num} (contentid={contentid}): {e}"
            errors.append(error_msg)
            print(f"    ERROR: {e}")
            # If we have an existing (partial) version, keep it
            if contentid in existing_issues:
                catalog["issues"].append(existing_issues[contentid])
                total_articles += len(existing_issues[contentid]["articles"])

        # Polite delay
        if i < len(ISSUES) - 1:
            time.sleep(DELAY)

    catalog["total_articles"] = total_articles

    # Write output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)

    # Summary
    print("\n" + "=" * 60)
    print(f"JFIA Catalog Complete")
    print(f"  Issues in catalog: {len(catalog['issues'])}/{len(ISSUES)} (skipped {skipped} already scraped)")
    if total_added or total_updated:
        print(f"  Articles added: {total_added}, updated: {total_updated}")
    print(f"  Total articles: {total_articles}")
    print(f"  Output: {OUTPUT_FILE}")

    if errors:
        print(f"\n  ERRORS ({len(errors)}):")
        for err in errors:
            print(f"    - {err}")

    # Articles per volume
    print("\n  Articles per volume:")
    vol_counts = {}
    for issue in catalog["issues"]:
        v = issue["volume"]
        vol_counts[v] = vol_counts.get(v, 0) + len(issue["articles"])
    for v in sorted(vol_counts):
        print(f"    Vol.{v}: {vol_counts[v]} articles")

    # Keyword frequency (top 20)
    kw_freq = {}
    for issue in catalog["issues"]:
        for article in issue["articles"]:
            for kw in article["keywords"]:
                kw_lower = kw.lower().strip()
                if kw_lower:
                    kw_freq[kw_lower] = kw_freq.get(kw_lower, 0) + 1

    if kw_freq:
        print(f"\n  Top 20 keywords:")
        for kw, count in sorted(kw_freq.items(), key=lambda x: -x[1])[:20]:
            print(f"    {count:3d}x {kw}")

    # Data quality summary
    no_abstract = sum(1 for iss in catalog['issues'] for a in iss['articles'] if not a['abstract'])
    no_keywords = sum(1 for iss in catalog['issues'] for a in iss['articles'] if not a['keywords'])
    no_authors = sum(1 for iss in catalog['issues'] for a in iss['articles'] if not a['authors'])
    print(f"\n  Data quality:")
    print(f"    Articles missing abstract: {no_abstract}/{total_articles}")
    print(f"    Articles missing keywords: {no_keywords}/{total_articles}")
    print(f"    Articles missing authors:  {no_authors}/{total_articles}")

    return catalog


if __name__ == "__main__":
    scrape_all()
