# LZ Radio Extractor

[![Tests](https://github.com/batinkov/lzradio_extractor/actions/workflows/tests.yml/badge.svg)](https://github.com/batinkov/lzradio_extractor/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Tools for turning the Bulgarian amateur radio license exam questions into JSON.

The Bulgarian Communications Regulation Commission (CRC / КРС) publishes the official exam questions only as [PDF files](https://crc.bg/bg/rubriki/143/testove-za-provejdane-na-izpiti-za-pravosposobnost-na-radiolubiteli). This repository keeps copies of those PDFs, detects when the CRC publishes new versions, and validates the JSON extracted from them. The JSON is used by [LZ Radio](https://github.com/batinkov/lzradio) ([lzradio.eu](https://lzradio.eu)), a web app for practising for the exams.

Extraction itself is done with an LLM and checked by a human; see the [extraction guide](docs/extraction-guide.md).

## Quick Start

Requires [uv](https://docs.astral.sh/uv/), which installs a suitable Python (3.11+) automatically. The tools use only the Python standard library.

```bash
uv sync

# Check whether the CRC has published new PDFs
uv run lzradio-check-updates

# Validate an extracted JSON file
uv run lzradio-validate extracted_json/Class2_Section1.json
```

## Tools

**`lzradio-check-updates`** follows the links on the CRC exam page to the current PDFs (CRC renames the files from time to time), downloads them to `downloads/` and compares them with `source_pdfs/`.
Exit codes: `0` up to date, `1` update available, `2` check failed (network error or the CRC site layout changed).
A [nightly workflow](.github/workflows/crc-pdf-check.yml) runs it and opens an issue when an update is found.

**`lzradio-validate`** checks extracted JSON files: structure and required fields, question numbering, answer keys, image names and KaTeX formatting.
Exit codes: `0` valid (possibly with warnings), `1` errors found.

## Workflow

1. `uv run lzradio-check-updates`. If an update is available, review the PDFs in `downloads/` and copy them to `source_pdfs/`.
2. Extract the questions with an LLM into `extracted_json/`, following the [extraction guide](docs/extraction-guide.md).
3. `uv run lzradio-validate extracted_json/<file>.json` and fix what it reports.
4. Copy the JSON (and any question images) into the LZ Radio repository and check it in the app.

## Repository Layout

```
source_pdfs/            Official CRC PDFs (class_<X>_razdel_<Y>.pdf)
template.json           Minimal JSON skeleton for one section
examples/               Real extracted questions, with and without KaTeX
docs/                   Extraction guide
src/lzradio_extractor/  validate.py and check_updates.py
tests/                  pytest tests (no network access needed)
extracted_json/         Your extraction output (gitignored)
downloads/              PDFs downloaded by the update check (gitignored)
```

## Development

```bash
uv sync                 # create .venv with pytest and ruff
uv run pytest           # run tests
uv run ruff check       # lint
uv run ruff format      # format
```

CI runs the same checks on every push and pull request.

## Contributing

Issues and pull requests are welcome, for example when the CRC site changes and the update check breaks, or when the validator misses a formatting problem. Corrections to the questions themselves belong in the [LZ Radio](https://github.com/batinkov/lzradio) repository.

## License

The code and documentation in this repository are licensed under the [MIT License](LICENSE).

The PDF files in `source_pdfs/` are official documents published by the CRC at [crc.bg](https://crc.bg/bg/rubriki/143/testove-za-provejdane-na-izpiti-za-pravosposobnost-na-radiolubiteli). They are included unmodified for reference and are not covered by the MIT License.
