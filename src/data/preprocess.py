"""Image preprocessing primitives used consistently at train and evaluation time."""
from __future__ import annotations

import cv2
import numpy as np


def circular_crop_and_resize(image_bgr: np.ndarray, size: int) -> np.ndarray:
    """Remove black letterboxing, preserve aspect ratio, and resize a fundus image."""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    height, width = image_bgr.shape[:2]
    if contours:
        largest = max(contours, key=cv2.contourArea)
        x, y, crop_width, crop_height = cv2.boundingRect(largest)
        if crop_width < 0.2 * width or crop_height < 0.2 * height:
            x, y, crop_width, crop_height = 0, 0, width, height
    else:
        x, y, crop_width, crop_height = 0, 0, width, height

    cropped = image_bgr[y : y + crop_height, x : x + crop_width]
    crop_height, crop_width = cropped.shape[:2]
    side = max(crop_height, crop_width)
    top = (side - crop_height) // 2
    bottom = side - crop_height - top
    left = (side - crop_width) // 2
    right = side - crop_width - left
    padded = cv2.copyMakeBorder(cropped, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(0, 0, 0))
    return cv2.resize(padded, (size, size), interpolation=cv2.INTER_AREA)
