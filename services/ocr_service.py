import json
import os
import subprocess
import sys
from pathlib import Path

from services.preprocess import preprocess_image


def extract_text(image_path):
    """Extract normal text with PaddleOCR."""
    runner = os.getenv("OCR_PYTHON", "").strip()
    if runner:
        return _extract_text_subprocess(runner, image_path)
    return _extract_text_local(image_path)


def _extract_text_subprocess(python_executable, image_path):
    command = [
        python_executable,
        str(Path(__file__).with_name("ocr_worker.py")),
        str(image_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=120, check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "PaddleOCR subprocess failed.")
    payload = json.loads(completed.stdout)
    if payload.get("error"):
        raise RuntimeError(payload["error"])
    return payload.get("text", "")


def _extract_text_local(image_path):
    try:
        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise RuntimeError("PaddleOCR is not installed. Run pip install -r requirements.txt.") from exc

    processed_path = preprocess_image(image_path)
    ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
    result = ocr.ocr(str(processed_path), cls=True)
    lines = []

    for page in result or []:
        for item in page or []:
            if len(item) >= 2 and item[1]:
                lines.append(item[1][0])

    return "\n".join(lines).strip()


if __name__ == "__main__":
    try:
        print(json.dumps({"text": _extract_text_local(sys.argv[1])}))
    except Exception as exc:
        print(json.dumps({"error": str(exc)}))
        sys.exit(1)
