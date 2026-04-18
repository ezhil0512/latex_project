# Command Reference Card

## Quick Commands

### 1. Installation & Setup
```bash
# Navigate to project
cd c:\Users\ezhil\OneDrive\Desktop\latex_genarator

# Activate virtual environment
.\.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Verify installation
python test_system.py
```

### 2. Running the Application
```bash
# Start server
python app.py

# Server will be available at
http://localhost:5000

# Stop server
Ctrl + C

# Run in debug mode
set FLASK_ENV=development
python app.py
```

### 3. Testing
```bash
# Run full system test
python test_system.py

# Run pytest on formatter tests
python -m pytest tests/test_latex_formatter.py -v

# Run specific test
python -m pytest tests/test_latex_formatter.py::test_redox_question -v

# Check test coverage
python -m pytest --cov=utils tests/
```

### 4. Maintenance
```bash
# Clean temporary files
rmdir /s /q temp_pdfs
rmdir /s /q temp_images

# Clean old batches (older than 7 days)
# Run this periodically:
python -c "
import os
from datetime import datetime, timedelta

outputs = 'outputs'
cutoff = datetime.now() - timedelta(days=7)

for batch_id in os.listdir(outputs):
    batch_path = os.path.join(outputs, batch_id)
    if os.path.isdir(batch_path):
        mtime = datetime.fromtimestamp(os.path.getmtime(batch_path))
        if mtime < cutoff:
            print(f'Old batch: {batch_id}')
"

# View application logs
# Check Flask console output for INFO/WARNING/ERROR messages
```

---

## File Operations

### Adding Custom Question Patterns
**File:** `utils/question_splitter.py`

```python
# Line ~25, modify QUESTION_PATTERNS
QUESTION_PATTERNS = [
    r'^\s*\d+[\.\)]\s+',          # 1. or 1)
    r'^\s*\(\d+\)\s+',             # (1)
    r'^\s*[Qq]uestion\s+\d+',      # Question 1
    r'^\s*Q\d+[\.\):\s]',          # Q1:
    r'^\s*[A-Z][\.\)]\s+',         # A.
    r'^\s*PROBLEM\s+\d+',          # [NEW] PROBLEM 1
]
```

### Adjusting Diagram Detection
**File:** `utils/diagram_extractor.py`

```python
# Line ~103, adjust thresholds
aspect_ratio_threshold = 3.0    # If too strict, lower to 2.5
edge_density_threshold = 0.15   # If too loose, raise to 0.20

# More text regions kept → aspect_ratio_threshold ↓
# More diagrams kept → edge_density_threshold ↑
```

### Customizing PDF Upload Limits
**File:** `app.py`

```python
# Line ~15, adjust MAX_CONTENT_LENGTH
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

# For larger files:
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB
```

### Changing LaTeX Template
**File:** `services/multi_question_service.py`

```python
# Look for: format_mixed_content() call
# Modify latex_formatter.py for document structure

# Or create custom template:
template = f"""
\\documentclass{{article}}
\\usepackage{{graphicx}}
\\title{{Question {q_num}}}
\\begin{{document}}
\\maketitle
{latex_content}
\\end{{document}}
"""
```

---

## API Reference (Flask Routes)

### 1. Single Image (Existing)
```bash
POST /upload
Content-Type: multipart/form-data

Fields:
  - image: <file>
  - diagram: <file> (optional)
  - correct_text: <string> (optional)

Response: Redirects to /result/{uuid}
```

### 2. Multi-Question PDF (New)
```bash
POST /process-pdf
Content-Type: multipart/form-data

Fields:
  - pdf: <file>  (required, .pdf only)

Response: 
  Status: 200
  Template: multi_result.html
  Context: {batch_id, questions[], status, ...}
```

### 3. Batch Retrieval (New)
```bash
GET /batch/<batch_id>

Response:
  Status: 200 if found, 404 if not
  Template: multi_result.html
  Context: Loaded from metadata.json
```

