"""
Question splitting utilities for detecting and separating individual questions
from combined text (e.g., from PDFs with multiple questions).
"""

import re
from typing import List, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class QuestionSplitter:
    """
    Split combined text into individual questions based on numbering,
    layout, or other heuristics.
    """

    # Patterns for question starts
    QUESTION_PATTERNS = [
        r'^\s*\d+[\.\)]\s+',           # 1. or 1)
        r'^\s*\(\d+\)\s+',             # (1)
        r'^\s*[Qq]uestion\s+\d+',      # Question 1
        r'^\s*Q\d+[\.\):\s]',          # Q1. or Q1:
        r'^\s*[A-Z][\.\)]\s+',         # A. or A)  (for labelled questions)
    ]

    def __init__(self, full_text: str, text_blocks: List[Dict] = None):
        """
        Initialize question splitter.
        
        Args:
            full_text: Combined text from all pages
            text_blocks: List of text block dicts with bbox info (optional)
        """
        self.full_text = full_text
        self.text_blocks = text_blocks or []
        self.questions = []

    def split_questions(self) -> List[Dict]:
        """
        Main method to split text into questions.
        
        Returns:
            List of question dicts, each containing text and metadata
        """
        # Try numbered split first (most reliable)
        if self._has_clear_numbering():
            return self._split_by_numbering()
        
        # Fall back to layout-based split
        if self.text_blocks:
            return self._split_by_layout()
        
        # Last resort: return entire text as single question
        logger.warning("Could not detect question boundaries, treating as single question")
        return [{
            'text': self.full_text,
            'blocks': [{'text': self.full_text}],
            'split_method': 'none'
        }]

    def _has_clear_numbering(self) -> bool:
        """
        Check if text has clear question numbering.
        
        Returns:
            True if numbering patterns detected consistently
        """
        lines = self.full_text.split('\n')
        numbering_count = 0
        
        for line in lines[:30]:  # Check first 30 lines
            for pattern in self.QUESTION_PATTERNS:
                if re.match(pattern, line.strip(), re.IGNORECASE):
                    numbering_count += 1
                    break
        
        # Need at least 2 numbered questions
        return numbering_count >= 2

    def _split_by_numbering(self) -> List[Dict]:
        """
        Split by detected question numbering.
        
        Returns:
            List of question dicts
        """
        questions = []
        current_question = None
        lines = self.full_text.split('\n')
        
        for line in lines:
            line_stripped = line.strip()
            
            # Check if this is a question start
            is_question_start = False
            for pattern in self.QUESTION_PATTERNS:
                if re.match(pattern, line_stripped, re.IGNORECASE):
                    is_question_start = True
                    break
            
            if is_question_start and line_stripped:
                # Save previous question
                if current_question and current_question['text'].strip():
                    questions.append(current_question)
                
                # Start new question
                current_question = {
                    'text': line_stripped,
                    'blocks': [line_stripped],
                    'split_method': 'numbering'
                }
            elif current_question is not None:
                current_question['text'] += '\n' + line
                current_question['blocks'].append(line)
        
        # Add last question
        if current_question and current_question['text'].strip():
            questions.append(current_question)
        
        # Filter out very short questions (likely fragments)
        questions = [q for q in questions if len(q['text'].strip()) > 50]
        
        return questions

    def _split_by_layout(self) -> List[Dict]:
        """
        Split by layout (vertical gaps in text blocks).
        
        Returns:
            List of question dicts
        """
        if not self.text_blocks:
            return []
        
        questions = []
        current_question = None
        prev_y_max = 0
        gap_threshold = 100  # pixels

        for block in self.text_blocks:
            bbox = block.get('bbox', {})
            y0 = bbox.get('y0', 0)
            y1 = bbox.get('y1', 0)
            text = block.get('text', '')
            
            if not text.strip():
                continue
            
            # Check for large vertical gap (new question)
            if prev_y_max > 0 and (y0 - prev_y_max) > gap_threshold:
                if current_question and current_question['text'].strip():
                    questions.append(current_question)
                current_question = None
            
            # Add to current or start new question
            if current_question is None:
                current_question = {
                    'text': text,
                    'blocks': [block],
                    'split_method': 'layout'
                }
            else:
                current_question['text'] += '\n' + text
                current_question['blocks'].append(block)
            
            prev_y_max = max(prev_y_max, y1)
        
        # Add last question
        if current_question and current_question['text'].strip():
            questions.append(current_question)
        
        return questions

    def extract_question_number(self, text: str) -> str:
        """
        Extract question number from text.
        
        Args:
            text: Question text
        
        Returns:
            Question number as string, or empty string if not found
        """
        for pattern in self.QUESTION_PATTERNS:
            match = re.match(pattern, text.strip(), re.IGNORECASE)
            if match:
                return match.group(0).strip()
        return ""

    def validate_split(self, questions: List[Dict]) -> Tuple[bool, str]:
        """
        Validate the split results.
        
        Args:
            questions: List of split questions
        
        Returns:
            Tuple of (is_valid, message)
        """
        if not questions:
            return False, "No questions were extracted"
        
        if len(questions) == 1:
            return True, "Single question extracted (no split needed)"
        
        # Check for reasonable question length
        avg_length = sum(len(q['text']) for q in questions) / len(questions)
        if avg_length < 50:
            return False, "Average question length too short"
        
        return True, f"Successfully split into {len(questions)} questions"
