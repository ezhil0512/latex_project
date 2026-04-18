"""
PDF processing utilities for extracting text, images, and metadata from PDFs.
Supports both digital and scanned PDFs.
"""

import fitz  # PyMuPDF
from pathlib import Path
from typing import List, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class PDFProcessor:
    """
    Process PDF files to extract text, images, and layout information.
    """

    def __init__(self, pdf_path: str):
        """
        Initialize PDF processor with a PDF file.
        
        Args:
            pdf_path: Path to PDF file
        """
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        try:
            self.doc = fitz.open(pdf_path)
        except Exception as e:
            raise ValueError(f"Failed to open PDF: {e}")
        
        self.pages = []
        self.metadata = {}

    def is_scanned_pdf(self) -> bool:
        """
        Detect if PDF is scanned (image-based) vs digital (text-based).
        
        Returns:
            True if PDF appears to be scanned/image-based
        """
        if not self.doc:
            return False
        
        try:
            first_page = self.doc[0]
            text = first_page.get_text()
            # If very little text extracted, likely a scanned PDF
            return len(text.strip()) < 100
        except:
            return True

    def extract_all_pages(self) -> List[Dict]:
        """
        Extract text and images from all pages.
        
        Returns:
            List of page data dicts containing text, images, and metadata
        """
        results = []
        is_scanned = self.is_scanned_pdf()
        
        for page_num in range(len(self.doc)):
            try:
                page = self.doc[page_num]
                page_data = {
                    'page_num': page_num + 1,
                    'text': page.get_text(),
                    'images': self._extract_page_images(page, page_num),
                    'is_scanned': is_scanned,
                    'height': page.rect.height,
                    'width': page.rect.width
                }
                results.append(page_data)
            except Exception as e:
                logger.warning(f"Error processing page {page_num + 1}: {e}")
                continue
        
        return results

    def _extract_page_images(self, page, page_num: int) -> List[Dict]:
        """
        Extract images from a single page.
        
        Args:
            page: PyMuPDF page object
            page_num: Page number (0-indexed)
        
        Returns:
            List of image info dicts
        """
        images = []
        try:
            img_list = page.get_images()
            
            for img_index, img in enumerate(img_list):
                try:
                    xref = img[0]
                    pix = fitz.Pixmap(self.doc, xref)
                    
                    # Save image temporarily
                    img_filename = f"page_{page_num + 1}_img_{img_index}.png"
                    img_path = Path("temp_images") / img_filename
                    img_path.parent.mkdir(exist_ok=True)
                    
                    # Convert CMYK to RGB if needed
                    if pix.n - pix.alpha > 3:
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                    
                    pix.save(str(img_path))
                    
                    # Get image rectangle (position on page)
                    rects = page.get_image_rects(xref)
                    if rects:
                        rect = rects[0]
                        images.append({
                            'path': str(img_path),
                            'rect': {
                                'x0': rect.x0,
                                'y0': rect.y0,
                                'x1': rect.x1,
                                'y1': rect.y1
                            },
                            'index': img_index,
                            'page': page_num + 1
                        })
                except Exception as e:
                    logger.warning(f"Error extracting image {img_index} from page {page_num + 1}: {e}")
                    continue
        
        except Exception as e:
            logger.warning(f"Error accessing images from page {page_num + 1}: {e}")
        
        return images

    def extract_text_blocks(self, page) -> List[Dict]:
        """
        Extract text blocks with layout information from a page.
        
        Args:
            page: PyMuPDF page object
        
        Returns:
            List of text block dicts with bbox and content
        """
        blocks = []
        try:
            for block in page.get_text("blocks"):
                if len(block) < 5:
                    continue
                
                x0, y0, x1, y1, text, block_no, block_type = block[:7]
                
                if text and text.strip():
                    blocks.append({
                        'text': text.strip(),
                        'bbox': {
                            'x0': x0,
                            'y0': y0,
                            'x1': x1,
                            'y1': y1,
                            'height': y1 - y0,
                            'width': x1 - x0
                        },
                        'type': block_type,
                        'block_no': block_no
                    })
        except Exception as e:
            logger.warning(f"Error extracting text blocks: {e}")
        
        return blocks

    def get_page_text_blocks(self, page_num: int) -> List[Dict]:
        """Get text blocks for a specific page."""
        if page_num < 0 or page_num >= len(self.doc):
            return []
        
        page = self.doc[page_num]
        return self.extract_text_blocks(page)

    def close(self):
        """Close the PDF document."""
        if self.doc:
            self.doc.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
