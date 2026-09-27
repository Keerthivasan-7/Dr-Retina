import 'dart:typed_data';

/// Mirrors the fields produced by matlab/runScreeningPipeline.m and
/// src/explain/report.py, so all three surfaces (Python, MATLAB, mobile)
/// report the same shape of result.
class ScreeningResult {
  final String fiqaLabel;
  final double fiqaConfidence;
  final Map<String, double> fiqaProbs;

  final int grade;
  final String gradeLabel;
  final double drConfidence;
  final bool isReferable;
  final Map<String, double> drProbs;

  final Map<String, double> lesionCoveragePct;
  final Uint8List overlayPng;
  final Uint8List originalPng;

  final double elapsedSeconds;

  ScreeningResult({
    required this.fiqaLabel,
    required this.fiqaConfidence,
    required this.fiqaProbs,
    required this.grade,
    required this.gradeLabel,
    required this.drConfidence,
    required this.isReferable,
    required this.drProbs,
    required this.lesionCoveragePct,
    required this.overlayPng,
    required this.originalPng,
    required this.elapsedSeconds,
  });
}

const List<String> icdrClasses = ["No_DR", "Mild", "Moderate", "Severe", "Proliferative_DR"];
const List<String> fiqaClasses = ["Good", "Usable", "Reject"];
const int referableThreshold = 2;

const Map<String, String> gradeDescriptions = {
  "No_DR": "No visible signs of diabetic retinopathy.",
  "Mild": "Mild non-proliferative DR — microaneurysms only.",
  "Moderate": "Moderate non-proliferative DR — more than microaneurysms but less than severe NPDR.",
  "Severe": "Severe non-proliferative DR — extensive haemorrhages/microaneurysms, venous beading, or IRMA.",
  "Proliferative_DR": "Proliferative DR — neovascularization and/or vitreous/preretinal haemorrhage present.",
};

const Map<String, String> lesionNames = {
  "MA": "Microaneurysms",
  "HE": "Haemorrhages",
  "EX": "Hard Exudates",
  "SE": "Soft Exudates",
  "OD": "Optic Disc",
};

const Map<String, String> lesionSourceModel = {
  "MA": "v2 (merged data)",
  "HE": "v2 (merged data)",
  "EX": "v2 (merged data)",
  "SE": "v2 (merged data)",
  "OD": "IDRiD-only",
};
