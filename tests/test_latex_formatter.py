from utils.latex_formatter import build_latex_document, format_mixed_content


def test_build_document_uses_math_friendly_packages():
    document = build_latex_document("x")

    assert r"\usepackage[margin=1in]{geometry}" in document
    assert r"\usepackage{mathtools}" in document
    assert r"\usepackage[version=4]{mhchem}" in document


def test_multiple_choice_physics_fraction_is_display_sized():
    text = "\n".join(
        [
            "Question:",
            "Two masses, M > m, are connected by a light string.",
            "a.",
            "(M + m)/(M - m) g",
            "b.",
            "(M - m)/(M + m) g",
        ]
    )

    body = format_mixed_content(text)

    assert r"\begin{description}" in body
    assert r"\item[\textbf{a.}] \(\displaystyle \left(\frac{M+m}{M-m}\right) g\)" in body
    assert r"\item[\textbf{b.}] \(\displaystyle \left(\frac{M-m}{M+m}\right) g\)" in body
    assert "Two masses, M > m, are connected by a light string." in body
    assert "\\[\nTwo masses, M > m, are connected by a light string.\n\\]" not in body


def test_degree_options_are_converted_and_trailing_garbage_is_removed():
    text = "\n".join([
        "21. What is the critical angle for total internal reflection?",
        "a. 90o",
        "b. 60o",
        "c. 45o",
        "o0 (p",
    ])
    body = format_mixed_content(text)

    assert r"\item[\textbf{a.}] \(\displaystyle 90^{\circ}\)" in body
    assert r"\item[\textbf{b.}] \(\displaystyle 60^{\circ}\)" in body
    assert r"\item[\textbf{c.}] \(\displaystyle 45^{\circ}\)" in body
    assert r"\item[\textbf{d.}] \(\displaystyle 0^{\circ}\)" in body
    assert "o0 (p" not in body

def test_chemical_option_with_ocr_misread_does_not_become_heading():
    text = "\n".join([
        "18. What is the functional group of alcohols?",
        "a) -COOH",
        "HO-(q",
        "c) -CHO",
        "d) -NH2",
    ])
    body = format_mixed_content(text)

    assert r"\item[\textbf{a.}] -COOH" in body
    assert r"\item[\textbf{b.}] -OH" in body
    assert r"HO-(q" not in body
    assert r"\item[\textbf{c.}] -CHO" in body
    assert r"\item[\textbf{d.}] \(\displaystyle -NH_{2}\)" in body


def test_redox_question_with_corrupted_first_option_is_corrected():
    text = "\n".join([
        "28. Which of the following is a redox reaction?",
        "n3 + 70suz uZ + 'Osn? (e",
        "b) NaOH + HCl -> NaCl + H2O",
        "c) CaCO3 -> CaO + CO2",
        "d) 2Na + Cl2 -> 2NaCl",
    ])
    body = format_mixed_content(text)

    assert r"\item[\textbf{a.}] \(\displaystyle CuSO_{4} + Zn \rightarrow ZnSO_{4} + Cu\)" in body
    assert r"\item[\textbf{b.}] \(\displaystyle NaOH + HCl \rightarrow NaCl + H_{2}O\)" in body
    assert r"\item[\textbf{c.}] \(\displaystyle CaCO_{3} \rightarrow CaO + CO_{2}\)" in body
    assert r"\item[\textbf{d.}] \(\displaystyle 2Na + Cl_{2} \rightarrow 2NaCl\)" in body


def test_redox_question_with_garbage_water_and_na_ci_is_corrected():
    text = "\n".join([
        "28. Which of the following is a redox reaction?",
        "n3 + 70suz uZ + 'Osn? (e",
        "b) NaOH + HCl -> NaCl + H,O",
        "c) CaCO3 -> CaO + CO2",
        "d) 2Na + Cl2 -> 2NaCl",
    ])
    body = format_mixed_content(text)

    assert r"\item[\textbf{a.}] \(\displaystyle CuSO_{4} + Zn \rightarrow ZnSO_{4} + Cu\)" in body
    assert r"\item[\textbf{b.}] \(\displaystyle NaOH + HCl \rightarrow NaCl + H_{2}O\)" in body
    assert r"\item[\textbf{c.}] \(\displaystyle CaCO_{3} \rightarrow CaO + CO_{2}\)" in body
    assert r"\item[\textbf{d.}] \(\displaystyle 2Na + Cl_{2} \rightarrow 2NaCl\)" in body


def test_atwood_machine_question_is_repaired_from_noisy_ocr():
    noisy_text = "\n".join(
        [
            "Question:",
            "Two masscs, M > , arc connccted by a light string hanging over a pullcy of ncgligiblc mass",
            "Whcn thc masscs arc rclcascd from rest, thc magnitudc of thc acccleration is:",
            "( M + m",
            "a. M - m M - mn",
        ]
    )

    body = format_mixed_content(noisy_text)

    assert r"Two masses, \(M > m\), are connected" in body
    assert r"\item[\textbf{b.}] \(\displaystyle \left(\frac{M-m}{M+m}\right)g\)" in body
    assert r"\item[\textbf{e.}] \(\displaystyle \left(\frac{M-m}{M}\right)g\)" in body


def test_standalone_equations_use_display_math_blocks():
    body = format_mixed_content("F = ma")

    assert body == "\\[\nF = ma\n\\]"


def test_flattened_powers_are_restored_in_inline_equations():
    body = format_mixed_content(
        "Equation of (x+1)2-x2=0 has number of\nreal roots equal to:\n(a) 1"
    )

    assert r"Equation of \((x+1)^{2}-x^{2}=0\) has number of" in body
    assert r"\textbf{a.}" in body
    assert r"\(\displaystyle 1\)" in body


def test_multiline_text_option_stays_in_same_choice():
    body = format_mixed_content(
        "\n".join(
            [
                "28. The central fringe is then",
                "(a) always bright",
                "(b) always dark",
                "(c) either dark or bright depending on the",
                "position of S",
                "(d) neither dark nor bright",
            ]
        )
    )

    assert r"\item[\textbf{c.}] either dark or bright depending on the position of S" in body
    assert r"\section*{position of S}" not in body


def test_missing_omega_symbol_is_repaired_in_resistor_question():
    body = format_mixed_content(
        "\n".join(
            [
                "41. If current through 3 resistor in the",
                "figure is 0.8 A, then potential drop",
                "across 4",
                "resistor is",
                "(a) 9.6 V",
            ]
        )
    )

    assert r"through \(3\Omega\) resistor" in body
    assert r"across \(4\Omega\)" in body
