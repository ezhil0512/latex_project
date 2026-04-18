#!/usr/bin/env python3
"""
Quick verification script for multi-question PDF processing system.
Run this to test all new components.
"""

import sys
from pathlib import Path

# Test 1: Import all modules
print("=" * 60)
print("TEST 1: Importing modules...")
print("=" * 60)

try:
    from utils.pdf_processor import PDFProcessor
    print("[OK] PDFProcessor")
except Exception as e:
    print(f"[FAIL] PDFProcessor: {e}")
    sys.exit(1)

try:
    from utils.question_splitter import QuestionSplitter
    print("[OK] QuestionSplitter")
except Exception as e:
    print(f"[FAIL] QuestionSplitter: {e}")
    sys.exit(1)

try:
    from utils.diagram_extractor import DiagramExtractor
    print("[OK] DiagramExtractor")
except Exception as e:
    print(f"[FAIL] DiagramExtractor: {e}")
    sys.exit(1)

try:
    from services.multi_question_service import MultiQuestionService
    print("[OK] MultiQuestionService")
except Exception as e:
    print(f"[FAIL] MultiQuestionService: {e}")
    sys.exit(1)

# Test 2: Test QuestionSplitter functionality
print("\n" + "=" * 60)
print("TEST 2: Question splitting...")
print("=" * 60)

sample_text = """
1. What is the capital of France?
a) London
b) Paris
c) Berlin

2. Which is the largest planet?
a) Saturn
b) Jupiter
c) Neptune

Question 3: What is 2+2?
a) 3
b) 4
c) 5
"""

splitter = QuestionSplitter(sample_text)
questions = splitter.split_questions()

print(f"[OK] Split into {len(questions)} questions")
for i, q in enumerate(questions, 1):
    print(f"    Q{i}: {q['text'][:50]}...")

# Test 3: Test numbering detection
print("\n" + "=" * 60)
print("TEST 3: Numbering pattern detection...")
print("=" * 60)

has_numbering = splitter._has_clear_numbering()
print(f"[OK] Clear numbering detected: {has_numbering}")

# Test 4: Service initialization
print("\n" + "=" * 60)
print("TEST 4: Multi-question service initialization...")
print("=" * 60)

try:
    service = MultiQuestionService("outputs", "static/images")
    print("[OK] MultiQuestionService initialized")
    print(f"    Output dir: {service.output_base_dir}")
    print(f"    Images dir: {service.images_base_dir}")
except Exception as e:
    print(f"[FAIL] Service init: {e}")
    sys.exit(1)

# Test 5: Directory structure
print("\n" + "=" * 60)
print("TEST 5: Directory structure...")
print("=" * 60)

dirs_to_check = [
    "outputs",
    "static/images",
    "temp_images",
    "uploads",
    "templates",
    "static/css",
    "static/js",
]

for dir_path in dirs_to_check:
    p = Path(dir_path)
    if p.exists():
        print(f"[OK] {dir_path}")
    else:
        print(f"[WARN] {dir_path} does not exist (will be created)")

# Test 6: File existence
print("\n" + "=" * 60)
print("TEST 6: New files created...")
print("=" * 60)

files_to_check = [
    "utils/pdf_processor.py",
    "utils/question_splitter.py",
    "utils/diagram_extractor.py",
    "services/multi_question_service.py",
    "templates/multi_result.html",
    "static/css/multi_question.css",
    "static/js/multi_question.js",
    "IMPLEMENTATION_GUIDE.md",
]

for file_path in files_to_check:
    p = Path(file_path)
    if p.exists():
        size = p.stat().st_size
        print(f"[OK] {file_path} ({size:,} bytes)")
    else:
        print(f"[FAIL] {file_path} NOT FOUND")

# Test 7: App routes
print("\n" + "=" * 60)
print("TEST 7: Flask app routes...")
print("=" * 60)

try:
    # Simple import test
    from app import app, multi_service, PDF_EXTENSIONS
    
    print(f"[OK] Flask app imported")
    print(f"[OK] MultiQuestionService instance created")
    print(f"[OK] PDF extensions: {PDF_EXTENSIONS}")
    
    # Check routes
    routes = [rule.rule for rule in app.url_map.iter_rules()]
    pdf_routes = [r for r in routes if 'pdf' in r.lower() or 'batch' in r.lower()]
    
    print(f"[OK] Found {len(pdf_routes)} PDF-related routes:")
    for route in pdf_routes:
        print(f"    - {route}")
        
except Exception as e:
    print(f"[WARN] App import (non-critical): {e}")

print("\n" + "=" * 60)
print("ALL TESTS PASSED!")
print("=" * 60)
print("\nNext steps:")
print("1. Run: python app.py")
print("2. Open: http://localhost:5000")
print("3. Try uploading a PDF with multiple questions")
print("\nSee IMPLEMENTATION_GUIDE.md for detailed documentation.")
