// Native on-device inference pipeline: FIQA gate -> calibrated DR grading ->
// lesion segmentation (OD from the IDRiD-only model, MA/HE/EX/SE from v2),
// mirroring src/explain/report.py and matlab/runScreeningPipeline.m so all
// three surfaces produce the same shape of result from the same ONNX
// exports (src/serve/export_onnx.py).
import 'dart:convert';
import 'dart:math' show exp;
import 'dart:typed_data';

import 'package:flutter/services.dart' show rootBundle;
import 'package:flutter_onnxruntime/flutter_onnxruntime.dart';
import 'package:image/image.dart' as img;

import '../models/screening_result.dart';
import 'preprocessing.dart';

class ScreeningPipeline {
  final OnnxRuntime _ort = OnnxRuntime();
  late OrtSession _fiqaSession;
  late OrtSession _drSession;
  late OrtSession _lesionSession;
  late OrtSession _lesionV2Session;
  late double _temperature;
  bool _loaded = false;

  bool get isLoaded => _loaded;

  Future<void> load() async {
    if (_loaded) return;
    _fiqaSession = await _ort.createSessionFromAsset('assets/models/fiqa_gate.onnx');
    _drSession = await _ort.createSessionFromAsset('assets/models/dr_grading.onnx');
    _lesionSession = await _ort.createSessionFromAsset('assets/models/lesion_segmentation.onnx');
    _lesionV2Session = await _ort.createSessionFromAsset('assets/models/lesion_segmentation_v2.onnx');

    final calibText = await rootBundle.loadString('assets/calibration.json');
    final calib = jsonDecode(calibText) as Map<String, dynamic>;
    _temperature = (calib['temperature'] as num).toDouble();

    _loaded = true;
  }

  List<double> _softmax(List<double> logits) {
    final maxVal = logits.reduce((a, b) => a > b ? a : b);
    final exps = logits.map((x) => exp(x - maxVal)).toList();
    final sum = exps.reduce((a, b) => a + b);
    return exps.map((x) => x / sum).toList();
  }

  Future<Float32List> _runSingleOutput(OrtSession session, Float32List input, int size) async {
    final inputName = session.inputNames[0];
    final outputName = session.outputNames[0];
    final inputValue = await OrtValue.fromList(input, [1, 3, size, size]);
    final outputs = await session.run({inputName: inputValue});
    final result = await outputs[outputName]!.asFlattenedList();
    inputValue.dispose();
    for (final v in outputs.values) {
      v.dispose();
    }
    return Float32List.fromList(result.map((v) => (v as num).toDouble()).toList());
  }

  double _sigmoid(double x) => 1.0 / (1.0 + exp(-x));

  Future<ScreeningResult> run(img.Image original) async {
    if (!_loaded) {
      throw StateError('ScreeningPipeline.load() must be called before run()');
    }
    final stopwatch = Stopwatch()..start();

    final processed224 = circularCropAndResize(original, 224);
    final processed512 = circularCropAndResize(original, 512);
    final fiqaInput = imageToChwNormalized(processed224);
    final mainInput = imageToChwNormalized(processed512);

    // --- FIQA gate ---
    final fiqaLogits = await _runSingleOutput(_fiqaSession, fiqaInput, 224);
    final fiqaProbsList = _softmax(fiqaLogits.toList());
    int fiqaIdx = 0;
    for (int i = 1; i < fiqaProbsList.length; i++) {
      if (fiqaProbsList[i] > fiqaProbsList[fiqaIdx]) fiqaIdx = i;
    }
    final fiqaProbs = <String, double>{
      for (int i = 0; i < fiqaClasses.length; i++) fiqaClasses[i]: fiqaProbsList[i],
    };

    // --- DR grading (temperature-calibrated) ---
    final drLogits = await _runSingleOutput(_drSession, mainInput, 512);
    final calibratedLogits = drLogits.map((v) => v / _temperature).toList();
    final drProbsList = _softmax(calibratedLogits);
    int drIdx = 0;
    for (int i = 1; i < drProbsList.length; i++) {
      if (drProbsList[i] > drProbsList[drIdx]) drIdx = i;
    }
    final drProbs = <String, double>{
      for (int i = 0; i < icdrClasses.length; i++) icdrClasses[i]: drProbsList[i],
    };
    final grade = drIdx;
    final isReferable = grade >= referableThreshold;

    // --- Lesion segmentation: OD from the 5-channel model, MA/HE/EX/SE from v2 ---
    final odLogitsRaw = await _runSingleOutput(_lesionSession, mainInput, 512);
    final v2LogitsRaw = await _runSingleOutput(_lesionV2Session, mainInput, 512);

    // Outputs are [1,C,512,512] flattened, C=5 for the OD model, C=4 for v2.
    const size = 512;
    const planeSize = size * size;
    List<bool> maskForChannel(Float32List logits, int channelIdx) {
      final start = channelIdx * planeSize;
      return List<bool>.generate(planeSize, (i) => _sigmoid(logits[start + i]) > 0.5);
    }

    final odMask = maskForChannel(odLogitsRaw, 4); // channel order MA,HE,EX,SE,OD
    final maMask = maskForChannel(v2LogitsRaw, 0);
    final heMask = maskForChannel(v2LogitsRaw, 1);
    final exMask = maskForChannel(v2LogitsRaw, 2);
    final seMask = maskForChannel(v2LogitsRaw, 3);

    final masks = <String, List<bool>>{"MA": maMask, "HE": heMask, "EX": exMask, "SE": seMask, "OD": odMask};
    final coverage = <String, double>{};
    for (final entry in masks.entries) {
      final count = entry.value.where((b) => b).length;
      coverage[entry.key] = 100.0 * count / planeSize;
    }

    // --- Overlay image ---
    final overlay = img.Image.from(processed512);
    const colors = {
      "MA": [255, 0, 0],
      "HE": [255, 128, 0],
      "EX": [255, 255, 0],
      "SE": [0, 255, 255],
      "OD": [0, 255, 0],
    };
    for (final code in ["MA", "HE", "EX", "SE", "OD"]) {
      final mask = masks[code]!;
      final col = colors[code]!;
      for (int y = 0; y < size; y++) {
        for (int x = 0; x < size; x++) {
          if (mask[y * size + x]) {
            final p = overlay.getPixel(x, y);
            overlay.setPixelRgb(
              x,
              y,
              (0.6 * p.r + 0.4 * col[0]).round(),
              (0.6 * p.g + 0.4 * col[1]).round(),
              (0.6 * p.b + 0.4 * col[2]).round(),
            );
          }
        }
      }
    }

    stopwatch.stop();

    return ScreeningResult(
      fiqaLabel: fiqaClasses[fiqaIdx],
      fiqaConfidence: fiqaProbsList[fiqaIdx],
      fiqaProbs: fiqaProbs,
      grade: grade,
      gradeLabel: icdrClasses[drIdx],
      drConfidence: drProbsList[drIdx],
      isReferable: isReferable,
      drProbs: drProbs,
      lesionCoveragePct: coverage,
      overlayPng: Uint8List.fromList(img.encodePng(overlay)),
      originalPng: Uint8List.fromList(img.encodePng(processed512)),
      elapsedSeconds: stopwatch.elapsedMilliseconds / 1000.0,
    );
  }

  Future<void> dispose() async {
    if (!_loaded) return;
    await _fiqaSession.close();
    await _drSession.close();
    await _lesionSession.close();
    await _lesionV2Session.close();
    _loaded = false;
  }
}
