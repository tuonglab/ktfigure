import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "community_posts.py"
spec = importlib.util.spec_from_file_location("community_posts", SCRIPT)
posts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(posts)


@pytest.mark.parametrize("url, platform, post_id", [
    ("https://twitter.com/scientist/status/123456?ref=abc", "x", "123456"),
    ("https://x.com/scientist/status/123456/", "x", "123456"),
    ("https://www.linkedin.com/feed/update/urn:li:activity:123456/", "linkedin", "activity:123456"),
    ("https://www.linkedin.com/posts/name_research-activity-123456-AbCd", "linkedin", "activity:123456"),
    ("https://www.linkedin.com/embed/feed/update/urn:li:share:123456", "linkedin", "share:123456"),
    ("https://www.linkedin.com/feed/update/urn%3Ali%3AugcPost%3A123456", "linkedin", "ugcPost:123456"),
])
def test_supported_post_urls(url, platform, post_id):
    post = posts.parse_post(url)
    assert post["platform"] == platform
    assert post["id"] == post_id
    assert "?" not in post["url"]


@pytest.mark.parametrize("url", [
    "https://x.com.evil.example/user/status/123",
    "http://x.com/user/status/123",
    "https://user:password@x.com/user/status/123",
    "https://x.com:444/user/status/123",
    "https://x.com/user",
    "https://linkedin.com/in/person",
    "https://www.linkedin.com/posts/name_activity-123abc",
    "https://example.org/post",
    "https://t.co/short",
    "javascript:alert(1)",
])
def test_reject_unsupported_or_unsafe_urls(url):
    with pytest.raises(ValueError):
        posts.parse_post(url)


def test_add_remove_and_reject_duplicate():
    url = "https://twitter.com/user/status/123?ref=old"
    entries = posts.update([], "add", url, "  A figure  ")
    assert entries == [{"platform": "x", "id": "123", "url": "https://x.com/user/status/123", "description": "A figure"}]
    with pytest.raises(ValueError, match="already"):
        posts.update(entries, "add", "https://x.com/another/status/123")
    assert posts.update(entries, "remove", url) == []
    with pytest.raises(ValueError, match="not in"):
        posts.update([], "remove", url)


def test_gallery_retains_latest_200_posts():
    entries = []
    for number in range(201):
        entries = posts.update(entries, "add", f"https://x.com/user/status/{number}")
    assert len(entries) == 200
    assert entries[0]["id"] == "200"
    assert entries[-1]["id"] == "1"


def test_rejects_long_description_and_unknown_operation():
    with pytest.raises(ValueError, match="description"):
        posts.update([], "add", "https://x.com/user/status/1", "x" * 501)
    with pytest.raises(ValueError, match="Operation"):
        posts.update([], "publish", "https://x.com/user/status/1")


def test_workflow_updates_index_and_rejects_invalid_input(tmp_path, monkeypatch):
    index = tmp_path / "entries.json"
    index.write_text("[]\n")
    monkeypatch.setattr(posts, "ENTRIES", index)
    monkeypatch.setenv("OPERATION", "add")
    monkeypatch.setenv("POST_URL", "https://x.com/user/status/123")
    monkeypatch.setenv("DESCRIPTION", "A public figure")
    posts.main()
    assert json.loads(index.read_text())[0]["description"] == "A public figure"
    existing = index.read_text()
    monkeypatch.setenv("POST_URL", "https://example.org/not-a-post")
    with pytest.raises(SystemExit):
        posts.main()
    assert index.read_text() == existing
