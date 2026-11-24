# CLAUDE.md

Guidance for AI coding agents working in this repository. See `README.md` for the project overview.

**Extracting questions from the PDFs? Follow `docs/extraction-guide.md`.**

## Commands

```bash
uv sync                                   # set up .venv (pytest, ruff)
uv run pytest                             # tests
uv run ruff check && uv run ruff format   # lint and format
uv run lzradio-validate template.json examples/*.json
uv run lzradio-check-updates              # needs network access to crc.bg
```

## Layout

- `src/lzradio_extractor/check_updates.py` – finds the PDFs by following links from the CRC exam page and compares them with `source_pdfs/` by SHA256.
- `src/lzradio_extractor/validate.py` – validates extracted JSON (structure, numbering, answer keys, image names, KaTeX).
- `tests/` – pytest; `test_check_updates.py` fakes the CRC site, so tests never touch the network.
- `.github/workflows/` – `tests.yml` (ruff + pytest on Python 3.11–3.14) and `crc-pdf-check.yml` (nightly check, opens an issue on update).

## Conventions

- Standard library only at runtime; `dependencies` in `pyproject.toml` stays empty.
- Python 3.11+, ruff config in `pyproject.toml` (line length 100).
- Exit codes are part of the interface (the nightly workflow relies on them):
  - `lzradio-check-updates`: `0` up to date, `1` update available, `2` check failed (including unexpected exceptions).
  - `lzradio-validate`: `0` valid, `1` errors.
- `source_pdfs/` holds the official CRC PDFs unmodified – never edit them.
- When changing validation rules, update `docs/extraction-guide.md` to match, and keep `template.json` and `examples/` passing without warnings.
