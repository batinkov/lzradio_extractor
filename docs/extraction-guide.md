# Extraction Guide

How to extract the questions from the CRC PDFs in `source_pdfs/` into JSON for [LZ Radio](https://github.com/batinkov/lzradio). It is written for both humans and the LLM doing the extraction: give the LLM this file together with the PDF.

The process has two LLM passes:

1. [**Pass 1: Extract**](#pass-1-extract) every question by the rules below, then [validate](#validate).
2. [**Pass 2: Check for PDF quirks**](#pass-2-check-for-pdf-quirks): compare the JSON with the PDF and fix the known exceptions, then validate again.
3. [**Human check**](#human-check) and [**transfer to LZ Radio**](#transfer-to-lz-radio).

## Source PDFs

| File | Class | Section |
|------|-------|---------|
| `class_1_razdel_1.pdf` | 1 | 1 – Електротехника и радиотехника |
| `class_1_razdel_2.pdf` | 1 | 2 – Кодове и радиолюбителски съкращения |
| `class_1_razdel_3.pdf` | 1 | 3 – Нормативна уредба |
| `class_2_razdel_1.pdf` | 2 | 1 – Електротехника и радиотехника |
| `class_2_razdel_2.pdf` | 2 | 2 – Кодове и радиолюбителски съкращения |
| `class_2_razdel_3.pdf` | 2 | 3 – Нормативна уредба |

Each PDF becomes one JSON file named `Class<X>_Section<Y>.json`.

## JSON Format

See `template.json` for the skeleton and `examples/` for real questions:
- `examples/simple_no_math.json` – plain text questions
- `examples/complex_with_katex.json` – Greek letters, fractions and formulas

```json
{
    "class": "Радиолюбителски клас 2",
    "section": "Раздел 1 – Електротехника и радиотехника",
    "update": "Актуализиран конспект 11.08.2025 г.",
    "questions": [
        {
            "question_number": 1,
            "question_body": "Текст на въпроса",
            "correct_answer": "Б",
            "choices": [
                {"key": "А", "text": "Първи отговор"},
                {"key": "Б", "text": "Втори отговор"},
                {"key": "В", "text": "Трети отговор"},
                {"key": "Г", "text": "Четвърти отговор"}
            ]
        }
    ]
}
```

- `class`, `section` and `update` are copied from the PDF heading.
- `question_number` is the number printed in the PDF. Never renumber: the PDFs have gaps (e.g. Class 1 Section 3 has no question 31), and the numbers must match the official PDF.
- Choice keys are the Cyrillic letters А, Б, В, Г, in that order. `correct_answer` is one of them.

### Reading the PDFs

In the PDF, each question ends with its correct answer in parentheses:

```
1. На колко мегахерца (MHz) са равни 144432 килохерца (kHz)? (Б)
 А. На 0,144432 MHz;
 Б. На 144,432 MHz;
 В.  На  144432000  MHz;
 Г. На 0,000144432 MHz.
```

becomes

```json
{
    "question_number": 1,
    "question_body": "На колко мегахерца (MHz) са равни 144432 килохерца (kHz)?",
    "correct_answer": "Б",
    "choices": [
        {"key": "А", "text": "На 0,144432 MHz"},
        {"key": "Б", "text": "На 144,432 MHz"},
        {"key": "В", "text": "На 144432000 MHz"},
        {"key": "Г", "text": "На 0,000144432 MHz"}
    ]
}
```

- The answer marker `(Б)` moves to `correct_answer` and is removed from the question text.
- The choice labels (`А.`) and the trailing `;` or `.` are dropped.
- Repeated spaces are collapsed into one.

### Image-based questions

Some questions show the answer choices as diagrams, circuits or symbols. For these:
- add an `"image"` field named `Class<X>_Section<Y>_<question number>.png`
- set all choice `"text"` fields to `""`

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

## KaTeX Formatting Rules

LZ Radio renders text between `$...$` with [KaTeX](https://katex.org/docs/supported.html). In JSON, backslashes are escaped: `$\lambda$` is written `"$\\lambda$"`.

### Greek letters – always KaTeX

- ✅ `$\lambda$`, `$\tau$`, `$\alpha$`, `$\beta$`, `$\gamma$`, `$\delta$`
- ❌ plain `λ`, `τ`, `α`, `β`

```json
"question_body": "антена с дължина 5/8 $\\lambda$ вместо четвъртвълнова"
"question_body": "параметърът $\\beta$ (бета) на биполярния транзистор"
"text": "Алфа ($\\alpha$)"
```

### Fractions – plain text or `\dfrac`

Simple numeric fractions may stay as plain text. If you use KaTeX, use `\dfrac`, not `\frac` (it renders too small).

- ✅ `1/30 ома`, `5/8 $\lambda$`
- ✅ `$\dfrac{1}{30}$ ома`, `$\dfrac{5}{8}\lambda$`
- ❌ `$\frac{1}{30}$`

### Formulas – KaTeX with `\dfrac`

- ✅ `$\tau = RC$`, `$Q = \dfrac{R}{X}$`, `$f = \dfrac{1}{2\pi\sqrt{LC}}$`
- ❌ `$\tau = R/C$`, plain `R/C`

### Units – plain text

Unit abbreviations stay plain, including those with µ and Ω:

- ✅ `µF`, `µH`, `MHz`, `kHz`, `kΩ`, `mA`, `mV`, `pF`, `nF`
- ❌ `$\mu$F`
- ✅ unit expressions such as `m/s` or `1/секунда` stay plain, too

µ as a variable in a formula (e.g. relative permeability) is KaTeX: `$\mu_r = 1$`.

## Pass 1: Extract

Two rules cannot be fixed later and apply already here:
- **Read the rendered pages, not the PDF's text layer.** The PDFs draw Greek letters and µ with a symbol font that is missing from copied or extracted text.
- **Keep the question numbers from the PDF**, including gaps.

Prompt:

```
Extract all questions from the attached Bulgarian amateur radio exam PDF
into JSON. Follow docs/extraction-guide.md and template.json exactly.

Reading the PDF:
- Read the rendered pages, not the text layer: Greek letters and µ are
  missing from the PDF's text.
- The heading gives "class", "section" and "update"; copy them verbatim.
- Each question ends with the correct answer in parentheses, e.g. "(Б)".
  Put that letter in "correct_answer" and remove it from "question_body".
- Choices are labelled А., Б., В., Г. Drop the label and the trailing
  ";" or "." from each choice text. Collapse repeated spaces.
- Use the question numbers printed in the PDF. Never renumber, even if
  a number is missing.

Content:
- Keep the original Bulgarian wording; do not fix, translate or rephrase it.
- Apply the KaTeX rules from the guide: Greek letters always in KaTeX,
  units (µF, MHz, kΩ) as plain text, formulas with \dfrac.
- If the choices are shown as a picture, add the "image" field and leave
  the choice texts empty.
- Never guess. If something is unreadable, keep your best reading and
  list it in the report below.

Output:
- Extract every question. If the output is too long, continue in further
  replies until done; never summarize or skip questions.
- Save the JSON to extracted_json/Class<X>_Section<Y>.json. No comments
  or markdown in the file.
- Afterwards, report: the number of questions, the first and last
  question number, any missing numbers, the image-based question
  numbers, and anything you were unsure about.
```

## Validate

```bash
uv run lzradio-validate extracted_json/Class2_Section1.json
```

Errors (exit code 1) must be fixed. Warnings point to likely formatting problems, such as a plain Greek letter or a formula written with `/`. Fix them, or leave them if they are deliberate, and re-run until the result is clean.

```
⚠ WARNINGS (2):
  ⚠ Question 5 body: Found plain Unicode Greek letter 'λ'. Use KaTeX: $\lambda$
  ⚠ Question 12, Choice 3: Found formula division 'R/C'. Use KaTeX: $\dfrac{R}{C}$
```

A warning about missing question numbers is expected when the PDF itself has a gap. Check that the PDF really skips that number.

## Pass 2: Check for PDF quirks

The CRC PDFs have known irregularities that a first pass easily gets wrong. Give the LLM the PDF and the JSON from pass 1 and let it check every question for these:

| Quirk | In the PDF | In the JSON |
|-------|-----------|-------------|
| Symbol font | `параметърът  (бета)`, `Алфа ()`, `лентата на пропускане f`, `дължина 1/4;` – Greek letters and µ missing from the text | Use the letter from the page image, in KaTeX: `$\beta$`, `$\Delta f$`, `1/4 $\lambda$`; µ in units as plain `µ` |
| Latin look-alike letters | `(A)`, `(B)`, `B. SSB;` – Latin A/B instead of Cyrillic А/В | Always Cyrillic А, Б, В, Г in `key` and `correct_answer` |
| Parentheses that are not the answer | `разграфен в ампери (А), тече ток …` – here `(А)` is the ampere unit | Only the parenthesis at the very end of the question is the answer; keep the others in the text |
| Numbering gaps | Class 1 Section 3: … 30, 32 … | Keep the gap; never renumber |
| Degree sign | `90о` – Cyrillic letter о | `90°` |
| Subscripts | `fp`, `Q/fp` in formulas | `$f_p$`, `$\dfrac{Q}{f_p}$` |
| Quotes | `„…“` or `“…”` | Keep the quotes exactly as in the PDF; do not replace them with `"` or `'` |

Prompt:

```
Attached are a Bulgarian amateur radio exam PDF and the JSON extracted
from it. Compare every question in the JSON with the rendered PDF page
and fix the PDF quirks listed in docs/extraction-guide.md under
"Pass 2: Check for PDF quirks". Change nothing else.

Report every change as: question number, field, old value, new value.
```

Validate again after pass 2.

## Human check

The validator checks the format, not the content. It cannot tell whether a question was transcribed correctly or the right answer was picked. Before transferring, compare against the PDF:
- the question count and missing numbers reported in pass 1
- the changes reported in pass 2
- the `correct_answer` of a sample of questions (e.g. every tenth)
- every question the LLM reported as uncertain

## Transfer to LZ Radio

All paths are in the [LZ Radio](https://github.com/batinkov/lzradio) repository.

- [ ] Copy the JSON to `data_bg/exam/Class<X>_Section<Y>.json`.
- [ ] Create the images of image-based questions and put them in `public/images/questions/bg/`, named exactly as in the JSON. The symbols in the PDFs are vector drawings, so they cannot be extracted as image files: render the page and crop it, e.g. `pdftoppm -png -r 300 -f 7 -l 7 source_pdfs/class_2_razdel_1.pdf page`.
- [ ] Update the English translation in `data_en/exam/` (and `public/images/questions/en/` if needed) for every changed question.
- [ ] Run the app (`npm run dev`) and check the changed sections: text, formulas, images and correct answers.
