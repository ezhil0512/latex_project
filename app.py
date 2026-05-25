import os
import shutil
import zipfile
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
    if not getattr(app, "_db_ready", False):
        try:
            init_db()
            app.config["DATABASE_INIT_ERROR"] = None
        except Exception as exc:
            app.config["DATABASE_INIT_ERROR"] = str(exc)
        app._db_ready = True


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
    diagram_latex = ""
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
        diagram_latex = make_diagram_latex(project_diagram_path.name)

    if not diagram_latex and not manual_only:
        try:
            extractor = DiagramExtractor(str(image_path))
            diagram = extractor.find_main_diagram()
            if is_confident_diagram(diagram, image_path):
                extracted_diagram_path = Path(extractor.extract_diagram(diagram["bbox"], str(images_dir)))
                text_only_path = project_dir / f"{image_path.stem}_text_only{image_path.suffix}"
                extractor.save_text_only_image_for_bbox(diagram["bbox"], str(text_only_path))
                ocr_image_path = text_only_path
                diagram_url = url_for(
                    "output_asset",
                    project_id=project_id,
                    filename=f"images/{extracted_diagram_path.name}",
                )
                diagram_latex = make_diagram_latex(extracted_diagram_path.name)
        except Exception as exc:
            diagram_latex = ""
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

    if diagram_latex and r"\includegraphics" not in latex_body:
        latex_body = insert_diagram(latex_body, diagram_latex)

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
        extracted_text=combined_text,
        equations=equations,
        latex_output=latex_document,
        output_name=zip_name,
        project_id=project_id,
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


if __name__ == "__main__":
    app.run(debug=True)
