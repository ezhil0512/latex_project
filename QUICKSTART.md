# Quick Start Guide - Multi-Question PDF LaTeX Generator

## Installation & Setup

### 1. Install Dependencies
```bash
cd c:\Users\ezhil\OneDrive\Desktop\latex_genarator
.\.venv\Scripts\pip install -r requirements.txt
```

### 2. Verify Installation
```bash
python test_system.py
```
You should see: `ALL TESTS PASSED!`

### 3. Start the Server
```bash
python app.py
```

Output:
```
 * Running on http://127.0.0.1:5000
```

### 4. Open in Browser
Navigate to: **http://localhost:5000**

---

## Using the System

### Method 1: Single Image (Existing)
1. Click **"📷 Single Image"** tab
2. Upload PNG or JPG
3. (Optional) Add separate diagram
4. (Optional) Paste correct text if OCR fails
5. Click **"Generate LaTeX"**
6. Download or copy result

### Method 2: Multi-Question PDF (New!)
1. Click **"📄 Multi-Question PDF"** tab
2. Select your PDF file
3. Click **"Process PDF Questions"**
4. Wait for processing (1-5 minutes depending on PDF size)
5. Review results:
   - See extracted text for each question
   - View associated diagrams
   - Edit LaTeX as needed
6. Download options:
   - Individual LaTeX file (per question)
   - All LaTeX files as ZIP

---

## Features Overview

### Automatic Processing
- **Question Detection** - Splits PDF into individual questions
- **Text Extraction** - Clean OCR text
- **Diagram Extraction** - Separates images from text
- **LaTeX Generation** - Maintains formatting accuracy

### Batch Management
- **Batch ID** - Unique identifier for PDF processing
- **Metadata** - Stored in `outputs/{batch_id}/metadata.json`
- **Results Caching** - Reload results anytime using batch ID
- **ZIP Download** - All LaTeX files in one package

### Quality Assurance
- **Live Preview** - See formatted math and text
- **Copy LaTeX** - One-click copy to clipboard
- **Edit In-Place** - Modify before download
- **Error Logging** - Detailed logs in console

---

## Example Workflows

### Workflow 1: Process Exam Paper
```
Input:  exam_questions.pdf (10 pages, 5 questions)
         |
         v
Process:  [Auto-detect questions] [Extract text] [Extract images]
         |
         v
Output:  q_1.tex, q_2.tex, q_3.tex, q_4.tex, q_5.tex
         + diagrams/
         + metadata.json
         |
         v
Download: exam_questions_latex_files.zip
```

### Workflow 2: Chemistry Problem Set
```
Input:  chemistry_chapter3.pdf
         |
         v
Process:  [Detect 8 questions] [Extract chemical formulas] [Keep diagrams]
         |
         v
Output:  8 separate LaTeX files with proper chemistry formatting
         |
         v
Use in:  Homework solution key, study materials
```

### Workflow 3: Mixed Content (Text + Images)
```
Input:  physics_lab_report.pdf (diagrams, equations, text)
         |
         v
Process:  [Auto-separate text from images] [Preserve layout]
         |
         v
Output:  Questions with:
         - Clean LaTeX text
         - High-quality diagrams in static/images/
         - Proper \includegraphics paths
```

---

## Directory Structure After Use

```
project/
├── outputs/
│   ├── abc123xyz789/           # Batch ID (auto-generated)
│   │   ├── q_1/
│   │   │   └── question_1.tex
│   │   ├── q_2/
│   │   │   └── question_2.tex
│   │   └── metadata.json       # Batch info
│   └── def456uvw321/
│
├── static/images/
│   ├── abc123xyz789/
│   │   ├── q_1/
│   │   │   ├── diagram_0.png
│   │   │   └── diagram_1.png
│   │   ├── q_2/
│   │   │   └── diagram_0.png
│   └── def456uvw321/
│
└── temp_pdfs/                  # Auto-cleaned after processing
```

---

## Common Tasks

### Task 1: Reopen Previous Batch
If you closed the results page:
1. Copy the **Batch ID** from the footer
2. Go to: `http://localhost:5000/batch/{batch_id}`
3. All results reloaded from cache

