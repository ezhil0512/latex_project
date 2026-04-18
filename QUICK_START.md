# Quick Start Guide - LaTeX Generator (Unified System)

## 🚀 For Users

### Get Started in 3 Steps

#### Step 1: Start the Server
```bash
# Windows PowerShell
./run.ps1

# Or manually:
python app.py
```

Server starts at: **http://localhost:5000**

#### Step 2: Open the App
```
Open browser → http://localhost:5000
```

You'll see a single upload form. Done! That's it. No tabs. No confusion.

#### Step 3: Upload & Process
```
1. Click [Choose File]
2. Pick an image (PNG/JPG) or PDF
3. (Optional) Add text corrections
4. Click [Process & Generate LaTeX]
5. Get your LaTeX output!
```

---

### What You Can Upload

✅ **Images:**
- `.png` - PNG images
- `.jpg`, `.jpeg` - JPEG photos

✅ **PDFs:**
- `.pdf` - Single or multi-page documents

❌ **Not supported:**
- `.gif`, `.bmp`, `.tiff` (use PNG instead)
- `.docx`, `.pptx`, `.xlsx` (convert to PDF first)
- Encrypted/password-protected PDFs

---

### Examples

#### Example 1: Chemistry Homework
```
1. Take photo of chemistry problem
2. Upload image
3. System extracts:
   - Chemical equations (as text)
   - Molecular diagrams (as images)
   - Reaction conditions
4. Get LaTeX-formatted homework!
```

#### Example 2: Physics Exam
```
1. Export exam as PDF
2. Upload PDF
3. System processes each question:
   - Question 1: Text → LaTeX
   - Question 2: Text + diagram → LaTeX
   - Question 3: Text → LaTeX
4. Get all questions as downloadable files!
```

#### Example 3: Quick Text to LaTeX
```
1. Upload image with handwritten notes
2. Manually correct OCR errors in text field
3. Click "Use only manual text"
4. Get clean LaTeX from your corrections!
```

---

### Result Page Guide

After processing, you'll see:

**For Images:**
```
📝 EXTRACTED TEXT
   Your OCR'd text (editable)

🖼️ EXTRACTED IMAGES
   Any diagrams found in the image

⚙️ LATEX CODE
   The final LaTeX document
   - [Copy] button
   - [Download] button  
   - [Preview] to see it rendered
```

**For PDFs:**
```
📋 QUESTIONS
   Question 1
   ├─ Text extracted
   ├─ Images gallery
   └─ [View LaTeX] [Copy] [Download]
   
   Question 2
   ├─ Text extracted
   ├─ Images gallery
   └─ [View LaTeX] [Copy] [Download]
   
📦 BATCH ACTIONS
   [Download All as ZIP]
```

---

### Troubleshooting

| Problem | Solution |
|---------|----------|
| "Server won't start" | Close other Python apps, try port 5001 |
| "File not uploading" | Check file size (<50MB), file type valid |
| "No text extracted" | Try different image angle or quality |
| "Diagrams not found" | Diagram might be too small or blurry |
| "PDF too slow" | Large PDFs take time, be patient |

---

## 🛠️ For Developers

### System Architecture

```
app.py                          Main Flask server
├─ /                            Index page (unified form)
├─ /process-unified (POST)      Single processing endpoint
│  └─ UnifiedProcessor.process()
│
services/
├─ unified_processor.py         Core pipeline
│  ├─ UnifiedProcessor class
│  ├─ File type detection
│  ├─ Image processing
│  └─ PDF processing
└─ ...other services
    
templates/
├─ index.html                   Unified upload form
├─ unified_result.html          Unified result page
└─ ...other templates

static/
├─ css/unified_result.css       Result page styling
└─ ...other assets
```

### Key Files

**Must understand these:**

1. **`services/unified_processor.py`**
   - Main processing orchestrator
   - File type detection
   - Image/PDF handling
   - OCR & diagram extraction

2. **`templates/index.html`**
   - Single unified upload form
   - Adapts to file type
   - Client-side preview

3. **`templates/unified_result.html`**
   - Handles single & multi-question results
   - Conditional rendering
   - Download functionality

4. **`app.py` route `/process-unified`**
   - Entry point for processing
   - File upload handling
   - Error management

### Code Quick Reference

#### Using UnifiedProcessor
```python
from services.unified_processor import UnifiedProcessor

processor = UnifiedProcessor(
    output_dir="outputs",
    image_dir="static/images"
)

result = processor.process(
    file_path="uploads/myfile.pdf",
    manual_text="Optional corrections",
    use_manual_only=False
)

if result["status"] == "success":
    file_type = result["file_type"]  # "image" or "pdf"
    data = result["result"]
    questions = result["questions"]  # List of questions
```

#### Adding New File Type
```python
# In unified_processor.py

def _detect_file_type(self, file_path):
    ext = Path(file_path).suffix.lower()
    if ext in {".png", ".jpg", ".jpeg"}:
        return "image"
    elif ext == ".pdf":
        return "pdf"
    elif ext == ".docx":  # NEW
        return "docx"
    return "unknown"

def _process_docx(self, file_path, **kwargs):
    # Implement DOCX processing here
    return {"extracted_text": "..."}
```

#### Customizing LaTeX Output
```python
# In unified_processor.py _format_latex()

latex_template = r"""
\documentclass{article}
\usepackage{graphicx}
\usepackage{amsmath}

\title{Custom Title}  # ← Customize here

\begin{document}
\maketitle

{equations_here}

{images_here}

\end{document}
"""
```

