"""Tests for lzradio_extractor.validate."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from lzradio_extractor.validate import QuestionValidator

ROOT = Path(__file__).resolve().parent.parent
REFERENCE_FILES = [ROOT / "template.json", *sorted((ROOT / "examples").glob("*.json"))]


# ----------------------------------------------------------------------
# Helpers


def question(number=1, body="Въпрос?", correct="А", texts=("a", "b", "c", "d"), **extra):
    q = {
        "question_number": number,
        "question_body": body,
        "correct_answer": correct,
        "choices": [{"key": k, "text": t} for k, t in zip("АБВГ", texts, strict=True)],
    }
    q.update(extra)
    return q


def latin(q):
    for choice, key in zip(q["choices"], "ABCD", strict=True):
        choice["key"] = key
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


def errors(data):
    return run(data)[0].errors


def warnings(data):
    return run(data)[0].warnings


def has(messages, fragment):
    return any(fragment in m for m in messages)


# ----------------------------------------------------------------------
# Reference files


@pytest.mark.parametrize("path", REFERENCE_FILES, ids=lambda p: p.name)
def test_reference_file_is_clean(path):
    result = QuestionValidator(str(path)).validate()
    assert result.errors == []
    assert result.warnings == []


def test_minimal_document_is_clean():
    assert errors(document()) == []
    assert warnings(document()) == []


# ----------------------------------------------------------------------
# Structure


def test_top_level_not_object():
    assert has(errors([1, 2]), "Top level must be a JSON object")


@pytest.mark.parametrize("field", ["class", "section", "update", "questions"])
def test_missing_top_level_field(field):
    data = document()
    del data[field]
    assert has(errors(data), f"Missing required field: '{field}'")


@pytest.mark.parametrize("value", ["", " ", None, 5])
def test_invalid_top_level_string(value):
    data = document()
    data["class"] = value
    assert has(errors(data), "'class' must be a non-empty string")


def test_questions_not_list():
    data = document()
    data["questions"] = {}
    assert has(errors(data), "'questions' must be an array")


def test_questions_empty():
    data = document()
    data["questions"] = []
    assert has(errors(data), "'questions' is empty")


def test_question_not_object():
    assert has(errors(document(question(), "oops")), "Question 2: Must be an object")


def test_question_body_null():
    assert has(errors(document(question(body=None))), "'question_body' must be a string")


@pytest.mark.parametrize("number", ["2", 2.0, True, None])
def test_question_number_not_integer(number):
    data = document(question(), question(number=number))
    assert has(errors(data), "'question_number' must be an integer")


def test_missing_question_field():
    q = question()
    del q["choices"]
    assert has(errors(document(q)), "Missing field 'choices'")


@pytest.mark.parametrize("count", [0, 3, 5])
def test_wrong_number_of_choices(count):
    q = question()
    q["choices"] = (q["choices"] * 2)[:count]
    assert has(errors(document(q)), f"Must have exactly 4 choices, found {count}")


def test_choices_not_list():
    assert has(errors(document(question(choices="abcd"))), "'choices' must be an array")


def test_choice_not_object():
    q = question()
    q["choices"][1] = "b"
    assert has(errors(document(q)), "Choice 2: Must be an object")


@pytest.mark.parametrize("field", ["key", "text"])
def test_choice_field_not_string(field):
    q = question()
    q["choices"][0][field] = 5
    assert has(errors(document(q)), f"'{field}' must be a string")


@pytest.mark.parametrize("field", ["key", "text"])
def test_choice_field_missing(field):
    q = question()
    del q["choices"][0][field]
    assert has(errors(document(q)), f"Choice 1: Missing '{field}'")


def test_unknown_fields_warn():
    data = document(question(extra_field=1))
    data["comment"] = "x"
    data["questions"][0]["choices"][0]["note"] = "x"
    found = warnings(data)
    assert has(found, "Unknown top-level field: 'comment'")
    assert has(found, "Unknown field 'extra_field'")
    assert has(found, "Choice 1: Unknown field 'note'")


def test_other_questions_still_checked_after_structure_error():
    data = document(question(body=None), question(number=2, correct=""))
    assert has(errors(data), "Question 2: Empty correct_answer")


def test_invalid_json_file(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    assert has(QuestionValidator(str(path)).validate().errors, "Invalid JSON syntax")


def test_non_utf8_file(tmp_path):
    path = tmp_path / "latin1.json"
    path.write_bytes('{"class": "é"}'.encode("latin-1"))
    assert has(QuestionValidator(str(path)).validate().errors, "not valid UTF-8")


def test_missing_file(tmp_path):
    result = QuestionValidator(str(tmp_path / "missing.json")).validate()
    assert has(result.errors, "File not found")


# ----------------------------------------------------------------------
# Content


def test_empty_correct_answer():
    assert has(errors(document(question(correct=""))), "Empty correct_answer")


def test_invalid_correct_answer():
    assert has(errors(document(question(correct="Д"))), "Invalid correct_answer 'Д'")


def test_correct_answer_not_in_choices():
    q = question(correct="Г")
    q["choices"][3]["key"] = "В"
    assert has(errors(document(q)), "not found in choice keys")


def test_duplicate_choice_keys():
    q = question()
    q["choices"][3]["key"] = "А"
    assert has(errors(document(q)), "Duplicate choice keys: ['А']")


def test_keys_out_of_order():
    q = question()
    q["choices"].reverse()
    assert has(warnings(document(q)), "Choice keys out of order")


def test_invalid_choice_key():
    q = question()
    q["choices"][0]["key"] = "X"
    assert has(errors(document(q)), "Invalid key 'X'")


def test_latin_keys_accepted():
    data = document(latin(question(correct="B")))
    assert errors(data) == []
    assert warnings(data) == []


def test_mixed_key_styles():
    data = document(question(), latin(question(number=2, correct="B")))
    assert has(errors(data), "Invalid key 'A'")


def test_empty_body():
    assert has(errors(document(question(body="  "))), "Empty question_body")


def test_empty_choice_text():
    assert has(errors(document(question(texts=("a", "", "c", "d")))), "Choice 2: Empty text")


def test_empty_choice_text_allowed_with_image():
    data = document(question(texts=("", "", "", ""), image="Class2_Section1_1.png"))
    assert errors(data) == []
    assert warnings(data) == []


@pytest.mark.parametrize("image", ["", "  ", None, 5])
def test_invalid_image(image):
    assert has(errors(document(question(image=image))), "'image' must be a non-empty string")


@pytest.mark.parametrize(
    "image", ["resistor.png", "Class3_Section1_1.png", "Class2_Section1_1.jpg"]
)
def test_image_bad_name(image):
    assert has(warnings(document(question(image=image))), "does not match 'Class<X>")


def test_image_number_mismatch():
    data = document(question(image="Class2_Section1_45.png"))
    assert has(warnings(data), "does not match question_number 1")


def test_long_body():
    assert has(warnings(document(question(body="а" * 501))), "Very long question body")


def test_numbers_sequential():
    data = document(question(1), question(2), question(3))
    assert errors(data) == []
    assert warnings(data) == []


def test_numbers_out_of_order():
    assert has(warnings(document(question(2), question(1))), "not in sequential order")


def test_numbers_gap():
    assert has(warnings(document(question(1), question(3))), "not sequential")


def test_numbers_duplicate():
    data = document(question(1), question(1))
    assert has(errors(data), "Duplicate question numbers: [1]")


# ----------------------------------------------------------------------
# KaTeX


def test_plain_greek_letter():
    data = document(question(body="дължина 5/8 λ"))
    assert has(warnings(data), "plain Unicode Greek letter 'λ'")


def test_greek_inside_katex_ok():
    assert warnings(document(question(body="дължина 5/8 $\\lambda$"))) == []


@pytest.mark.parametrize("text", ["10 µF", "5 µH", "3 µs", "2 μF", "1 µА"])
def test_micro_sign_in_units_ok(text):
    assert warnings(document(question(body=text))) == []


@pytest.mark.parametrize("text", ["µ = 5", "μ = 5", "µ"])
def test_mu_variable_warns(text):
    assert has(warnings(document(question(body=text))), "plain Unicode Greek letter")


def test_mu_variable_next_to_unit_warns():
    # Previously skipped because the text also contained "µF"
    found = warnings(document(question(body="10 µF и μ = 5")))
    assert len(found) == 1
    assert "'μ'" in found[0]


def test_each_greek_occurrence_counted():
    _, stats = run(document(question(body="λ и λ")))
    assert stats["greek_letters_found"] == 2


@pytest.mark.parametrize("text", ["R/C", "Q/fp", "U/I"])
def test_formula_division(text):
    data = document(question(texts=(text, "b", "c", "d")))
    assert has(warnings(data), f"'{text}'")


@pytest.mark.parametrize(
    "text", ["m/s", "km/h", "AM/FM", "TX/RX", "CW/SSB", "1/30", "и/или", "5/8", "$R/C$"]
)
def test_not_formula_division(text):
    assert warnings(document(question(texts=(text, "b", "c", "d")))) == []


def test_frac_instead_of_dfrac():
    data = document(question(body="$\\frac{1}{2}$"))
    assert has(warnings(data), "Use \\dfrac instead of \\frac")


def test_frac_warned_even_with_dfrac_present():
    data = document(question(body="$\\dfrac{1}{2}$ и $\\frac{1}{3}$"))
    assert has(warnings(data), "Use \\dfrac instead of \\frac")


def test_dfrac_ok():
    assert warnings(document(question(body="$\\dfrac{1}{2}$"))) == []


def test_mismatched_dollars():
    assert has(errors(document(question(body="$\\lambda"))), "Mismatched $ delimiters")


@pytest.mark.parametrize("cmd", ["lambda", "tau", "dfrac{1}{2}", "sqrt{2}", "pi"])
def test_command_without_backslash(cmd):
    data = document(question(body=f"${cmd}$"))
    assert has(errors(data), "appears without backslash")


def test_katex_mu_in_unit():
    assert has(warnings(document(question(body="10 $\\mu$F"))), "$\\mu$ in unit context")


def test_unit_expression_in_katex():
    data = document(question(body="$\\dfrac{1}{\\text{секунда}}$"))
    assert has(warnings(data), "Unit expression wrapped in KaTeX")


# ----------------------------------------------------------------------
# Statistics


def test_stats_count_questions_not_fields():
    q1 = question(1, body="$\\tau$?", texts=("$\\tau = RC$", "$\\tau = \\dfrac{R}{C}$", "c", "d"))
    q2 = question(2)
    q3 = question(3, body="λ")
    _, stats = run(document(q1, q2, q3))
    assert stats["total_questions"] == 3
    assert stats["questions_with_katex"] == 1
    assert stats["questions_with_math"] == 2


def test_stats_count_images():
    _, stats = run(document(question(image="Class2_Section1_1.png")))
    assert stats["questions_with_images"] == 1


# ----------------------------------------------------------------------
# Command line


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "lzradio_extractor.validate", *args],
        capture_output=True,
        text=True,
    )


@pytest.fixture
def write_json(tmp_path):
    def write(data, name="questions.json"):
        path = tmp_path / name
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return str(path)

    return write


def test_cli_no_arguments():
    assert run_cli().returncode == 1


def test_cli_valid_file_exits_0(write_json):
    proc = run_cli(write_json(document()))
    assert proc.returncode == 0
    assert "VALIDATION PASSED" in proc.stdout
    assert "\033[" not in proc.stdout  # no colors when not a terminal


def test_cli_warnings_exit_0(write_json):
    proc = run_cli(write_json(document(question(body="λ"))))
    assert proc.returncode == 0
    assert "PASSED WITH WARNINGS" in proc.stdout


def test_cli_errors_exit_1(write_json):
    proc = run_cli(write_json(document(question(correct=""))))
    assert proc.returncode == 1
    assert "VALIDATION FAILED" in proc.stdout


def test_cli_multiple_files(write_json):
    good = write_json(document(), "good.json")
    bad = write_json(document(question(correct="")), "bad.json")
    proc = run_cli(good, bad)
    assert proc.returncode == 1
    assert "Files validated: 2" in proc.stdout


def test_cli_malformed_input_does_not_crash(write_json):
    proc = run_cli(write_json(document(question(body=None), question(number="2"), "oops")))
    assert proc.returncode == 1
    assert "Traceback" not in proc.stderr
