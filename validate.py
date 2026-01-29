#!/usr/bin/env python3
"""
JSON Question File Validator for Bulgarian Amateur Radio Exam Questions

Validates structure, content, and KaTeX formatting of question JSON files.
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any
from collections import Counter


class Colors:
    """ANSI color codes for terminal output"""
    RED = '\033[91m'
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    RESET = '\033[0m'


class ValidationResult:
    """Stores validation results"""
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []

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

    # Greek letters that should use KaTeX
    GREEK_LETTERS = ['λ', 'τ', 'α', 'β', 'γ', 'δ', 'ε', 'η', 'θ', 'μ', 'π', 'ρ', 'σ', 'φ', 'ω']

    # Omega is acceptable in units but should be KaTeX in formulas
    # We'll be lenient with Ω in units

    # Valid choice keys
    CYRILLIC_KEYS = ['А', 'Б', 'В', 'Г']
    LATIN_KEYS = ['A', 'B', 'C', 'D']

    def __init__(self, filepath: str):
        self.filepath = Path(filepath)
        self.result = ValidationResult()
        self.data = None
        self.stats = {
            'total_questions': 0,
            'questions_with_math': 0,
            'questions_with_katex': 0,
            'questions_with_images': 0,
            'greek_letters_found': 0,
            'fractions_found': 0,
        }

    def validate(self) -> ValidationResult:
        """Run all validations"""
        print(f"\n{Colors.BOLD}Validating: {self.filepath.name}{Colors.RESET}")
        print("=" * 70)

        # Load and parse JSON
        if not self._load_json():
            return self.result

        # Structure validations
        self._validate_structure()

        if not self.result.has_errors():
            # Content validations
            self._validate_content()

            # KaTeX validations
            self._validate_katex()

            # Best practices
            self._validate_best_practices()

        return self.result

    def _load_json(self) -> bool:
        """Load and parse JSON file"""
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
            self.result.add_info(f"✓ Valid JSON syntax")
            return True
        except FileNotFoundError:
            self.result.add_error(f"File not found: {self.filepath}")
            return False
        except json.JSONDecodeError as e:
            self.result.add_error(f"Invalid JSON syntax: {e}")
            return False

    def _validate_structure(self):
        """Validate JSON structure"""
        # Check top-level required fields
        required_fields = ['class', 'section', 'update', 'questions']
        for field in required_fields:
            if field not in self.data:
                self.result.add_error(f"Missing required field: '{field}'")

        if 'questions' not in self.data:
            return

        if not isinstance(self.data['questions'], list):
            self.result.add_error("'questions' must be an array")
            return

        self.stats['total_questions'] = len(self.data['questions'])

        # Validate each question
        for idx, question in enumerate(self.data['questions'], 1):
            self._validate_question_structure(question, idx)

    def _validate_question_structure(self, question: Dict, idx: int):
        """Validate structure of a single question"""
        # Required fields
        required = ['question_number', 'question_body', 'correct_answer', 'choices']
        for field in required:
            if field not in question:
                self.result.add_error(f"Question {idx}: Missing field '{field}'")

        # Track if this question has an image (for image-based questions, empty text is OK)
        has_image = 'image' in question

        # Validate choices
        if 'choices' in question:
            if not isinstance(question['choices'], list):
                self.result.add_error(f"Question {idx}: 'choices' must be an array")
            elif len(question['choices']) != 4:
                self.result.add_error(
                    f"Question {idx}: Must have exactly 4 choices, found {len(question['choices'])}"
                )
            else:
                # Validate each choice
                for choice_idx, choice in enumerate(question['choices']):
                    if not isinstance(choice, dict):
                        self.result.add_error(f"Question {idx}, Choice {choice_idx + 1}: Must be an object")
                        continue

                    if 'key' not in choice:
                        self.result.add_error(f"Question {idx}, Choice {choice_idx + 1}: Missing 'key'")
                    if 'text' not in choice:
                        self.result.add_error(f"Question {idx}, Choice {choice_idx + 1}: Missing 'text'")

                    # Store has_image flag for later validation
                    if not hasattr(self, '_questions_with_images'):
                        self._questions_with_images = set()
                    if has_image:
                        self._questions_with_images.add(idx)

    def _validate_content(self):
        """Validate content of questions"""
        if 'questions' not in self.data:
            return

        question_numbers = []

        # Detect which key style is used (Cyrillic or Latin)
        first_question = self.data['questions'][0] if self.data['questions'] else {}
        first_choices = first_question.get('choices', [])
        if first_choices and 'key' in first_choices[0]:
            first_key = first_choices[0]['key']
            expected_keys = self.CYRILLIC_KEYS if first_key in self.CYRILLIC_KEYS else self.LATIN_KEYS
        else:
            expected_keys = self.CYRILLIC_KEYS  # default

        # Initialize set for tracking image-based questions
        if not hasattr(self, '_questions_with_images'):
            self._questions_with_images = set()

        for idx, question in enumerate(self.data['questions'], 1):
            # Check if this is an image-based question
            has_image = 'image' in question
            if has_image:
                self._questions_with_images.add(idx)
                self.stats['questions_with_images'] += 1
            # Check question number
            q_num = question.get('question_number')
            if q_num is None:
                continue

            question_numbers.append(q_num)

            # Check if question body is empty
            q_body = question.get('question_body', '').strip()
            if not q_body:
                self.result.add_error(f"Question {idx}: Empty question_body")

            # Check correct_answer
            correct = question.get('correct_answer')
            if correct:
                if correct not in expected_keys:
                    self.result.add_error(
                        f"Question {idx}: Invalid correct_answer '{correct}'. Expected one of: {expected_keys}"
                    )

            # Validate choices
            choices = question.get('choices', [])
            if len(choices) == 4:
                choice_keys = []
                for choice_idx, choice in enumerate(choices):
                    key = choice.get('key')
                    text = choice.get('text', '').strip()

                    if key:
                        choice_keys.append(key)
                        if key not in expected_keys:
                            self.result.add_error(
                                f"Question {idx}, Choice {choice_idx + 1}: Invalid key '{key}'. Expected one of: {expected_keys}"
                            )

                    if not text:
                        # Empty text is acceptable for image-based questions
                        if not has_image:
                            self.result.add_error(f"Question {idx}, Choice {choice_idx + 1}: Empty text")

                # Check if correct_answer exists in choices
                if correct and correct not in choice_keys:
                    self.result.add_error(
                        f"Question {idx}: correct_answer '{correct}' not found in choice keys: {choice_keys}"
                    )

                # Check for duplicate keys
                if len(choice_keys) != len(set(choice_keys)):
                    duplicates = [k for k, count in Counter(choice_keys).items() if count > 1]
                    self.result.add_error(f"Question {idx}: Duplicate choice keys: {duplicates}")

        # Check question number sequence
        if question_numbers:
            expected = list(range(1, len(question_numbers) + 1))
            if question_numbers != expected:
                # Check for duplicates (ERROR - this is always a problem)
                duplicates = [num for num, count in Counter(question_numbers).items() if count > 1]
                if duplicates:
                    self.result.add_error(f"Duplicate question numbers: {duplicates}")

                # Check for gaps or wrong order (WARNING - can match original PDF)
                if sorted(question_numbers) == expected:
                    self.result.add_warning(
                        f"Question numbers are not in sequential order. Got: {question_numbers}"
                    )
                else:
                    self.result.add_warning(
                        f"Question numbers are not sequential. Expected 1-{len(question_numbers)}, got: {question_numbers}"
                    )

    def _validate_katex(self):
        """Validate KaTeX formatting"""
        if 'questions' not in self.data:
            return

        for idx, question in enumerate(self.data['questions'], 1):
            q_body = question.get('question_body', '')

            # Check question body
            self._check_katex_in_text(q_body, f"Question {idx} body", idx)

            # Check choices
            for choice_idx, choice in enumerate(question.get('choices', [])):
                text = choice.get('text', '')
                self._check_katex_in_text(text, f"Question {idx}, Choice {choice_idx + 1}", idx)

    def _check_katex_in_text(self, text: str, location: str, q_num: int):
        """Check for KaTeX issues in text"""
        if not text:
            return

        # Track if this question has math content
        has_math = False
        has_katex = False

        # Check for Greek letters (excluding µ in units and Ω in units)
        for letter in self.GREEK_LETTERS:
            if letter in text:
                # Check if it's µ in a unit context (µF, µH, µV, µA)
                if letter == 'μ' or letter == 'µ':
                    # Check if followed by F, H, V, A (unit abbreviations)
                    pattern = r'[μµ][FHVA]\b'
                    if re.search(pattern, text):
                        continue  # This is acceptable

                # Check if it's outside of KaTeX
                # Look for the letter not within $...$
                parts = text.split('$')
                for i, part in enumerate(parts):
                    if i % 2 == 0:  # Outside KaTeX
                        if letter in part:
                            self.result.add_warning(
                                f"{location}: Found plain Unicode Greek letter '{letter}'. Use KaTeX: $\\{self._get_latex_name(letter)}$"
                            )
                            self.stats['greek_letters_found'] += 1
                            has_math = True
                            break

        # Note: Simple numeric fractions (number/number) are acceptable as plain text
        # Only warn about formula divisions with variables (R/C, Q/X, etc.)
        # So we skip checking for numeric fractions like 1/30, 5/8, etc.

        # Check for formula division patterns (R/C, Q/X, etc.) outside KaTeX
        formula_pattern = r'\b([A-Z])/([A-Z])\b'
        matches = re.finditer(formula_pattern, text)
        for match in matches:
            pos = match.start()
            before_text = text[:pos]
            dollar_count = before_text.count('$')
            if dollar_count % 2 == 0:  # Outside KaTeX
                var1, var2 = match.groups()
                self.result.add_warning(
                    f"{location}: Found formula division '{var1}/{var2}'. Use KaTeX: $\\dfrac{{{var1}}}{{{var2}}}$"
                )
                has_math = True

        # Check for \frac instead of \dfrac
        if r'\frac' in text and r'\dfrac' not in text:
            self.result.add_warning(
                f"{location}: Use \\dfrac instead of \\frac for proper display-size fractions"
            )
            has_math = True

        # Check for mismatched $ delimiters
        dollar_count = text.count('$')
        if dollar_count % 2 != 0:
            self.result.add_error(f"{location}: Mismatched $ delimiters (found {dollar_count})")

        # Check for unescaped backslashes
        # When JSON is parsed, \\ becomes \, so properly escaped commands will have single \
        # We're looking for LaTeX commands that appear WITHOUT a backslash before them
        if '$' in text:
            has_katex = True
            # Extract KaTeX content
            katex_parts = re.findall(r'\$([^$]+)\$', text)
            for katex in katex_parts:
                # Common LaTeX commands - check if they appear without backslash
                latex_commands = ['lambda', 'tau', 'alpha', 'beta', 'gamma', 'delta', 'dfrac', 'frac', 'sqrt', 'pi']
                for cmd in latex_commands:
                    # Use regex to find the command NOT preceded by backslash
                    # This will match 'frac' but not '\frac'
                    pattern = r'(?<!\\)\b' + re.escape(cmd) + r'\b'
                    if re.search(pattern, katex):
                        self.result.add_error(
                            f"{location}: LaTeX command '{cmd}' appears without backslash. Use \\\\{cmd} in JSON"
                        )

        # Check for µ wrapped in KaTeX when used in units
        katex_mu_in_unit = re.search(r'\$\\mu\$[FHVA]\b', text)
        if katex_mu_in_unit:
            self.result.add_warning(
                f"{location}: Found $\\mu$ in unit context. Use plain µ for units (µF, µH, µV, µA)"
            )

        # Check for unit expressions wrapped in KaTeX
        unit_expr_pattern = r'\$\\dfrac\{1\}.*?(second|секунда|hour|minute)\}'
        if re.search(unit_expr_pattern, text, re.IGNORECASE):
            self.result.add_warning(
                f"{location}: Unit expression wrapped in KaTeX. Keep unit labels as plain text (e.g., '1/second')"
            )

        # Update stats
        if has_math:
            self.stats['questions_with_math'] += 1
        if has_katex:
            self.stats['questions_with_katex'] += 1

    def _get_latex_name(self, greek_letter: str) -> str:
        """Get LaTeX command name for Greek letter"""
        mapping = {
            'λ': 'lambda',
            'τ': 'tau',
            'α': 'alpha',
            'β': 'beta',
            'γ': 'gamma',
            'δ': 'delta',
            'ε': 'epsilon',
            'η': 'eta',
            'θ': 'theta',
            'μ': 'mu',
            'µ': 'mu',  # Alternate micro symbol
            'π': 'pi',
            'ρ': 'rho',
            'σ': 'sigma',
            'φ': 'phi',
            'ω': 'omega',
        }
        return mapping.get(greek_letter, 'unknown')

    def _validate_best_practices(self):
        """Validate best practices"""
        if 'questions' not in self.data:
            return

        for idx, question in enumerate(self.data['questions'], 1):
            q_body = question.get('question_body', '')

            # Warn about very long question bodies
            if len(q_body) > 500:
                self.result.add_warning(
                    f"Question {idx}: Very long question body ({len(q_body)} chars)"
                )

    def print_results(self):
        """Print validation results with colors"""
        print()

        # Errors
        if self.result.errors:
            print(f"{Colors.RED}{Colors.BOLD}✗ ERRORS ({len(self.result.errors)}):{Colors.RESET}")
            for error in self.result.errors:
                print(f"  {Colors.RED}✗ {error}{Colors.RESET}")
            print()

        # Warnings
        if self.result.warnings:
            print(f"{Colors.YELLOW}{Colors.BOLD}⚠ WARNINGS ({len(self.result.warnings)}):{Colors.RESET}")
            for warning in self.result.warnings:
                print(f"  {Colors.YELLOW}⚠ {warning}{Colors.RESET}")
            print()

        # Info
        if self.result.info and not self.result.errors:
            print(f"{Colors.CYAN}ℹ INFO:{Colors.RESET}")
            for info in self.result.info:
                print(f"  {Colors.CYAN}ℹ {info}{Colors.RESET}")
            print()

        # Statistics
        print(f"{Colors.BOLD}📊 STATISTICS:{Colors.RESET}")
        print(f"  Total questions: {self.stats['total_questions']}")
        if self.stats['questions_with_images'] > 0:
            print(f"  Questions with images: {self.stats['questions_with_images']}")
        print(f"  Questions with math content: {self.stats['questions_with_math']}")
        print(f"  Questions with KaTeX: {self.stats['questions_with_katex']}")
        if self.stats['greek_letters_found'] > 0:
            print(f"  Plain Greek letters found: {self.stats['greek_letters_found']}")
        if self.stats['fractions_found'] > 0:
            print(f"  Plain fractions found: {self.stats['fractions_found']}")
        print()

        # Summary
        if self.result.has_errors():
            print(f"{Colors.RED}{Colors.BOLD}❌ VALIDATION FAILED{Colors.RESET}")
            print(f"   {len(self.result.errors)} error(s), {len(self.result.warnings)} warning(s)")
        elif self.result.warnings:
            print(f"{Colors.YELLOW}{Colors.BOLD}⚠️  VALIDATION PASSED WITH WARNINGS{Colors.RESET}")
            print(f"   {len(self.result.warnings)} warning(s)")
        else:
            print(f"{Colors.GREEN}{Colors.BOLD}✅ VALIDATION PASSED{Colors.RESET}")
            print(f"   No errors or warnings")
        print()


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print(f"{Colors.BOLD}Usage:{Colors.RESET} python validate.py <json_file> [json_file ...]")
        print(f"\nValidates Bulgarian Amateur Radio Exam question JSON files.")
        print(f"\nExamples:")
        print(f"  python validate.py examples/simple_no_math.json")
        print(f"  python validate.py examples/*.json")
        sys.exit(1)

    files = sys.argv[1:]
    total_errors = 0
    total_warnings = 0

    for filepath in files:
        validator = QuestionValidator(filepath)
        result = validator.validate()
        validator.print_results()

        total_errors += len(result.errors)
        total_warnings += len(result.warnings)

    # Overall summary for multiple files
    if len(files) > 1:
        print("=" * 70)
        print(f"{Colors.BOLD}OVERALL SUMMARY:{Colors.RESET}")
        print(f"  Files validated: {len(files)}")
        print(f"  Total errors: {total_errors}")
        print(f"  Total warnings: {total_warnings}")
        print()

    # Exit code
    sys.exit(1 if total_errors > 0 else 0)


if __name__ == '__main__':
    main()