### Task 2: Download All Questions as One ZIP
1. Process PDF
2. Click **"⬇️ Download All LaTeX (ZIP)"**
3. Unzip and get all question files

### Task 3: Edit & Re-download
1. In LaTeX textarea, make changes
2. Click **"📋 Copy LaTeX"**
3. Save locally or click **"⬇️ Download .tex"**

### Task 4: Include Diagrams in LaTeX
The system auto-includes:
```latex
\includegraphics[width=0.45\textwidth]{../static/images/{batch_id}/q_1/diagram_0.png}
```

---

## Troubleshooting

### Problem: PDF not processing
**Solution:**
- Check PDF is not corrupted (try opening in PDF viewer)
- Try smaller PDF first (< 20 pages)
- Check browser console for errors (F12)

### Problem: Questions not splitting correctly
**Solution:**
- Ensure PDF has clear question numbering (1., 2., Q1, etc.)
- Or questions separated by large gaps
- Check console for splitting method used

### Problem: LaTeX has errors
**Solution:**
- Click **"👁️ Preview"** to see formatted output
- Edit suspicious lines in LaTeX editor
- Most issues are auto-corrected by formatter

### Problem: Images not showing
**Solution:**
- Check image paths in LaTeX: `/static/images/...`
- Ensure images directory has files
- Try relative path: `../static/images/...`

### Problem: Slow processing
**Solution:**
- Try smaller PDF first
- Processing speed: ~2-3 sec per page
- Close other apps to free RAM

### Problem: Error: "PyMuPDF not found"
**Solution:**
```bash
.\.venv\Scripts\pip install PyMuPDF==1.23.8
```

---

## Performance Tips

### For Large PDFs (50+ pages)
1. Split into multiple files first
2. Process one file at a time
3. Download and consolidate results

### For Better OCR
- Use high-quality PDF (300+ dpi)
- Ensure text is clear and dark
- Avoid rotated text

### For Faster Processing
- Use digital PDF (not scanned)
- Disable diagram extraction if not needed
- Process during off-peak hours

---

## File Limits

- **PDF Size:** 16 MB (configurable in app.py)
- **Questions per PDF:** Unlimited
- **Diagrams per Question:** Unlimited
- **Storage:** No auto-delete (monitor /outputs folder)

---

## Advanced Usage

### Python API (For Automation)
```python
from services.multi_question_service import MultiQuestionService

service = MultiQuestionService()

# Process PDF
result = service.process_pdf("questions.pdf", "batch_001")

if result['status'] == 'success':
    batch = result['data']
    print(f"Processed {batch['total_questions']} questions")
    
    # Access results
    for q in batch['questions']:
        print(f"Q{q['question_num']}: {q['status']}")
        print(f"  LaTeX: {q['latex_path']}")
        print(f"  Images: {q['diagrams']}")

# Get cached batch
cached = service.get_batch_results("batch_001")
```

### Direct Module Usage
```python
from utils.pdf_processor import PDFProcessor
from utils.question_splitter import QuestionSplitter

# Extract PDF
pdf = PDFProcessor("file.pdf")
pages = pdf.extract_all_pages()

# Split questions
text = "\n".join([p['text'] for p in pages])
splitter = QuestionSplitter(text)
questions = splitter.split_questions()

print(f"Found {len(questions)} questions")
```

---

## Support & Documentation

- **Implementation Guide:** `IMPLEMENTATION_GUIDE.md`
- **Test Script:** `python test_system.py`
- **Code Comments:** See utils/ and services/
- **Issue Logs:** Check Flask console output

---

## Version Info

- **Version:** 2.0
- **Release:** April 2026
- **Backward Compatible:** ✓ Yes
- **Status:** Production Ready

---

## Next Steps

1. ✅ Installation complete
2. ✅ System verified
3. 📄 Try with sample PDF
4. 🚀 Use in production
5. 📚 Read `IMPLEMENTATION_GUIDE.md` for advanced topics

**Ready to convert PDFs to LaTeX? Start here:** http://localhost:5000 🎉
