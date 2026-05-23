import os
import json
import shutil
import subprocess
import sys
import threading
import webbrowser
import zipfile
import re
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

from services.math_service import extract_math
from services.ocr_service import extract_text
from utils.database import init_db, save_history
from utils.diagram_extractor import DiagramExtractor
from utils.latex_formatter import build_latex_document, format_mixed_content

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}
UPLOAD_EXPIRATION_SECONDS = 900

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-me")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def is_optional_math_error(error):
    message = str(error).lower()
    return (
        "shm.dll" in message
        or "specified procedure could not be found" in message
        or ("error loading" in message and "torch" in message)
        or "height and width must be > 0" in message
    )


def delete_file_quietly(path):
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def cleanup_old_uploads():
    expiration = datetime.utcnow() - timedelta(seconds=UPLOAD_EXPIRATION_SECONDS)
    for path in UPLOAD_DIR.iterdir():
        if path.is_file():
            try:
                if datetime.utcfromtimestamp(path.stat().st_mtime) < expiration:
                    delete_file_quietly(path)
            except OSError:
                pass


def make_output_project(stem):
    project_id = secure_filename(stem) or uuid4().hex
    project_dir = OUTPUT_DIR / project_id
    if project_dir.exists():
        project_id = f"{project_id}_{uuid4().hex[:8]}"
        project_dir = OUTPUT_DIR / project_id

    images_dir = project_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    return project_id, project_dir, images_dir


def copy_image_to_project(source_path, images_dir, preferred_name):
    image_name = secure_filename(preferred_name) or f"diagram_{uuid4().hex}.png"
    target_path = images_dir / image_name
    if target_path.exists():
        target_path = images_dir / f"{target_path.stem}_{uuid4().hex[:8]}{target_path.suffix}"

    shutil.copy2(source_path, target_path)
    return target_path


def make_diagram_latex(image_filename):
    return "\n".join(
        [
            r"\begin{center}",
            rf"\includegraphics[width=0.55\textwidth]{{images/{image_filename}}}",
            r"\end{center}",
        ]
    )


def make_diagram_manifest_entry(diagram_id, question_label, option_label, position_order, image_filename, bbox):
    return {
        "diagram_id": diagram_id,
        "associated_question": question_label,
        "associated_option": option_label,
        "position_order": position_order,
        "cropped_image_reference": f"images/{image_filename}",
        "bbox": [int(value) for value in bbox],
    }


def attach_option_grid_metadata(manifest, image_path, project_dir):
    if len(manifest) < 4:
        return manifest

    option_items = manifest[1:5] if len(manifest) >= 5 else manifest[:4]
    rows = cluster_by_center(option_items, axis="y")
    if len(rows) != 2 or any(len(row) != 2 for row in rows):
        return manifest

    labeled_options = label_option_diagram_crops(option_items, project_dir)
    if set(labeled_options) == {"A", "B", "C", "D"}:
        ordered_options = [labeled_options[label] for label in ["A", "B", "C", "D"]]
    else:
        ordered_options = []
        for row in rows:
            ordered_options.extend(sorted(row, key=lambda item: item["_center_x"]))

    question_label = manifest[0].get("associated_question", "Question 1")
    if len(manifest) == 4:
        question_label = "Question 1"

    for label, item in zip(["A", "B", "C", "D"], ordered_options):
        item["associated_question"] = question_label
        item["associated_option"] = label
        item["option_text"] = extract_option_cell_tail_text(image_path, item, ordered_options, project_dir)
        clean_option_label_from_crop(project_dir / item["cropped_image_reference"])

    return manifest


def label_option_diagram_crops(option_items, project_dir):
    labeled = {}
    for item in option_items:
        label = detect_option_label_from_crop(project_dir / item["cropped_image_reference"])
        if label in {"A", "B", "C", "D"} and label not in labeled:
            labeled[label] = item
    return labeled


