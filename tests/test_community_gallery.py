import importlib.util
import io
import json
import random
import os
import subprocess
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request

import pytest
from PIL import Image


SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "community_gallery.py"
spec = importlib.util.spec_from_file_location("community_gallery", SCRIPT)
gallery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gallery)


def image_bytes(mode="RGB", size=(2400, 1000), format="PNG"):
    output = io.BytesIO()
    Image.new(mode, size, "red").save(output, format=format)
    return output.getvalue()


def issue_body():
    return """### Image

![figure](https://github.com/user-attachments/assets/12345678-1234-1234-1234-123456789abc)

### Display name

_No response_

### Description

An example panel.

### Feedback about ktfigure

The layout tools helped me arrange the panels.

### Paper citation

Example et al., Journal, 2026

### DOI

https://doi.org/10.1000/example%2F123

### Paper or project URL

https://example.org/paper

### Permission

- [X] I have permission to share this image publicly and understand it will be stored in the repository's history.
"""


def test_submission_compresses_and_builds_index(tmp_path, monkeypatch):
    items = tmp_path / "items"
    monkeypatch.setattr(gallery, "ITEMS", items)
    monkeypatch.setattr(gallery, "INDEX", tmp_path / "entries.json")
    event = {"issue": {"number": 42, "created_at": "2026-01-01T00:00:00Z", "body": issue_body()}}
    with patch.object(gallery, "download_image", return_value=image_bytes()):
        gallery.submit(event)
    gallery.build()
    entries = json.loads(gallery.INDEX.read_text())
    assert entries[0]["name"] == "Anonymous"
    assert entries[0]["description"] == "An example panel."
    assert entries[0]["feedback"] == "The layout tools helped me arrange the panels."
    assert entries[0]["citation"] == "Example et al., Journal, 2026"
    assert entries[0]["doi"] == "10.1000/example/123"
    assert entries[0]["link"] == "https://example.org/paper"
    assert entries[0]["image"] == "42.jpg"
    stored = items / entries[0]["image"]
    assert stored.stat().st_size < 1_000_000
    with Image.open(stored) as image:
        assert image.size == (1600, 667)
        assert image.format == "JPEG"


@pytest.mark.parametrize("value, expected", [
    ("", ""),
    ("10.1000/example", "10.1000/example"),
    ("doi: 10.1000/example", "10.1000/example"),
    ("https://dx.doi.org/10.1000/example%23figure", "10.1000/example#figure"),
])
def test_normalize_doi(value, expected):
    assert gallery.normalize_doi(value) == expected


@pytest.mark.parametrize("value", [
    "https://example.org/10.1000/example",
    "https://doi.org.evil.example/10.1000/example",
    "https://doi.org:invalid/10.1000/example",
    "10.1000/contains spaces",
    "javascript:alert(1)",
])
def test_reject_invalid_doi(value):
    with pytest.raises(gallery.GalleryError, match="DOI"):
        gallery.normalize_doi(value)


def test_png_transparency_and_unsupported_image():
    extension, data = gallery.compress_image(image_bytes(mode="RGBA", size=(20, 20)))
    assert extension == "png"
    with Image.open(io.BytesIO(data)) as image:
        assert image.mode == "RGBA"
    with pytest.raises(gallery.GalleryError, match="JPEG and PNG"):
        gallery.compress_image(image_bytes(size=(20, 20), format="GIF"))
    with pytest.raises(gallery.GalleryError, match="invalid"):
        gallery.compress_image(b"not an image")


def test_large_image_is_compressed_and_metadata_is_removed():
    image = Image.frombytes("RGBA", (900, 900), random.Random(42).randbytes(900 * 900 * 4))
    exif = Image.Exif()
    exif[270] = "private metadata"
    original = io.BytesIO()
    image.save(original, format="PNG", exif=exif)
    assert len(original.getvalue()) > 1_000_000
    _, data = gallery.compress_image(original.getvalue())
    assert len(data) < 1_000_000
    with Image.open(io.BytesIO(data)) as compressed:
        assert not compressed.getexif()


