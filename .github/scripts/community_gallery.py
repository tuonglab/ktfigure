"""Prepare community submissions and build the static gallery index."""

import argparse
import io
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import warnings
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError


ROOT = Path(__file__).resolve().parents[2]
ITEMS = ROOT / "docs" / "community" / "items"
INDEX = ROOT / "docs" / "community" / "entries.json"
LIMIT = 200
MAX_INPUT = 10 * 1024 * 1024
MAX_OUTPUT = 1_000_000
Image.MAX_IMAGE_PIXELS = 20_000_000
ASSET = re.compile(r"https://github\.com/user-attachments/assets/[0-9a-fA-F-]{36}\b")
REDIRECT_HOSTS = {
    "github.com",
    "objects.githubusercontent.com",
    "private-user-images.githubusercontent.com",
    "release-assets.githubusercontent.com",
    "user-images.githubusercontent.com",
}


class GalleryError(ValueError):
    pass


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlsplit(newurl)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in REDIRECT_HOSTS
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
        ):
            raise GalleryError("The image redirected to an unsupported host.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_image(url):
    if not ASSET.fullmatch(url):
        raise GalleryError("Attach exactly one image using GitHub's image uploader.")
    opener = urllib.request.build_opener(SafeRedirect())
    request = urllib.request.Request(url, headers={"User-Agent": "ktfigure-community-gallery"})
    with opener.open(request, timeout=30) as response:
        data = response.read(MAX_INPUT + 1)
    if len(data) > MAX_INPUT:
        raise GalleryError("The original image exceeds 10 MiB.")
    return data


def compress_image(data):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as original:
                if original.format not in ("JPEG", "PNG"):
                    raise GalleryError("Only JPEG and PNG images are supported.")
                original.load()
                image = ImageOps.exif_transpose(original)
                has_alpha = "A" in image.getbands() or "transparency" in image.info
                image = image.convert("RGBA" if has_alpha else "RGB")
                image.info.clear()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        raise GalleryError("The image is invalid or too large to process safely.") from exc

    image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    extension = "png" if has_alpha else "jpg"
    while True:
        output = io.BytesIO()
        if has_alpha:
            image.save(output, format="PNG", optimize=True)
        else:
            image.save(output, format="JPEG", quality=82, optimize=True)
        if output.tell() < MAX_OUTPUT:
            return extension, output.getvalue()
        if max(image.size) <= 100:
            raise GalleryError("The image could not be compressed below 1 MB.")
        size = tuple(max(1, int(dimension * 0.8)) for dimension in image.size)
        image = image.resize(size, Image.Resampling.LANCZOS)


def fields(body):
    matches = list(re.finditer(r"(?m)^### (Image|Display name|Description|Feedback about ktfigure|Paper citation|DOI|Paper or project URL|Permission)\s*$", body))
    result = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        name = match.group(1)
        if name in result:
            raise GalleryError("The submission contains duplicate form fields.")
        value = body[match.end():end].strip()
        result[name] = "" if value == "_No response_" else value
    return result


def plain_field(value, maximum, name):
    value = value.strip()
    if len(value) > maximum:
        raise GalleryError(f"{name} must be at most {maximum} characters.")
    return value


def normalize_doi(value):
    value = plain_field(value, 500, "DOI")
    if not value:
        return ""
    if value.lower().startswith("doi:"):
        value = value[4:].strip()
    elif "://" in value:
        try:
            parsed = urllib.parse.urlsplit(value)
            port = parsed.port
        except ValueError as exc:
            raise GalleryError("Enter a DOI or a doi.org link.") from exc
        if (
            parsed.scheme not in ("http", "https")
            or parsed.hostname not in ("doi.org", "dx.doi.org")
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or port not in (None, 80, 443)
        ):
            raise GalleryError("Enter a DOI or a doi.org link.")
        value = urllib.parse.unquote(parsed.path.lstrip("/"))
    if len(value) > 500 or not re.fullmatch(r"10\.[0-9]{4,9}/\S+", value, flags=re.IGNORECASE):
        raise GalleryError("Enter a DOI such as 10.1000/example or a doi.org link.")
    return value


def load_items():
    if not ITEMS.exists():
        return []
    items = []
    for path in ITEMS.glob("*.json"):
        with path.open(encoding="utf-8") as file:
            entry = json.load(file)
        items.append((entry, path))
    return sorted(items, key=lambda item: (item[0]["created_at"], item[0]["issue"]))


def prune():
    items = load_items()
    for entry, path in items[:-LIMIT]:
        image = ITEMS / Path(entry["image"]).name
        image.unlink()
        path.unlink()
    return max(0, len(items) - LIMIT)


def submit(event):
    issue = event["issue"]
    number = issue["number"]
    if not isinstance(number, int) or number <= 0:
        raise GalleryError("Invalid issue number.")
    if (ITEMS / f"{number}.json").exists():
        raise GalleryError("This issue has already been added to the gallery.")
    values = fields(issue.get("body") or "")
    urls = ASSET.findall(values.get("Image", ""))
    if len(urls) != 1:
        raise GalleryError("Attach exactly one image using GitHub's image uploader.")
    if not re.search(r"(?im)^\s*-\s*\[x\]\s*I have permission to share", values.get("Permission", "")):
        raise GalleryError("Confirm that you have permission to share the image.")
    link = plain_field(values.get("Paper or project URL", ""), 500, "URL")
    if link:
        parsed = urllib.parse.urlsplit(link)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
            raise GalleryError("The project URL must be a public HTTP or HTTPS URL.")
    entry = {
        "issue": number,
        "created_at": issue["created_at"],
        "name": plain_field(values.get("Display name", ""), 100, "Display name") or "Anonymous",
        "description": plain_field(values.get("Description", ""), 1500, "Description"),
        "feedback": plain_field(values.get("Feedback about ktfigure", ""), 1500, "Feedback"),
        "citation": plain_field(values.get("Paper citation", ""), 500, "Citation"),
        "doi": normalize_doi(values.get("DOI", "")),
        "link": link,
    }
    extension, data = compress_image(download_image(urls[0]))
    entry["image"] = f"{number}.{extension}"
    ITEMS.mkdir(parents=True, exist_ok=True)
    (ITEMS / entry["image"]).write_bytes(data)
    (ITEMS / f"{number}.json").write_text(json.dumps(entry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    prune()
    if not (ITEMS / f"{number}.json").exists():
        raise GalleryError("This submission is older than the 200 current gallery entries.")


def build():
    entries = [item for item, _ in reversed(load_items())][:LIMIT]
    INDEX.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("submit", "prune", "build"))
    parser.add_argument("--issue", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "submit":
            if not args.issue:
                parser.error("--issue is required for submit")
            with args.issue.open(encoding="utf-8") as file:
                submit({"issue": json.load(file)})
        elif args.command == "prune":
            print(f"Removed {prune()} old gallery items.")
        else:
            build()
    except (GalleryError, OSError, urllib.error.URLError, KeyError) as exc:
        print(f"Gallery error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
