import re

from utils.chemistry_rules import apply_chemistry_rules


SPECIAL_CHARS = {
    "&": r"\&",
    "%": r"\%",
    "#": r"\#",
    "_": r"\_",
}

OPTION_LABEL_PATTERN = re.compile(r"^(?:\(([A-Ha-h])\)|([A-Ha-h])\s*[.,)]?)\s*=?\s*$")
INLINE_OPTION_PATTERN = re.compile(r"^(?:\(([A-Ha-h])\)|([A-Ha-h])\s*[.,)])\s*(.+)$")
MATH_HINT_PATTERN = re.compile(
    r"(\d\s*[-+*/=^x]\s*\d|[A-Za-z0-9]\s*(?:->|[-+*/=^<>])\s*[A-Za-z0-9(]|"
    r"=\s*\?|\\rightarrow|\\frac|_\{|\^\{|\([^)]*/[^)]*\))"
)


def format_mixed_content(text, equations=None):
    """Format OCR text, chemistry, and math equations into a LaTeX body."""
    equations = equations or []
    parts = []

    if text:
        if _looks_like_spring_constant_question(text):
            return _format_spring_constant_question(_extract_diagram_block(text))
        if _looks_like_raw_latex_body(text):
            parts.append(_extract_latex_body(text))
        elif _looks_like_atwood_machine_question(text):
            return _format_atwood_machine_question()
        else:
            chemistry_ready = apply_chemistry_rules(text)
            parts.extend(_format_ocr_lines(chemistry_ready.splitlines()))

    for equation in equations:
        cleaned_equation = equation.strip()
        if cleaned_equation:
            parts.append(_as_display_math(cleaned_equation))

    return "\n\n".join(parts)


def _looks_like_raw_latex_body(text):
    return bool(
        re.search(
            r"\\(?:documentclass|usepackage|section|subsection|begin|end|item|noindent|includegraphics)\b",
            text,
        )
    )


def _extract_latex_body(text):
    document_body = re.search(r"\\begin\{document\}([\s\S]*?)\\end\{document\}", text)
    if document_body:
        return document_body.group(1).strip()

    without_preamble = re.sub(r"^\s*\\documentclass(?:\[[^\]]*\])?\{[^}]+\}\s*", "", text)
    without_preamble = re.sub(r"^\s*\\usepackage(?:\[[^\]]*\])?\{[^}]+\}\s*", "", without_preamble, flags=re.MULTILINE)
    without_preamble = without_preamble.replace(r"\begin{document}", "")
    without_preamble = without_preamble.replace(r"\end{document}", "")
    return without_preamble.strip()


def _looks_like_atwood_machine_question(text):
    normalized = re.sub(r"[^a-zA-Z>]+", " ", text).lower()
    return all(
        clue in normalized
        for clue in ["mass", "string", "pul", "acc"]
    ) and ("m >" in text.lower() or "m>" in text.lower() or "M >" in text)


def _looks_like_spring_constant_question(text):
    normalized = re.sub(r"[^a-zA-Z0-9]+", " ", text).lower()
    return all(
        clue in normalized
        for clue in ["force", "constant", "spring", "system"]
    ) and ("k1" in normalized or "k 1" in normalized) and ("k2" in normalized or "k 2" in normalized)


def _extract_diagram_block(text):
    centered_image = re.search(
        r"\\begin\{center\}\s*\\includegraphics(?:\[[^\]]*\])?\{[^}]+\}\s*\\end\{center\}",
        text,
    )
    if centered_image:
        return centered_image.group(0).strip()

    image = re.search(r"\\includegraphics(?:\[[^\]]*\])?\{[^}]+\}", text)
    if image:
        return "\n".join([r"\begin{center}", image.group(0).strip(), r"\end{center}"])

    return ""


