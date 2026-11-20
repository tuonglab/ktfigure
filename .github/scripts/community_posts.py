"""Add or remove a maintainer-approved social post from the gallery."""

import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit


ENTRIES = Path(__file__).resolve().parents[2] / "docs" / "community" / "entries.json"
LIMIT = 200


def parse_post(url):
    try:
        parsed = urlsplit(url.strip())
        host, port = parsed.hostname, parsed.port
    except ValueError as exc:
        raise ValueError("Invalid post URL.") from exc
    if parsed.scheme != "https" or parsed.username or parsed.password or port not in (None, 443):
        raise ValueError("Use an HTTPS post URL without credentials or a nonstandard port.")
    path = unquote(parsed.path)
    if host in ("x.com", "www.x.com", "twitter.com", "www.twitter.com"):
        match = re.fullmatch(r"/([A-Za-z0-9_]{1,15})/status/([0-9]{1,25})/?", path)
        if match:
            return {"platform": "x", "id": match.group(2),
                    "url": f"https://x.com/{match.group(1)}/status/{match.group(2)}"}
    elif host in ("linkedin.com", "www.linkedin.com"):
        match = re.fullmatch(r"/(?:embed/)?feed/update/urn:li:(activity|share|ugcPost):([0-9]{1,25})/?", path)
        if not match and re.fullmatch(r"/posts/[A-Za-z0-9_%.-]+/?", parsed.path):
            match = re.search(r"(activity|share|ugcPost)-([0-9]{1,25})(?:-|/?$)", path)
        if match:
            kind, post_id = match.groups()
            return {"platform": "linkedin", "id": f"{kind}:{post_id}",
                    "url": urlunsplit(("https", "www.linkedin.com", parsed.path.rstrip("/"), "", ""))}
    raise ValueError("Use a supported public X or LinkedIn post URL, not a profile or short link.")


def update(entries, operation, url, description=""):
    post = parse_post(url)
    description = description.strip()
    if len(description) > 500:
        raise ValueError("The description must be at most 500 characters.")
    matching = [entry for entry in entries if entry["platform"] == post["platform"] and entry["id"] == post["id"]]
    if operation == "add":
        if matching:
            raise ValueError("This post is already in the gallery.")
        post["description"] = description
        return ([post] + entries)[:LIMIT]
    if operation == "remove":
        if not matching:
            raise ValueError("This post is not in the gallery.")
        return [entry for entry in entries if entry not in matching]
    raise ValueError("Operation must be add or remove.")


def main():
    import os

    try:
        entries = json.loads(ENTRIES.read_text(encoding="utf-8"))
        if not isinstance(entries, list):
            raise ValueError("Invalid gallery index.")
        entries = update(entries, os.environ["OPERATION"], os.environ["POST_URL"], os.environ.get("DESCRIPTION", ""))
        ENTRIES.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except (ValueError, KeyError, OSError) as exc:
        print(f"Community gallery error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
