# Architecture & Use Cases

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        USER INTERFACE (Web)                              │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                     Index.html - Tab UI                          │   │
│  │  ┌─────────────────────────────────────────────────────────────┐ │   │
│  │  │ [📷 Single Image] [📄 Multi-Question PDF] ◄───── Tab Select │ │   │
│  │  └─────────────────────────────────────────────────────────────┘ │   │
│  │    ↓                      ↓                                        │   │
│  │  Tab 1                  Tab 2                                      │   │
│  │  Single Image           Multi-PDF                                 │   │
│  │  (existing)             (new feature)                             │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                        ↓                    ↓
        ┌───────────────────────┐  ┌──────────────────────────┐
        │  Single Image Route   │  │  Multi-PDF Route         │
        │  /upload (existing)   │  │  /process-pdf (new) POST │
        └───────────────────────┘  └──────────────────────────┘
                        ↓                    ↓
        ┌───────────────────────┐  ┌──────────────────────────┐
        │   Image Processing    │  │   PDF Processing         │
        │   (existing)          │  │   (new pipeline)         │
        │                       │  │                          │
        │ 1. OCR Extract        │  │ 1. PDFProcessor          │
        │ 2. LaTeX Gen          │  │    ├─ Extract pages      │
        │ 3. Download/Preview   │  │    ├─ Get text blocks    │
        │                       │  │    └─ Extract images     │
        └───────────────────────┘  │                          │
                                    │ 2. QuestionSplitter      │
                                    │    ├─ Detect Q1, Q2...   │
                                    │    ├─ Split by numbering │
                                    │    └─ Fallback: layout   │
                                    │                          │
                                    │ 3. DiagramExtractor      │
                                    │    ├─ Separate text/img  │
                                    │    ├─ Classify regions   │
                                    │    └─ Save diagrams      │
                                    │                          │
                                    │ 4. MultiQuestionService  │
                                    │    ├─ Process per Q      │
                                    │    ├─ Generate LaTeX     │
                                    │    ├─ Save results       │
                                    │    └─ Create metadata    │
                                    └──────────────────────────┘
                                           ↓
        ┌─────────────────────────────────────────────────────┐
        │    Database & File Storage                          │
        │  ┌──────────────────────────────────────────────┐   │
        │  │ outputs/                                     │   │
        │  │ ├─ {batch_id}/                              │   │
        │  │ │  ├─ q_1/question_1.tex                    │   │
        │  │ │  ├─ q_2/question_2.tex                    │   │
        │  │ │  └─ metadata.json                         │   │
        │  │                                              │   │
        │  │ static/images/                               │   │
        │  │ ├─ {batch_id}/                              │   │
        │  │ │  ├─ q_1/diagram_0.png                     │   │
        │  │ │  └─ q_2/diagram_0.png                     │   │
        │  └──────────────────────────────────────────────┘   │
        └─────────────────────────────────────────────────────┘
                                           ↓
        ┌─────────────────────────────────────────────────────┐
        │  Results Page: multi_result.html                    │
        │  ┌──────────────────────────────────────────────┐   │
        │  │ Batch ID: abc123xyz789  Processed: 2 of 3   │   │
        │  ├──────────────────────────────────────────────┤   │
        │  │ QUESTION 1                                   │   │
        │  │ ┌──────────────────────────────────────────┐ │   │
        │  │ │ Text: "Given equation x+y=5..."         │ │   │
        │  │ │ Diagrams: 2 images                      │ │   │
        │  │ │ LaTeX: \documentclass{article}...       │ │   │
        │  │ │ [👁️ Preview] [📋 Copy] [⬇️ Download]   │ │   │
        │  │ └──────────────────────────────────────────┘ │   │
        │  ├──────────────────────────────────────────────┤   │
        │  │ QUESTION 2                                   │   │
        │  │ [Similar card layout...]                    │   │
        │  ├──────────────────────────────────────────────┤   │
        │  │ [⬇️ Download All as ZIP]                    │   │
        │  └──────────────────────────────────────────────┘   │
        └─────────────────────────────────────────────────────┘
