# LZ Radio Extractor

Tools and documentation for extracting Bulgarian amateur radio license exam questions from official CRC PDF files into structured JSON format.

## Overview

This repository contains tools to:
- Check for updates to official CRC (Communications Regulation Commission) PDF files
- Extract exam questions from PDFs using LLM assistance
- Validate extracted JSON files for correctness and formatting
- Maintain consistency with KaTeX mathematical notation

## Quick Start

### Prerequisites
- [uv](https://docs.astral.sh/uv/) (installs a suitable Python automatically)
- Python 3.11 or higher - the tools themselves use only the standard library
- Internet connection (for PDF update checks)
- Access to Claude or another LLM for PDF extraction

### Setup

```bash
uv sync
```

### Check for PDF Updates

Before extracting, check if CRC has published updated versions:

```bash
uv run lzradio-check-updates
```

This follows the links on the CRC exam page to find the current PDFs (CRC renames them from time to time), downloads them to `downloads/` and compares them with your local copies.

Exit codes: `0` up to date, `1` update available, `2` check failed (network error or the CRC site layout changed).

### Extract Questions from PDF

1. Open a PDF file from `source_pdfs/`
2. Use an LLM (Claude recommended) to extract questions following the format in `template.json`
3. Refer to `CLAUDE.md` for detailed formatting rules (especially KaTeX for mathematical notation)
4. Save extracted questions to `extracted_json/`

**See `CLAUDE.md` for complete extraction workflow and LLM prompt examples.**

### Validate Extracted JSON

After extracting questions, validate the JSON file:

```bash
uv run lzradio-validate extracted_json/Class1_Section1.json
```

The validator checks:
- ✅ JSON structure and required fields
- ✅ Question numbering and answer keys
- ⚠️ KaTeX formatting for Greek letters (λ, τ, α, β, etc.)
- ⚠️ Proper handling of image-based questions

Fix any warnings, then re-validate until clean.

## Directory Structure

```
lzradio_extractor/
├── source_pdfs/              # Official PDF files from CRC
│   ├── class_1_razdel_1.pdf
│   ├── class_1_razdel_2.pdf
│   └── ...
├── extracted_json/           # Your extracted JSON files (temporary)
├── downloads/                # Downloaded PDFs for comparison (gitignored)
├── examples/                 # Reference examples
│   ├── simple_no_math.json
│   └── complex_with_katex.json
├── template.json             # JSON structure template
├── src/lzradio_extractor/
│   ├── validate.py           # JSON validator (lzradio-validate)
│   └── check_updates.py      # CRC update checker (lzradio-check-updates)
├── tests/                    # pytest tests
├── pyproject.toml            # Project metadata, dev dependencies, tool config
├── uv.lock                   # Locked dev dependencies
├── CLAUDE.md                 # Detailed extraction guide (for LLMs)
└── README.md                 # This file
```

## Files in This Repository

### Official Source PDFs

- `source_pdfs/class_1_razdel_1.pdf` - Class 1, Section 1: Електротехника и радиотехника
- `source_pdfs/class_1_razdel_2.pdf` - Class 1, Section 2: Кодове и радиолюбителски съкращения
- `source_pdfs/class_1_razdel_3.pdf` - Class 1, Section 3: Нормативна уредба
- `source_pdfs/class_2_razdel_1.pdf` - Class 2, Section 1: Електротехника и радиотехника
- `source_pdfs/class_2_razdel_2.pdf` - Class 2, Section 2: Кодове и радиолюбителски съкращения
- `source_pdfs/class_2_razdel_3.pdf` - Class 2, Section 3: Нормативна уредба

### Tools

**`lzradio-check-updates`** (`src/lzradio_extractor/check_updates.py`)
- Finds the current PDFs by following links from the CRC exam page (no hardcoded file URLs)
- Downloads them to `downloads/` and compares with local files using SHA256 hashes
- Exit codes: 0 up to date, 1 update available, 2 check failed
- Reports which files have been updated

**`lzradio-validate`** (`src/lzradio_extractor/validate.py`)
- Validates JSON structure and content
- Checks KaTeX formatting for mathematical notation
- Handles image-based questions
- Provides detailed error and warning reports

**`template.json`**
- Complete JSON structure example
- Shows all required fields
- Includes KaTeX formatting examples
- Demonstrates image-based questions

### Documentation

**`CLAUDE.md`** (Detailed extraction guide)
- Complete KaTeX formatting rules
- Extraction workflow with LLM prompts
- Post-extraction checklist
- Common patterns and examples

**`examples/`**
- `simple_no_math.json` - Questions without mathematical content
- `complex_with_katex.json` - Questions with formulas and Greek letters

## Extraction Workflow

1. **Check for Updates**
   ```bash
   uv run lzradio-check-updates
   ```

2. **Extract Questions**
   - Use LLM to extract from PDF
   - Follow format in `template.json`
   - Apply KaTeX rules from `CLAUDE.md`
   - Save to `extracted_json/`

3. **Validate**
   ```bash
   uv run lzradio-validate extracted_json/YourFile.json
   ```

4. **Fix Issues**
   - Review warnings
   - Fix KaTeX formatting
   - Re-validate

5. **Manual Steps** (after validation passes)
   - Extract and place question images (if any) in application repo
   - Copy validated JSON to application data directory
   - Test in the application

## KaTeX Formatting Rules

Mathematical notation must use KaTeX for proper rendering:

**Greek Letters (REQUIRED):**
- ❌ Plain: `λ`, `τ`, `α`, `β`
- ✅ KaTeX: `$\lambda$`, `$\tau$`, `$\alpha$`, `$\beta$`

**Fractions (OPTIONAL):**
- ✅ Plain text: `1/30`, `5/8` (acceptable for simple fractions)
- ✅ KaTeX: `$\dfrac{1}{30}$`, `$\dfrac{5}{8}$` (for professional rendering)

**Units (KEEP PLAIN):**
- ✅ Correct: `µF`, `MHz`, `kΩ` (plain text for unit abbreviations)
- ❌ Wrong: `$\mu$F` (don't wrap units in KaTeX)

See `CLAUDE.md` for complete formatting rules and examples.

## Image-Based Questions

Some questions show answer choices as diagrams, circuits, or symbols in images:

```json
{
    "question_number": 45,
    "question_body": "С кой от символите се представя резистор?",
    "image": "Class2_Section1_45.png",
    "correct_answer": "В",
    "choices": [
        {"key": "А", "text": ""},
        {"key": "Б", "text": ""},
        {"key": "В", "text": ""},
        {"key": "Г", "text": ""}
    ]
}
```

The validator accepts empty choice text when an `image` field is present.

## Development

```bash
uv sync                 # create .venv with dev tools (pytest, ruff)
uv run pytest           # run tests
uv run ruff check       # lint
uv run ruff format      # format
```

CI runs the same checks on every push and pull request (`.github/workflows/tests.yml`).

## Contributing

This is a manual extraction workflow with human-in-the-loop validation. The process is:

1. Check for PDF updates
2. Extract with LLM assistance
3. Validate and fix
4. Manually transfer to application

## License

The code and documentation in this repository are licensed under the [MIT License](LICENSE).

The PDF files in `source_pdfs/` are official documents published by the Bulgarian Communications Regulation Commission (CRC / КРС) at [crc.bg](https://crc.bg/bg/rubriki/143/testove-za-provejdane-na-izpiti-za-pravosposobnost-na-radiolubiteli). They are included unmodified for reference and are not covered by the MIT License.

