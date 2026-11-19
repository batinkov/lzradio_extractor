# Extraction Guide for LLMs

**This file is specifically designed for LLMs (Large Language Models) assisting with question extraction from PDF files.**

If you're a human user, see `README.md` for a general overview. This document contains detailed formatting rules, extraction workflows, and examples optimized for AI assistants like Claude.

---

# Source PDF Files

The `source_pdfs/` directory contains the official PDF files from CRC (Communications Regulation Commission) for Bulgarian amateur radio license exam questions.

## PDF Files

- `source_pdfs/class_1_razdel_1.pdf` - Class 1, Section 1: Електротехника и радиотехника
- `source_pdfs/class_1_razdel_2.pdf` - Class 1, Section 2: Кодове и радиолюбителски съкращения
- `source_pdfs/class_1_razdel_3.pdf` - Class 1, Section 3: Нормативна уредба
- `source_pdfs/class_2_razdel_1.pdf` - Class 2, Section 1: Електротехника и радиотехника
- `source_pdfs/class_2_razdel_2.pdf` - Class 2, Section 2: Кодове и радиолюбителски съкращения
- `source_pdfs/class_2_razdel_3.pdf` - Class 2, Section 3: Нормативна уредба

## Directory Structure

```
lzradio_extractor/
├── source_pdfs/              # Original PDF files from CRC
│   ├── class_1_razdel_1.pdf
│   ├── class_1_razdel_2.pdf
│   └── ...
├── extracted_json/           # Your extracted JSON files (temporary working directory)
├── downloads/                # Downloaded PDFs for update checks (gitignored)
├── examples/                 # Reference examples
│   ├── simple_no_math.json   # Questions without mathematical content
│   └── complex_with_katex.json  # Questions with KaTeX formatting
├── template.json             # Minimal JSON structure template
├── src/lzradio_extractor/
│   ├── validate.py           # JSON validator (lzradio-validate)
│   └── check_updates.py      # CRC update checker (lzradio-check-updates)
├── tests/                    # pytest tests
├── pyproject.toml            # Project metadata, dev dependencies, tool config
├── uv.lock                   # Locked dev dependencies
└── CLAUDE.md                 # This file - formatting rules and workflow
```

## Checking for Updates

Before extracting questions, you can check if the CRC has published updated versions of the PDF files:

```bash
uv run lzradio-check-updates
```