```

---

## Module Responsibilities

### PDFProcessor (`utils/pdf_processor.py`)
**Purpose:** Extract pages, text, and images from PDF

**Input:** PDF file path  
**Output:** List of page dictionaries with text, images, coordinates

```python
pdf = PDFProcessor("document.pdf")
pages = pdf.extract_all_pages()
# Returns:
# [
#   {
#     'page_num': 1,
#     'text': 'Question 1: ...',
#     'images': [Image1, Image2, ...],
#     'text_blocks': [(x,y,w,h,text), ...]
#   },
#   ...
# ]
```

**Key Methods:**
- `is_scanned_pdf()` - Detect if PDF is scanned or digital
- `extract_all_pages()` - Get all page data
- `extract_text_blocks()` - Get text regions with coordinates
- `_extract_page_images()` - Extract and store images

---

### QuestionSplitter (`utils/question_splitter.py`)
**Purpose:** Detect and split questions into separate entities

**Input:** Combined text from PDF pages  
**Output:** List of individual question texts

```python
text = "1. First question...\n2. Second question..."
splitter = QuestionSplitter(text)
questions = splitter.split_questions()
# Returns:
# [
#   "First question...",
#   "Second question..."
# ]
```

**Splitting Strategies:**
1. **Numbering-based** (Primary)
   - Patterns: "1.", "1)", "(1)", "Q1", "Question 1"
   - Line-by-line detection

2. **Layout-based** (Fallback)
   - Large vertical gaps (100px+) indicate question boundary
   - Used when numbering not detected

**Key Methods:**
- `split_questions()` - Main orchestrator
- `_has_clear_numbering()` - Check if numbering exists
- `_split_by_numbering()` - Line-based splitting
- `_split_by_layout()` - Gap-based splitting
- `validate_split()` - Verify results

---

### DiagramExtractor (`utils/diagram_extractor.py`)
**Purpose:** Separate text regions from diagram regions

**Input:** Page image with text and diagrams mixed  
**Output:** Separated text and diagram regions

```python
extractor = DiagramExtractor()
result = extractor.separate_text_from_diagram(page_image)
# Returns:
# {
#   'text_regions': [...],      # Text rectangles
#   'diagram_regions': [...],   # Diagram rectangles
#   'main_diagram': Image       # Largest diagram
# }
```

**Classification Heuristics:**
- **Aspect Ratio**: > 3.0 → Text (wide lines)
- **Edge Density**: > 0.15 → Text (many lines)
- **Line Orientation**: Horizontal >> Vertical → Text

**Key Methods:**
- `separate_text_from_diagram()` - Main classifier
- `_is_text_region()` - Multi-heuristic detection
- `extract_diagram()` - Save specific region
- `find_main_diagram()` - Largest diagram
- `get_text_only_image()` - Remove diagrams for OCR

---

### MultiQuestionService (`services/multi_question_service.py`)
**Purpose:** Orchestrate entire pipeline and manage batch results

**Input:** PDF file, batch ID  
**Output:** Batch results with per-question LaTeX

```python
service = MultiQuestionService()
result = service.process_pdf("exam.pdf", "batch_001")
# Returns:
# {
#   'status': 'success',
#   'data': {
#     'batch_id': 'batch_001',
#     'total_questions': 3,
#     'questions': [
#       {
#         'question_num': 1,
#         'status': 'success',
#         'text': '...',
#         'latex_path': 'outputs/batch_001/q_1/...',
#         'diagrams': ['image_0.png', 'image_1.png']
#       },
#       ...
#     ]
#   }
# }
```

**Key Methods:**
- `process_pdf()` - Main entry point
- `_process_single_question()` - Per-question processor
- `_save_batch_metadata()` - Persist results
- `get_batch_results()` - Retrieve cached results
- `cleanup_temp_files()` - Clean temporaries

---

## Use Case Flows

### Use Case 1: Chemistry Exam (5 Questions)

```
USER ACTION:
  Click "📄 Multi-Question PDF"
  Select "chemistry_exam.pdf"
  Click "Process"
  