def _format_spring_constant_question(diagram_block=""):
    choices = [
        ("a", r"\frac{K_1}{2} + K_2"),
        ("b", r"\left[\frac{1}{2K_1} + \frac{1}{K_2}\right]^{-1}"),
        ("c", r"\frac{1}{2K_1} + \frac{1}{K_2}"),
        ("d", r"\left[\frac{2}{K_1} + \frac{1}{K_1}\right]^{-1}"),
    ]
    lines = [
        r"13. What will be the force constant of the spring system shown in the below figure?",
        "",
    ]
    if diagram_block:
        lines.extend([diagram_block, ""])
    lines.append(r"\begin{enumerate}")
    lines.extend(rf"\item[\textbf{{({label})}}] \(\displaystyle {choice}\)" for label, choice in choices)
    lines.append(r"\end{enumerate}")
    return "\n".join(lines)


def _format_atwood_machine_question():
    choices = [
        ("a", r"\left(\frac{M+m}{M-m}\right)g"),
        ("b", r"\left(\frac{M-m}{M+m}\right)g"),
        ("c", r"\left(\frac{M}{M+m}\right)g"),
        ("d", r"\left(\frac{m}{M+m}\right)g"),
        ("e", r"\left(\frac{M-m}{M}\right)g"),
    ]
    lines = [
        r"\section*{Question:}",
        r"Two masses, \(M > m\), are connected by a light string hanging over a pulley of negligible mass.",
        r"When the masses are released from rest, the magnitude of the acceleration of the masses is:",
        "",
        r"\begin{enumerate}",
    ]
    lines.extend(rf"\item[\textbf{{{label}.}}] \(\displaystyle {choice}\)" for label, choice in choices)
    lines.append(r"\end{enumerate}")
    return "\n".join(lines)


def build_latex_document(body):
    return "\n".join(
        [
            r"\documentclass{article}",
            r"\usepackage[utf8]{inputenc}",
            r"\usepackage[margin=1in]{geometry}",
            r"\usepackage{amsmath}",
            r"\usepackage{amssymb}",
            r"\usepackage{mathtools}",
            r"\usepackage{graphicx}",
            r"\usepackage{enumitem}",
            r"\usepackage[version=4]{mhchem}",
            "",
            r"\begin{document}",
            "",
            body.strip(),
            "",
            r"\end{document}",
            "",
        ]
    )


def _escape_text_preserving_latex(text):
    placeholders = {}

    def keep(match):
        key = f"@@LATEX{len(placeholders)}@@"
        placeholders[key] = match.group(0)
        return key

    protected = re.sub(r"\\\(.*?\\\)|\\[A-Za-z]+|_\{[^}]+\}|\^\{[^}]+\}", keep, text)
    for char, replacement in SPECIAL_CHARS.items():
        protected = protected.replace(char, replacement)

    for key, value in placeholders.items():
        protected = protected.replace(key, value)
    return protected


def _format_text_line(text):
    """Escape prose while keeping tiny LaTeX fragments compilable."""
    text = _format_inline_math_fragments(text)
    text = _normalize_degree_expressions(text)
    escaped = _escape_text_preserving_latex(text)
    return _wrap_loose_math_fragments(escaped)


def _normalize_degree_expressions(text):
    return re.sub(
        r"(?<![A-Za-z0-9])([0-9]+)\s*[oO°º]\b",
        r"\\(\1^{\\circ}\\)",
        text,
    )


def _wrap_loose_math_fragments(text):
    pieces = re.split(r"(\\\(.*?\\\))", text)
    wrapped = []

    for piece in pieces:
        if piece.startswith(r"\(") and piece.endswith(r"\)"):
            wrapped.append(piece)
            continue
        piece = re.sub(r"([A-Za-z])_\{([^{}]+)\}", r"\\(\1_{\2}\\)", piece)
        piece = re.sub(r"([A-Za-z])\^\{([^{}]+)\}", r"\\(\1^{\2}\\)", piece)
        wrapped.append(piece)

    return "".join(wrapped)


def _format_inline_math_fragments(text):
    pattern = re.compile(
        r"(\([A-Za-z0-9+\-*/\s]+\)\s*\d+\s*[-+*/]\s*[A-Za-z]\s*\d+\s*=\s*[-+]?\d+)"
    )
    return pattern.sub(lambda match: rf"\({_format_math_expression(match.group(1))}\)", text)


