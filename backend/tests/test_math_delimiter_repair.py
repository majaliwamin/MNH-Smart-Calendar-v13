"""Regression coverage for malformed LaTex delimiters in model replies."""
from app.class_rep.output_validation import repair_math_delimiters


def test_double_escaped_delimiters_are_collapsed():
    text = r"Chi-square (\\(\chi^2\\)) and \\[\chi^2=\sum \frac{(O-E)^2}{E}\\]"
    repaired = repair_math_delimiters(text)
    assert r"\\(" not in repaired
    assert r"\(" in repaired
    assert r"\[" in repaired


def test_dollar_math_and_stray_dollars_are_normalised():
    text = r"Compare $\chi^2$ with \\(\chi^2$ statistic\\)."
    repaired = repair_math_delimiters(text)
    assert r"\(\chi^2\)" in repaired
    assert "$" not in repaired


def test_inline_math_nested_in_display_math_is_unwrapped():
    text = r"\[E_{ij} = \frac{\(\text{Row } i\) \times \(\text{Col } j\)}{N}\]"
    repaired = repair_math_delimiters(text)
    assert r"\(\text{Row } i\)" not in repaired
    assert r"\text{Row } i" in repaired


def test_unbalanced_display_delimiter_is_closed():
    assert repair_math_delimiters(r"\[df=(R-1)(C-1)").endswith(r"\]")


def test_fenced_code_is_left_untouched():
    text = "```python\nprint('\\\\(')\n```\n" + r"\\(\chi^2\\)"
    repaired = repair_math_delimiters(text)
    assert "print('\\\\(')" in repaired
    assert r"\(\chi^2\)" in repaired


def test_empty_reply_is_unchanged():
    assert repair_math_delimiters("") == ""
