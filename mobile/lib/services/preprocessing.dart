// Ports src/data/preprocess.py's circular_crop_and_resize + the ImageNet
// normalization used throughout the Python/MATLAB pipelines, so the mobile
// app produces numerically comparable results.
//
// One deliberate simplification vs the Python version: cv2's version finds
// the LARGEST CONTOUR's bounding box; this finds the bounding box of ALL
// thresholded (non-black) pixels directly, without contour detection (not
// available in Dart's `image` package). For a fundus photo — one solid
// bright circular region on a black background — these are equivalent in
// practice; the difference only matters if there's separate bright noise
// far from the main image, which doesn't happen in real fundus captures.
import 'dart:math' as math;
import 'dart:typed_data';

import 'package:image/image.dart' as img;

const List<double> imagenetMean = [0.485, 0.456, 0.406];
const List<double> imagenetStd = [0.229, 0.224, 0.225];

/// Removes black letterboxing, pads to a square, and resizes — matching
/// circular_crop_and_resize in src/data/preprocess.py.
img.Image circularCropAndResize(img.Image image, int size) {
  final width = image.width;
  final height = image.height;

  int minX = width, minY = height, maxX = -1, maxY = -1;
  const threshold = 10;
  for (int y = 0; y < height; y++) {
    for (int x = 0; x < width; x++) {
      final p = image.getPixel(x, y);
      final gray = (0.299 * p.r + 0.587 * p.g + 0.114 * p.b);
      if (gray > threshold) {
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (y < minY) minY = y;
        if (y > maxY) maxY = y;
      }
    }
  }

  int x0 = 0, y0 = 0, cropW = width, cropH = height;
  if (maxX >= minX && maxY >= minY) {
    final boxW = maxX - minX + 1;
    final boxH = maxY - minY + 1;
    if (boxW >= 0.2 * width && boxH >= 0.2 * height) {
      x0 = minX;
      y0 = minY;
      cropW = boxW;
      cropH = boxH;
    }
  }

  final cropped = img.copyCrop(image, x: x0, y: y0, width: cropW, height: cropH);

  final side = math.max(cropped.width, cropped.height);
  final top = ((side - cropped.height) / 2).floor();
  final left = ((side - cropped.width) / 2).floor();
  final padded = img.Image(width: side, height: side, numChannels: 3);
  img.fill(padded, color: img.ColorRgb8(0, 0, 0));
  img.compositeImage(padded, cropped, dstX: left, dstY: top);

  return img.copyResize(padded, width: size, height: size, interpolation: img.Interpolation.average);
}

/// HWC uint8 image -> normalized CHW Float32List (1x3xSxS, NCHW — matches
/// the ONNX models' expected input layout).
Float32List imageToChwNormalized(img.Image resized) {
  final size = resized.width;
  final out = Float32List(3 * size * size);
  final planeSize = size * size;
  for (int y = 0; y < size; y++) {
    for (int x = 0; x < size; x++) {
      final p = resized.getPixel(x, y);
      final r = p.r / 255.0;
      final g = p.g / 255.0;
      final b = p.b / 255.0;
      final idx = y * size + x;
      out[idx] = (r - imagenetMean[0]) / imagenetStd[0];
      out[planeSize + idx] = (g - imagenetMean[1]) / imagenetStd[1];
      out[2 * planeSize + idx] = (b - imagenetMean[2]) / imagenetStd[2];
    }
  }
  return out;
}