### Common Development Tasks

#### Add preprocessing step
```python
# In UnifiedProcessor._process_image()

# Before OCR
image = cv2.imread(file_path)
image = self._preprocess_image(image)  # ← Add this
extracted_text = ocr_engine.extract(image)
```

#### Add custom OCR engine
```python
# Create services/ocr_engine.py
class CustomOCR:
    def extract(self, image_array):
        # Your OCR logic
        return "extracted text"

# In unified_processor.py
from services.ocr_engine import CustomOCR
self.ocr = CustomOCR()

# Use it
text = self.ocr.extract(image)
```

#### Add new extraction feature
```python
# In UnifiedProcessor._process_image()

result = {
    "extracted_text": text,
    "equations": equations,
    "images": images,
    "latex_output": latex,
    "your_new_feature": self._extract_new_thing(image)  # ← Add this
}
```

### Testing

#### Test single file
```bash
python -c "
from services.unified_processor import UnifiedProcessor
p = UnifiedProcessor()
result = p.process('uploads/test.jpg')
print(result['status'])
"
```

#### Test PDF processing
```bash
python -c "
from services.unified_processor import UnifiedProcessor
p = UnifiedProcessor()
result = p.process('uploads/exam.pdf')
print(f\"Questions: {len(result['questions'])}\")
"
```

#### Check imports
```bash
python -c "from services.unified_processor import UnifiedProcessor; print('✓ OK')"
```

### Debugging

#### Enable verbose logging
```python
# In app.py
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# In unified_processor.py
logger.debug(f"Processing: {file_path}")
logger.debug(f"File type: {file_type}")
```

#### Check file processing
```bash
# Monitor what happens
python app.py  # Watch terminal output

# Then upload file and check:
# 1. Upload message
# 2. File type detection
# 3. Processing steps
# 4. LaTeX generation
# 5. Success/error
```

#### Inspect result data
```python
# In app.py /process-unified
print("Result keys:", result.keys())
print("File type:", result.get("file_type"))
print("Questions:", len(result.get("questions", [])))
print("Status:", result.get("status"))
```

### Configuration

#### Change upload size
```python
# app.py
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB
```

#### Change output directory
```python
# app.py
OUTPUT_DIR = Path("my_outputs")  # Was: "outputs"
```

#### Disable certain features
```python
# services/unified_processor.py
self.extract_diagrams = True   # Set to False to skip
self.extract_equations = True  # Set to False to skip
```

### Performance Tips

1. **Compress images before upload**
   - Smaller files = faster processing

2. **Use OCR cache**
   - Don't re-process same file

3. **Parallel PDF processing**
   - Process pages in parallel

4. **Lower image resolution**
   - 150 DPI usually sufficient

### Extension Ideas

```python
# Add these features:

1. Real-time preview
   # Stream LaTeX as it's generated
   
2. Math equation solver
   # Call SymPy for symbolic computation
   
3. Code extraction
   # Extract code blocks from PDFs
   
4. Template selection
   # Multiple LaTeX templates
   
5. Batch processing
   # Multiple files at once
   
6. API mode
   # Accept JSON requests
   
7. OCR language support
   # Detect language automatically
   
8. Integration with Overleaf
   # Direct upload to Overleaf project
```

---

## 📊 Monitoring

### Server Health

```bash
# Check if running
curl http://localhost:5000/

# Check Python imports
python -c "import app; import services.unified_processor; print('✓ OK')"

# Check file permissions
dir outputs/
dir uploads/
dir static/
```

### Performance Monitoring

```python
# Add timing to unified_processor.py

import time

def process(self, file_path, **kwargs):
    start = time.time()
    
    # ... processing ...
    
    elapsed = time.time() - start
    print(f"Processing took {elapsed:.2f}s")
```

---

## 📚 Documentation Files

- **`UNIFIED_SYSTEM.md`** - Complete system documentation
- **`BEFORE_AND_AFTER.md`** - Comparison with old system
- **`QUICK_START.md`** - This file
- **`README.md`** - Original project readme

---

## 🎯 Next Steps

### As a User
1. Run the server
2. Upload an image or PDF
3. Get LaTeX
4. Celebrate! 🎉

### As a Developer
1. Review `services/unified_processor.py`
2. Check `templates/unified_result.html`
3. Read `app.py` route `/process-unified`
4. Add custom features as needed

### For Contribution
1. Follow existing code style
2. Add docstrings for new functions
3. Test before committing
4. Update documentation

---

## ✅ Verification Checklist

Before using in production:

- [ ] Server starts without errors: `python app.py`
- [ ] Can upload image: Open browser, try PNG
- [ ] Can upload PDF: Open browser, try PDF
- [ ] LaTeX generates: Check output
- [ ] Downloads work: Try download button
- [ ] No errors in console: Watch terminal
- [ ] File permissions OK: Check outputs/ directory
- [ ] Imports all work: `python -c "import services.unified_processor"`

---

## 📞 Support

If something breaks:

1. **Check the errors**
   - Look in terminal output
   - Check browser console (F12)
   - Check browser network tab

2. **Check documentation**
   - Read error messages carefully
   - Look in UNIFIED_SYSTEM.md
   - Search for the error type

3. **Check file**
   - Is file corrupted?
   - Is file size reasonable?
   - Is file type correct?

4. **Restart server**
   - `Ctrl+C` to stop
   - `python app.py` to start fresh

---

**Ready to generate some LaTeX?** 🚀

Let's go! →
