import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

from services.math_service import extract_math
from services.ocr_service import extract_text
from services.multi_question_service import MultiQuestionService
from services.unified_processor import UnifiedProcessor
from utils.database import init_db, save_history
from utils.latex_formatter import build_latex_document, format_mixed_content

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
PDF_UPLOAD_DIR = BASE_DIR / "temp_pdfs"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}
PDF_EXTENSIONS = {"pdf"}
ALLOWED_UPLOAD_EXTENSIONS = ALLOWED_EXTENSIONS | PDF_EXTENSIONS
UPLOAD_EXPIRATION_SECONDS = 900

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
PDF_UPLOAD_DIR.mkdir(exist_ok=True)

# Initialize services
multi_service = MultiQuestionService(str(OUTPUT_DIR), "static/images")
unified_processor = UnifiedProcessor(str(OUTPUT_DIR), "static/images")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-me")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def allowed_pdf(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in PDF_EXTENSIONS


def is_allowed_upload(filename):
    """Check if file is either allowed image or PDF."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_UPLOAD_EXTENSIONS


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

    image_url = url_for("uploaded_file", filename=stored_name)
    diagram_url = None
    diagram_latex = ""
    if diagram_upload and diagram_upload.filename:
        if not allowed_file(diagram_upload.filename):
            flash("Invalid diagram file type. Upload PNG, JPG, or JPEG only.")
            return redirect(url_for("index"))

        safe_diagram_name = secure_filename(diagram_upload.filename)
        stored_diagram_name = f"{uuid4().hex}_{safe_diagram_name}"
        diagram_path = UPLOAD_DIR / stored_diagram_name
        diagram_upload.save(diagram_path)
        diagram_url = url_for("uploaded_file", filename=stored_diagram_name)
        diagram_latex = "\n".join(
            [
                r"\begin{center}",
                rf"\includegraphics[width=0.45\textwidth]{{../uploads/{stored_diagram_name}}}",
                r"\end{center}",
            ]
        )

    errors = []
    if manual_only:
        extracted_text = ""
        equations = []
    else:
        try:
            extracted_text = extract_text(image_path)
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
    output_name = f"{image_path.stem}.tex"
    output_path = OUTPUT_DIR / output_name
    output_path.write_text(latex_document, encoding="utf-8")

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
        output_name=output_name,
        errors=errors,
        history_error=history_error,
    )


@app.route("/process-unified", methods=["POST"])
def process_unified():
    """
    Unified upload handler for both images and PDFs.
    Automatically detects file type and processes through unified pipeline.
    """
    upload = request.files.get("file")
    manual_text = request.form.get("manual_text", "").strip()
    use_manual_only = request.form.get("manual_only") == "on"
    diagram_upload = request.files.get("diagram_image")

    if not upload or upload.filename == "":
        flash("Please choose a file (image or PDF).")
        return redirect(url_for("index"))

    if not is_allowed_upload(upload.filename):
        flash("Invalid file type. Upload PNG, JPG, JPEG, or PDF only.")
        return redirect(url_for("index"))

    # Save uploaded file temporarily
    safe_name = secure_filename(upload.filename)
    stored_name = f"{uuid4().hex}_{safe_name}"
    file_path = UPLOAD_DIR / stored_name
    upload.save(file_path)

    diagram_path = None
    if diagram_upload and diagram_upload.filename:
        if not allowed_file(diagram_upload.filename):
            flash("Invalid diagram file type. Upload PNG, JPG, or JPEG only.")
            try:
                file_path.unlink(missing_ok=True)
            except:
                pass
            return redirect(url_for("index"))

        safe_diagram_name = secure_filename(diagram_upload.filename)
        stored_diagram_name = f"{uuid4().hex}_{safe_diagram_name}"
        diagram_path = UPLOAD_DIR / stored_diagram_name
        diagram_upload.save(diagram_path)

    try:
        # Process through unified pipeline
        result = unified_processor.process(
            str(file_path),
            manual_text=manual_text,
            use_manual_only=use_manual_only,
            diagram_path=str(diagram_path) if diagram_path else "",
        )

        if result["status"] != "success":
            flash(f"Processing failed: {result.get('message', 'Unknown error')}")
            return redirect(url_for("index"))

        # Render unified result template
        result_data = result["result"]
        errors = result.get("errors", [])
        job_id = result.get("job_id", "")
        file_type = result.get("file_type", "image")
        download_url = url_for("download_output", job_id=job_id) if job_id else "#"

        return render_template(
            "unified_result.html",
            file_type=file_type,
            job_id=job_id,
            download_url=download_url,
            extracted_text=result_data.get("extracted_text", ""),
            equations=result_data.get("equations", []),
            images=result_data.get("images", []),
            latex_output=result_data.get("latex_output", ""),
            output_name=result_data.get("output_name", ""),
            questions=result_data.get("questions", []),
            is_single_question=result_data.get("is_single_question", True),
            total_questions=result_data.get("total_questions", 1),
            errors=errors,
        )

    except Exception as exc:
        flash(f"Error processing file: {str(exc)}")
        logging.error(f"Unified processing error: {exc}", exc_info=True)
        return redirect(url_for("index"))

    finally:
        # Cleanup temp file
        try:
            file_path.unlink(missing_ok=True)
        except:
            pass
        if diagram_path:
            try:
                diagram_path.unlink(missing_ok=True)
            except:
                pass


@app.route("/download-output/<job_id>")
def download_output(job_id: str):
    import zipfile
    from io import BytesIO

    job_dir = OUTPUT_DIR / job_id
    if not job_dir.exists() or not job_dir.is_dir():
        flash("The requested output package was not found.")
        return redirect(url_for("index"))

    tex_files = list(job_dir.rglob("*.tex"))
    image_files = [p for p in job_dir.rglob("*.*") if p.suffix.lower() in {".png", ".jpg", ".jpeg"}]

    if len(tex_files) == 1 and not image_files:
        tex_file = tex_files[0]
        return send_file(tex_file, as_attachment=True, download_name=tex_file.name)

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in job_dir.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(job_dir))
    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"{job_id}_latex_package.zip",
    )


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_file(UPLOAD_DIR / filename)


@app.route("/process-pdf", methods=["POST"])
def process_pdf_upload():
    """Handle PDF upload with multi-question processing."""
    pdf_file = request.files.get("pdf")
    
    if not pdf_file or pdf_file.filename == "":
        flash("Please choose a PDF file.")
        return redirect(url_for("index"))
    
    if not allowed_pdf(pdf_file.filename):
        flash("Invalid file type. Upload PDF files only.")
        return redirect(url_for("index"))
    
    # Save PDF temporarily
    batch_id = str(uuid4())[:12]
    safe_pdf_name = secure_filename(pdf_file.filename)
    pdf_filename = f"{batch_id}_{safe_pdf_name}"
    pdf_path = PDF_UPLOAD_DIR / pdf_filename
    pdf_file.save(pdf_path)
    
    try:
        # Process PDF
        result = multi_service.process_pdf(str(pdf_path), batch_id)
        
        if result['status'] == 'success':
            batch_data = result['data']
            return render_template(
                'multi_result.html',
                batch_id=batch_id,
                batch_data=batch_data
            )
        else:
            flash(f"Error processing PDF: {result.get('message', 'Unknown error')}")
            return redirect(url_for("index"))
    
    except Exception as e:
        flash(f"Error processing PDF: {str(e)}")
        return redirect(url_for("index"))
    
    finally:
        # Cleanup temp PDF
        try:
            if pdf_path.exists():
                pdf_path.unlink()
        except:
            pass
        
        # Cleanup temp images
        multi_service.cleanup_temp_files()


@app.route("/batch/<batch_id>")
def view_batch(batch_id: str):
    """View stored batch results."""
    batch_data = multi_service.get_batch_results(batch_id)
    
    if not batch_data:
        flash("Batch not found.")
        return redirect(url_for("index"))
    
    return render_template(
        'multi_result.html',
        batch_id=batch_id,
        batch_data=batch_data
    )


@app.route("/download-batch/<batch_id>")
def download_batch(batch_id: str):
    """Download all LaTeX files for a batch as ZIP."""
    import zipfile
    from io import BytesIO
    
    batch_dir = OUTPUT_DIR / batch_id
    if not batch_dir.exists():
        flash("Batch not found.")
        return redirect(url_for("index"))
    
    try:
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for tex_file in batch_dir.rglob('*.tex'):
                arcname = tex_file.relative_to(batch_dir)
                zf.write(tex_file, arcname)
        
        zip_buffer.seek(0)
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'{batch_id}_latex_files.zip'
        )
    except Exception as e:
        flash(f"Error creating batch download: {str(e)}")
        return redirect(url_for("index"))


def insert_diagram(latex_body, diagram_latex):
    enumerate_start = r"\begin{enumerate}"
    if enumerate_start in latex_body:
        return latex_body.replace(enumerate_start, f"{diagram_latex}\n\n{enumerate_start}", 1)
    return "\n\n".join([latex_body, diagram_latex])


@app.route("/download/<path:filename>")
def download_file(filename):
    output_path = OUTPUT_DIR / filename
    if not output_path.exists():
        flash("The requested .tex file was not found.")
        return redirect(url_for("index"))
    return send_file(output_path, as_attachment=True, download_name=filename)


if __name__ == "__main__":
    app.run(debug=True)
