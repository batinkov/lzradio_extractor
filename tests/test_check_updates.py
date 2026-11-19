"""Tests for lzradio_extractor.check_updates (no network access)."""

import hashlib

import pytest

from lzradio_extractor import check_updates as cu

BASE = "https://crc.bg"
CLASS_URLS = {
    1: f"{BASE}/bg/rubriki/145/radiolubitelski-klas-1",
    2: f"{BASE}/bg/rubriki/144/radiolubitelski-klas-2",
}
PDF_BASE = f"{BASE}/files/URChS/Radioamateur"
SECTION_TITLES = {
    1: "Раздел 1 - Електротехника и радиотехника",
    2: "Раздел 2 - Кодове и радиолюбителски съкращения",
    3: "Раздел 3 - Нормативна уредба",
}


def link(href, text, title=None):
    """An <a> element shaped like the ones on crc.bg."""
    title_attr = f' title="{title or text}"'
    return (
        f'<h5 class="title"><a href="{href}"{title_attr} target="_blank">'
        f'<i class="bi bi-arrow-right"></i>\n    {text}\n</a></h5>'
    )


def page(*links):
    nav = (
        '<nav><a href="https://crc.bg/bg/rubriki/4/za-nas">За нас</a>'
        '<a href="https://crc.bg/bg/rubriki/142/informacija-za-radiolubiteli">'
        "Информация за радиолюбители</a></nav>"
    )
    return f"<html><body>{nav}<ul>{''.join(links)}</ul></body></html>".encode()


def index_page():
    return page(
        link(CLASS_URLS[2], "Радиолюбителски клас 2"),
        link(CLASS_URLS[1], "Радиолюбителски клас 1"),
    )


def class_page(pdf_urls):
    return page(*(link(url, SECTION_TITLES[s]) for s, url in sorted(pdf_urls.items())))


def pdf(content):
    return b"%PDF-1.7\n" + content.encode()


def default_pdf_urls(cls):
    return {s: f"{PDF_BASE}/class_{cls}_razdel_{s}.pdf" for s in (1, 2, 3)}


class FakeSite:
    """Serves a fake crc.bg. Fill .pages with url -> bytes."""

    def __init__(self, pdf_urls=None):
        self.pdf_urls = pdf_urls or {cls: default_pdf_urls(cls) for cls in (1, 2)}
        self.pages = {cu.INDEX_URL: index_page()}
        for cls, urls in self.pdf_urls.items():
            self.pages[CLASS_URLS[cls]] = class_page(urls)
            for s, url in urls.items():
                self.pages[url] = pdf(f"class {cls} section {s}")
        self.requested = []

    def pdf_url(self, cls, section):
        return self.pdf_urls[cls][section]

    def fetch(self, url):
        self.requested.append(url)
        if url not in self.pages:
            raise cu.CheckError(f"HTTP 404 Not Found: {url}")
        return self.pages[url]


@pytest.fixture
def site(monkeypatch):
    fake = FakeSite()
    monkeypatch.setattr(cu, "fetch", fake.fetch)
    return fake


@pytest.fixture
def repo(tmp_path, site):
    """A repository root whose source_pdfs/ matches the fake site."""
    source = tmp_path / "source_pdfs"
    source.mkdir()
    for cls in (1, 2):
        for s in (1, 2, 3):
            data = site.pages[site.pdf_url(cls, s)]
            (source / f"class_{cls}_razdel_{s}.pdf").write_bytes(data)
    return tmp_path


# ----------------------------------------------------------------------
# Link parsing


def test_link_parser_collects_text_and_title():
    parser = cu.LinkParser()
    parser.feed('<a href="/x" title="T">  Some\n   <b>text</b> </a><a>no href</a>')
    assert parser.links == [("/x", "Some text", "T"), ("", "no href", "")]


def test_get_links_makes_urls_absolute(monkeypatch):
    monkeypatch.setattr(cu, "fetch", lambda url: b'<a href="/files/a.pdf">A</a>')
    assert cu.get_links("https://crc.bg/bg/rubriki/1/x") == [("https://crc.bg/files/a.pdf", "A ")]


def test_find_class_pages(site):
    assert cu.find_class_pages() == CLASS_URLS


def test_find_class_pages_missing_class(site):
    site.pages[cu.INDEX_URL] = page(link(CLASS_URLS[2], "Радиолюбителски клас 2"))
    with pytest.raises(cu.CheckError, match=r"Class page\(s\) \[1\] not found"):
        cu.find_class_pages()


def test_find_class_pages_ignores_non_rubriki_links(site):
    site.pages[cu.INDEX_URL] = page(
        link(f"{PDF_BASE}/klas1.pdf", "Радиолюбителски клас 1"),
        link(CLASS_URLS[2], "Радиолюбителски клас 2"),
    )
    with pytest.raises(cu.CheckError, match=r"\[1\] not found"):
        cu.find_class_pages()


def test_find_section_pdfs_uses_link_text_not_filename(site):
    renamed = {
        1: f"{PDF_BASE}/Class2AktualiziranRazdel1_2025.pdf",
        2: f"{PDF_BASE}/class_2_razdel_2.pdf",
        3: f"{PDF_BASE}/class_2_razdel_3.pdf_2026.pdf",
    }
    site.pages[CLASS_URLS[2]] = class_page(renamed)
    assert cu.find_section_pdfs(CLASS_URLS[2]) == renamed


