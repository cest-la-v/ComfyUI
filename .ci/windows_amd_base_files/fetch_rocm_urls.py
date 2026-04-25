"""
Fetch the latest ROCm Windows wheel URLs from https://repo.radeon.com/rocm/windows/

Prints one URL per line to stdout.  Warnings and errors go to stderr.
Exit 0 on success, 1 on failure.

Usage:
    python fetch_rocm_urls.py [--python-tag cp312] [--dry-run]
"""
from __future__ import annotations

import argparse
import re
import sys
import urllib.parse
import urllib.request
from html.parser import HTMLParser


BASE_URL = "https://repo.radeon.com/rocm/windows/"

# Ordered: first match wins for each package name.
# rocm_sdk_devel is intentionally absent (~220 MB developer-only wheel).
def _package_patterns(py_tag: str) -> list[tuple[str, list[str]]]:
    rocm_build = r"(?:\+|%2B)(?:rocm|rocmsdk)"
    return [
        ("rocm_sdk_core",             [r"^rocm_sdk_core-.*-py3-none-win_amd64\.whl$"]),
        ("rocm_sdk_libraries_custom", [r"^rocm_sdk_libraries_custom-.*-py3-none-win_amd64\.whl$"]),
        ("rocm",                      [r"^rocm-.*\.tar\.gz$"]),
        ("torch",       [rf"^torch-.*{rocm_build}.*-{py_tag}-{py_tag}-win_amd64\.whl$",
                         rf"^torch-.*{rocm_build}.*-win_amd64\.whl$"]),
        ("torchaudio",  [rf"^torchaudio-.*{rocm_build}.*-{py_tag}-{py_tag}-win_amd64\.whl$",
                         rf"^torchaudio-.*{rocm_build}.*-win_amd64\.whl$"]),
        ("torchvision", [rf"^torchvision-.*{rocm_build}.*-{py_tag}-{py_tag}-win_amd64\.whl$",
                         rf"^torchvision-.*{rocm_build}.*-win_amd64\.whl$"]),
    ]


class _HrefParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            for k, v in attrs:
                if k == "href" and v:
                    self.hrefs.append(v)


def _fetch_hrefs(url: str) -> list[str]:
    with urllib.request.urlopen(url, timeout=15) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    parser = _HrefParser()
    parser.feed(html)
    return parser.hrefs


def _latest_release(hrefs: list[str]) -> str:
    """Return the latest rocm-rel-X.X.X/ directory name."""
    releases = sorted(
        {h.strip("/") for h in hrefs if re.match(r"rocm-rel-[\d.]+/?$", h)},
        key=lambda s: tuple(int(x) for x in re.findall(r"\d+", s)),
    )
    if not releases:
        raise RuntimeError("No rocm-rel-X.X.X/ directories found at " + BASE_URL)
    return releases[-1]


def _select(files: list[str], patterns: list[str]) -> str | None:
    for pat in patterns:
        for f in files:
            if re.search(pat, urllib.parse.unquote(f)):
                return f
    return None


def fetch_urls(py_tag: str) -> list[str]:
    print(f"[1/2] Fetching release index: {BASE_URL}", file=sys.stderr)
    index_hrefs = _fetch_hrefs(BASE_URL)
    latest = _latest_release(index_hrefs)
    release_url = f"{BASE_URL}{latest}/"
    print(f"      Latest release : {release_url}", file=sys.stderr)

    print(f"[2/2] Fetching file list (python tag: {py_tag})...", file=sys.stderr)
    file_hrefs = _fetch_hrefs(release_url)
    files = [urllib.parse.unquote(h) for h in file_hrefs if h.endswith((".whl", ".tar.gz"))]

    urls: list[str] = []
    missing: list[str] = []
    for pkg, patterns in _package_patterns(py_tag):
        match = _select(files, patterns)
        if match:
            url = match if match.startswith("http") else f"{release_url}{match}"
            urls.append(url)
            print(f"      + {pkg}", file=sys.stderr)
        else:
            missing.append(pkg)
            print(f"      ! {pkg} — not found (skipping)", file=sys.stderr)

    if missing:
        print(f"WARNING: packages not found: {', '.join(missing)}", file=sys.stderr)
    if not urls:
        raise RuntimeError("No matching wheels found.")
    return urls


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--python-tag",
        default=f"cp{sys.version_info.major}{sys.version_info.minor}",
        help="Python ABI tag, e.g. cp312 (default: auto-detect)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print URLs but do not install")
    args = parser.parse_args()

    try:
        urls = fetch_urls(args.python_tag)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    for url in urls:
        print(url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