def detect_option_label_from_crop(crop_path):
    try:
        text = extract_text(crop_path)
    except Exception:
        return ""

    match = re.search(r"\(?\s*([A-Da-d])\s*\)?", text)
    return match.group(1).upper() if match else ""


def clean_option_label_from_crop(crop_path):
    try:
        import cv2
        import numpy as np

        image = cv2.imread(str(crop_path))
        if image is None:
            return False

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        dark = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY_INV)[1]
        component_count, labels, stats, _centroids = cv2.connectedComponentsWithStats(dark, 8)
        height, width = gray.shape[:2]
        cleaned = False

        for component_id in range(1, component_count):
            x, y, w, h, area = stats[component_id]
            right = x + w
            if not _looks_like_option_label_component(x, y, w, h, area, width, height, right):
                continue

            pad = max(2, width // 80)
            cv2.rectangle(
                image,
                (max(0, x - pad), max(0, y - pad)),
                (min(width, right + pad), min(height, y + h + pad)),
                (255, 255, 255),
                -1,
            )
            cleaned = True

        if cleaned:
            cv2.imwrite(str(crop_path), image)
        return cleaned
    except Exception:
        return False


def _looks_like_option_label_component(x, y, w, h, area, image_width, image_height, right):
    if area < 4:
        return False
    left_zone = x < image_width * 0.18 and right < image_width * 0.24
    compact = w <= image_width * 0.25 and h <= image_height * 0.60
    label_sized = area <= image_width * image_height * 0.08
    not_top_substituent = y > image_height * 0.18
    return left_zone and compact and label_sized and not_top_substituent


def cluster_by_center(items, axis):
    center_key = f"_center_{axis}"
    for item in items:
        x, y, w, h = item["bbox"]
        item["_center_x"] = x + (w / 2)
        item["_center_y"] = y + (h / 2)

    sorted_items = sorted(items, key=lambda item: item[center_key])
    clusters = []
    threshold = max(18, sum(item["bbox"][3 if axis == "y" else 2] for item in sorted_items) / max(1, len(sorted_items)) * 0.7)
    for item in sorted_items:
        if not clusters or abs(item[center_key] - clusters[-1][0][center_key]) > threshold:
            clusters.append([item])
        else:
            clusters[-1].append(item)
    return clusters


def extract_option_cell_tail_text(image_path, option_item, option_items, project_dir):
    try:
        import cv2

        image = cv2.imread(str(image_path))
        if image is None:
            return ""

        height, width = image.shape[:2]
        x, y, w, h = option_item["bbox"]
        center_x = option_item["_center_x"]
        center_y = option_item["_center_y"]

        same_row = [item for item in option_items if abs(item["_center_y"] - center_y) < max(20, h * 0.8)]
        same_col = [item for item in option_items if abs(item["_center_x"] - center_x) < max(20, w * 0.8)]

        row_left = min(item["bbox"][0] for item in same_row)
        row_right = max(item["bbox"][0] + item["bbox"][2] for item in same_row)
        col_top = min(item["bbox"][1] for item in same_col)
        col_bottom = max(item["bbox"][1] + item["bbox"][3] for item in same_col)
        middle_x = (row_left + row_right) // 2
        middle_y = (col_top + col_bottom) // 2

        left = max(0, x - 38)
        right = width if center_x >= middle_x else min(width, middle_x)
        top = max(0, y - 10)
        bottom = height if center_y >= middle_y else min(height, middle_y + 10)

        cell_dir = project_dir / "_option_cells"
        cell_dir.mkdir(exist_ok=True)
        cell_path = cell_dir / f"{option_item['diagram_id']}.png"
        cv2.imwrite(str(cell_path), image[top:bottom, left:right])
        raw_text = extract_text(cell_path)
        delete_file_quietly(cell_path)
        return clean_option_cell_tail(raw_text)
    except Exception:
        return ""


def clean_option_cell_tail(raw_text):
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if not lines:
        return ""

    for index, line in enumerate(lines):
        if re.fullmatch(r"\(?[A-Da-d]\)?", line):
            continue
        if re.search(r"\band\b", line, re.IGNORECASE):
            tail = " ".join([line, *lines[index + 1 :]])
            tail = re.sub(r"^\s*and\s*", "and ", tail, flags=re.IGNORECASE)
            return format_option_tail_text(tail)
    return ""


def format_option_tail_text(text):
    cleaned = re.sub(r"\s+", " ", text.strip())
    cleaned = cleaned.replace("CH,OH", "CH3OH").replace("CH;OH", "CH3OH").replace("CH.OH", "CH3OH")
    cleaned = re.sub(r"\bCH[.;,](?=\s|$)", "CH4", cleaned)
    cleaned = re.sub(r"\band CH\s*$", "and CH4", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bCH4\b", r"\\(CH_{4}\\)", cleaned)
    cleaned = re.sub(r"\bCH3OH\b", r"\\(CH_{3}OH\\)", cleaned)
    return cleaned


def update_diagram_manifest_questions(manifest, latex_body):
    question_labels = [
        f"Question {match.group(1)}"
        for match in re.finditer(r"(?m)^\s*(\d+)[.)]\s+", latex_body)
    ]
    if not question_labels:
        return manifest

    for index, item in enumerate(manifest):
        if item.get("associated_option"):
            item["associated_question"] = question_labels[0]
        else:
            item["associated_question"] = question_labels[min(index, len(question_labels) - 1)]
    return manifest


def clean_manifest_for_output(manifest):
    return [
        {key: value for key, value in item.items() if not key.startswith("_")}
        for item in manifest
    ]


def reorder_diagram_outputs(diagram_latex_blocks, diagram_urls, manifest):
    if not has_option_diagrams(manifest):
        return diagram_latex_blocks, diagram_urls, manifest

    label_order = {"A": 0, "B": 1, "C": 2, "D": 3}

    def sort_key(item):
        index, _latex_block, _url, metadata = item
        option = metadata.get("associated_option")
        if option in label_order:
            return (1, label_order[option])
        return (0, metadata.get("position_order", index))

    items = sorted(
        zip(range(len(manifest)), diagram_latex_blocks, diagram_urls, manifest),
        key=sort_key,
    )

    reordered_blocks = [item[1] for item in items]
    reordered_urls = [item[2] for item in items]
    reordered_manifest = []
    for position, item in enumerate(items, 1):
        metadata = dict(item[3])
        metadata["position_order"] = position
        reordered_manifest.append(metadata)

    return reordered_blocks, reordered_urls, reordered_manifest


def make_zip_package(project_dir, zip_path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as package:
        readme = "\n".join(
            [
                "How to open this LaTeX package",
                "",
                "1. Extract this ZIP first.",
                "2. Open the extracted folder.",
                "3. Open main.tex from the extracted folder in TeXstudio.",
                "",
                "Do not open main.tex directly from inside the ZIP preview.",
                "If you do, TeXstudio compiles from a temporary folder and cannot find images/.",
                "",
            ]
        )
        package.writestr("README.txt", readme)

        main_tex = project_dir / "main.tex"
        if main_tex.exists():
            package.write(main_tex, "main.tex")

        images_dir = project_dir / "images"
        if images_dir.exists():
            for path in images_dir.rglob("*"):
                if path.is_file():
                    package.write(path, path.relative_to(project_dir))

        manifest = project_dir / "diagram_manifest.json"
        if manifest.exists():
            package.write(manifest, "diagram_manifest.json")


def get_project_dir(project_id):
    project_dir = (OUTPUT_DIR / secure_filename(project_id)).resolve()
    if project_dir == OUTPUT_DIR.resolve() or OUTPUT_DIR.resolve() not in project_dir.parents:
        return None
    return project_dir


def is_confident_diagram(diagram, image_path):
    if not diagram:
        return False

    try:
        import cv2

        image = cv2.imread(str(image_path))
        if image is None:
            return False
        height, width = image.shape[:2]
    except Exception:
        return False

    x, y, w, h = diagram["bbox"]
    area_ratio = (w * h) / max(1, width * height)
    return (
        area_ratio >= 0.02
        and area_ratio <= 0.65
        and w >= width * 0.08
        and h >= height * 0.08
        and y >= height * 0.03
    )


def extract_project_diagrams(image_path, project_id, project_dir, images_dir):
    extractor = DiagramExtractor(str(image_path))
    diagrams = extractor.find_diagrams()
    confident_diagrams = [diagram for diagram in diagrams if is_confident_diagram(diagram, image_path)]
    if not confident_diagrams:
        main_diagram = extractor.find_main_diagram()
        if is_confident_diagram(main_diagram, image_path):
            confident_diagrams = [main_diagram]

    diagram_latex_blocks = []
    diagram_urls = []
    manifest = []

    for index, diagram in enumerate(confident_diagrams, 1):
        should_refine = not diagram.get("refined", False)
        extracted_path = Path(extractor.extract_diagram(diagram["bbox"], str(images_dir), refine=should_refine))
        diagram_latex_blocks.append(make_diagram_latex(extracted_path.name))
        diagram_urls.append(
            url_for(
                "output_asset",
                project_id=project_id,
                filename=f"images/{extracted_path.name}",
            )
        )
        manifest.append(
            make_diagram_manifest_entry(
                diagram_id=f"diag_{index}",
                question_label=f"Question {index}",
                option_label=None,
                position_order=index,
                image_filename=extracted_path.name,
                bbox=diagram["bbox"],
            )
        )

    manifest = clean_manifest_for_output(attach_option_grid_metadata(manifest, image_path, project_dir))
    diagram_latex_blocks, diagram_urls, manifest = reorder_diagram_outputs(diagram_latex_blocks, diagram_urls, manifest)

    if confident_diagrams:
        text_only_path = project_dir / f"{image_path.stem}_text_only{image_path.suffix}"
        extractor.save_text_only_image_for_bboxes(
            [diagram["bbox"] for diagram in confident_diagrams],
            str(text_only_path),
            refine=any(not diagram.get("refined", False) for diagram in confident_diagrams),
        )
        (project_dir / "diagram_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return diagram_latex_blocks, diagram_urls, text_only_path, manifest

    return [], [], image_path, []


@app.before_request
def prepare_database():
    if not getattr(app, "_db_ready", False):
        try:
            init_db()
            app.config["DATABASE_INIT_ERROR"] = None
        except Exception as exc:
            app.config["DATABASE_INIT_ERROR"] = str(exc)
        app._db_ready = True
    cleanup_old_uploads()


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/process", methods=["POST"])
def process_upload():
    upload = request.files.get("image")
    diagram_upload = request.files.get("diagram_image")
    manual_text = request.form.get("manual_text", "").strip()
    manual_only = request.form.get("manual_only") == "on"

    if not upload or upload.filename == "":
        flash("Please choose a PNG or JPG image.")
        return redirect(url_for("index"))

    if not allowed_file(upload.filename):
        flash("Invalid file type. Upload PNG, JPG, or JPEG only.")
        return redirect(url_for("index"))

    safe_name = secure_filename(upload.filename)
    stored_name = f"{uuid4().hex}_{safe_name}"
    image_path = UPLOAD_DIR / stored_name
    upload.save(image_path)
    project_id, project_dir, images_dir = make_output_project(image_path.stem)

    image_url = url_for("uploaded_file", filename=stored_name)
    diagram_url = None
    diagram_urls = []
    diagram_latex_blocks = []
    diagram_manifest = []
    ocr_image_path = image_path
    if diagram_upload and diagram_upload.filename:
        if not allowed_file(diagram_upload.filename):
            flash("Invalid diagram file type. Upload PNG, JPG, or JPEG only.")
            return redirect(url_for("index"))

        safe_diagram_name = secure_filename(diagram_upload.filename)
        stored_diagram_name = f"{uuid4().hex}_{safe_diagram_name}"
        diagram_path = UPLOAD_DIR / stored_diagram_name
        diagram_upload.save(diagram_path)
        project_diagram_path = copy_image_to_project(diagram_path, images_dir, f"diagram_{safe_diagram_name}")
        diagram_url = url_for("uploaded_file", filename=stored_diagram_name)
        diagram_urls = [diagram_url]
        diagram_latex_blocks = [make_diagram_latex(project_diagram_path.name)]
        diagram_manifest = [
            make_diagram_manifest_entry(
                diagram_id="diag_1",
                question_label="Question 1",
                option_label=None,
                position_order=1,
                image_filename=project_diagram_path.name,
                bbox=(0, 0, 0, 0),
            )
        ]
        (project_dir / "diagram_manifest.json").write_text(json.dumps(diagram_manifest, indent=2), encoding="utf-8")

    if not diagram_latex_blocks and not manual_only:
        try:
            diagram_latex_blocks, diagram_urls, ocr_image_path, diagram_manifest = extract_project_diagrams(
                image_path,
                project_id,
                project_dir,
                images_dir,
            )
            diagram_url = diagram_urls[0] if diagram_urls else None
        except Exception as exc:
            diagram_latex_blocks = []
            diagram_urls = []
            errors = [f"Diagram separation skipped: {exc}"]
        else:
            errors = []
    else:
        errors = []

    if manual_only:
        extracted_text = ""
        equations = []
    else:
        try:
            extracted_text = extract_text(ocr_image_path)
        except Exception as exc:
            extracted_text = ""
            errors.append(f"Text OCR failed: {exc}")

        try:
            equations = extract_math(image_path)
        except Exception as exc:
            equations = []
            if not is_optional_math_error(exc):
                errors.append(f"Math OCR failed: {exc}")

    combined_text = manual_text if manual_only else "\n".join(part for part in [extracted_text, manual_text] if part).strip()
    latex_body = format_mixed_content(combined_text, equations)

    if not latex_body.strip():
        latex_body = "% No readable content was found. You can edit this LaTeX manually."
        errors.append("No text or equations were detected.")

    if diagram_latex_blocks and r"\includegraphics" not in latex_body:
        latex_body = insert_diagrams(latex_body, diagram_latex_blocks, diagram_manifest)

    if diagram_manifest:
        diagram_manifest = clean_manifest_for_output(update_diagram_manifest_questions(diagram_manifest, latex_body))
        (project_dir / "diagram_manifest.json").write_text(json.dumps(diagram_manifest, indent=2), encoding="utf-8")

    latex_document = build_latex_document(latex_body)
    output_path = project_dir / "main.tex"
    output_path.write_text(latex_document, encoding="utf-8")
    zip_name = f"{project_id}.zip"
    zip_path = OUTPUT_DIR / zip_name
    make_zip_package(project_dir, zip_path)

    history_error = None
    if app.config.get("DATABASE_INIT_ERROR"):
        history_error = f"Database connection issue: {app.config['DATABASE_INIT_ERROR']}"

    try:
        if not history_error:
            save_history(
                filename=safe_name,
                image_path="",
                extracted_text=combined_text,
                latex_output=latex_document,
            )
    except Exception as exc:
        history_error = f"Database save failed: {exc}"

    return render_template(
        "result.html",
        image_url=image_url,
        diagram_url=diagram_url,
        diagram_urls=diagram_urls,
        diagram_manifest=diagram_manifest,
        extracted_text=combined_text,
        equations=equations,
        latex_output=latex_document,
        output_name=zip_name,
        project_id=project_id,
        project_path=str(project_dir),
        errors=errors,
        history_error=history_error,
    )


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_file(UPLOAD_DIR / filename)


@app.route("/outputs/<project_id>/<path:filename>")
def output_asset(project_id, filename):
    output_path = (OUTPUT_DIR / project_id / filename).resolve()
    if OUTPUT_DIR.resolve() not in output_path.parents:
        flash("The requested file path is invalid.")
        return redirect(url_for("index"))
    return send_file(output_path)


def insert_diagram(latex_body, diagram_latex):
    enumerate_start = r"\begin{enumerate}"
    if enumerate_start in latex_body:
        return latex_body.replace(enumerate_start, f"{diagram_latex}\n\n{enumerate_start}", 1)
    return "\n\n".join([latex_body, diagram_latex])


def insert_diagrams(latex_body, diagram_latex_blocks, diagram_manifest=None):
    if not diagram_latex_blocks:
        return latex_body
    diagram_manifest = diagram_manifest or []
    if has_option_diagrams(diagram_manifest):
        return insert_option_diagrams(latex_body, diagram_latex_blocks, diagram_manifest)
    if len(diagram_latex_blocks) == 1:
        return insert_diagram(latex_body, diagram_latex_blocks[0])

    marker = r"\begin{description}"
    parts = latex_body.split(marker)
    if len(parts) == 1:
        return "\n\n".join([latex_body, *diagram_latex_blocks])

    rebuilt = [parts[0]]
    diagram_index = 0
    for option_block in parts[1:]:
        if diagram_index < len(diagram_latex_blocks):
            rebuilt.append(f"{diagram_latex_blocks[diagram_index]}\n\n{marker}{option_block}")
            diagram_index += 1
        else:
            rebuilt.append(f"{marker}{option_block}")

    if diagram_index < len(diagram_latex_blocks):
        rebuilt.append("\n\n" + "\n\n".join(diagram_latex_blocks[diagram_index:]))

    return "".join(rebuilt)


def has_option_diagrams(diagram_manifest):
    return sum(1 for item in diagram_manifest if item.get("associated_option")) >= 2


def insert_option_diagrams(latex_body, diagram_latex_blocks, diagram_manifest):
    question_blocks = [
        diagram_latex_blocks[index]
        for index, item in enumerate(diagram_manifest)
        if not item.get("associated_option") and index < len(diagram_latex_blocks)
    ]
    option_items = [
        (item.get("associated_option"), diagram_latex_blocks[index], item.get("option_text", ""))
        for index, item in enumerate(diagram_manifest)
        if item.get("associated_option") and index < len(diagram_latex_blocks)
    ]
    option_items = sorted(option_items, key=lambda item: "ABCD".find(item[0]) if item[0] in "ABCD" else 99)

    body_with_question_diagrams = insert_before_first_description(latex_body, question_blocks) if question_blocks else latex_body
    option_block = build_option_diagram_block(option_items)
    if not option_block:
        return body_with_question_diagrams

    return replace_first_description_block(body_with_question_diagrams, option_block)


def build_option_diagram_block(option_items):
    if not option_items:
        return ""

    lines = [r"\begin{description}[leftmargin=1.6em,style=nextline]"]
    for label, diagram_latex, option_text in option_items:
        lines.append(rf"\item[\textbf{{{label.lower()}.}}]")
        lines.append(diagram_latex)
        if option_text:
            lines.append(option_text)
    lines.append(r"\end{description}")
    return "\n".join(lines)


def replace_first_description_block(latex_body, replacement):
    match = re.search(r"\\begin\{description\}(?:\[[^\]]*\])?[\s\S]*?\\end\{description\}", latex_body)
    if not match:
        return "\n\n".join([latex_body, replacement])
    return f"{latex_body[:match.start()]}{replacement}{latex_body[match.end():]}"


def insert_before_first_description(latex_body, diagram_latex_blocks):
    if not diagram_latex_blocks:
        return latex_body

    diagram_latex = "\n\n".join(diagram_latex_blocks)
    match = re.search(r"\\begin\{description\}(?:\[[^\]]*\])?", latex_body)
    if not match:
        return "\n\n".join([latex_body, diagram_latex])
    return f"{latex_body[:match.start()]}{diagram_latex}\n\n{latex_body[match.start():]}"


@app.route("/download/<path:filename>")
def download_file(filename):
    output_path = (OUTPUT_DIR / filename).resolve()
    if OUTPUT_DIR.resolve() not in output_path.parents:
        flash("The requested file path is invalid.")
        return redirect(url_for("index"))
    if not output_path.exists():
        flash("The requested .tex file was not found.")
        return redirect(url_for("index"))
    return send_file(output_path, as_attachment=True, download_name=filename)


@app.route("/download-package/<project_id>", methods=["POST"])
def download_package(project_id):
    project_dir = get_project_dir(project_id)
    if not project_dir or not project_dir.exists():
        flash("The requested LaTeX package was not found.")
        return redirect(url_for("index"))

    latex_output = request.form.get("latex_output", "")
    if "latex_output" in request.form:
        (project_dir / "main.tex").write_text(latex_output, encoding="utf-8")

    zip_name = f"{project_dir.name}.zip"
    zip_path = OUTPUT_DIR / zip_name
    make_zip_package(project_dir, zip_path)
    return send_file(zip_path, as_attachment=True, download_name=zip_name)


@app.route("/save-project/<project_id>", methods=["POST"])
def save_project(project_id):
    project_dir = get_project_dir(project_id)
    if not project_dir or not project_dir.exists():
        flash("The requested LaTeX folder was not found.")
        return redirect(url_for("index"))

    latex_output = request.form.get("latex_output", "")
    (project_dir / "main.tex").write_text(latex_output, encoding="utf-8")

    zip_path = OUTPUT_DIR / f"{project_dir.name}.zip"
    make_zip_package(project_dir, zip_path)
    flash("Saved main.tex and refreshed the ZIP package.")
    return redirect(url_for("project_result", project_id=project_dir.name))


@app.route("/project/<project_id>")
def project_result(project_id):
    project_dir = get_project_dir(project_id)
    if not project_dir or not project_dir.exists():
        flash("The requested LaTeX folder was not found.")
        return redirect(url_for("index"))

    output_path = project_dir / "main.tex"
    if not output_path.exists():
        flash("main.tex was not found in that folder.")
        return redirect(url_for("index"))

    return render_template(
        "result.html",
        image_url=None,
        diagram_url=None,
        diagram_urls=[],
        diagram_manifest=[],
        extracted_text="",
        equations=[],
        latex_output=output_path.read_text(encoding="utf-8"),
        output_name=f"{project_dir.name}.zip",
        project_id=project_dir.name,
        project_path=str(project_dir),
        errors=[],
        history_error=None,
    )


@app.route("/open-project/<project_id>", methods=["POST"])
def open_project(project_id):
    project_dir = get_project_dir(project_id)
    if not project_dir or not project_dir.exists():
        flash("The requested LaTeX folder was not found.")
        return redirect(url_for("index"))

    latex_output = request.form.get("latex_output", "")
    if "latex_output" in request.form:
        (project_dir / "main.tex").write_text(latex_output, encoding="utf-8")
        make_zip_package(project_dir, OUTPUT_DIR / f"{project_dir.name}.zip")

    try:
        open_local_path(project_dir)
        flash("Saved changes and opened the LaTeX folder.")
    except OSError as exc:
        flash(f"Saved changes, but the folder could not be opened automatically: {exc}")

    return redirect(url_for("project_result", project_id=project_dir.name))


def open_local_path(path):
    if os.name == "nt":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def open_app_in_browser(url):
    browser_commands = [
        os.getenv("LATEX_GENERATOR_BROWSER"),
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "msedge",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        "chrome",
        "firefox",
    ]

    for browser_command in filter(None, browser_commands):
        try:
            webbrowser.register(
                "external-browser",
                None,
                webbrowser.BackgroundBrowser(browser_command),
                preferred=True,
            )
            webbrowser.get("external-browser").open_new_tab(url)
            return
        except webbrowser.Error:
            continue

    if os.name == "nt":
        subprocess.Popen(["cmd", "/c", "start", "", url], shell=False)
    else:
        webbrowser.open_new_tab(url)


if __name__ == "__main__":
    threading.Timer(1.0, lambda: open_app_in_browser("http://127.0.0.1:5000")).start()
    app.run(debug=True, use_reloader=False)