### 4. Batch Download (New)
```bash
GET /download-batch/<batch_id>

Response:
  Status: 200
  Content-Type: application/zip
  Body: All .tex files in batch as ZIP
```

### 5. Image Download (Existing)
```bash
GET /uploads/<path:filename>

Returns: Static files from uploads/ or static/images/
```

---

## Python Module Reference

### PDFProcessor
```python
from utils.pdf_processor import PDFProcessor

# Initialize
processor = PDFProcessor("document.pdf")

# Check if scanned
is_scanned = processor.is_scanned_pdf()

# Extract all
pages = processor.extract_all_pages()
# → [{'page_num': 1, 'text': '...', 'images': [...], ...}, ...]

# Extract text blocks
blocks = processor.extract_text_blocks(page_num=1)
# → [{'x': 10, 'y': 20, 'width': 100, 'height': 50, 'text': '...'}, ...]

# Context manager (auto-cleanup)
with PDFProcessor("doc.pdf") as pdf:
    pages = pdf.extract_all_pages()
```

### QuestionSplitter
```python
from utils.question_splitter import QuestionSplitter

# Initialize
splitter = QuestionSplitter(combined_text)

# Split questions
questions = splitter.split_questions()
# → ['Question 1 text...', 'Question 2 text...', ...]

# Check if numbering detected
has_numbering = splitter._has_clear_numbering()
# → True if 2+ numbering patterns in first 30 lines

# Validate split
is_valid = splitter.validate_split(questions)
# → True if all questions are substantial
```

### DiagramExtractor
```python
from utils.diagram_extractor import DiagramExtractor

# Initialize
extractor = DiagramExtractor()

# Separate regions
result = extractor.separate_text_from_diagram(image)
# → {'text_regions': [...], 'diagram_regions': [...], 'main_diagram': ...}

# Find main diagram
main = extractor.find_main_diagram(image)
# → Main diagram by area

# Get text-only (remove diagrams)
text_only = extractor.get_text_only_image(image)
# → Image with diagrams filled white (good for OCR)
```

### MultiQuestionService
```python
from services.multi_question_service import MultiQuestionService

# Initialize
service = MultiQuestionService(output_dir="outputs", image_dir="static/images")

# Process PDF
result = service.process_pdf("exam.pdf", batch_id="batch_001")
# → {'status': 'success', 'data': {...}}

# Retrieve cached
cached = service.get_batch_results("batch_001")
# → Same structure as above

# Cleanup temp files
service.cleanup_temp_files("batch_001")
```

---

## Directory Structure

### Output Folders
```
outputs/
├── abc123xyz789/              # Batch ID
│   ├── q_1/
│   │   ├── question_1.tex     # LaTeX content
│   │   └── metadata.json      # Question info
│   ├── q_2/
│   │   ├── question_2.tex
│   │   └── metadata.json
│   └── metadata.json          # Batch metadata

static/images/
├── abc123xyz789/
│   ├── q_1/
│   │   ├── diagram_0.png
│   │   ├── diagram_1.png
│   │   └── ...
│   └── q_2/
│       └── diagram_0.png

temp_pdfs/                     # Auto-cleaned
├── upload_xyz.pdf

temp_images/                   # Auto-cleaned
└── extracted_images_*.png
```

### Source Files
```
utils/
├── __init__.py
├── pdf_processor.py           [465 lines]
├── question_splitter.py       [310 lines]
├── diagram_extractor.py       [310 lines]
├── latex_formatter.py         [EXISTING]
└── math_extractor.py          [EXISTING]

services/
├── __init__.py
├── multi_question_service.py  [290 lines]
└── ...                        [EXISTING]

templates/
├── index.html                 [UPDATED]
├── multi_result.html          [140 lines]
├── result.html                [EXISTING]
└── ...

static/
├── css/
│   ├── style.css              [UPDATED]
│   └── multi_question.css     [360 lines]
├── js/
│   ├── main.js                [EXISTING]
│   └── multi_question.js      [290 lines]
├── images/                    [DYNAMIC]
└── ...

tests/
├── test_latex_formatter.py    [EXISTING]
└── ...

scripts/
└── ...
```

