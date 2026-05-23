import cv2
import numpy as np

from utils.diagram_extractor import DiagramExtractor


def test_diagram_crop_excludes_separated_option_text(tmp_path):
    image = np.full((380, 320, 3), 255, np.uint8)
    cv2.line(image, (160, 40), (60, 240), (0, 0, 0), 2)
    cv2.line(image, (160, 40), (260, 240), (0, 0, 0), 2)
    cv2.line(image, (60, 240), (260, 240), (0, 0, 0), 2)
    cv2.line(image, (60, 280), (260, 280), (0, 0, 0), 2)
    cv2.putText(image, "2m", (145, 275), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.putText(image, "(a) 5 x 10^-7 T", (20, 325), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)

    image_path = tmp_path / "diagram_with_option.png"
    cv2.imwrite(str(image_path), image)

    diagrams = DiagramExtractor(str(image_path)).find_diagrams()

    assert diagrams
    x, y, w, h = diagrams[0]["bbox"]
    assert y + h < 305
    assert y + h > 240


def test_crop_left_edge_moves_past_option_marker_fragment(tmp_path):
    image = np.full((66, 147, 3), 255, np.uint8)
    cv2.putText(image, ")", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.line(image, (46, 7), (80, 7), (0, 0, 0), 2)
    cv2.line(image, (46, 7), (30, 33), (0, 0, 0), 2)
    cv2.line(image, (30, 33), (46, 59), (0, 0, 0), 2)
    cv2.line(image, (46, 59), (80, 59), (0, 0, 0), 2)
    cv2.line(image, (80, 7), (96, 33), (0, 0, 0), 2)
    cv2.line(image, (96, 33), (80, 59), (0, 0, 0), 2)
    cv2.putText(image, "OH", (118, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)

    image_path = tmp_path / "option_marker_fragment.png"
    cv2.imwrite(str(image_path), image)

    x, y, w, h = DiagramExtractor(str(image_path))._trim_left_option_marker((0, 0, 147, 66))

    assert x >= 27
    assert x <= 44
    assert w == 147 - x
    assert y == 0
    assert h == 66


def test_crop_left_edge_keeps_real_left_side_chemistry_text(tmp_path):
    image = np.full((63, 177, 3), 255, np.uint8)
    cv2.putText(image, "O2N", (31, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.line(image, (57, 6), (104, 6), (0, 0, 0), 2)
    cv2.line(image, (57, 6), (41, 31), (0, 0, 0), 2)
    cv2.line(image, (41, 31), (57, 56), (0, 0, 0), 2)
    cv2.line(image, (57, 56), (104, 56), (0, 0, 0), 2)
    cv2.line(image, (104, 6), (120, 31), (0, 0, 0), 2)
    cv2.line(image, (120, 31), (104, 56), (0, 0, 0), 2)
    cv2.putText(image, "OH", (149, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)

    image_path = tmp_path / "left_chemistry_text.png"
    cv2.imwrite(str(image_path), image)

    assert DiagramExtractor(str(image_path))._trim_left_option_marker((0, 0, 177, 63)) == (0, 0, 177, 63)


def test_extract_diagram_can_save_already_refined_chemistry_crop(tmp_path):
    image = np.full((260, 320, 3), 255, np.uint8)
    cv2.putText(image, "O2N", (62, 154), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.line(image, (108, 120), (155, 120), (0, 0, 0), 2)
    cv2.line(image, (108, 120), (92, 145), (0, 0, 0), 2)
    cv2.line(image, (92, 145), (108, 170), (0, 0, 0), 2)
    cv2.line(image, (108, 170), (155, 170), (0, 0, 0), 2)
    cv2.line(image, (155, 120), (171, 145), (0, 0, 0), 2)
    cv2.line(image, (171, 145), (155, 170), (0, 0, 0), 2)
    cv2.putText(image, "OH", (199, 152), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)

    image_path = tmp_path / "option_c_source.png"
    output_dir = tmp_path / "crops"
    cv2.imwrite(str(image_path), image)

    crop_path = DiagramExtractor(str(image_path)).extract_diagram((55, 112, 170, 70), str(output_dir), refine=False)

    crop = cv2.imread(crop_path, cv2.IMREAD_GRAYSCALE)
    left_substituent_dark = np.sum(crop[:, :45] < 220)
    structure_dark = np.sum(crop[:, 45:] < 220)
    assert left_substituent_dark > 25
    assert structure_dark > 100


def test_final_crop_removes_blank_margins_after_marker_cleanup(tmp_path):
    image = np.full((120, 220, 3), 255, np.uint8)
    cv2.line(image, (90, 30), (150, 30), (0, 0, 0), 2)
    cv2.line(image, (90, 30), (65, 70), (0, 0, 0), 2)
    cv2.line(image, (65, 70), (90, 100), (0, 0, 0), 2)
    cv2.line(image, (90, 100), (150, 100), (0, 0, 0), 2)
    cv2.line(image, (150, 30), (175, 70), (0, 0, 0), 2)
    cv2.line(image, (175, 70), (150, 100), (0, 0, 0), 2)

    image_path = tmp_path / "loose_diagram.png"
    cv2.imwrite(str(image_path), image)

    x, y, w, h = DiagramExtractor(str(image_path))._trim_blank_margins((0, 0, 220, 120))

    assert 55 <= x <= 65
    assert 20 <= y <= 30
    assert 112 <= w <= 130
    assert 78 <= h <= 90
