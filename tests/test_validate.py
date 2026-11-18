"""Tests for validate.py.  Run with:  python3 -m unittest -v"""

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from validate import QuestionValidator  # noqa: E402


def question(number=1, body="Въпрос?", correct="А", texts=("a", "b", "c", "d"), **extra):
    q = {
        "question_number": number,
        "question_body": body,
        "correct_answer": correct,
        "choices": [{"key": k, "text": t} for k, t in zip("АБВГ", texts)],
    }
    q.update(extra)
    return q


def document(*questions):
    return {
        "class": "Радиолюбителски клас 2",
        "section": "Раздел 1 – Електротехника и радиотехника",
        "update": "Актуализиран конспект 11.08.2025 г.",
        "questions": list(questions) or [question()],
    }


def run(data):
    validator = QuestionValidator(data=data)
    result = validator.validate()
    return result, validator.stats


class ValidatorTestCase(unittest.TestCase):
    def assertClean(self, data):
        result, _ = run(data)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.warnings, [])

    def assertError(self, data, fragment):
        result, _ = run(data)
        self.assertTrue(any(fragment in e for e in result.errors),
                        f"no error containing {fragment!r}; errors: {result.errors}")

    def assertWarning(self, data, fragment):
        result, _ = run(data)
        self.assertTrue(any(fragment in w for w in result.warnings),
                        f"no warning containing {fragment!r}; warnings: {result.warnings}")

    def assertNoWarning(self, data):
        result, _ = run(data)
        self.assertEqual(result.warnings, [])


class TestReferenceFiles(ValidatorTestCase):
    def test_template_and_examples_are_clean(self):
        for path in [ROOT / "template.json", *sorted((ROOT / "examples").glob("*.json"))]:
            with self.subTest(file=path.name):
                validator = QuestionValidator(str(path))
                result = validator.validate()
                self.assertEqual(result.errors, [])
                self.assertEqual(result.warnings, [])


class TestStructure(ValidatorTestCase):
    def test_minimal_document_is_clean(self):
        self.assertClean(document())

    def test_top_level_not_object(self):
        self.assertError([1, 2], "Top level must be a JSON object")

    def test_missing_top_level_fields(self):
        data = document()
        del data["update"]
        self.assertError(data, "Missing required field: 'update'")

    def test_empty_top_level_string(self):
        data = document()
        data["class"] = " "
        self.assertError(data, "'class' must be a non-empty string")

    def test_questions_not_list(self):
        data = document()
        data["questions"] = {}
        self.assertError(data, "'questions' must be an array")

    def test_questions_empty(self):
        data = document()
        data["questions"] = []
        self.assertError(data, "'questions' is empty")

    def test_question_not_object(self):
        self.assertError(document(question(), "oops"), "Question 2: Must be an object")

    def test_question_body_null(self):
        self.assertError(document(question(body=None)), "'question_body' must be a string")

    def test_question_number_string(self):
        self.assertError(document(question(), question(number="2")),
                         "'question_number' must be an integer")

    def test_question_number_bool(self):
        self.assertError(document(question(number=True)), "'question_number' must be an integer")

    def test_missing_question_field(self):
        q = question()
        del q["choices"]
        self.assertError(document(q), "Missing field 'choices'")

    def test_wrong_number_of_choices(self):
        q = question()
        q["choices"].pop()
        self.assertError(document(q), "Must have exactly 4 choices, found 3")

    def test_choice_not_object(self):
        q = question()
        q["choices"][1] = "b"
        self.assertError(document(q), "Choice 2: Must be an object")

    def test_choice_text_not_string(self):
        q = question()
        q["choices"][0]["text"] = 5
        self.assertError(document(q), "'text' must be a string")

    def test_unknown_fields_warn(self):
        data = document(question(extra_field=1))
        data["comment"] = "x"
        data["questions"][0]["choices"][0]["note"] = "x"
        self.assertWarning(data, "Unknown top-level field: 'comment'")
        self.assertWarning(data, "Unknown field 'extra_field'")
        self.assertWarning(data, "Choice 1: Unknown field 'note'")

    def test_other_questions_still_checked_after_structure_error(self):
        data = document(question(body=None), question(number=2, correct=""))
        self.assertError(data, "Question 2: Empty correct_answer")

    def test_invalid_json_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write("{not json")
        self.addCleanup(Path(f.name).unlink)
        result = QuestionValidator(f.name).validate()
        self.assertTrue(any("Invalid JSON syntax" in e for e in result.errors))

    def test_missing_file(self):
        result = QuestionValidator("/nonexistent/file.json").validate()
        self.assertTrue(any("File not found" in e for e in result.errors))


