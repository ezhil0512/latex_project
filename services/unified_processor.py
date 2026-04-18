"""
Unified processor for both image and PDF files.
Automatically detects file type and processes through appropriate pipeline.
"""

import shutil
from pathlib import Path
from typing import Any, Dict, List
import logging
from uuid import uuid4

from utils.latex_formatter import build_latex_document, format_mixed_content
from utils.pdf_processor import PDFProcessor
from utils.question_splitter import QuestionSplitter
from services.ocr_service import extract_text
from services.math_service import extract_math

logger = logging.getLogger(__name__)


class UnifiedProcessor:
    """
    Processes both images and PDFs through a unified pipeline.
    Automatically detects file type and routes to appropriate handler.
    """

    def __init__(self, output_dir: str = "outputs", image_dir: str = "static/images"):
        self.output_dir = Path(output_dir)
        self.image_dir = Path(image_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        self.image_dir.mkdir(exist_ok=True, parents=True)

    def process(
        self,
        file_path: str,
        manual_text: str = "",
        use_manual_only: bool = False,
        diagram_path: str = "",
    ) -> Dict[str, Any]:
        file_path = Path(file_path)

        if not file_path.exists():
            return {
                "status": "error",
                "message": f"File not found: {file_path}",
                "errors": ["File not found"],
            }

        file_type = self._detect_file_type(file_path)

        if file_type == "image":
            return self._process_image(file_path, manual_text, use_manual_only, diagram_path)
        elif file_type == "pdf":
            return self._process_pdf(file_path, manual_text)

        return {
            "status": "error",
            "message": "Unsupported file type",
            "errors": ["Only images (.png, .jpg, .jpeg) and PDFs are supported"],
        }

    def _detect_file_type(self, file_path: Path) -> str:
        if not isinstance(file_path, Path):
            file_path = Path(file_path)
        extension = file_path.suffix.lower()

        if extension in {".png", ".jpg", ".jpeg"}:
            return "image"
        if extension == ".pdf":
            return "pdf"
        return "unknown"

    def _ensure_job_dirs(self, job_id: str):
        output_dir = self.output_dir / job_id
        static_image_dir = self.image_dir / job_id
        output_image_dir = output_dir / "images"
        output_dir.mkdir(exist_ok=True, parents=True)
        static_image_dir.mkdir(exist_ok=True, parents=True)
        output_image_dir.mkdir(exist_ok=True, parents=True)
        return output_dir, static_image_dir, output_image_dir

    def _process_image(
        self,
        file_path: Path,
        manual_text: str,
        use_manual_only: bool,
        diagram_path: str = "",
    ) -> Dict[str, Any]:
        errors: List[str] = []
        extracted_text = ""
        equations: List[str] = []
        images: List[str] = []

        job_id = uuid4().hex[:12]
        output_dir, static_image_dir, output_image_dir = self._ensure_job_dirs(job_id)

        original_image_name = file_path.name
        static_image_path = static_image_dir / original_image_name
        output_image_path = output_image_dir / original_image_name
        shutil.copyfile(file_path, static_image_path)
        shutil.copyfile(file_path, output_image_path)

        static_image_url = f"/static/images/{job_id}/{original_image_name}"
        relative_image_path = f"images/{original_image_name}"
        images.append(static_image_url)

        diagram_relative_path = None
        if diagram_path:
            diagram_file = Path(diagram_path)
            if diagram_file.exists():
                diagram_name = diagram_file.name
                static_diagram_path = static_image_dir / diagram_name
                output_diagram_path = output_image_dir / diagram_name
                shutil.copyfile(diagram_file, static_diagram_path)
                shutil.copyfile(diagram_file, output_diagram_path)
                static_diagram_url = f"/static/images/{job_id}/{diagram_name}"
                diagram_relative_path = f"images/{diagram_name}"
                images.append(static_diagram_url)

        if not use_manual_only:
            try:
                extracted_text = extract_text(file_path)
            except Exception as exc:
                errors.append(f"Text OCR failed: {exc}")
                logger.warning(f"OCR failed: {exc}")

            try:
                equations = extract_math(file_path)
            except Exception as exc:
                errors.append(f"Math OCR failed: {exc}")
                logger.warning(f"Math extraction failed: {exc}")

        combined_text = manual_text if use_manual_only else "\n".join(
            part for part in [extracted_text, manual_text] if part
        ).strip()

        latex_body = format_mixed_content(combined_text, equations)
        if not latex_body.strip():
            latex_body = "% No readable content was found. You can edit this LaTeX manually."
            errors.append("No text or equations were detected.")

        if r"\includegraphics" not in latex_body:
            include_path = diagram_relative_path or relative_image_path
            image_latex = "\n".join(
                [
                    r"\begin{center}",
                    rf"\includegraphics[width=0.5\textwidth]{{{include_path}}}",
                    r"\end{center}",
                ]
            )
            latex_body = self._insert_diagram(latex_body, image_latex)

        latex_document = build_latex_document(latex_body)
        output_tex_path = output_dir / "main.tex"
        output_tex_path.write_text(latex_document, encoding="utf-8")

        return {
            "status": "success",
            "file_type": "image",
            "job_id": job_id,
            "result": {
                "extracted_text": combined_text,
                "equations": equations,
                "images": images,
                "latex_output": latex_document,
                "output_name": output_tex_path.name,
                "is_single_question": True,
                "questions": [
                    {
                        "question_num": 1,
                        "text": combined_text,
                        "images": images,
                        "latex": latex_document,
                    }
                ],
            },
            "errors": errors,
        }

    def _process_pdf(self, file_path: Path, manual_text: str = "") -> Dict[str, Any]:
        errors: List[str] = []
        job_id = uuid4().hex[:12]
        output_dir, static_image_dir, output_image_dir = self._ensure_job_dirs(job_id)

        try:
            pdf_processor = PDFProcessor(str(file_path))
            pages = pdf_processor.extract_all_pages()

            if not pages:
                return {
                    "status": "error",
                    "message": "No pages extracted from PDF",
                    "errors": ["PDF appears to be empty or corrupted"],
                }

            combined_text = "\n".join(page.get("text", "") for page in pages)
            splitter = QuestionSplitter(combined_text)
            questions_text = splitter.split_questions() or [combined_text]

            questions_results: List[Dict[str, Any]] = []
            for q_num, q_text in enumerate(questions_text, 1):
                q_rel_dir = f"q_{q_num}"
                static_q_dir = static_image_dir / q_rel_dir
                output_q_dir = output_image_dir / q_rel_dir
                static_q_dir.mkdir(exist_ok=True, parents=True)
                output_q_dir.mkdir(exist_ok=True, parents=True)

                question_images: List[str] = []
                question_image_rel_paths: List[str] = []

                for page in pages:
                    for img_data in page.get("images", []):
                        source_path = Path(img_data.get("path", ""))
                        if not source_path.exists():
                            continue
                        image_name = source_path.name
                        static_target = static_q_dir / image_name
                        output_target = output_q_dir / image_name
                        shutil.copyfile(source_path, static_target)
                        shutil.copyfile(source_path, output_target)
                        question_images.append(f"/static/images/{job_id}/{q_rel_dir}/{image_name}")
                        question_image_rel_paths.append(f"images/{q_rel_dir}/{image_name}")

                latex_body = format_mixed_content(q_text, [])
                if not latex_body.strip():
                    latex_body = f"% Question {q_num}\n% No readable content found."

                if question_image_rel_paths:
                    image_latex = "\n".join(
                        [
                            r"\begin{center}",
                            "\n".join(
                                rf"\includegraphics[width=0.45\textwidth]{{{img_path}}}"
                                for img_path in question_image_rel_paths
                            ),
                            r"\end{center}",
                        ]
                    )
                    latex_body = f"{image_latex}\n\n{latex_body}"

                latex_document = build_latex_document(latex_body)
                question_tex_path = output_dir / f"question_{q_num}.tex"
                question_tex_path.write_text(latex_document, encoding="utf-8")

                questions_results.append(
                    {
                        "question_num": q_num,
                        "text": q_text,
                        "images": question_images,
                        "latex": latex_document,
                        "status": "success",
                        "output_name": question_tex_path.name,
                    }
                )

            return {
                "status": "success",
                "file_type": "pdf",
                "job_id": job_id,
                "result": {
                    "extracted_text": combined_text,
                    "equations": [],
                    "images": [],
                    "latex_output": "",
                    "output_name": "",
                    "is_single_question": False,
                    "questions": questions_results,
                    "total_questions": len(questions_results),
                },
                "errors": errors,
            }

        except Exception as exc:
            logger.error(f"PDF processing failed: {exc}")
            return {
                "status": "error",
                "message": f"PDF processing failed: {exc}",
                "errors": [str(exc)],
            }

    def _insert_diagram(self, latex_body: str, diagram_latex: str) -> str:
        if "% endinsert " in latex_body:
            return latex_body.replace("% endinsert ", diagram_latex)
        return f"{diagram_latex}\n\n{latex_body}"
