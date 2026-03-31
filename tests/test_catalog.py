"""Schema validation for jfia_catalog.json.

Tests verify the committed catalog is well-formed. They do NOT run the scraper.
Run with: pytest tests/ -v
"""

import json
from pathlib import Path

CATALOG_PATH = Path(__file__).parent.parent / "jfia_catalog.json"
REQUIRED_TOP_LEVEL = {"scraped_at", "total_articles", "issues"}
REQUIRED_ISSUE_FIELDS = {"volume", "issue", "articles"}
REQUIRED_ARTICLE_FIELDS = {"title"}


def _load_catalog():
    with open(CATALOG_PATH, encoding="utf-8") as f:
        return json.load(f)


def test_catalog_exists():
    assert CATALOG_PATH.exists(), (
        "jfia_catalog.json missing — run: python JFIA_metadata_scraper.py"
    )


def test_catalog_parses_as_json():
    data = _load_catalog()
    assert isinstance(data, dict), f"Expected dict at top level, got {type(data)}"


def test_top_level_structure():
    data = _load_catalog()
    missing = REQUIRED_TOP_LEVEL - set(data.keys())
    assert not missing, f"Missing top-level keys: {missing}"


def test_total_articles_positive():
    data = _load_catalog()
    assert data["total_articles"] > 0, "total_articles is 0"


def test_issues_is_nonempty_list():
    data = _load_catalog()
    assert isinstance(data["issues"], list), "issues must be a list"
    assert len(data["issues"]) > 0, "issues list is empty"


def test_issue_structure():
    data = _load_catalog()
    for i, issue in enumerate(data["issues"]):
        missing = REQUIRED_ISSUE_FIELDS - set(issue.keys())
        assert not missing, f"Issue {i} missing fields: {missing}"
        assert isinstance(issue["articles"], list), f"Issue {i} articles must be a list"


def test_every_article_has_title():
    data = _load_catalog()
    for issue in data["issues"]:
        for article in issue["articles"]:
            missing = REQUIRED_ARTICLE_FIELDS - set(article.keys())
            assert not missing, (
                f"Article in vol {issue.get('volume')} missing fields: {missing}"
            )
            assert article["title"], (
                f"Article in vol {issue.get('volume')} has empty title"
            )


def test_article_count_matches_total():
    data = _load_catalog()
    actual = sum(len(issue["articles"]) for issue in data["issues"])
    claimed = data["total_articles"]
    assert actual == claimed, f"Article count mismatch: {actual} actual vs {claimed} claimed"
