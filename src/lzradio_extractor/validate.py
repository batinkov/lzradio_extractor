#!/usr/bin/env python3
"""
JSON Question File Validator for Bulgarian Amateur Radio Exam Questions

Validates structure, content, and KaTeX formatting of question JSON files.

Usage:
    lzradio-validate <json_file> [json_file ...]

Exit codes:
    0  no errors (warnings are allowed)
    1  at least one file has errors
"""

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def _use_color() -> bool:
    return sys.stdout.isatty() and "NO_COLOR" not in os.environ


class Colors:
    """ANSI color codes; empty when output is not a terminal or NO_COLOR is set."""

    _on = _use_color()
    RED = '\033[91m' if _on else ''
    YELLOW = '\033[93m' if _on else ''
    GREEN = '\033[92m' if _on else ''
    CYAN = '\033[96m' if _on else ''
    BOLD = '\033[1m' if _on else ''
    RESET = '\033[0m' if _on else ''


class ValidationResult:
    """Stores validation results"""

    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.info: list[str] = []

    def add_error(self, msg: str):
        self.errors.append(msg)

    def add_warning(self, msg: str):
        self.warnings.append(msg)

    def add_info(self, msg: str):
        self.info.append(msg)

    def has_errors(self) -> bool:
        return len(self.errors) > 0