This script will:
1. Open the CRC exam page (https://crc.bg/bg/rubriki/143/...) and follow the links to the Class 1 and Class 2 pages
2. Identify each PDF by its link text ("Раздел N"), not by filename - CRC renames the files
3. Download all 6 PDFs to `downloads/`, saved as `class_X_razdel_Y.pdf`
4. Compare SHA256 hashes with your local files in `source_pdfs/`
5. Report which files are up to date and which have been updated

Exit codes: `0` up to date, `1` update available, `2` check failed (network error or site layout changed).

**Example output when files match:**
```
✅ ALL FILES UP TO DATE
   All 6 files match the CRC website
```

**Example output when updates are available:**
```
⚠️  UPDATES AVAILABLE
  • class_2_razdel_3.pdf (changed)
```

If updates are detected, manually review the changes in `downloads/` and decide whether to copy them to `source_pdfs/` and re-extract the questions.

## Extraction Workflow

### Step 1: Understand the Structure

Before extracting questions, review the JSON structure in `template.json`. This file shows:
- Required top-level fields: `class`, `section`, `update`, `questions`
- Question structure with 4 multiple-choice answers
- Image-based questions (where choices are shown in an image, not as text)

See `examples/` directory for complete working examples:
- `simple_no_math.json` - Simple questions without mathematical symbols
- `complex_with_katex.json` - Questions with Greek letters, fractions, and formulas

### Step 2: Extract Questions from PDF

**Using an LLM (like Claude) for extraction:**

When using an LLM to extract questions from PDFs, provide clear instructions. Here's a recommended prompt template:

```
I need you to extract questions from this Bulgarian amateur radio exam PDF.

Requirements:
1. Follow the JSON structure in template.json exactly
2. Extract ALL questions with their 4 answer choices (А, Б, В, Г)
3. Apply KaTeX formatting rules:
   - Greek letters (λ, τ, α, β, γ, δ) MUST use KaTeX: $\lambda$, $\tau$, etc.
   - Simple fractions (1/30, 5/8) can stay as plain text OR use KaTeX $\dfrac{1}{30}$
   - Unit abbreviations (µF, MHz, kΩ) stay as plain text
   - Formulas should use KaTeX for professional rendering
4. For questions with diagrams/symbols as answers, add an "image" field and leave choice text empty

Output format:
{
    "class": "Радиолюбителски клас X",
    "section": "Раздел Y – [section name]",
    "update": "Актуализиран конспект [date from PDF]",
    "questions": [...]
}

Save the output to: extracted_json/Class[X]_Section[Y].json
```

**Manual extraction steps:**

1. Open the PDF file from `source_pdfs/`
2. Extract each question with its 4 answer choices
3. Note which answer is correct (А, Б, В, or Г)
4. Follow the KaTeX formatting rules below for mathematical content
5. Save extracted questions to `extracted_json/`

**Image-based Questions:**
Some questions show answer choices as diagrams, circuits, or symbols in an image. For these:
- Add an `"image"` field with the image filename
- Set all choice `"text"` fields to empty strings `""`
- The validator will accept empty text when an image field is present

Example:
```json
{
    "question_number": 45,
    "question_body": "С кой от символите се представя резистор (съпротивление)?",
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

### Step 3: Validate the JSON File

After creating or modifying a JSON file, run the validation script:

```bash
uv run lzradio-validate your_file.json
```

The validator checks:
- ✅ **Structure**: Valid JSON, required fields, correct data types
- ✅ **Content**: Sequential question numbers, valid choice keys, correct answers
- ⚠️ **KaTeX**: Greek letters, fractions, formulas use proper syntax
- ⚠️ **Units**: Unit abbreviations (µF, MHz) stay as plain text
- 📊 **Statistics**: Question counts, math content usage

**Exit codes:**
- `0` - Validation passed (no errors)
- `1` - Validation failed (errors found)

**Example output:**
```
Validating: Class2_Section1.json
======================================================================

⚠ WARNINGS (2):
  ⚠ Question 5 body: Found plain Unicode Greek letter 'λ'. Use KaTeX: $\lambda$
  ⚠ Question 12, Choice 3: Found formula division 'R/C'. Use KaTeX: $\dfrac{R}{C}$

ℹ INFO:
  ℹ ✓ Valid JSON syntax

📊 STATISTICS:
  Total questions: 150
  Questions with math content: 45
  Questions with KaTeX: 43
  Plain Greek letters found: 1

⚠️  VALIDATION PASSED WITH WARNINGS
   2 warning(s)
```

### Step 4: Fix Issues

If the validator reports warnings or errors:
1. Review the message and location (question number, choice number)
2. Apply the KaTeX formatting rules below
3. Re-run the validator
4. Repeat until validation passes

### Step 5: Post-Extraction Manual Steps

After validation passes, complete these manual steps:

**Checklist:**

- [ ] **Extract question images** (if any)
  - Questions with `"image"` field reference image files
  - Extract diagrams/circuits/symbols from PDF
  - Save as PNG files with exact filenames from JSON
  - Place in: `../lzradio/public/images/questions/bg/`
  - Example: `Class2_Section1_45.png`

- [ ] **Copy JSON to application**
  - Copy validated JSON file to: `../lzradio/data_bg/`
  - Use the naming convention: `Class[X]_Section[Y].json`
  - Example: `Class1_Section1.json`

- [ ] **Test in application**
  - Start dev server: `npm run dev` (in ../lzradio/)
  - Navigate to the specific exam section
  - Verify mathematical notation renders correctly (Greek letters, fractions)
  - Check question text and answers display properly
  - Test image-based questions (if any)
  - Verify correct answers are marked properly

- [ ] **Clean up**
  - Extracted JSON can be removed from `extracted_json/` after successful transfer
  - Or keep for reference if needed

**Note:** All these steps are manual and require human verification. The extraction process is not fully automated.

## Exporting Questions from PDFs

When exporting questions from these PDF files to JSON format for use in the application, follow these guidelines:

### KaTeX Formatting Rules

**IMPORTANT: Always use KaTeX syntax for mathematical notation, formulas, and Greek letters.**

#### 1. Greek Letters
Use KaTeX syntax, NOT plain Unicode characters:

- ✅ Correct: `$\lambda$` for λ (lambda - wavelength)
- ✅ Correct: `$\tau$` for τ (tau - time constant)
- ✅ Correct: `$\alpha$`, `$\beta$`, `$\gamma$`, `$\delta$`
- ❌ Wrong: Plain Unicode `λ`, `τ`, etc.

#### 2. Fractions

**Simple numeric fractions (like 1/2, 1/3, 5/8, 1/30) are acceptable as plain text.**

However, for complex formulas or when you want professional mathematical typesetting, use `\dfrac` (display-style):

- ✅ Acceptable: `1/30` - plain text for simple fractions
- ✅ Acceptable: `5/8` - plain text for simple fractions
- ✅ Also correct: `$\dfrac{1}{30}$` - KaTeX for professional rendering
- ✅ Also correct: `$\dfrac{5}{8}$` - KaTeX for professional rendering
- ❌ Wrong: `$\frac{1}{30}$` - if using KaTeX, use `\dfrac` not `\frac`

#### 3. Common Patterns

**Wavelength (dължина на вълната):**
```json
"question_body": "антена с дължина 5/8 λ"                    // Plain text OK
"question_body": "антена с дължина $\\dfrac{5}{8}\\lambda$"  // Or use KaTeX
```

**Time constant (времеконстанта):**
```json
"question_body": "времеконстантата $\\tau$ на една RC група"
"text": "$\\tau = RC$"
```

**Ohm values (съпротивление):**
```json
"text": "1/30 ома"              // Simple fraction - plain text OK
"text": "$\\dfrac{1}{30}$ ома"  // Or use KaTeX for professional rendering
"text": "30 ома"
```

**Formulas (формули):**
```json
"text": "$f = \\dfrac{1}{2\\pi\\sqrt{LC}}$"
"text": "$Q = \\dfrac{R}{X}$"
```

**Transistor parameters:**
```json
"question_body": "параметърът $\\beta$ (бета) на биполярния транзистор"
"text": "Алфа ($\\alpha$)"
"text": "Бета ($\\beta$)"
```

#### 4. Formulas with Division

**Convert formula fractions to `\dfrac`:**

When formulas contain division with "/", convert to proper fraction notation:

- ✅ Correct: `$\tau = \dfrac{R}{C}$` (formula showing relationship)
- ✅ Correct: `$Q = \dfrac{R}{X}$` (quality factor formula)
- ✅ Correct: `$f = \dfrac{1}{2\pi\sqrt{LC}}$` (resonant frequency)
- ❌ Wrong: `$\tau = R/C$` (slash notation in formulas)

**Keep unit expressions as plain text:**

When "/" appears in unit designations (reciprocal units), keep as plain text:

- ✅ Correct: `"1/секунда"` or `"1/second"` (frequency unit, equivalent to Hertz)
- ✅ Correct: `"m/s"` (meters per second)
- ❌ Wrong: `"$\dfrac{1}{\text{секунда}}$"` (unnecessary formatting for unit labels)
- **Reason**: These are unit labels/descriptions, not mathematical operations to evaluate

#### 5. When NOT to Use KaTeX

**Unit abbreviations with µ (micro) - Keep as plain text:**

- ✅ Correct: `µF`, `µH`, `µV`, `µA` - standard unit abbreviations
- ❌ Wrong: `$\mu$F` - unnecessary for simple units
- **Reason**: Unit abbreviations should remain plain text for consistency with other units (MHz, kHz, mA, mV, nF, pF, etc.)

**Other units - Keep as plain text:**
- Frequency: `MHz`, `kHz`, `GHz`, `Hz`
- Resistance: `kΩ`, `MΩ`, `Ω` (Omega in units is acceptable as Unicode)
- Current: `mA`, `µA`, `A`
- Voltage: `mV`, `µV`, `V`
- Capacitance: `pF`, `nF`, `µF`, `F`
- Inductance: `µH`, `mH`, `H`

**Exception - When µ appears in formulas or as a variable:**
```json
// If µ represents permeability or another variable in a formula, use KaTeX:
"text": "$\\mu_r = 1$" (relative permeability)
```

#### 6. Example Transformations

**Before (incorrect - plain Unicode Greek letter):**
```json
{
  "question_body": "антена с дължина 5/8 λ вместо четвъртвълнова"
}
```

**After (correct - KaTeX for Greek letters):**
```json
{
  "question_body": "антена с дължина 5/8 $\\lambda$ вместо четвъртвълнова"
}
```

**Note:** Simple fractions like `5/8` can remain as plain text. Greek letters like `λ` must use KaTeX.

### Why This Matters

1. **Consistency**: All mathematical notation renders uniformly across browsers
2. **Professional**: Proper mathematical typesetting improves readability
3. **Scalable**: Complex formulas with square roots, exponents, etc. are supported
4. **Future-proof**: New formulas can be added using standard LaTeX notation
5. **Accessibility**: Screen readers handle KaTeX-rendered math better

### Workflow

When exporting from PDF:

1. Extract question text and answers
2. Identify mathematical content that should use KaTeX:
   - Greek letters (λ, τ, α, β, γ, δ, etc.) - **always use KaTeX**
   - Simple numeric fractions (1/30, 5/8, etc.) - **plain text is acceptable**
   - Formulas with division (R/C, Q/fp, etc.) - **use KaTeX for professional rendering**
   - Unit expressions (1/second, m/s, etc.) - **keep as plain text**
3. Apply KaTeX formatting where needed:
   - **Required:** Greek letters must use KaTeX (`$\lambda$`, `$\tau$`)
   - **Optional:** Simple fractions can be plain text (1/30) or KaTeX (`$\dfrac{1}{30}$`)
   - **Recommended:** Complex formulas should use KaTeX for clarity
4. If using KaTeX for fractions, use `\dfrac` (not `\frac`) for proper display size
5. Keep unit designations as plain text (don't wrap in KaTeX)
6. Test rendering in the application at http://localhost:5173

### Current Status

**Bulgarian Files (data_bg/):**
- Class 1, Section 1: ✅ Updated with KaTeX (τ and formulas)
- Class 1, Section 2: ✅ No math content
- Class 1, Section 3: ✅ No math content
- Class 2, Section 1: ✅ Updated with KaTeX (λ and fractions)
- Class 2, Section 2: ✅ No math content
- Class 2, Section 3: ✅ No math content

**English Files (data_en/):**
- Class 1, Section 1: ✅ Fully uses KaTeX
- Class 1, Section 2: ✅ No math content
- Class 1, Section 3: ✅ No math content
- Class 2, Section 1: ✅ Updated with KaTeX (λ and fractions)
- Class 2, Section 2: ✅ No math content
- Class 2, Section 3: ✅ No math content

### Testing

After exporting/updating questions:

1. Start dev server: `npm run dev` (in ../lzradio/)
2. Navigate to exam sections with math content
3. Verify fractions render at proper size
4. Verify Greek letters render correctly
5. Check both Bulgarian and English versions

### Reference

- KaTeX documentation: https://katex.org/docs/supported.html
- KaTeX rendering code: `../lzradio/src/lib/katex.js`
- Question display component: `../lzradio/src/components/exam/QuestionDisplay.svelte`
