"""
Multi-question processing service that orchestrates PDF extraction,
question splitting, diagram extraction, and LaTeX generation.
"""

from pathlib import Path
from typing import Dict, List
from datetime import datetime
import json
import logging
import shutil

from utils.pdf_processor import PDFProcessor
from utils.question_splitter import QuestionSplitter
from utils.diagram_extractor import DiagramExtractor
from utils.latex_formatter import build_latex_document, format_mixed_content
from services.math_service import extract_math

logger = logging.getLogger(__name__)


class MultiQuestionService:
    """
    Service for processing PDFs with multiple questions.
    Orchestrates extraction, splitting, and LaTeX generation.
    """

    def __init__(self, output_base_dir: str = "outputs", images_base_dir: str = "static/images"):
        """
        Initialize the service.
        
        Args:
            output_base_dir: Directory for LaTeX outputs
            images_base_dir: Directory for extracted images
        """
        self.output_base_dir = Path(output_base_dir)
        self.output_base_dir.mkdir(exist_ok=True)
        
        self.images_base_dir = Path(images_base_dir)
        self.images_base_dir.mkdir(exist_ok=True)
        
        self.temp_dir = Path("temp_images")
        self.temp_dir.mkdir(exist_ok=True)

    def process_pdf(self, pdf_path: str, batch_name: str) -> Dict:
        """
        Main entry point for PDF processing.
        
        Args:
            pdf_path: Path to PDF file
            batch_name: Batch identifier
        
        Returns:
            Dict with status and results
        """
        try:
            # Step 1: Extract PDF
            logger.info(f"Processing PDF: {pdf_path}")
            with PDFProcessor(pdf_path) as processor:
                pages = processor.extract_all_pages()
                is_scanned = processor.is_scanned_pdf()
            
            logger.info(f"Extracted {len(pages)} pages (scanned: {is_scanned})")
            
            # Step 2: Extract all text and combine
            all_text = "\n".join([p['text'] for p in pages])
            
            # Step 3: Collect text blocks for layout analysis
            text_blocks = []
            with PDFProcessor(pdf_path) as processor:
                for page_num in range(len(processor.doc)):
                    blocks = processor.get_page_text_blocks(page_num)
                    text_blocks.extend(blocks)
            
            # Step 4: Split into questions
            logger.info("Splitting into questions...")
            splitter = QuestionSplitter(all_text, text_blocks)
            questions = splitter.split_questions()
            
            is_valid, message = splitter.validate_split(questions)
            logger.info(f"Split validation: {message}")
            
            # Step 5: Process each question
            batch_results = {
                'batch_id': batch_name,
                'total_questions': len(questions),
                'questions': [],
                'timestamp': self._get_timestamp(),
                'is_scanned_pdf': is_scanned
            }
            
            for q_index, question_data in enumerate(questions, 1):
                logger.info(f"Processing question {q_index}/{len(questions)}")
                q_result = self._process_single_question(
                    q_index,
                    question_data,
                    pages,
                    batch_name
                )
                batch_results['questions'].append(q_result)
            
            # Step 6: Save batch metadata
            self._save_batch_metadata(batch_name, batch_results)
            
            logger.info(f"Batch {batch_name} processing complete")
            return {'status': 'success', 'data': batch_results}
        
        except Exception as e:
            logger.error(f"Error processing PDF: {e}", exc_info=True)
            return {'status': 'error', 'message': str(e)}

    def _process_single_question(self, q_num: int, q_data: Dict,
                                pages: List, batch_name: str) -> Dict:
        """
        Process a single question.
        
        Args:
            q_num: Question number
            q_data: Question data dict from splitter
            pages: List of extracted pages
            batch_name: Batch identifier
        
        Returns:
            Question result dict
        """
        question_text = q_data.get('text', '')
        
        # Extract associated diagrams
        diagrams = []
        for page_data in pages:
            for img_info in page_data.get('images', []):
                diagrams.append(img_info)
        
        # Extract math equations
        equations = []
        try:
            if diagrams:
                equations = extract_math(diagrams[0]['path'])
        except Exception as e:
            logger.warning(f"Could not extract equations: {e}")
        
        # Generate LaTeX
        try:
            latex_body = format_mixed_content(question_text, equations)
            latex_doc = build_latex_document(latex_body)
        except Exception as e:
            logger.error(f"Error generating LaTeX for question {q_num}: {e}")
            latex_doc = f"% Error generating LaTeX: {e}\n{question_text}"
        
        # Save LaTeX output
        output_dir = self.output_base_dir / batch_name / f"q_{q_num}"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        tex_filename = f"question_{q_num}.tex"
        tex_path = output_dir / tex_filename
        tex_path.write_text(latex_doc, encoding='utf-8')
        
        # Save associated images
        img_dir = self.images_base_dir / batch_name / f"q_{q_num}"
        img_dir.mkdir(parents=True, exist_ok=True)
        
        saved_images = []
        for idx, diagram_info in enumerate(diagrams):
            try:
                src_path = Path(diagram_info['path'])
                if src_path.exists():
                    dst_filename = f"diagram_{idx}.png"
                    dst_path = img_dir / dst_filename
                    shutil.copy(str(src_path), str(dst_path))
                    
                    # Store relative path for web serving
                    rel_path = dst_path.relative_to(Path('static')).as_posix()
                    saved_images.append(rel_path)
            except Exception as e:
                logger.warning(f"Error copying diagram {idx}: {e}")
        
        return {
            'question_num': q_num,
            'text': question_text[:500] + ('...' if len(question_text) > 500 else ''),
            'full_latex': latex_doc,
            'latex_path': str(tex_path.relative_to(self.output_base_dir)),
            'latex_filename': tex_filename,
            'diagrams': saved_images,
            'equations_count': len(equations),
            'status': 'success'
        }

    def _save_batch_metadata(self, batch_name: str, batch_results: Dict):
        """
        Save batch processing metadata.
        
        Args:
            batch_name: Batch identifier
            batch_results: Batch results dict
        """
        metadata_path = self.output_base_dir / batch_name / "metadata.json"
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.write_text(json.dumps(batch_results, indent=2), encoding='utf-8')

    def get_batch_results(self, batch_name: str) -> Dict:
        """
        Retrieve stored batch results.
        
        Args:
            batch_name: Batch identifier
        
        Returns:
            Batch results dict, or empty dict if not found
        """
        metadata_path = self.output_base_dir / batch_name / "metadata.json"
        if metadata_path.exists():
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error reading batch metadata: {e}")
        
        return {}

    def cleanup_temp_files(self):
        """Clean up temporary image files."""
        try:
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                self.temp_dir.mkdir()
        except Exception as e:
            logger.warning(f"Error cleaning temp files: {e}")

    @staticmethod
    def _get_timestamp() -> str:
        """Get current timestamp."""
        return datetime.now().isoformat()
