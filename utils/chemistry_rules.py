import re

STATE_PATTERN = re.compile(r"([A-Za-z][A-Za-z0-9]*(?:\^[0-9]+[+-]?)?)\((aq|s|l|g)\)")
FORMULA_PATTERN = re.compile(r"(?<![A-Za-z0-9])(?:[A-Z][a-z]?\d*|\([A-Za-z0-9]+\)\d*)+(?:\^[0-9]+[+-]?)?(?![A-Za-z0-9])")


def apply_chemistry_rules(text):
    """Convert common chemistry notation into LaTeX-friendly notation."""
    if not text:
        return ""

    converted = text
    converted = converted.replace("<->", r"\leftrightarrow")
    converted = converted.replace("->", r"\rightarrow")
    converted = converted.replace("=>", r"\rightarrow")

    converted = STATE_PATTERN.sub(lambda match: f"{_format_formula(match.group(1))}_{{({match.group(2)})}}", converted)
    converted = FORMULA_PATTERN.sub(lambda match: _format_formula(match.group(0)), converted)
    return converted


def _format_formula(formula):
    if not _looks_like_chemical_formula(formula):
        return formula

    charge = ""
    base = formula
    if "^" in formula:
        base, charge = formula.split("^", 1)

    formatted = re.sub(r"([A-Za-z\)])(\d+)", r"\1_{\2}", base)
    if charge:
        formatted = f"{formatted}^{{{charge}}}"
    return formatted


def _looks_like_chemical_formula(value):
    if len(value) < 2:
        return False
    if not re.search(r"[A-Z]", value):
        return False
    if re.fullmatch(r"[A-Z][a-z]+", value):
        return False
    return bool(re.search(r"\d|\^|[A-Z].*[A-Z]|\(|\)", value))