class TestContent(ValidatorTestCase):
    def test_empty_correct_answer(self):
        self.assertError(document(question(correct="")), "Empty correct_answer")

    def test_invalid_correct_answer(self):
        self.assertError(document(question(correct="Д")), "Invalid correct_answer 'Д'")

    def test_correct_answer_not_in_choices(self):
        q = question(correct="Г")
        q["choices"][3]["key"] = "В"
        self.assertError(document(q), "not found in choice keys")

    def test_duplicate_choice_keys(self):
        q = question()
        q["choices"][3]["key"] = "А"
        self.assertError(document(q), "Duplicate choice keys: ['А']")

    def test_keys_out_of_order(self):
        q = question()
        q["choices"].reverse()
        self.assertWarning(document(q), "Choice keys out of order")

    def test_invalid_choice_key(self):
        q = question()
        q["choices"][0]["key"] = "X"
        self.assertError(document(q), "Invalid key 'X'")

    def test_latin_keys_accepted(self):
        q = question(correct="B")
        for choice, key in zip(q["choices"], "ABCD"):
            choice["key"] = key
        self.assertClean(document(q))

    def test_mixed_key_styles(self):
        q2 = question(number=2, correct="B")
        for choice, key in zip(q2["choices"], "ABCD"):
            choice["key"] = key
        self.assertError(document(question(), q2), "Invalid key 'A'")

    def test_empty_body(self):
        self.assertError(document(question(body="  ")), "Empty question_body")

    def test_empty_choice_text(self):
        self.assertError(document(question(texts=("a", "", "c", "d"))), "Choice 2: Empty text")

    def test_empty_choice_text_allowed_with_image(self):
        self.assertClean(document(question(texts=("", "", "", ""), image="Class2_Section1_1.png")))

    def test_empty_image(self):
        self.assertError(document(question(image="")), "'image' must be a non-empty string")

    def test_image_bad_name(self):
        self.assertWarning(document(question(image="resistor.png")), "does not match 'Class<X>")

    def test_image_number_mismatch(self):
        self.assertWarning(document(question(image="Class2_Section1_45.png")),
                           "does not match question_number 1")

    def test_long_body(self):
        self.assertWarning(document(question(body="а" * 501)), "Very long question body")

    def test_numbers_sequential(self):
        self.assertClean(document(question(1), question(2), question(3)))

    def test_numbers_out_of_order(self):
        self.assertWarning(document(question(2), question(1)), "not in sequential order")

    def test_numbers_gap(self):
        self.assertWarning(document(question(1), question(3)), "not sequential")

    def test_numbers_duplicate(self):
        self.assertError(document(question(1), question(1)), "Duplicate question numbers: [1]")


