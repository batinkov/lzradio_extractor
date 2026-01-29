#!/usr/bin/env python3
"""
Check for updates to CRC PDF files

Downloads official PDF files from CRC website and compares them with local copies
to detect when new versions are available.
"""

import hashlib
import sys
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError


class Colors:
    """ANSI color codes for terminal output"""
    RED = '\033[91m'
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    RESET = '\033[0m'


def calculate_sha256(filepath: Path) -> str:
    """Calculate SHA256 hash of a file"""
    sha256_hash = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            # Read in chunks to handle large files
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"  {Colors.RED}Error calculating hash: {e}{Colors.RESET}")
        return None


def download_file(url: str, destination: Path) -> bool:
    """Download a file from URL to destination path"""
    try:
        # Add user agent to avoid potential blocks
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})

        with urlopen(req, timeout=30) as response:
            content = response.read()

        # Write to file
        destination.parent.mkdir(parents=True, exist_ok=True)
        with open(destination, 'wb') as f:
            f.write(content)

        return True

    except HTTPError as e:
        print(f"  {Colors.RED}HTTP Error {e.code}: {e.reason}{Colors.RESET}")
        return False
    except URLError as e:
        print(f"  {Colors.RED}URL Error: {e.reason}{Colors.RESET}")
        return False
    except TimeoutError:
        print(f"  {Colors.RED}Timeout: Server did not respond{Colors.RESET}")
        return False
    except Exception as e:
        print(f"  {Colors.RED}Error: {e}{Colors.RESET}")
        return False


def check_updates():
    """Check for updates to CRC PDF files"""

    # Base URL for CRC files
    BASE_URL = "https://crc.bg/files/URChS/Radioamateur"

    # Files to check
    files = [
        "class_1_razdel_1.pdf",
        "class_1_razdel_2.pdf",
        "class_1_razdel_3.pdf",
        "class_2_razdel_1.pdf",
        "class_2_razdel_2.pdf",
        "class_2_razdel_3.pdf",
    ]

    # Directories
    aux_dir = Path("aux")
    source_dir = Path("source_pdfs")

    # Create aux directory if it doesn't exist
    aux_dir.mkdir(exist_ok=True)

    print(f"\n{Colors.BOLD}Checking for updates to CRC PDF files{Colors.RESET}")
    print("=" * 70)
    print(f"Source: {BASE_URL}")
    print(f"Local:  {source_dir}/")
    print()

    # Track results
    results = {
        'identical': [],
        'updated': [],
        'download_failed': [],
        'missing_local': [],
    }

    # Check each file
    for filename in files:
        print(f"{Colors.BOLD}{filename}{Colors.RESET}")

        # Construct URL
        url = f"{BASE_URL}/{filename}"

        # Paths
        aux_file = aux_dir / filename
        source_file = source_dir / filename

        # Download file
        print(f"  Downloading from {url}...")
        if not download_file(url, aux_file):
            results['download_failed'].append(filename)
            print()
            continue

        print(f"  {Colors.GREEN}✓ Downloaded{Colors.RESET}")

        # Calculate hash of downloaded file
        aux_hash = calculate_sha256(aux_file)
        if not aux_hash:
            results['download_failed'].append(filename)
            print()
            continue

        # Check if source file exists
        if not source_file.exists():
            print(f"  {Colors.YELLOW}⚠ File not found in {source_dir}/{Colors.RESET}")
            results['missing_local'].append(filename)
            print()
            continue

        # Calculate hash of source file
        source_hash = calculate_sha256(source_file)
        if not source_hash:
            results['download_failed'].append(filename)
            print()
            continue

        # Compare hashes
        if aux_hash == source_hash:
            print(f"  {Colors.GREEN}✓ Files match (SHA256: {aux_hash[:16]}...){Colors.RESET}")
            results['identical'].append(filename)
        else:
            print(f"  {Colors.YELLOW}⚠ FILES DIFFER - Update available!{Colors.RESET}")
            print(f"    Downloaded: {aux_hash[:16]}...")
            print(f"    Local:      {source_hash[:16]}...")
            results['updated'].append(filename)

        print()

    # Print summary
    print("=" * 70)
    print(f"{Colors.BOLD}SUMMARY{Colors.RESET}")
    print()

    if results['identical']:
        print(f"{Colors.GREEN}✓ Up to date ({len(results['identical'])} files):{Colors.RESET}")
        for f in results['identical']:
            print(f"  • {f}")
        print()

    if results['updated']:
        print(f"{Colors.YELLOW}⚠ Updates available ({len(results['updated'])} files):{Colors.RESET}")
        for f in results['updated']:
            print(f"  • {f}")
        print()

    if results['missing_local']:
        print(f"{Colors.YELLOW}⚠ Missing from {source_dir}/ ({len(results['missing_local'])} files):{Colors.RESET}")
        for f in results['missing_local']:
            print(f"  • {f}")
        print()

    if results['download_failed']:
        print(f"{Colors.RED}✗ Download failed ({len(results['download_failed'])} files):{Colors.RESET}")
        for f in results['download_failed']:
            print(f"  • {f}")
        print()

    # Overall status
    total = len(files)
    if results['updated'] or results['missing_local'] or results['download_failed']:
        if results['updated']:
            print(f"{Colors.YELLOW}{Colors.BOLD}⚠️  UPDATES AVAILABLE{Colors.RESET}")
            print(f"   {len(results['updated'])} file(s) have been updated on the CRC website")
        else:
            print(f"{Colors.YELLOW}{Colors.BOLD}⚠️  ISSUES DETECTED{Colors.RESET}")
            print(f"   Check missing or failed downloads above")
        return 1
    else:
        print(f"{Colors.GREEN}{Colors.BOLD}✅ ALL FILES UP TO DATE{Colors.RESET}")
        print(f"   All {total} files match the CRC website")
        return 0


def main():
    """Main entry point"""
    try:
        exit_code = check_updates()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Interrupted by user{Colors.RESET}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{Colors.RED}{Colors.BOLD}Unexpected error:{Colors.RESET} {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