def test_find_section_pdfs_ignores_non_pdf_links(site):
    urls = default_pdf_urls(2)
    site.pages[CLASS_URLS[2]] = page(
        link(f"{BASE}/bg/rubriki/9/razdel-1", "Раздел 1 - описание"),
        *(link(url, SECTION_TITLES[s]) for s, url in urls.items()),
    )
    assert cu.find_section_pdfs(CLASS_URLS[2]) == urls


def test_find_section_pdfs_accepts_uppercase_extension(site):
    urls = default_pdf_urls(2)
    urls[1] = f"{PDF_BASE}/RAZDEL1.PDF"
    site.pages[CLASS_URLS[2]] = class_page(urls)
    assert cu.find_section_pdfs(CLASS_URLS[2])[1] == urls[1]


def test_find_section_pdfs_missing_section(site):
    urls = default_pdf_urls(2)
    del urls[3]
    site.pages[CLASS_URLS[2]] = class_page(urls)
    with pytest.raises(cu.CheckError, match=r"found \[1, 2\]"):
        cu.find_section_pdfs(CLASS_URLS[2])


def test_find_section_pdfs_conflicting_links(site):
    urls = default_pdf_urls(2)
    site.pages[CLASS_URLS[2]] = page(
        *(link(url, SECTION_TITLES[s]) for s, url in urls.items()),
        link(f"{PDF_BASE}/other.pdf", SECTION_TITLES[1]),
    )
    with pytest.raises(cu.CheckError, match="Several PDFs for section 1"):
        cu.find_section_pdfs(CLASS_URLS[2])


def test_find_section_pdfs_same_link_twice_ok(site):
    urls = default_pdf_urls(2)
    site.pages[CLASS_URLS[2]] = page(
        *(link(url, SECTION_TITLES[s]) for s, url in urls.items()),
        link(urls[1], SECTION_TITLES[1]),
    )
    assert cu.find_section_pdfs(CLASS_URLS[2]) == urls


# ----------------------------------------------------------------------
# Whole check


def test_up_to_date(repo, site, capsys):
    assert cu.check_updates(repo) == cu.EXIT_UP_TO_DATE
    assert "ALL FILES UP TO DATE" in capsys.readouterr().out
    assert len(list((repo / "downloads").glob("*.pdf"))) == 6


def test_changed_file(repo, site, capsys):
    site.pages[site.pdf_url(2, 3)] = pdf("new version")
    assert cu.check_updates(repo) == cu.EXIT_UPDATED
    out = capsys.readouterr().out
    assert "class_2_razdel_3.pdf (changed)" in out
    downloaded = (repo / "downloads" / "class_2_razdel_3.pdf").read_bytes()
    assert downloaded == pdf("new version")


def test_renamed_file_with_same_content_is_up_to_date(repo, site):
    old_url = site.pdf_url(2, 1)
    new_url = f"{PDF_BASE}/Class2AktualiziranRazdel1_2025.pdf"
    site.pages[new_url] = site.pages.pop(old_url)
    site.pdf_urls[2][1] = new_url
    site.pages[CLASS_URLS[2]] = class_page(site.pdf_urls[2])
    assert cu.check_updates(repo) == cu.EXIT_UP_TO_DATE
    assert new_url in site.requested


def test_missing_local_file(repo, site, capsys):
    (repo / "source_pdfs" / "class_1_razdel_2.pdf").unlink()
    assert cu.check_updates(repo) == cu.EXIT_UPDATED
    assert "class_1_razdel_2.pdf (missing locally)" in capsys.readouterr().out


def test_download_not_a_pdf(repo, site):
    site.pages[site.pdf_url(1, 1)] = b"<html>Error</html>"
    with pytest.raises(cu.CheckError, match="is not a PDF"):
        cu.check_updates(repo)


def test_download_fails(repo, site):
    del site.pages[site.pdf_url(1, 1)]
    with pytest.raises(cu.CheckError, match="404"):
        cu.check_updates(repo)


def test_missing_source_dir(tmp_path, site):
    with pytest.raises(cu.CheckError, match="source_pdfs not found"):
        cu.check_updates(tmp_path)


def test_sha256():
    assert cu.sha256(b"abc") == hashlib.sha256(b"abc").hexdigest()


# ----------------------------------------------------------------------
# main() exit codes


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (None, cu.EXIT_UP_TO_DATE),
        ("update", cu.EXIT_UPDATED),
        ("error", cu.EXIT_ERROR),
    ],
)
def test_main_exit_codes(repo, site, change, expected):
    if change == "update":
        site.pages[site.pdf_url(1, 1)] = pdf("changed")
    elif change == "error":
        del site.pages[cu.INDEX_URL]
    with pytest.raises(SystemExit) as exc:
        cu.main(["--root", str(repo)])
    assert exc.value.code == expected


def test_main_unexpected_error_exits_2(repo, monkeypatch, capsys):
    def boom(root):
        raise ValueError("simulated bug")

    monkeypatch.setattr(cu, "check_updates", boom)
    with pytest.raises(SystemExit) as exc:
        cu.main(["--root", str(repo)])
    assert exc.value.code == cu.EXIT_ERROR
    assert "simulated bug" in capsys.readouterr().err


def test_fetch_wraps_network_errors(monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(cu, "urlopen", fail)
    with pytest.raises(cu.CheckError, match="connection refused"):
        cu.fetch("https://crc.bg/x")
