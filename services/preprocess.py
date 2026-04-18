from pathlib import Path

import cv2


def preprocess_image(image_path):
    """Resize, denoise, and threshold an image for OCR."""
    source = Path(image_path)
    image = cv2.imread(str(source))
    if image is None:
        raise ValueError("Could not read image file.")

    height, width = image.shape[:2]
    max_side = max(height, width)
    if max_side < 1400:
        scale = 1400 / max_side
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        height, width = image.shape[:2]
        max_side = max(height, width)

    if max_side > 1800:
        scale = 1800 / max_side
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    thresholded = cv2.adaptiveThreshold(
        denoised,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11,
    )

    output_path = source.with_name(f"{source.stem}_processed{source.suffix}")
    cv2.imwrite(str(output_path), thresholded)
    return output_path