def test_rejects_missing_permission_invalid_links_and_external_redirects(tmp_path, monkeypatch):
    monkeypatch.setattr(gallery, "ITEMS", tmp_path / "items")
    event = {"issue": {"number": 42, "created_at": "2026-01-01T00:00:00Z", "body": issue_body().replace("[X]", "[ ]")}}
    with pytest.raises(gallery.GalleryError, match="permission"):
        gallery.submit(event)
    event["issue"]["body"] = issue_body().replace("https://example.org/paper", "javascript:alert(1)")
    with pytest.raises(gallery.GalleryError, match="HTTP or HTTPS"):
        gallery.submit(event)
    with pytest.raises(gallery.GalleryError, match="unsupported host"):
        gallery.SafeRedirect().redirect_request(
            Request("https://github.com/"), None, 302, "", {}, "http://127.0.0.1/"
        )


def test_github_attachment_bucket_redirect_is_allowed():
    url = "https://github-production-user-asset-6210df.s3.amazonaws.com/image?signature=secret"
    redirected = gallery.SafeRedirect().redirect_request(
        Request("https://github.com/"), None, 302, "", {}, url
    )
    assert redirected.full_url == url


@pytest.mark.parametrize("url", [
    "https://attacker.s3.amazonaws.com/image?signature=secret",
    "https://github-production-user-asset-6210df.s3.amazonaws.com.evil.example/image",
    "https://user:password@github-production-user-asset-6210df.s3.amazonaws.com/image",
    "https://github-production-user-asset-6210df.s3.amazonaws.com:444/image",
    "http://github-production-user-asset-6210df.s3.amazonaws.com/image",
])
def test_redirect_rejects_untrusted_destinations_without_leaking_url(url):
    with pytest.raises(gallery.GalleryError, match="unsupported host") as error:
        gallery.SafeRedirect().redirect_request(Request("https://github.com/"), None, 302, "", {}, url)
    assert "secret" not in str(error.value)
    assert "password" not in str(error.value)


def test_prune_removes_oldest_and_preserves_newest(tmp_path, monkeypatch):
    monkeypatch.setattr(gallery, "ITEMS", tmp_path)
    monkeypatch.setattr(gallery, "LIMIT", 2)
    for number in (1, 2, 3):
        entry = {"issue": number, "created_at": f"2026-01-0{number}T00:00:00Z", "image": f"{number}.jpg"}
        (tmp_path / f"{number}.json").write_text(json.dumps(entry))
        (tmp_path / f"{number}.jpg").write_bytes(b"image")
    assert gallery.prune() == 1
    assert not (tmp_path / "1.json").exists()
    assert not (tmp_path / "1.jpg").exists()
    assert (tmp_path / "2.jpg").exists()
    assert (tmp_path / "3.jpg").exists()


@pytest.mark.parametrize("kind, expected_workflows", [
    ("submission", ["community-retention.yml", "pages.yml"]),
    ("retention", ["pages.yml"]),
])
def test_merge_dispatches_followup_workflows(tmp_path, kind, expected_workflows):
    log = tmp_path / "gh.log"
    gh = tmp_path / "gh"
    gh.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$FAKE_GH_LOG"\n')
    gh.chmod(0o755)
    env = {**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}", "FAKE_GH_LOG": str(log),
           "GITHUB_REPOSITORY": "tuonglab/ktfigure", "BASE_BRANCH": "master"}
    script = SCRIPT.parent / "merge_community_pr.sh"
    subprocess.run(["bash", str(script), "community/figure-42", "abc123", kind], env=env, check=True)
    commands = log.read_text().splitlines()
    assert "--match-head-commit abc123" in commands[0]
    assert [command.split()[2] for command in commands[1:]] == expected_workflows


def test_failed_merge_never_dispatches_workflows(tmp_path):
    log = tmp_path / "gh.log"
    gh = tmp_path / "gh"
    gh.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$FAKE_GH_LOG"\nexit 1\n')
    gh.chmod(0o755)
    sleep = tmp_path / "sleep"
    sleep.write_text("#!/bin/sh\nexit 0\n")
    sleep.chmod(0o755)
    env = {**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}", "FAKE_GH_LOG": str(log),
           "GITHUB_REPOSITORY": "tuonglab/ktfigure", "BASE_BRANCH": "master"}
    script = SCRIPT.parent / "merge_community_pr.sh"
    result = subprocess.run(["bash", str(script), "community/figure-42", "abc123", "submission"], env=env)
    assert result.returncode != 0
    assert len(log.read_text().splitlines()) == 6
    assert "workflow run" not in log.read_text()