---

## Environment Variables

### Optional
```bash
# Debug mode
set FLASK_ENV=development
set FLASK_DEBUG=1

# Max upload size (bytes)
set MAX_CONTENT_LENGTH=33554432

# Temporary directory
set TEMP_DIR=temp_pdfs

# Output directory
set OUTPUT_DIR=outputs

# Image directory
set IMAGE_DIR=static/images
```

### Python Path
```bash
# Add project to Python path (if needed)
set PYTHONPATH=%PYTHONPATH%;c:\Users\ezhil\OneDrive\Desktop\latex_genarator
```

---

## Common Errors & Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `ModuleNotFoundError: PyMuPDF` | Missing package | `pip install PyMuPDF==1.23.8` |
| `FileNotFoundError: uploads/` | Directory missing | `mkdir uploads` or check path |
| `Port 5000 already in use` | Another app running | Change port or kill process |
| `PDF is corrupted` | Invalid PDF format | Try different PDF |
| `No questions detected` | Wrong numbering format | Check Q1, Q2 format exists |
| `Image not found in LaTeX` | Wrong path reference | Verify `/static/images/...` path |
| `OSError: Too many open files` | Resource leak | Restart server, check cleanup |

---

## Performance Optimization

### For Faster Processing
```bash
# 1. Use digital PDFs (not scanned)
# 2. Process smaller batches (<50 pages)
# 3. Disable OCR if not needed

# 4. Increase temp directory cleanup
python -c "
import os, shutil
for f in os.listdir('temp_pdfs'):
    shutil.rmtree(f'temp_pdfs/{f}')
"
```

### For Better Results
```bash
# 1. Ensure high-quality PDF (300+ dpi if scanned)
# 2. Clear, dark text
# 3. Consistent question numbering
# 4. Minimal complex graphics (slows processing)
```

### Server Requirements
```
Minimum:
- RAM: 2 GB
- Disk: 1 GB (for cache)
- CPU: 1.5 GHz

Recommended:
- RAM: 4 GB
- Disk: 5 GB
- CPU: 2.4 GHz
```

---

## Batch ID Format

```
Batch IDs are 12-character hex strings:
a1b2c3d4e5f6
deadbeef1234
cafebabe5678

Generated by: uuid.uuid4().hex[:12]

Batch ID in URLs:
http://localhost:5000/batch/a1b2c3d4e5f6
http://localhost:5000/download-batch/cafebabe5678

Metadata location:
outputs/{batch_id}/metadata.json

Results location:
outputs/{batch_id}/q_1/question_1.tex
outputs/{batch_id}/q_2/question_2.tex
```

---

## Useful Shortcuts

### Windows PowerShell
```powershell
# Navigate to project
cd Desktop\latex_genarator

# Activate venv
.\.venv\Scripts\Activate.ps1

# Run tests
python test_system.py

# Start server (backgrounded)
Start-Process -NoNewWindow python app.py

# Kill server on port 5000
Get-Process | Where-Object {$_.Port -eq 5000} | Stop-Process
```

### Linux/Mac (Bash)
```bash
# Activate venv
source .venv/bin/activate

# Run tests
python test_system.py

# Start server (backgrounded)
python app.py &

# Kill server
kill $(lsof -t -i:5000)
```

---

## Support Resources

1. **[QUICKSTART.md](QUICKSTART.md)** - User guide
2. **[IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)** - Technical details
3. **[ARCHITECTURE.md](ARCHITECTURE.md)** - System design
4. **[SUMMARY.md](SUMMARY.md)** - Feature overview
5. **Console logs** - Flask server output
6. **[test_system.py](test_system.py)** - Verify setup

---

**Print this card and keep it nearby!** 📝
