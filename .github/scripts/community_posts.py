"""Add or remove a maintainer-approved social post from the gallery."""

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit


ENTRIES = Path(__file__).resolve().parents[2] / "docs" / "community" / "entries.json"
LIMIT = 200


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def resolve_linkedin_short_url(url):
    opener = urllib.request.build_opener(NoRedirect())
    for _ in range(5):
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.hostname not in ("lnkd.in", "www.lnkd.in")
                or parsed.username is not None or parsed.password is not None
                or parsed.port not in (None, 443)):
            raise ValueError("The LinkedIn short link redirected to an unsupported destination.")
        request = urllib.request.Request(url, headers={"User-Agent": "ktfigure-community-gallery"})
        try:
            with opener.open(request, timeout=15):
                raise ValueError("The LinkedIn short link did not redirect to a post.")
        except urllib.error.HTTPError as exc:
            with exc:
                location = exc.headers.get("Location")
                if exc.code not in (301, 302, 303, 307, 308) or not location:
                    raise ValueError(f"The LinkedIn short link could not be resolved (HTTP {exc.code}).") from exc
                url = urljoin(url, location)
        except urllib.error.URLError as exc:
            raise ValueError("The LinkedIn short link could not be resolved; try the full post URL.") from exc
        try:
            target = urlsplit(url)
            host, port = target.hostname, target.port
        except ValueError as exc:
            raise ValueError("The LinkedIn short link redirected to an invalid URL.") from exc
        if (target.scheme != "https" or target.username is not None or target.password is not None
                or port not in (None, 443)):
            raise ValueError("The LinkedIn short link redirected to an unsupported destination.")
        if host in ("linkedin.com", "www.linkedin.com"):
            return url
        if host not in ("lnkd.in", "www.lnkd.in"):
            raise ValueError("The LinkedIn short link redirected to an unsupported destination.")
    raise ValueError("The LinkedIn short link has too many redirects.")


def parse_post(url):
    try:
        parsed = urlsplit(url.strip())
        host, port = parsed.hostname, parsed.port
    except ValueError as exc:
        raise ValueError("Invalid post URL.") from exc
    if parsed.scheme != "https" or parsed.username or parsed.password or port not in (None, 443):
        raise ValueError("Use an HTTPS post URL without credentials or a nonstandard port.")
    if host in ("lnkd.in", "www.lnkd.in"):
        if not re.fullmatch(r"/(?:p/)?[A-Za-z0-9_-]+/?", parsed.path):
            raise ValueError("Use a valid LinkedIn short link.")
        return parse_post(resolve_linkedin_short_url(url.strip()))
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
    raise ValueError("Use a supported public X or LinkedIn post URL, not a profile or unsupported short link.")


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