SYSTEM FLOW:
  1. PDFProcessor
     - Read 10 pages
     - Extract 200 text blocks
     - Extract 15 images
     
  2. QuestionSplitter
     - Detect pattern: "1)", "2)", "3)", ...
     - Split into 5 questions
     
  3. DiagramExtractor (per question)
     - Q1: 2 diagrams found → save
     - Q2: 0 diagrams
     - Q3: 1 diagram found → save
     - Q4: 0 diagrams
     - Q5: 3 diagrams found → save
     
  4. LaTeX Generator (per question)
     - Q1: Chemistry formula → ✓ Success
     - Q2: Balance equation → ✓ Success
     - Q3: Orbital diagram → ✓ Success
     - Q4: Redox reaction → ✓ Success
     - Q5: Bonding theory → ✓ Success
     
  5. Save Results
     - outputs/abc123xyz789/q_1/question_1.tex
     - outputs/abc123xyz789/q_2/question_2.tex
     - ... (3, 4, 5)
     - outputs/abc123xyz789/metadata.json
     
RESULT:
  User sees multi_result.html with all 5 questions
  Each card shows: text preview, diagram count, LaTeX editor
  Option to download individual or all as ZIP
```

---

### Use Case 2: Scanned Textbook Pages (8 Questions)

```
USER ACTION:
  Click "📄 Multi-Question PDF"
  Select "textbook_chapter3.pdf" (scanned)
  Click "Process"
  
SYSTEM FLOW:
  1. PDFProcessor
     - Detect: is_scanned_pdf() = True
     - Extract pages + OCR text
     
  2. QuestionSplitter
     - No clear numbering detected
     - Fallback to layout-based splitting
     - Detect vertical gaps between questions
     - Split into 8 questions
     
  3. DiagramExtractor
     - Many text regions (scanned = more noise)
     - Careful classification
     - Extract high-confidence diagrams
     
  4. LaTeX Generator
     - Run OCR cleanup on each question
     - Fix common scanned PDF errors
     - Generate LaTeX
     
RESULT:
  Output includes flag: "scanned_pdf": true
  User can see warning: "⚠️ Scanned PDF - OCR applied"
  Preview shows any OCR issues
  User can edit before final download
```

---

### Use Case 3: Mixed Content (1 Long Question with 4 Diagrams)

```
USER ACTION:
  Click "📄 Multi-Question PDF"
  Select "single_long_question.pdf"
  Click "Process"
  
SYSTEM FLOW:
  1. PDFProcessor
     - Read 2 pages
     - Text: "Analyze the following circuit..."
     - Images: 4 circuit diagrams
     
  2. QuestionSplitter
     - No question boundaries detected
     - Treat entire document as 1 question
     
  3. DiagramExtractor
     - Identify 4 diagrams
     - Save as: diagram_0.png, diagram_1.png, etc.
     
  4. LaTeX Generator
     - Generate single .tex file
     - Include all 4 diagrams with proper paths:
       \includegraphics{../static/images/batch_id/q_1/diagram_0.png}
       \includegraphics{../static/images/batch_id/q_1/diagram_1.png}
       ...
     
RESULT:
  Single question card with:
  - Full problem text
  - 4-image gallery
  - Complete LaTeX with all image references
```

---

### Use Case 4: Download & Integrate with LaTeX

```
USER ACTION:
  Process PDF → Get results → Click "⬇️ Download All (ZIP)"
  
SYSTEM OUTPUT:
  exam_latex_files.zip
  ├── q_1/
  │   └── question_1.tex
  ├── q_2/
  │   └── question_2.tex
  └── ... (more questions)
  