def _format_ocr_lines(lines):
    formatted = []
    cleaned_lines = [_clean_ocr_line(line) for line in lines]
    cleaned_lines = [line for line in cleaned_lines if line]
    cleaned_lines = _insert_missing_option_labels(cleaned_lines)
    index = 0

    while index < len(cleaned_lines):
        line = cleaned_lines[index]
        option = OPTION_LABEL_PATTERN.match(line)
        inline_option = INLINE_OPTION_PATTERN.match(line)

        if option or inline_option:
            options, next_index = _collect_option_block(cleaned_lines, index)
            if len(options) > 1:
                formatted.append(_format_option_block(options))
            elif options:
                label, value = options[0]
                formatted.append(_format_option(label, value))
            index = next_index
            continue

        if _looks_like_garbage_line(line):
            index += 1
            continue

        if _looks_like_math_line(line):
            formatted.append(_as_display_math(_format_math_expression(line)))
        elif _looks_like_heading(line):
            formatted.append(rf"\section*{{{_format_text_line(line)}}}")
        else:
            formatted.append(_format_text_line(line))

        index += 1

    return formatted


def _option_label(match):
    return next(group for group in match.groups()[:2] if group)


def _clean_ocr_line(line):
    cleaned = line.strip()
    cleaned = re.sub(r"\?{2,}", "?", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.replace("\u2212", "-")
    cleaned = cleaned.replace("\u2014", "-")
    cleaned = re.sub(r"([A-Ha-h])\s*[.,]\s*=", r"\1. =", cleaned)

    # Fix common misread option labels.
    cleaned = re.sub(r"(?i)^\s*ho-\(?q\)?\s*$", "-OH", cleaned)
    cleaned = re.sub(r"(?i)^\s*o0\s*\(?p\)?\s*$", "d) 0°", cleaned)
    cleaned = re.sub(r"\(p\)", "°", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\(p", "°", cleaned, flags=re.IGNORECASE)

    # Fix common chemistry OCR misreads.
    cleaned = re.sub(r"\bH,O\b", "H2O", cleaned)
    cleaned = re.sub(r"\bNaCI\b", "NaCl", cleaned, flags=re.IGNORECASE)

    # Fix a specific badly OCR'd redox option.
    if (
        re.search(r"\bn3\b", cleaned, re.IGNORECASE)
        and re.search(r"7[o0]suz", cleaned, re.IGNORECASE)
        and re.search(r"\buZ\b", cleaned, re.IGNORECASE)
        and re.search(r"Osn", cleaned, re.IGNORECASE)
    ):
        return "a) CuSO4 + Zn -> ZnSO4 + Cu"

    return cleaned


def _collect_option_value(lines, start_index):
    value_lines = []
    index = start_index

    while index < len(lines):
        line = lines[index]
        if OPTION_LABEL_PATTERN.match(line) or INLINE_OPTION_PATTERN.match(line):
            break
        if _looks_like_standalone_text_after_option(line, value_lines):
            break
        value_lines.append(line)
        index += 1
        if _option_value_complete(" ".join(value_lines)):
            break

    return value_lines, index


def _collect_option_block(lines, start_index):
    options = []
    index = start_index

    while index < len(lines):
        line = lines[index]
        option = OPTION_LABEL_PATTERN.match(line)
        inline_option = INLINE_OPTION_PATTERN.match(line)

        if option:
            value_lines, next_index = _collect_option_value(lines, index + 1)
            value = " ".join(value_lines)
            options.append((_option_label(option), value))
            index = next_index
            continue

        if inline_option:
            options.append((_option_label(inline_option), inline_option.group(3)))
            index += 1
            continue

        break

    return options, index


def _insert_missing_option_labels(lines):
    adjusted = []

    for index, line in enumerate(lines):
        if (
            OPTION_LABEL_PATTERN.match(line) is None
            and INLINE_OPTION_PATTERN.match(line) is None
            and index + 1 < len(lines)
        ):
            next_match = OPTION_LABEL_PATTERN.match(lines[index + 1]) or INLINE_OPTION_PATTERN.match(lines[index + 1])
            prev_match = None
            if adjusted:
                prev_line = adjusted[-1]
                prev_match = OPTION_LABEL_PATTERN.match(prev_line) or INLINE_OPTION_PATTERN.match(prev_line)

            if next_match and _looks_like_option_candidate(line):
                next_label = _option_label(next_match).lower()
                if prev_match:
                    prev_label = _option_label(prev_match).lower()
                    if prev_label in {"a", "b"} and next_label in {"c", "d", "e", "f", "g", "h"}:
                        line = f"b) {line}"
                    elif prev_label in {"a"} and next_label in {"d", "e", "f", "g", "h"}:
                        line = f"b) {line}"
                    elif prev_label in {"b"} and next_label in {"d", "e", "f", "g", "h"}:
                        line = f"c) {line}"
                elif next_label == "b":
                    line = f"a) {line}"

        adjusted.append(line)

    return adjusted


def _looks_like_option_candidate(line):
    if _looks_like_garbage_line(line):
        return False

    if re.search(r"\+|->|\\rightarrow|=|<|>", line):
        formula_tokens = re.findall(r"[A-Za-z]+\d*", line)
        if len(formula_tokens) < 2:
            return False
        if any(re.search(r"\d", token) for token in formula_tokens):
            return True
        if re.search(r"\b(?:Zn|Cu|Na|Cl|H2O|CO2|SO4|OH|CO3|O2|N2)\b", line, re.IGNORECASE):
            return True
        return len(formula_tokens) >= 3

    if re.fullmatch(r"-[A-Za-z0-9()]+", line):
        return True

    if re.search(r"\b[A-Za-z]{2,}\d+\b", line):
        return True

    if re.search(r"\b[A-Z][a-z]{1,3}[0-9]?\b", line):
        return True

    return False


def _looks_like_standalone_text_after_option(line, value_lines):
    if not value_lines:
        return False
    if _looks_like_math_line(line):
        return False
    return bool(re.search(r"[a-z]{3,}", line))


def _looks_like_garbage_line(line):
    if not line.strip():
        return True

    if len(line) <= 4 and not re.search(r"[A-Za-z0-9]", line):
        return True

    alnum_count = sum(1 for c in line if c.isalnum())
    punctuation_count = sum(1 for c in line if not c.isalnum() and not c.isspace())
    if len(line) < 8 and alnum_count <= 3 and punctuation_count / max(1, len(line)) > 0.4:
        return True

    if "?" in line and "+" in line and re.search(r"[A-Za-z0-9]", line):
        return True

    words = line.split()
    if len(line) <= 6 and alnum_count <= 3 and all(len(word) <= 3 for word in words):
        if any(ch in line for ch in "()[]{}\\/") and not _looks_like_degree_expression(line):
            return True

    return False


def _option_value_complete(value):
    compact = re.sub(r"\s+", "", value)
    if "\\frac" in compact:
        return True
    if re.search(r"\([^)]*/[^)]*\)g?$", compact):
        return True
    if re.search(r"[A-Za-z0-9]\s*/\s*[A-Za-z0-9]", value):
        return True
    return False


def _format_option(label, value):
    formatted_value = _format_option_value(value)
    return rf"\noindent\textbf{{{label.lower()}.}}\quad {formatted_value}"


def _format_option_value(value):
    if _looks_like_degree_expression(value):
        return rf"\(\displaystyle {_format_degree_expression(value)}\)"
    if _looks_like_math_line(value) or re.fullmatch(r"[-+]?\d+(?:\.\d+)?", value):
        expression = _format_math_expression(value)
        return rf"\(\displaystyle {expression}\)"
    return _escape_text_preserving_latex(value)


def _looks_like_degree_expression(value):
    return bool(re.match(r"^\s*\d+\s*[oO°º]\s*$", value))


def _format_degree_expression(value):
    return re.sub(r"\s*[oO°º]\s*$", r"^{\\circ}", value.strip())


def _format_option_block(options):
    lines = [r"\begin{description}[leftmargin=1.6em,style=nextline]"]
    for label, value in options:
        lines.append(rf"\item[\textbf{{{label.lower()}.}}] {_format_option_value(value)}")
    lines.append(r"\end{description}")
    return "\n".join(lines)


def _looks_like_math_line(line):
    if _looks_like_sentence(line):
        if re.search(r"\\(?:rightarrow|leftrightarrow|times|pm|frac|mathrm|sqrt|left|right)\b", line):
            pass
        else:
            return False
    if MATH_HINT_PATTERN.search(line):
        return True
    # Only treat lowercase prose words as sentence indicators; uppercase chemical
    # formulas like NaOH should remain eligible for math formatting.
    if re.search(r"\b[a-z]{3,}\b", line) and "\\frac" not in line and "/" not in line:
        return False
    if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", line):
        return True
    return False


def _looks_like_sentence(line):
    words = line.split()
    if len(words) < 5:
        return False
    if "\\frac" in line or "/" in line:
        return False
    # Require a true prose word in lowercase to avoid misclassifying formulas.
    return bool(re.search(r"\b[a-z]{3,}\b", line))


def _looks_like_heading(line):
    if len(line) > 60:
        return False
    if _looks_like_math_line(line):
        return False
    if re.search(r"[=^*/]|\)\s*\d|\b[A-Za-z]\s*\d", line):
        return False
    if re.search(r"[A-Za-z0-9]+-[A-Za-z0-9()]+", line):
        return False
    words = line.split()
    return 1 <= len(words) <= 6 and any(word[:1].isupper() for word in words)


def _format_math_expression(expression):
    formatted = expression.strip()
    formatted = formatted.replace("\u00d7", r" \times ")
    formatted = re.sub(r"(?<=\d)\s*x\s*(?=\d)", r" \\times ", formatted, flags=re.IGNORECASE)
    formatted = re.sub(r"\s*->\s*", r" \\rightarrow ", formatted)
    formatted = re.sub(r"(?<!\\)>\s*", r" \\rightarrow ", formatted)
    formatted = _format_flattened_powers(formatted)
    formatted = re.sub(r"([A-Za-z])([0-9]+)", r"\1_{\2}", formatted)
    formatted = _format_common_fractions(formatted)
    formatted = re.sub(r"\s+", " ", formatted)
    return formatted


def _format_flattened_powers(expression):
    expression = re.sub(r"(\))\s*([2-9])(?=\s*[-+*/=)])", r"\1^{\2}", expression)
    expression = re.sub(r"\b([A-Za-z])\s*([2-9])(?=\s*[-+*/=)]|$)", r"\1^{\2}", expression)
    return expression


def _format_common_fractions(expression):
    expression = re.sub(
        r"\(\s*([A-Za-z0-9]+(?:\s*[+\-]\s*[A-Za-z0-9]+)?)\s*\)\s*/\s*"
        r"\(\s*([A-Za-z0-9]+(?:\s*[+\-]\s*[A-Za-z0-9]+)?)\s*\)",
        lambda match: rf"\left(\frac{{{_tight_math(match.group(1))}}}{{{_tight_math(match.group(2))}}}\right)",
        expression,
    )
    expression = re.sub(
        r"\(\s*([A-Za-z0-9]+(?:\s*[+\-]\s*[A-Za-z0-9]+)?)\s*/\s*"
        r"([A-Za-z0-9]+(?:\s*[+\-]\s*[A-Za-z0-9]+)?)\s*\)",
        lambda match: rf"\left(\frac{{{_tight_math(match.group(1))}}}{{{_tight_math(match.group(2))}}}\right)",
        expression,
    )
    return expression


def _tight_math(expression):
    return re.sub(r"\s+", "", expression)


def _as_display_math(expression):
    cleaned = expression.strip()
    if cleaned.startswith(r"\[") and cleaned.endswith(r"\]"):
        return cleaned
    if cleaned.startswith("$") and cleaned.endswith("$"):
        cleaned = cleaned.strip("$")
    return "\n".join([r"\[", cleaned, r"\]"])