class QuestionValidator:
    """Validates question JSON files"""

    # Greek letters that must use KaTeX, with their LaTeX command names.
    # 'µ' (U+00B5 MICRO SIGN) and 'μ' (U+03BC GREEK SMALL LETTER MU) look the
    # same; both are allowed as a unit prefix (µF, µH, ...), nowhere else.
    GREEK_LETTERS = {
        'α': 'alpha',
        'β': 'beta',
        'γ': 'gamma',
        'δ': 'delta',
        'Δ': 'Delta',
        'ε': 'epsilon',
        'η': 'eta',
        'θ': 'theta',
        'λ': 'lambda',
        'μ': 'mu',
        'µ': 'mu',
        'π': 'pi',
        'ρ': 'rho',
        'σ': 'sigma',
        'τ': 'tau',
        'φ': 'phi',
        'ω': 'omega',
    }
    MICRO = ('µ', 'μ')
    # Ω is acceptable as Unicode (it is used in units: kΩ, MΩ)

    # Formula division like R/C, U/I, Q/fp (outside KaTeX). Uppercase
    # abbreviations such as AM/FM or TX/RX do not match.
    FORMULA_DIVISION = re.compile(r'\b([A-Za-z][a-z0-9]{0,2})/([A-Za-z][a-z0-9]{0,2})\b')
    # Unit denominators that make "x/y" a unit, not a formula (m/s, km/h)
    UNIT_DENOMINATORS = {'s', 'h', 'm', 'km', 'min', 'sec'}

    # LaTeX commands that must be written with a backslash inside $...$
    LATEX_COMMANDS = [
        'lambda',
        'tau',
        'alpha',
        'beta',
        'gamma',
        'delta',
        'dfrac',
        'frac',
        'sqrt',
        'pi',
    ]

    IMAGE_NAME = re.compile(r'^Class[12]_Section[123]_(\d+)\.png$')

    # Valid choice keys
    CYRILLIC_KEYS = ['А', 'Б', 'В', 'Г']
    LATIN_KEYS = ['A', 'B', 'C', 'D']

    TOP_LEVEL_FIELDS = {'class', 'section', 'update', 'questions'}
    QUESTION_REQUIRED = {'question_number', 'question_body', 'correct_answer', 'choices'}
    QUESTION_OPTIONAL = {'image'}
    CHOICE_FIELDS = {'key', 'text'}

    def __init__(self, filepath: str | None = None, data: Any = None):
        self.filepath = Path(filepath) if filepath else None
        self.data = data
        self.result = ValidationResult()
        self.stats = {
            'total_questions': 0,
            'questions_with_math': 0,
            'questions_with_katex': 0,
            'questions_with_images': 0,
            'greek_letters_found': 0,
        }

    @property
    def name(self) -> str:
        return self.filepath.name if self.filepath else '<data>'

    def validate(self) -> ValidationResult:
        """Run all validations"""
        if self.filepath is not None and not self._load_json():
            return self.result

        if not self._validate_top_level():
            return self.result

        valid_questions = []
        for idx, question in enumerate(self.data['questions'], 1):
            if self._validate_question_structure(question, idx):
                valid_questions.append((idx, question))

        if valid_questions:
            expected_keys = self._detect_keys(valid_questions)
            for idx, question in valid_questions:
                self._validate_question_content(question, idx, expected_keys)
                self._validate_question_katex(question, idx)
            self._validate_numbering(valid_questions)

        return self.result

    # ------------------------------------------------------------------
    # Structure

    def _load_json(self) -> bool:
        try:
            with open(self.filepath, encoding='utf-8') as f:
                self.data = json.load(f)
            self.result.add_info("✓ Valid JSON syntax")
            return True
        except FileNotFoundError:
            self.result.add_error(f"File not found: {self.filepath}")
        except UnicodeDecodeError as e:
            self.result.add_error(f"File is not valid UTF-8: {e}")
        except json.JSONDecodeError as e:
            self.result.add_error(f"Invalid JSON syntax: {e}")
        return False

    def _validate_top_level(self) -> bool:
        if not isinstance(self.data, dict):
            self.result.add_error("Top level must be a JSON object")
            return False

        for field in ('class', 'section', 'update'):
            if field not in self.data:
                self.result.add_error(f"Missing required field: '{field}'")
            elif not isinstance(self.data[field], str) or not self.data[field].strip():
                self.result.add_error(f"Field '{field}' must be a non-empty string")

        for field in sorted(set(self.data) - self.TOP_LEVEL_FIELDS):
            self.result.add_warning(f"Unknown top-level field: '{field}'")

        if 'questions' not in self.data:
            self.result.add_error("Missing required field: 'questions'")
            return False
        if not isinstance(self.data['questions'], list):
            self.result.add_error("'questions' must be an array")
            return False
        if not self.data['questions']:
            self.result.add_error("'questions' is empty")
            return False

        self.stats['total_questions'] = len(self.data['questions'])
        return True

    def _validate_question_structure(self, question: Any, idx: int) -> bool:
        """Check fields and types of one question. Returns True if usable."""
        loc = f"Question {idx}"
        if not isinstance(question, dict):
            self.result.add_error(f"{loc}: Must be an object")
            return False

        ok = True
        for field in sorted(self.QUESTION_REQUIRED - set(question)):
            self.result.add_error(f"{loc}: Missing field '{field}'")
            ok = False
        for field in sorted(set(question) - self.QUESTION_REQUIRED - self.QUESTION_OPTIONAL):
            self.result.add_warning(f"{loc}: Unknown field '{field}'")

        num = question.get('question_number')
        if 'question_number' in question and (not isinstance(num, int) or isinstance(num, bool)):
            self.result.add_error(f"{loc}: 'question_number' must be an integer, got {num!r}")
            ok = False

        for field in ('question_body', 'correct_answer'):
            if field in question and not isinstance(question[field], str):
                self.result.add_error(f"{loc}: '{field}' must be a string, got {question[field]!r}")
                ok = False

        image = question.get('image')
        if 'image' in question and (not isinstance(image, str) or not image.strip()):
            self.result.add_error(f"{loc}: 'image' must be a non-empty string")
            ok = False

        choices = question.get('choices')
        if 'choices' in question:
            if not isinstance(choices, list):
                self.result.add_error(f"{loc}: 'choices' must be an array")
                ok = False
            elif len(choices) != 4:
                self.result.add_error(f"{loc}: Must have exactly 4 choices, found {len(choices)}")
                ok = False
            else:
                for c_idx, choice in enumerate(choices, 1):
                    c_loc = f"{loc}, Choice {c_idx}"
                    if not isinstance(choice, dict):
                        self.result.add_error(f"{c_loc}: Must be an object")
                        ok = False
                        continue
                    for field in sorted(self.CHOICE_FIELDS - set(choice)):
                        self.result.add_error(f"{c_loc}: Missing '{field}'")
                        ok = False
                    for field in sorted(set(choice) - self.CHOICE_FIELDS):
                        self.result.add_warning(f"{c_loc}: Unknown field '{field}'")
                    for field in self.CHOICE_FIELDS & set(choice):
                        if not isinstance(choice[field], str):
                            self.result.add_error(
                                f"{c_loc}: '{field}' must be a string, got {choice[field]!r}"
                            )
                            ok = False
        return ok

    # ------------------------------------------------------------------
    # Content

    def _detect_keys(self, questions) -> list[str]:
        """Use Latin keys only if the first question uses them; Cyrillic otherwise."""
        first_key = questions[0][1]['choices'][0]['key']
        return self.LATIN_KEYS if first_key in self.LATIN_KEYS else self.CYRILLIC_KEYS

    def _validate_question_content(self, question: dict, idx: int, expected_keys: list[str]):
        loc = f"Question {idx}"
        has_image = 'image' in question
        if has_image:
            self.stats['questions_with_images'] += 1
            self._validate_image_name(question, loc)

        if not question['question_body'].strip():
            self.result.add_error(f"{loc}: Empty question_body")
        elif len(question['question_body']) > 500:
            self.result.add_warning(
                f"{loc}: Very long question body ({len(question['question_body'])} chars)"
            )

        keys = [c['key'] for c in question['choices']]
        for c_idx, choice in enumerate(question['choices'], 1):
            if choice['key'] not in expected_keys:
                self.result.add_error(
                    f"{loc}, Choice {c_idx}: Invalid key '{choice['key']}'. "
                    f"Expected one of: {expected_keys}"
                )
            if not choice['text'].strip() and not has_image:
                self.result.add_error(f"{loc}, Choice {c_idx}: Empty text")

        duplicates = [k for k, n in Counter(keys).items() if n > 1]
        if duplicates:
            self.result.add_error(f"{loc}: Duplicate choice keys: {duplicates}")
        elif keys != expected_keys and set(keys) == set(expected_keys):
            self.result.add_warning(f"{loc}: Choice keys out of order: {keys}")

        correct = question['correct_answer']
        if not correct.strip():
            self.result.add_error(f"{loc}: Empty correct_answer")
        elif correct not in expected_keys:
            self.result.add_error(
                f"{loc}: Invalid correct_answer '{correct}'. Expected one of: {expected_keys}"
            )
        elif correct not in keys:
            self.result.add_error(
                f"{loc}: correct_answer '{correct}' not found in choice keys: {keys}"
            )

    def _validate_image_name(self, question: dict, loc: str):
        image = question['image']
        m = self.IMAGE_NAME.match(image)
        if not m:
            self.result.add_warning(
                f"{loc}: Image name '{image}' does not match 'Class<X>_Section<Y>_<N>.png'"
            )
        elif int(m.group(1)) != question['question_number']:
            self.result.add_warning(
                f"{loc}: Image '{image}' does not match question_number "
                f"{question['question_number']}"
            )

    def _validate_numbering(self, questions):
        numbers = [q['question_number'] for _, q in questions]
        expected = list(range(1, len(numbers) + 1))
        if numbers == expected:
            return
        duplicates = sorted(n for n, c in Counter(numbers).items() if c > 1)
        if duplicates:
            self.result.add_error(f"Duplicate question numbers: {duplicates}")
        elif sorted(numbers) == expected:
            self.result.add_warning(f"Question numbers are not in sequential order. Got: {numbers}")
        else:
            self.result.add_warning(
                f"Question numbers are not sequential. Expected 1-{len(numbers)}, got: {numbers}"
            )

    # ------------------------------------------------------------------
    # KaTeX

    def _validate_question_katex(self, question: dict, idx: int):
        fields = [(f"Question {idx} body", question['question_body'])]
        fields += [
            (f"Question {idx}, Choice {c_idx}", c['text'])
            for c_idx, c in enumerate(question['choices'], 1)
        ]

        has_math = has_katex = False
        for location, text in fields:
            math, katex = self._check_katex_in_text(text, location)
            has_math |= math
            has_katex |= katex

        if has_katex:
            self.stats['questions_with_katex'] += 1
        if has_math or has_katex:
            self.stats['questions_with_math'] += 1

    @staticmethod
    def _outside_math(text: str) -> list[str]:
        """Parts of text that are not between $...$ delimiters."""
        return text.split('$')[::2]

    def _check_katex_in_text(self, text: str, location: str):
        """Check one text field. Returns (has_plain_math, has_katex)."""
        if not text:
            return False, False
        has_math = False

        if text.count('$') % 2 != 0:
            self.result.add_error(f"{location}: Mismatched $ delimiters (found {text.count('$')})")

        for part in self._outside_math(text):
            # Plain Greek letters (each occurrence is checked separately)
            for i, ch in enumerate(part):
                if ch not in self.GREEK_LETTERS:
                    continue
                nxt = part[i + 1 : i + 2]
                if ch in self.MICRO and nxt.isalpha():
                    continue  # unit prefix: µF, µH, µs, ...
                self.result.add_warning(
                    f"{location}: Found plain Unicode Greek letter '{ch}'. "
                    f"Use KaTeX: $\\{self.GREEK_LETTERS[ch]}$"
                )
                self.stats['greek_letters_found'] += 1
                has_math = True

            # Formula divisions such as R/C
            for m in self.FORMULA_DIVISION.finditer(part):
                num, den = m.groups()
                if den in self.UNIT_DENOMINATORS:
                    continue
                self.result.add_warning(
                    f"{location}: Found formula division '{num}/{den}'. "
                    f"Use KaTeX: $\\dfrac{{{num}}}{{{den}}}$"
                )
                has_math = True

        katex_parts = re.findall(r'\$([^$]+)\$', text)
        for katex in katex_parts:
            if re.search(r'\\frac\b', katex):  # \dfrac does not match
                self.result.add_warning(
                    f"{location}: Use \\dfrac instead of \\frac for proper display-size fractions"
                )
            for cmd in self.LATEX_COMMANDS:
                if re.search(r'(?<!\\)\b' + re.escape(cmd) + r'\b', katex):
                    self.result.add_error(
                        f"{location}: LaTeX command '{cmd}' appears without backslash. "
                        f"Use \\\\{cmd} in JSON"
                    )

        if re.search(r'\$\\mu\$[A-Za-zΩ]', text):
            self.result.add_warning(
                f"{location}: Found $\\mu$ in unit context. Use plain µ for units (µF, µH, µV, µA)"
            )

        if re.search(r'\$\\dfrac\{1\}.*?(second|секунда|hour|minute)\}', text, re.IGNORECASE):
            self.result.add_warning(
                f"{location}: Unit expression wrapped in KaTeX. "
                "Keep unit labels as plain text (e.g., '1/second')"
            )

        return has_math, bool(katex_parts)

    # ------------------------------------------------------------------
    # Output

    def print_results(self):
        """Print validation results with colors"""
        print(f"\n{Colors.BOLD}Validating: {self.name}{Colors.RESET}")
        print("=" * 70)
        print()

        if self.result.errors:
            print(f"{Colors.RED}{Colors.BOLD}✗ ERRORS ({len(self.result.errors)}):{Colors.RESET}")
            for error in self.result.errors:
                print(f"  {Colors.RED}✗ {error}{Colors.RESET}")
            print()

        if self.result.warnings:
            count = len(self.result.warnings)
            print(f"{Colors.YELLOW}{Colors.BOLD}⚠ WARNINGS ({count}):{Colors.RESET}")
            for warning in self.result.warnings:
                print(f"  {Colors.YELLOW}⚠ {warning}{Colors.RESET}")
            print()

        if self.result.info and not self.result.errors:
            print(f"{Colors.CYAN}ℹ INFO:{Colors.RESET}")
            for info in self.result.info:
                print(f"  {Colors.CYAN}ℹ {info}{Colors.RESET}")
            print()

        print(f"{Colors.BOLD}📊 STATISTICS:{Colors.RESET}")
        print(f"  Total questions: {self.stats['total_questions']}")
        if self.stats['questions_with_images'] > 0:
            print(f"  Questions with images: {self.stats['questions_with_images']}")
        print(f"  Questions with math content: {self.stats['questions_with_math']}")
        print(f"  Questions with KaTeX: {self.stats['questions_with_katex']}")
        if self.stats['greek_letters_found'] > 0:
            print(f"  Plain Greek letters found: {self.stats['greek_letters_found']}")
        print()

        if self.result.has_errors():
            print(f"{Colors.RED}{Colors.BOLD}❌ VALIDATION FAILED{Colors.RESET}")
            print(f"   {len(self.result.errors)} error(s), {len(self.result.warnings)} warning(s)")
        elif self.result.warnings:
            print(f"{Colors.YELLOW}{Colors.BOLD}⚠️  VALIDATION PASSED WITH WARNINGS{Colors.RESET}")
            print(f"   {len(self.result.warnings)} warning(s)")
        else:
            print(f"{Colors.GREEN}{Colors.BOLD}✅ VALIDATION PASSED{Colors.RESET}")
            print("   No errors or warnings")
        print()


def main(argv=None):
    """Main entry point"""
    files = sys.argv[1:] if argv is None else list(argv)
    if not files:
        print(f"{Colors.BOLD}Usage:{Colors.RESET} lzradio-validate <json_file> [json_file ...]")
        print("\nValidates Bulgarian Amateur Radio Exam question JSON files.")
        print("\nExamples:")
        print("  lzradio-validate examples/simple_no_math.json")
        print("  lzradio-validate examples/*.json")
        sys.exit(1)

    total_errors = 0
    total_warnings = 0

    for filepath in files:
        validator = QuestionValidator(filepath)
        result = validator.validate()
        validator.print_results()
        total_errors += len(result.errors)
        total_warnings += len(result.warnings)

    if len(files) > 1:
        print("=" * 70)
        print(f"{Colors.BOLD}OVERALL SUMMARY:{Colors.RESET}")
        print(f"  Files validated: {len(files)}")
        print(f"  Total errors: {total_errors}")
        print(f"  Total warnings: {total_warnings}")
        print()

    sys.exit(1 if total_errors > 0 else 0)


if __name__ == '__main__':
    main()
