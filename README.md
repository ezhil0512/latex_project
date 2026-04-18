# Offline LaTeX Generator

A beginner-friendly Flask web app that converts uploaded images and optional text into clean LaTeX. It supports normal OCR, equation extraction, chemistry formatting rules, `.tex` downloads, and PostgreSQL history storage. The app is free to use and is designed to work offline once the dependencies are installed.

## What Works Offline

- Flask web UI for uploading PNG/JPG/JPEG images.
- Image preview before upload.
- PaddleOCR text extraction.
- pix2tex math extraction.
- OpenCV preprocessing before OCR.
- Chemistry formatter after OCR and before final LaTeX output.
- Editable LaTeX result, copy button, and `.tex` download.
- PostgreSQL history table using the `latex_generator` database.

The app is structured so PaddleOCR and pix2tex can run in separate Python environments by setting `OCR_PYTHON` and `MATH_PYTHON` in `.env`.

## Setup

1. Edit `.env` and set your real PostgreSQL password:

```env
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/latex_generator
```

2. Create the PostgreSQL database manually:

```sql
CREATE DATABASE latex_generator;
```

Or create it from the project after installing requirements:

```powershell
.\.venv\Scripts\python.exe scripts\create_database.py
```

3. Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

4. Install packages:

```powershell
pip install -r requirements.txt
```

5. Copy `.env.example` to `.env` and update the password:

```powershell
Copy-Item .env.example .env
```

6. Run the app:

```powershell
python app.py
```

7. Open:

```text
http://127.0.0.1:5000
```

## Separate OCR Environments

Heavy OCR packages sometimes conflict. To isolate them, create separate environments and point the app to each Python executable:

```powershell
python -m venv .venv-ocr
.\.venv-ocr\Scripts\pip install paddleocr paddlepaddle opencv-python Pillow numpy

python -m venv .venv-math
.\.venv-math\Scripts\pip install pix2tex Pillow
```

Then edit `.env`:

```env
OCR_PYTHON=C:\Users\ezhil\OneDrive\Desktop\latex_genarator\.venv-ocr\Scripts\python.exe
MATH_PYTHON=C:\Users\ezhil\OneDrive\Desktop\latex_genarator\.venv-math\Scripts\python.exe
```

Leave those values empty to run OCR inside the main Flask environment.

## Notes

- First OCR runs can be slow because models may initialize or download if not already cached.
- For full offline use, install packages and model files while connected once, then keep them cached locally.
- If PostgreSQL is not running, the app still processes files but shows a database warning.
