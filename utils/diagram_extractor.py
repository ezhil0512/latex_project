"""
Diagram extraction utilities for detecting and separating diagrams from text
in images and PDFs using OpenCV.
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


class DiagramExtractor:
    """
    Detect and extract diagrams/images from pages, separating them from text.
    """

    def __init__(self, image_path: str):
        """
        Initialize diagram extractor with an image file.
        
        Args:
            image_path: Path to image file
        """
        self.image_path = Path(image_path)
        if not self.image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        self.image = cv2.imread(str(image_path))
        if self.image is None:
            raise ValueError(f"Failed to load image: {image_path}")
        
        self.gray = cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY)
        self.height, self.width = self.image.shape[:2]

    def separate_text_from_diagram(self) -> Dict:
        """
        Separate text regions from diagram regions using contour detection.
        
        Returns:
            Dict with 'text_regions' and 'diagram_regions' lists
        """
        # Threshold to binary
        _, binary = cv2.threshold(self.gray, 150, 255, cv2.THRESH_BINARY_INV)
        
        # Apply morphological operations to connect nearby components
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        
        # Find contours
        contours, _ = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        text_regions = []
        diagram_regions = []
        
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            
            # Skip tiny artifacts (< 10px)
            if w < 10 or h < 10:
                continue
            
            # Skip regions that are too large (likely page background)
            if w > self.width * 0.95 or h > self.height * 0.95:
                continue
            
            # Extract region
            try:
                region = self.image[y:y+h, x:x+w]
                
                # Classify: text vs diagram
                if self._is_text_region(region):
                    text_regions.append({
                        'bbox': (x, y, w, h),
                        'type': 'text',
                        'area': w * h
                    })
                else:
                    diagram_regions.append({
                        'bbox': (x, y, w, h),
                        'type': 'diagram',
                        'area': w * h
                    })
            except Exception as e:
                logger.warning(f"Error processing contour: {e}")
                continue
        
        return {
            'text_regions': text_regions,
            'diagram_regions': diagram_regions
        }

    def _is_text_region(self, region: np.ndarray) -> bool:
        """
        Heuristic to distinguish text from diagrams.
        
        Text characteristics:
        - Many thin horizontal lines
        - High stroke density in regular patterns
        - High aspect ratio (wide rectangles)
        
        Diagram characteristics:
        - Curves, circles, varied shapes
        - Lower edge density
        - More varied contours
        
        Args:
            region: Image region to classify
        
        Returns:
            True if region is likely text
        """
        if region.size == 0:
            return False
        
        h, w = region.shape[:2]
        
        # Skip very small regions
        if h < 5 or w < 5:
            return False
        
        aspect_ratio = max(w, h) / (min(w, h) + 1)
        
        # Text typically has high aspect ratio (wide rectangles)
        if aspect_ratio > 3.0:
            return True
        
        # Analyze edge density
        try:
            region_gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY) if len(region.shape) == 3 else region
            edges = cv2.Canny(region_gray, 50, 150)
            edge_density = np.sum(edges > 0) / edges.size
            
            # High edge density (many lines) suggests text
            if edge_density > 0.15:
                return True
            
            # Analyze line orientation
            lines = cv2.HoughLinesP(edges, 1, np.pi/180, 50, minLineLength=10, maxLineGap=5)
            if lines is not None:
                horizontal_lines = sum(1 for line in lines if abs(line[0][1] - line[0][3]) < 2)
                vertical_lines = sum(1 for line in lines if abs(line[0][0] - line[0][2]) < 2)
                
                # More horizontal lines suggest text
                if horizontal_lines > vertical_lines * 2:
                    return True
        
        except Exception as e:
            logger.warning(f"Error analyzing region: {e}")
        
        return False

    def extract_diagram(self, bbox: Tuple, output_dir: str) -> str:
        """
        Extract and save a specific diagram region.
        
        Args:
            bbox: Bounding box tuple (x, y, w, h)
            output_dir: Directory to save extracted diagram
        
        Returns:
            Path to saved diagram file
        """
        x, y, w, h = bbox
        diagram = self.image[y:y+h, x:x+w]
        
        if diagram.size == 0:
            raise ValueError("Empty diagram region")
        
        output_path = Path(output_dir) / f"diagram_{int(x)}_{int(y)}.png"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        success = cv2.imwrite(str(output_path), diagram)
        if not success:
            raise IOError(f"Failed to save diagram to {output_path}")
        
        return str(output_path)

    def find_main_diagram(self) -> Dict:
        """
        Find the largest/main diagram in the image.
        
        Returns:
            Dict with diagram info, or empty dict if none found
        """
        regions = self.separate_text_from_diagram()
        diagram_regions = regions.get('diagram_regions', [])
        
        if not diagram_regions:
            return {}
        
        # Return largest diagram
        largest = max(diagram_regions, key=lambda r: r['area'])
        return largest

    def get_text_only_image(self, output_path: str) -> str:
        """
        Generate image with diagrams removed (text only).
        
        Args:
            output_path: Path to save text-only image
        
        Returns:
            Path to saved image
        """
        regions = self.separate_text_from_diagram()
        diagram_regions = regions.get('diagram_regions', [])
        
        # Create copy of original image
        text_only = self.image.copy()
        
        # Fill diagram regions with white
        for region in diagram_regions:
            x, y, w, h = region['bbox']
            cv2.rectangle(text_only, (x, y), (x+w, y+h), (255, 255, 255), -1)
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        success = cv2.imwrite(output_path, text_only)
        if not success:
            raise IOError(f"Failed to save image to {output_path}")
        
        return output_path
