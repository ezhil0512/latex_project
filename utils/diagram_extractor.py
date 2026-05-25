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
        
        # Text lines are usually wide but shallow. Wide diagram parts such as
        # rays, springs, and axes should continue through the diagram checks.
        if aspect_ratio > 3.0 and h < self.height * 0.08:
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
        x, y, w, h = self._refine_diagram_bbox(bbox)
        diagram = self.image[y:y+h, x:x+w]
        
        if diagram.size == 0:
            raise ValueError("Empty diagram region")
        
        output_path = Path(output_dir) / f"diagram_{int(x)}_{int(y)}.png"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        success = cv2.imwrite(str(output_path), diagram)
        if not success:
            raise IOError(f"Failed to save diagram to {output_path}")
        
        return str(output_path)

    def save_text_only_image_for_bbox(self, bbox: Tuple, output_path: str) -> str:
        """
        Save a copy of the source image with the detected diagram removed.
        This keeps diagram labels from being read as normal question text.
        """
        x, y, w, h = self._refine_diagram_bbox(bbox)
        padding = max(3, int(min(self.width, self.height) * 0.01))
        left = max(0, x - padding)
        top = max(0, y - padding)
        right = min(self.width, x + w + padding)
        bottom = min(self.height, y + h + padding)

        text_only = self.image.copy()
        cv2.rectangle(text_only, (left, top), (right, bottom), (255, 255, 255), -1)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        success = cv2.imwrite(str(output_path), text_only)
        if not success:
            raise IOError(f"Failed to save image to {output_path}")

        return str(output_path)

    def _refine_diagram_bbox(self, bbox: Tuple) -> Tuple:
        """
        Keep the diagram crop close to line-art while avoiding neighboring
        question text and answer options.
        """
        x, y, w, h = [int(value) for value in bbox]
        pad_x = max(18, int(self.width * 0.08))
        pad_y = max(10, int(self.height * 0.04))
        left = max(0, x - pad_x)
        top = max(0, y - pad_y)
        right = min(self.width, x + w + pad_x)
        bottom = min(self.height, y + h + pad_y)

        refined = self._bbox_from_hough_lines(left, top, right, bottom, (x, y, w, h))
        if refined is None:
            refined = self._bbox_from_line_art(left, top, right, bottom, (x, y, w, h))
        if refined is None:
            return left, top, right - left, bottom - top
        refined = self._trim_neighboring_text(refined, (x, y, w, h))
        return self._add_tight_padding(refined)

    def _trim_neighboring_text(self, bbox: Tuple, seed_bbox: Tuple) -> Tuple:
        x, y, w, h = [int(value) for value in bbox]
        seed_x, seed_y, seed_w, seed_h = [int(value) for value in seed_bbox]

        new_top = self._top_after_question_text(y, seed_y)
        bottom_limit = self._bottom_before_options(y + h, seed_y + seed_h)
        new_bottom = max(new_top + 1, bottom_limit)
        return x, new_top, w, new_bottom - new_top

    def _top_after_question_text(self, current_top: int, seed_top: int) -> int:
        if current_top >= seed_top:
            return current_top

        band = self.gray[current_top:seed_top, :]
        if band.size == 0:
            return current_top

        dark = cv2.threshold(band, 220, 255, cv2.THRESH_BINARY_INV)[1]
        row_counts = np.sum(dark > 0, axis=1)
        text_rows = np.where(row_counts > self.width * 0.12)[0]
        if not len(text_rows):
            return current_top

        return min(self.height, seed_top + max(4, int(self.height * 0.01)))

    def _bottom_before_options(self, current_bottom: int, seed_bottom: int) -> int:
        if current_bottom <= seed_bottom:
            return current_bottom

        band = self.gray[seed_bottom:current_bottom, :]
        if band.size == 0:
            return current_bottom

        dark = cv2.threshold(band, 220, 255, cv2.THRESH_BINARY_INV)[1]
        row_counts = np.sum(dark > 0, axis=1)
        option_rows = np.where(row_counts > self.width * 0.10)[0]
        if not len(option_rows):
            return current_bottom

        return max(seed_bottom, seed_bottom + int(option_rows.min()) - max(4, int(self.height * 0.012)))

    def _bbox_from_hough_lines(self, left: int, top: int, right: int, bottom: int, seed_bbox: Tuple) -> Tuple:
        roi = self.gray[top:bottom, left:right]
        if roi.size == 0:
            return None

        blurred = cv2.GaussianBlur(roi, (3, 3), 0)
        edges = cv2.Canny(blurred, 50, 150)
        min_line_length = max(12, int(min(self.width, self.height) * 0.055))
        max_line_gap = max(4, int(min(self.width, self.height) * 0.018))
        threshold = max(18, int(min(self.width, self.height) * 0.05))
        lines = cv2.HoughLinesP(
            edges,
            1,
            np.pi / 180,
            threshold,
            minLineLength=min_line_length,
            maxLineGap=max_line_gap,
        )
        if lines is None:
            return None

        mask = np.zeros_like(roi)
        for line in lines:
            x1, y1, x2, y2 = line[0]
            length = np.hypot(x2 - x1, y2 - y1)
            if length < min_line_length:
                continue
            cv2.line(mask, (x1, y1), (x2, y2), 255, max(2, int(min(self.width, self.height) * 0.006)))

        kernel_size = max(3, int(min(self.width, self.height) * 0.012))
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
        mask = cv2.dilate(mask, kernel, iterations=1)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        seed_x, seed_y, seed_w, seed_h = seed_bbox
        boxes = []
        for contour in contours:
            cx, cy, cw, ch = cv2.boundingRect(contour)
            if cw * ch < self.width * self.height * 0.001:
                continue
            if top + cy + ch < seed_y:
                continue
            boxes.append((left + cx, top + cy, cw, ch))

        if not boxes:
            return None

        grouped = self._group_nearby_boxes(
            boxes,
            horizontal_margin=max(15, self.width // 12),
            vertical_margin=max(6, self.height // 40),
        )
        grouped = [box for box in grouped if box[2] * box[3] >= self.width * self.height * 0.01]
        if not grouped:
            return None

        return max(grouped, key=lambda box: box[2] * box[3])

    def _bbox_from_line_art(self, left: int, top: int, right: int, bottom: int, seed_bbox: Tuple) -> Tuple:
        roi = self.gray[top:bottom, left:right]
        if roi.size == 0:
            return None

        roi_height, roi_width = roi.shape[:2]
        dark_pixels = cv2.threshold(roi, 220, 255, cv2.THRESH_BINARY_INV)[1]
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        connected = cv2.dilate(dark_pixels, kernel, iterations=1)
        contours, _ = cv2.findContours(connected, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        seed_x, seed_y, seed_w, seed_h = seed_bbox
        boxes = []
        for contour in contours:
            cx, cy, cw, ch = cv2.boundingRect(contour)
            if top + cy + ch < seed_y:
                continue
            if self._is_diagram_component(cx, cy, cw, ch, roi_width, roi_height):
                boxes.append((left + cx, top + cy, cw, ch))

        if not boxes:
            return None

        grouped = self._group_nearby_boxes(boxes, horizontal_margin=max(16, self.width // 10), vertical_margin=max(12, self.height // 18))
        gx, gy, gw, gh = max(grouped, key=lambda box: box[2] * box[3])
        return gx, gy, gw, gh

    def _is_diagram_component(self, x: int, y: int, w: int, h: int, roi_width: int, roi_height: int) -> bool:
        if w < 3 or h < 3:
            return False

        area = w * h
        page_area = self.width * self.height
        long_horizontal = w > self.width * 0.10 and h < self.height * 0.08
        long_vertical = h > self.height * 0.10 and w < self.width * 0.08
        blocky_line_art = area > page_area * 0.0015 and w > self.width * 0.04 and h > self.height * 0.04

        likely_option_text = (
            h < self.height * 0.07
            and w < self.width * 0.28
            and y > roi_height * 0.68
            and not long_horizontal
            and not long_vertical
        )
        likely_question_text = (
            h < self.height * 0.07
            and w < self.width * 0.45
            and y < roi_height * 0.18
            and not long_horizontal
            and not long_vertical
        )
        if likely_option_text or likely_question_text:
            return False

        return long_horizontal or long_vertical or blocky_line_art

    def _add_tight_padding(self, bbox: Tuple) -> Tuple:
        x, y, w, h = [int(value) for value in bbox]
        pad_x = max(5, int(self.width * 0.012))
        pad_y = max(4, int(self.height * 0.01))
        left = max(0, x - pad_x)
        top = max(0, y - pad_y)
        right = min(self.width, x + w + pad_x)
        bottom = min(self.height, y + h + pad_y)
        return (
            left,
            top,
            max(1, right - left),
            max(1, bottom - top),
        )

    def find_main_diagram(self) -> Dict:
        """
        Find the largest/main diagram in the image.
        
        Returns:
            Dict with diagram info, or empty dict if none found
        """
        regions = self.separate_text_from_diagram()
        diagram_regions = regions.get('diagram_regions', [])
        structural_region = self._find_structural_diagram_region()
        fallback_region = self._find_right_side_ink_region()
        
        if not diagram_regions:
            return structural_region or fallback_region
        
        # Return largest diagram
        largest = max(diagram_regions, key=lambda r: r['area'])
        if structural_region and self._is_better_diagram_crop(largest, structural_region):
            return structural_region
        if fallback_region and self._includes_header_text(largest, fallback_region):
            return fallback_region
        return largest

    def _is_better_diagram_crop(self, current: Dict, candidate: Dict) -> bool:
        x, y, w, h = current["bbox"]
        candidate_x, candidate_y, candidate_w, candidate_h = candidate["bbox"]
        current_area = w * h
        candidate_area = candidate_w * candidate_h
        candidate_not_header = candidate_y > self.height * 0.08
        fills_missing_parts = candidate_area > current_area * 1.35
        current_is_fragment = w < self.width * 0.30 or h < self.height * 0.28
        return candidate_not_header and fills_missing_parts and current_is_fragment

    def _includes_header_text(self, region: Dict, fallback_region: Dict) -> bool:
        x, y, w, h = region["bbox"]
        fallback_x, fallback_y, fallback_w, fallback_h = fallback_region["bbox"]
        touches_top = y <= self.height * 0.06
        fallback_is_lower = fallback_y > y + self.height * 0.08
        fallback_is_substantial = fallback_w * fallback_h >= w * h * 0.20
        return touches_top and fallback_is_lower and fallback_is_substantial

    def _find_structural_diagram_region(self) -> Dict:
        """
        Find diagrams made from separated long strokes, such as ray diagrams,
        screens, springs, pulleys, and circuit-like figures.
        """
        dark_pixels = cv2.threshold(self.gray, 210, 255, cv2.THRESH_BINARY_INV)[1]
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        connected = cv2.dilate(dark_pixels, kernel, iterations=1)
        contours, _ = cv2.findContours(connected, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        boxes = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if self._looks_like_structural_part(x, y, w, h):
                boxes.append((x, y, w, h))

        if not boxes:
            return {}

        groups = self._group_nearby_boxes(boxes)
        if not groups:
            return {}

        x, y, w, h = max(groups, key=lambda box: box[2] * box[3])
        if w * h < self.width * self.height * 0.025:
            return {}

        padding = max(10, int(min(self.width, self.height) * 0.035))
        top_padding = max(4, int(min(self.width, self.height) * 0.015))
        x = max(0, x - padding)
        y = max(0, y - top_padding)
        right = min(self.width, x + w + (padding * 2))
        bottom = min(self.height, y + h + top_padding + padding)
        w = right - x
        h = bottom - y

        return {
            'bbox': (x, y, w, h),
            'type': 'diagram',
            'area': w * h,
            'fallback': 'structural_lines'
        }

    def _looks_like_structural_part(self, x: int, y: int, w: int, h: int) -> bool:
        if y < self.height * 0.08:
            return False
        if w < 3 or h < 3:
            return False
        if w > self.width * 0.85:
            return False

        area = w * h
        tall_part = h > self.height * 0.16 and w < self.width * 0.35
        broad_part = w > self.width * 0.12 and h > self.height * 0.08
        not_text_line = not (w > h * 3.5 and h < self.height * 0.08)
        return area > self.width * self.height * 0.0015 and (tall_part or broad_part) and not_text_line

    def _group_nearby_boxes(self, boxes: List[Tuple], horizontal_margin=None, vertical_margin=None) -> List[Tuple]:
        groups = []
        horizontal_margin = horizontal_margin if horizontal_margin is not None else max(35, self.width // 5)
        vertical_margin = vertical_margin if vertical_margin is not None else max(18, self.height // 12)

        for box in sorted(boxes, key=lambda item: item[0]):
            x, y, w, h = box
            merged = False
            for index, group in enumerate(groups):
                gx, gy, gw, gh = group
                near_horizontally = x <= gx + gw + horizontal_margin and x + w >= gx - horizontal_margin
                near_vertically = y <= gy + gh + vertical_margin and y + h >= gy - vertical_margin
                if near_horizontally and near_vertically:
                    left = min(gx, x)
                    top = min(gy, y)
                    right = max(gx + gw, x + w)
                    bottom = max(gy + gh, y + h)
                    groups[index] = (left, top, right - left, bottom - top)
                    merged = True
                    break
            if not merged:
                groups.append(box)

        if len(groups) == len(boxes):
            return groups
        return self._group_nearby_boxes(groups, horizontal_margin, vertical_margin)

    def _find_right_side_ink_region(self) -> Dict:
        """
        Fallback for exam questions where the diagram sits to the right of
        options/text, such as spring, circuit, or mechanics figures.
        """
        right_start = int(self.width * 0.45)
        right_gray = self.gray[:, right_start:]
        dark_pixels = cv2.threshold(right_gray, 210, 255, cv2.THRESH_BINARY_INV)[1]

        # Connect nearby diagram strokes without joining the question sentence.
        kernel_width = max(7, self.width // 70)
        kernel_height = max(5, self.height // 90)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_width, kernel_height))
        connected = cv2.morphologyEx(dark_pixels, cv2.MORPH_CLOSE, kernel, iterations=1)

        contours, _ = cv2.findContours(connected, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates = []
        for contour in contours:
            roi_x, y, w, h = cv2.boundingRect(contour)
            if self._looks_like_right_side_diagram(roi_x, y, w, h):
                candidates.append((roi_x, y, w, h))

        if not candidates:
            return {}

        roi_x, y, w, h = max(candidates, key=lambda bbox: bbox[2] * bbox[3] * bbox[3])
        merged = self._merge_nearby_right_side_parts((roi_x, y, w, h), contours)
        if merged is None:
            return {}
        roi_x, y, w, h = merged

        padding = max(8, int(min(self.width, self.height) * 0.03))
        x = max(0, right_start + roi_x - padding)
        y = max(0, y - padding)
        right = min(self.width, right_start + roi_x + w + padding)
        bottom = min(self.height, y + h + padding)
        w = right - x
        h = bottom - y

        return {
            'bbox': (x, y, w, h),
            'type': 'diagram',
            'area': w * h,
            'fallback': 'right_side_ink'
        }

    def _looks_like_right_side_diagram(self, roi_x: int, y: int, w: int, h: int) -> bool:
        min_width = self.width * 0.06
        min_height = self.height * 0.14
        min_area = self.width * self.height * 0.006
        if w < min_width or h < min_height or w * h < min_area:
            return False

        aspect_ratio = w / max(1, h)
        if aspect_ratio > 3.5:
            return False

        center_x = self.width * 0.45 + roi_x + (w / 2)
        return center_x > self.width * 0.55

    def _merge_nearby_right_side_parts(self, seed_bbox: Tuple, contours: List) -> Tuple:
        seed_x, seed_y, seed_w, seed_h = seed_bbox
        left = seed_x
        top = seed_y
        right = seed_x + seed_w
        bottom = seed_y + seed_h
        horizontal_margin = max(18, self.width // 18)
        vertical_margin = max(18, self.height // 18)

        changed = True
        while changed:
            changed = False
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                if w * h < self.width * self.height * 0.0008:
                    continue

                near_horizontally = x <= right + horizontal_margin and x + w >= left - horizontal_margin
                near_vertically = y <= bottom + vertical_margin and y + h >= top - vertical_margin
                if not near_horizontally or not near_vertically:
                    continue

                if y < self.height * 0.16 and w > h * 2.2:
                    continue

                new_left = min(left, x)
                new_top = min(top, y)
                new_right = max(right, x + w)
                new_bottom = max(bottom, y + h)
                if (new_left, new_top, new_right, new_bottom) != (left, top, right, bottom):
                    left, top, right, bottom = new_left, new_top, new_right, new_bottom
                    changed = True

        if right <= left or bottom <= top:
            return None
        return left, top, right - left, bottom - top

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
