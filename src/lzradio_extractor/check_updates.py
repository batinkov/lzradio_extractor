#!/usr/bin/env python3
"""
Check the CRC website for updated amateur radio exam PDFs.

CRC renames its PDF files from time to time, so file URLs are not hardcoded.
Instead the script starts at the CRC index page, follows the links to the
class pages ("Радиолюбителски клас 1/2") and identifies each PDF by its link
text ("Раздел N"). Every PDF is downloaded to downloads/ and compared by
SHA256 with the local copy in source_pdfs/class_X_razdel_Y.pdf.

Both directories are resolved relative to the repository root, which is the
current directory unless --root is given.

Usage:
    lzradio-check-updates [--root DIR]

Exit codes:
    0  all files up to date
    1  at least one file differs from (or is missing in) source_pdfs/
    2  the check could not be completed (network error, site layout changed, ...)
"""

import argparse
import hashlib
import os
import re
import sys
import traceback
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

INDEX_URL = (
    "https://crc.bg/bg/rubriki/143/"
    "testove-za-provejdane-na-izpiti-za-pravosposobnost-na-radiolubiteli"
)
USER_AGENT = "lzradio-extractor (CRC exam PDF update check)"
TIMEOUT = 30

CLASSES = (1, 2)
SECTIONS = (1, 2, 3)

SOURCE_DIR_NAME = "source_pdfs"
DOWNLOAD_DIR_NAME = "downloads"

EXIT_UP_TO_DATE = 0
EXIT_UPDATED = 1
EXIT_ERROR = 2


def _use_color() -> bool:
    return sys.stdout.isatty() and "NO_COLOR" not in os.environ


class Colors:
    """ANSI color codes; empty when output is not a terminal or NO_COLOR is set."""

    _on = _use_color()
    RED = '\033[91m' if _on else ''
    YELLOW = '\033[93m' if _on else ''
    GREEN = '\033[92m' if _on else ''
    BOLD = '\033[1m' if _on else ''
    RESET = '\033[0m' if _on else ''


class CheckError(Exception):
    """The check could not be completed."""


class LinkParser(HTMLParser):
    """Collects (href, text, title) for every <a> element."""

    def __init__(self):
        super().__init__()
        self.links = []
        self._current = None

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            attrs = dict(attrs)
            self._current = {
                'href': attrs.get('href') or '',
                'title': attrs.get('title') or '',
                'text': [],
            }

    def handle_data(self, data):
        if self._current is not None:
            self._current['text'].append(data)

    def handle_endtag(self, tag):
        if tag == 'a' and self._current is not None:
            text = ' '.join(''.join(self._current['text']).split())
            self.links.append((self._current['href'], text, self._current['title']))
            self._current = None


def fetch(url: str) -> bytes:
    req = Request(url, headers={'User-Agent': USER_AGENT})
    try:
        with urlopen(req, timeout=TIMEOUT) as response:
            return response.read()
    except HTTPError as e:
        raise CheckError(f"HTTP {e.code} {e.reason}: {url}") from e
    except OSError as e:  # URLError and TimeoutError are OSError subclasses
        reason = getattr(e, 'reason', e)
        raise CheckError(f"Cannot fetch {url}: {reason}") from e


def get_links(url: str):
    """Return absolute (href, label) pairs for all links on a page."""
    parser = LinkParser()
    parser.feed(fetch(url).decode('utf-8', errors='replace'))
    return [(urljoin(url, href), f"{text} {title}") for href, text, title in parser.links if href]


def find_class_pages() -> dict:
    """Map class number -> URL of its page, found via the index page."""
    pages = {}
    for href, label in get_links(INDEX_URL):
        m = re.search(r'клас\s*([12])\b', label, re.IGNORECASE)
        if m and '/rubriki/' in href:
            pages.setdefault(int(m.group(1)), href)
    missing = [c for c in CLASSES if c not in pages]
    if missing:
        raise CheckError(
            f"Class page(s) {missing} not found on {INDEX_URL} - did the site layout change?"
        )
    return pages