USER NEXT STEPS:
  1. Extract ZIP
  2. Compile with: pdflatex question_1.tex
  3. Result: question_1.pdf
  
  For documents with images:
  4. Ensure images/ folder has diagrams
  5. Compile again (path references will work)
  
ALTERNATIVE:
  - Copy from preview editor
  - Paste into TeXworks / Overleaf
  - Diagrams auto-reference with correct paths
```

---

## Data Flow Diagram

```
┌──────────────────────────────────────────┐
│ PDF Input                                 │
│ - chemistry_exam.pdf (5 questions)       │
│ - 10 pages                                │
│ - Contains text + diagrams                │
└──────────────┬───────────────────────────┘
               │
               ├─→ [PDFProcessor]
               │   Extract: pages, text, images
               │   Output: page[] with text_blocks, images
               │
               ├─→ [QuestionSplitter]
               │   Input: combined text
               │   Detect: Q1, Q2, Q3, Q4, Q5
               │   Output: questions[]
               │
               ├─→ [DiagramExtractor] ×5
               │   Input: Q_i text + images
               │   Classify: text_region | diagram_region
               │   Output: diagrams[]
               │
               ├─→ [LaTeX Formatter] ×5
               │   Input: Q_i text + images
               │   Process: OCR cleanup, formula fix
               │   Output: full_latex
               │
               ├─→ [Batch Manager]
               │   Save: outputs/{batch_id}/q_i/question_i.tex
               │   Save: static/images/{batch_id}/q_i/diagram_j.png
               │   Save: outputs/{batch_id}/metadata.json
               │
               └─→ [Result Handler]
                   Render: multi_result.html
                   Show: per-question cards
                   Options: preview, copy, download
                   
Output: ZIP with all .tex files + metadata
```

---

## Performance Characteristics

| Operation | Time (5-page PDF) | Bottleneck |
|-----------|-------------------|-----------|
| PDF Extract | 1-2 sec | File I/O |
| Question Split | <1 sec | Regex matching |
| Text Extraction | 1-3 sec | OCR (if scanned) |
| Image Extraction | 1-2 sec | Disk write |
| Diagram Detection | 2-3 sec | OpenCV processing |
| LaTeX Generation | 1-2 sec | Formatter logic |
| **Total** | **~8-15 sec** | OCR (if scanned) |

**Optimization Tips:**
- Use digital PDFs (not scanned) → 50% faster
- Process smaller PDFs first to test
- Server resources: 2+ GB RAM recommended

---

## Error Handling

```
PDF Upload
    ↓
Valid? No → Show error → User uploads again
    ↓ Yes
Extract Pages
    ↓
Success? No → Mark page failed, continue → Show warnings
    ↓ Yes
Split Questions
    ↓
Questions found? No → Treat as single question
    ↓ Yes
Process Each Question
    ↓
Success? No → Show error for that question, continue
    ↓ Yes
Generate Results
    ↓
Return batch with:
  - Successful questions ✓
  - Failed questions with error messages ✗
  - Partial results available
  - User can download what worked
```

**Error Messages:**
- "PDF is corrupted" → Try different PDF
- "No questions detected" → Check numbering format
- "Image extraction failed" → Check disk space
- "LaTeX generation failed" → Try editing text

---

## Future Enhancements

1. **Async Processing**
   - Queue long PDFs
   - WebSocket updates to user

2. **Question Reordering**
   - Drag-drop in results
   - Regenerate in new order

3. **Tesseract OCR**
   - Optional scanned PDF enhancement
   - Improve OCR accuracy

4. **Question Metadata**
   - Difficulty levels
   - Topics/chapters
   - Expected solutions

5. **Collaborative Editing**
   - Share batch IDs
   - Comment on questions
   - Track changes

6. **Database Integration**
   - Store results permanently
   - Search/filter questions
   - Build question bank

---

**Questions?** See [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) for detailed technical docs.