class TestKatex(ValidatorTestCase):
    def test_plain_greek_letter(self):
        self.assertWarning(document(question(body="дължина 5/8 λ")), "plain Unicode Greek letter 'λ'")

    def test_greek_inside_katex_ok(self):
        self.assertNoWarning(document(question(body="дължина 5/8 $\\lambda$")))

    def test_micro_sign_in_units_ok(self):
        for unit in ("10 µF", "5 µH", "3 µs", "2 μF", "1 µА"):
            with self.subTest(unit=unit):
                self.assertNoWarning(document(question(body=unit)))

    def test_mu_variable_warns(self):
        self.assertWarning(document(question(body="µ = 5")), "plain Unicode Greek letter 'µ'")

    def test_mu_variable_next_to_unit_warns(self):
        # Previously skipped because the text also contained "µF"
        result, _ = run(document(question(body="10 µF и μ = 5")))
        self.assertEqual(len(result.warnings), 1)
        self.assertIn("'μ'", result.warnings[0])

    def test_each_greek_occurrence_counted(self):
        _, stats = run(document(question(body="λ и λ")))
        self.assertEqual(stats["greek_letters_found"], 2)

    def test_formula_division(self):
        for text, frag in (("R/C", "'R/C'"), ("Q/fp", "'Q/fp'"), ("U/I", "'U/I'")):
            with self.subTest(text=text):
                self.assertWarning(document(question(texts=(text, "b", "c", "d"))), frag)

    def test_not_formula_division(self):
        for text in ("m/s", "km/h", "AM/FM", "TX/RX", "CW/SSB", "1/30", "и/или", "5/8"):
            with self.subTest(text=text):
                self.assertNoWarning(document(question(texts=(text, "b", "c", "d"))))

    def test_frac_instead_of_dfrac(self):
        self.assertWarning(document(question(body="$\\frac{1}{2}$")), "Use \\dfrac instead of \\frac")

    def test_frac_warned_even_with_dfrac_present(self):
        self.assertWarning(document(question(body="$\\dfrac{1}{2}$ и $\\frac{1}{3}$")),
                           "Use \\dfrac instead of \\frac")

    def test_dfrac_ok(self):
        self.assertNoWarning(document(question(body="$\\dfrac{1}{2}$")))

    def test_mismatched_dollars(self):
        self.assertError(document(question(body="$\\lambda")), "Mismatched $ delimiters")

    def test_command_without_backslash(self):
        self.assertError(document(question(body="$lambda$")), "'lambda' appears without backslash")

    def test_katex_mu_in_unit(self):
        self.assertWarning(document(question(body="10 $\\mu$F")), "$\\mu$ in unit context")

    def test_unit_expression_in_katex(self):
        self.assertWarning(document(question(body="$\\dfrac{1}{\\text{секунда}}$")),
                           "Unit expression wrapped in KaTeX")


class TestStats(ValidatorTestCase):
    def test_counts_questions_not_fields(self):
        q1 = question(1, body="$\\tau$?", texts=("$\\tau = RC$", "$\\tau = \\dfrac{R}{C}$", "c", "d"))
        q2 = question(2)
        q3 = question(3, body="λ")
        _, stats = run(document(q1, q2, q3))
        self.assertEqual(stats["total_questions"], 3)
        self.assertEqual(stats["questions_with_katex"], 1)
        self.assertEqual(stats["questions_with_math"], 2)

    def test_counts_images(self):
        _, stats = run(document(question(image="Class2_Section1_1.png")))
        self.assertEqual(stats["questions_with_images"], 1)


class TestCommandLine(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "validate.py"), *args],
                              capture_output=True, text=True)

    def _write(self, data):
        f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        json.dump(data, f, ensure_ascii=False)
        f.close()
        self.addCleanup(Path(f.name).unlink)
        return f.name

    def test_no_arguments(self):
        self.assertEqual(self._run().returncode, 1)

    def test_valid_file_exits_0(self):
        proc = self._run(self._write(document()))
        self.assertEqual(proc.returncode, 0)
        self.assertIn("VALIDATION PASSED", proc.stdout)
        self.assertNotIn("\033[", proc.stdout)  # no colors when not a terminal

    def test_warnings_exit_0(self):
        proc = self._run(self._write(document(question(body="λ"))))
        self.assertEqual(proc.returncode, 0)
        self.assertIn("PASSED WITH WARNINGS", proc.stdout)

    def test_errors_exit_1(self):
        proc = self._run(self._write(document(question(correct=""))))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("VALIDATION FAILED", proc.stdout)

    def test_malformed_input_does_not_crash(self):
        bad = copy.deepcopy(document(question(body=None), question(number="2"), "oops"))
        proc = self._run(self._write(bad))
        self.assertEqual(proc.returncode, 1)
        self.assertNotIn("Traceback", proc.stderr)


if __name__ == "__main__":
    unittest.main()