def find_section_pdfs(class_url: str) -> dict:
    """Map section number -> PDF URL, found via the link text on a class page."""
    pdfs = {}
    for href, label in get_links(class_url):
        if not urlparse(href).path.lower().endswith('.pdf'):
            continue
        m = re.search(r'Раздел\s*(\d+)', label, re.IGNORECASE)
        if not m:
            continue
        section = int(m.group(1))
        if section in pdfs and pdfs[section] != href:
            raise CheckError(f"Several PDFs for section {section} on {class_url}")
        pdfs[section] = href
    if sorted(pdfs) != list(SECTIONS):
        raise CheckError(
            f"Expected PDFs for sections {list(SECTIONS)} on {class_url}, "
            f"found {sorted(pdfs)} - did the site layout change?"
        )
    return pdfs


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check_updates(root: Path) -> int:
    source_dir = root / SOURCE_DIR_NAME
    download_dir = root / DOWNLOAD_DIR_NAME
    if not source_dir.is_dir():
        raise CheckError(f"{source_dir} not found - run from the repository root or pass --root")

    print(f"\n{Colors.BOLD}Checking for updates to CRC PDF files{Colors.RESET}")
    print("=" * 70)
    print(f"Index:  {INDEX_URL}")
    print(f"Local:  {source_dir}/")
    print()

    remote = {}  # local filename -> PDF URL
    for cls, class_url in sorted(find_class_pages().items()):
        for section, pdf_url in sorted(find_section_pdfs(class_url).items()):
            remote[f"class_{cls}_razdel_{section}.pdf"] = pdf_url

    download_dir.mkdir(exist_ok=True)
    identical, updated, missing = [], [], []

    for name, url in remote.items():
        print(f"{Colors.BOLD}{name}{Colors.RESET}")
        print(f"  {url}")
        data = fetch(url)
        if not data.startswith(b'%PDF'):
            raise CheckError(f"{url} is not a PDF")
        (download_dir / name).write_bytes(data)
        remote_hash = sha256(data)

        local = source_dir / name
        if not local.exists():
            print(f"  {Colors.YELLOW}⚠ Not found locally{Colors.RESET}")
            missing.append(name)
        elif sha256(local.read_bytes()) == remote_hash:
            print(f"  {Colors.GREEN}✓ Up to date (SHA256: {remote_hash[:16]}...){Colors.RESET}")
            identical.append(name)
        else:
            print(f"  {Colors.YELLOW}⚠ Differs from local copy - update available{Colors.RESET}")
            updated.append(name)
        print()

    print("=" * 70)
    if updated or missing:
        print(f"{Colors.YELLOW}{Colors.BOLD}⚠️  UPDATES AVAILABLE{Colors.RESET}")
        for name in updated:
            print(f"  • {name} (changed)")
        for name in missing:
            print(f"  • {name} (missing locally)")
        print(f"\nNew versions saved in {download_dir}/")
        return EXIT_UPDATED

    print(f"{Colors.GREEN}{Colors.BOLD}✅ ALL FILES UP TO DATE{Colors.RESET}")
    print(f"   All {len(identical)} files match the CRC website")
    return EXIT_UP_TO_DATE


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Check the CRC website for updated amateur radio exam PDFs.",
        epilog="Exit codes: 0 up to date, 1 update available, 2 check failed.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="repository root containing source_pdfs/ (default: current directory)",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        sys.exit(check_updates(args.root.resolve()))
    except CheckError as e:
        print(f"\n{Colors.RED}{Colors.BOLD}✗ CHECK FAILED:{Colors.RESET} {e}")
        sys.exit(EXIT_ERROR)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Interrupted by user{Colors.RESET}")
        sys.exit(130)
    except Exception:
        # Unexpected bug: show the traceback, but never exit with 1
        # (that would be reported as "update available").
        print(f"\n{Colors.RED}{Colors.BOLD}✗ UNEXPECTED ERROR:{Colors.RESET}", flush=True)
        traceback.print_exc()
        sys.exit(EXIT_ERROR)


if __name__ == '__main__':
    main()
