from utils.latex_formatter import build_latex_document, format_mixed_content
import cv2
import numpy as np

from app import clean_option_label_from_crop, format_option_tail_text, insert_diagrams, reorder_diagram_outputs


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


def test_mangled_scientific_option_a_is_repaired():
    body = format_mixed_content(
        "\n".join(
            [
                "43. A current of 1 A is flowing in the sides of an",
                "equilateral triangle of side 2 m. The magnetic",
                "field at the centroid of the triangle is [See figure]",
                "[a} 5XiU :1",
                "(b) 2.4 x 10-6 T",
                "(c) 9 x 10-7T",
                "(d) 1.6 10-4 T",
            ]
        )
    )

    assert r"\item[\textbf{a.}] \(\displaystyle 5 \times 10^{-7} T\)" in body
    assert r"\item[\textbf{b.}] \(\displaystyle 2.4 \times 10^{-6} T\)" in body
    assert r"\item[\textbf{c.}] \(\displaystyle 9 \times 10^{-7}T\)" in body
    assert r"\item[\textbf{d.}] \(\displaystyle 1.6 \times 10^{-4} T\)" in body


def test_resistance_options_keep_missing_omega_units():
    body = format_mixed_content(
        "\n".join(
            [
                "44. In the below figure, the ammeter reads 5 A and",
                "voltmeter reads 50 V. The actual resistance R",
                "is",
                "(a) 10",
                "(b) greater than 10",
                "(c) less than 10",
                "(d) none of the above",
            ]
        )
    )

    assert r"\item[\textbf{a.}] \(\displaystyle 10\Omega\)" in body
    assert r"\item[\textbf{b.}] greater than \(10\Omega\)" in body
    assert r"\item[\textbf{c.}] less than \(10\Omega\)" in body


def test_multiple_diagrams_are_inserted_before_matching_option_blocks():
    body = "\n\n".join(
        [
            "43. Question body",
            r"\begin{description}[leftmargin=1.6em,style=nextline]",
            r"\item[\textbf{a.}] A",
            r"\end{description}",
            "44. Question body",
            r"\begin{description}[leftmargin=1.6em,style=nextline]",
            r"\item[\textbf{a.}] B",
            r"\end{description}",
        ]
    )

    updated = insert_diagrams(body, ["DIAGRAM_ONE", "DIAGRAM_TWO"])

    assert updated.index("DIAGRAM_ONE") < updated.index(r"\item[\textbf{a.}] A")
    assert updated.index("DIAGRAM_TWO") < updated.index(r"\item[\textbf{a.}] B")
    assert updated.index("DIAGRAM_ONE") < updated.index("44. Question body")


def test_option_diagrams_are_placed_inside_matching_options():
    body = "\n\n".join(
        [
            "77. What are organic products formed in the following reaction?",
            r"\begin{description}[leftmargin=1.6em,style=nextline]",
            r"\item[\textbf{b.}]",
            r"\item[\textbf{a.}] HOHC",
            r"\item[\textbf{c.}]",
            r"\item[\textbf{h.}]",
            r"\end{description}",
        ]
    )
    diagrams = ["REACTION", "OPT_A", "OPT_B", "OPT_C", "OPT_D"]
    manifest = [
        {"associated_option": None},
        {"associated_option": "A", "option_text": r"and \(CH_{4}\)"},
        {"associated_option": "B", "option_text": r"and \(CH_{3}OH\)"},
        {"associated_option": "C", "option_text": r"and \(CH_{3}OH\)"},
        {"associated_option": "D", "option_text": r"and \(CH_{4}\)"},
    ]

    updated = insert_diagrams(body, diagrams, manifest)

    assert updated.index("REACTION") < updated.index(r"\begin{description}")
    assert r"\item[\textbf{a.}]" in updated
    assert r"\item[\textbf{d.}]" in updated
    assert updated.index("OPT_A") < updated.index("OPT_B") < updated.index("OPT_C") < updated.index("OPT_D")
    assert "HOHC" not in updated
    assert r"and \(CH_{3}OH\)" in updated


def test_option_cell_tail_ocr_cleanup_for_small_chemistry_text():
    assert format_option_tail_text("and CH.") == r"and \(CH_{4}\)"
    assert format_option_tail_text("and CH;OH") == r"and \(CH_{3}OH\)"
    assert format_option_tail_text("and CH,OH") == r"and \(CH_{3}OH\)"


def test_option_diagram_outputs_are_reordered_by_labels_for_display():
    blocks = ["A_IMG", "B_IMG", "D_IMG", "C_IMG"]
    urls = ["a.png", "b.png", "d.png", "c.png"]
    manifest = [
        {"associated_option": "A", "position_order": 1},
        {"associated_option": "B", "position_order": 2},
        {"associated_option": "D", "position_order": 3},
        {"associated_option": "C", "position_order": 4},
    ]

    new_blocks, new_urls, new_manifest = reorder_diagram_outputs(blocks, urls, manifest)

    assert new_blocks == ["A_IMG", "B_IMG", "C_IMG", "D_IMG"]
    assert new_urls == ["a.png", "b.png", "c.png", "d.png"]
    assert [item["associated_option"] for item in new_manifest] == ["A", "B", "C", "D"]
    assert [item["position_order"] for item in new_manifest] == [1, 2, 3, 4]


def test_option_label_is_removed_from_saved_crop_without_erasing_structure_text(tmp_path):
    image = np.full((90, 180, 3), 255, np.uint8)
    cv2.putText(image, "(c)", (5, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.putText(image, "O2N", (31, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2, cv2.LINE_AA)
    image_path = tmp_path / "option_crop.png"
    cv2.imwrite(str(image_path), image)

    assert clean_option_label_from_crop(image_path)

    cleaned = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    label_dark = np.sum(cleaned[25:65, 0:30] < 220)
    substituent_dark = np.sum(cleaned[20:65, 31:90] < 220)
    assert label_dark < 12
    assert substituent_dark > 25


def test_right_parenthesis_fragment_is_removed_from_option_crop(tmp_path):
    image = np.full((66, 147, 3), 255, np.uint8)
    cv2.putText(image, ")", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.line(image, (46, 7), (80, 7), (0, 0, 0), 2)
    cv2.line(image, (46, 7), (30, 33), (0, 0, 0), 2)
    cv2.line(image, (30, 33), (46, 59), (0, 0, 0), 2)
    cv2.line(image, (46, 59), (80, 59), (0, 0, 0), 2)
    cv2.line(image, (80, 7), (96, 33), (0, 0, 0), 2)
    cv2.line(image, (96, 33), (80, 59), (0, 0, 0), 2)
    cv2.putText(image, "OH", (118, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)
    image_path = tmp_path / "option_crop_fragment.png"
    cv2.imwrite(str(image_path), image)

    assert clean_option_label_from_crop(image_path)

    cleaned = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    label_dark = np.sum(cleaned[20:45, 15:28] < 220)
    structure_dark = np.sum(cleaned[:, 40:145] < 220)
    assert label_dark < 3
    assert structure_dark > 100
