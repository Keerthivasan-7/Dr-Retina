import 'package:flutter/material.dart';

import '../models/screening_result.dart';
import '../theme/app_colors.dart';

class ResultsScreen extends StatelessWidget {
  final ScreeningResult result;
  const ResultsScreen({super.key, required this.result});

  Color _gradeColor(int grade) {
    switch (grade) {
      case 0:
      case 1:
        return AppColors.good;
      case 2:
        return AppColors.warn;
      default:
        return AppColors.bad;
    }
  }

  Color _fiqaColor(String label) {
    switch (label) {
      case "Good":
        return AppColors.good;
      case "Usable":
        return AppColors.warn;
      default:
        return AppColors.bad;
    }
  }

  @override
  Widget build(BuildContext context) {
    final gradeColor = _gradeColor(result.grade);
    final fiqaColor = _fiqaColor(result.fiqaLabel);

    final presentLesions = <String>[];
    for (final code in ["MA", "HE", "EX", "SE"]) {
      final pct = result.lesionCoveragePct[code] ?? 0;
      if (pct > 0.01) {
        presentLesions.add("${lesionNames[code]} (${pct.toStringAsFixed(2)}% of image area)");
      }
    }
    final lesionSentence = presentLesions.isEmpty
        ? "No microaneurysms, haemorrhages, or exudates were segmented above the detection threshold."
        : "Segmented lesion evidence: ${presentLesions.join('; ')}.";

    final qualityNote = result.fiqaLabel == "Reject"
        ? "Image quality was flagged as REJECT — the grade below is unreliable; request a recapture."
        : result.fiqaLabel == "Usable"
            ? "Image quality was Usable (not ideal) — findings should be interpreted with that in mind."
            : "Image quality was Good.";

    final actionSentence = result.isReferable
        ? "This case is REFERABLE (ICDR >= 2) and should be routed to an ophthalmologist for confirmation."
        : "This case is not referable at the current threshold (ICDR < 2); routine screening follow-up is appropriate.";

    return Scaffold(
      backgroundColor: AppColors.bg,
      appBar: AppBar(
        backgroundColor: AppColors.accent,
        foregroundColor: Colors.white,
        title: const Text("Screening Result"),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Row(
            children: [
              Expanded(child: _imageCard("Original", result.originalPng)),
              const SizedBox(width: 10),
              Expanded(child: _imageCard("Lesion evidence", result.overlayPng)),
            ],
          ),
          const SizedBox(height: 8),
          const Text(
            "MA=red  HE=orange  EX=yellow  SE=cyan  OD=green",
            style: TextStyle(fontSize: 11, color: AppColors.textSub),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 16),

          _card(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _sectionLabel("IMAGE QUALITY"),
                const SizedBox(height: 6),
                _badge(
                  "${result.fiqaLabel}  •  ${(result.fiqaConfidence * 100).toStringAsFixed(1)}% confidence",
                  fiqaColor,
                  fiqaColor.withValues(alpha: 0.12),
                ),
                const SizedBox(height: 14),
                _sectionLabel("ICDR GRADE"),
                const SizedBox(height: 4),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text("${result.grade}",
                        style: TextStyle(fontSize: 40, fontWeight: FontWeight.bold, color: gradeColor)),
                    const SizedBox(width: 10),
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Text(result.gradeLabel,
                          style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: gradeColor)),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                _sectionLabel("CALIBRATED CONFIDENCE"),
                const SizedBox(height: 6),
                ClipRRect(
                  borderRadius: BorderRadius.circular(6),
                  child: LinearProgressIndicator(
                    value: result.drConfidence,
                    minHeight: 10,
                    backgroundColor: AppColors.neutralBg,
                    valueColor: const AlwaysStoppedAnimation(AppColors.accent),
                  ),
                ),
                const SizedBox(height: 4),
                Text("${(result.drConfidence * 100).toStringAsFixed(1)}%",
                    style: const TextStyle(fontWeight: FontWeight.bold, color: AppColors.accent)),
                const SizedBox(height: 14),
                SizedBox(
                  width: double.infinity,
                  child: _badge(
                    result.isReferable
                        ? "⚠  REFERABLE — REFER TO OPHTHALMOLOGIST"
                        : "✓  NOT REFERABLE — ROUTINE FOLLOW-UP",
                    Colors.white,
                    result.isReferable ? AppColors.bad : AppColors.good,
                    center: true,
                  ),
                ),
                const SizedBox(height: 8),
                Text("Screened in ${result.elapsedSeconds.toStringAsFixed(2)}s on-device — meets the PS's <30s review target",
                    style: const TextStyle(fontSize: 11, color: AppColors.textSub), textAlign: TextAlign.center),
              ],
            ),
          ),
          const SizedBox(height: 14),

          _card(
            title: "CLINICAL SUMMARY (auto-generated from model outputs)",
            child: Text(
              "ICDR grade ${result.grade} (${result.gradeLabel}), calibrated confidence "
              "${(result.drConfidence * 100).toStringAsFixed(1)}%. ${gradeDescriptions[result.gradeLabel]}\n\n"
              "$qualityNote\n\n$lesionSentence\n\n$actionSentence\n\n"
              "This summary is generated deterministically from the structured model outputs above "
              "(a fixed template filling in the numbers) — it is not a free-text generation and cannot "
              "state anything the numbers don't already show.",
              style: const TextStyle(fontSize: 13, height: 1.4, color: AppColors.textMain),
            ),
          ),
          const SizedBox(height: 14),

          _card(
            title: "PER-LESION EVIDENCE",
            child: Table(
              border: TableBorder.all(color: AppColors.border),
              columnWidths: const {0: FlexColumnWidth(2), 1: FlexColumnWidth(1), 2: FlexColumnWidth(1.2), 3: FlexColumnWidth(1.6)},
              children: [
                _tableHeaderRow(["Lesion", "Present", "Coverage %", "Source model"]),
                for (final code in ["MA", "HE", "EX", "SE", "OD"])
                  _tableRow([
                    lesionNames[code]!,
                    (result.lesionCoveragePct[code] ?? 0) > 0.01 ? "Yes" : "No",
                    (result.lesionCoveragePct[code] ?? 0).toStringAsFixed(3),
                    lesionSourceModel[code]!,
                  ]),
              ],
            ),
          ),
          const SizedBox(height: 14),

          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppColors.caveatBg,
              border: Border.all(color: AppColors.caveatBorder),
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text("⚠  LIMITATIONS & CAVEATS",
                    style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: AppColors.caveatText)),
                SizedBox(height: 8),
                Text(
                  "Optic Disc: IDRiD-only (54 images), 0.842 dice. MA/HE/EX/SE: merged IDRiD+DDR+e-ophtha "
                  "(~1,300 images), pretrained encoder + Focal Tversky Loss. Proof-of-concept scale, not a "
                  "validated clinical result.\n\n"
                  "Microaneurysm dice = 0.029 (literature best on much larger, cleaner data is ~0.56) — "
                  "treat MA marks as a weak signal, not a definitive finding.\n\n"
                  "This overlay is direct per-lesion segmentation evidence, not a coarse Grad-CAM attention map.",
                  style: TextStyle(fontSize: 12, color: AppColors.caveatText, height: 1.4),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),
          const Text(
            "Dr.Retina — Explainable AI Diabetic Retinopathy Screening (PS 26038)\nProof-of-concept — not a validated clinical device",
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 11, color: AppColors.textSub),
          ),
          const SizedBox(height: 12),
        ],
      ),
    );
  }

  Widget _imageCard(String label, image) {
    return Column(
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(10),
          child: AspectRatio(
            aspectRatio: 1,
            child: Container(color: const Color(0xFF0F0F12), child: Image.memory(image, fit: BoxFit.contain)),
          ),
        ),
        const SizedBox(height: 4),
        Text(label, style: const TextStyle(fontSize: 11, color: AppColors.textSub)),
      ],
    );
  }

  Widget _card({String? title, required Widget child}) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.card,
        border: Border.all(color: AppColors.border),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (title != null) ...[_sectionLabel(title), const SizedBox(height: 8)],
          child,
        ],
      ),
    );
  }

  Widget _sectionLabel(String text) =>
      Text(text, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: AppColors.textSub));

  Widget _badge(String text, Color fg, Color bg, {bool center = false}) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(8)),
      child: Text(text,
          textAlign: center ? TextAlign.center : TextAlign.start,
          style: TextStyle(color: fg, fontWeight: FontWeight.bold, fontSize: 13)),
    );
  }

  TableRow _tableHeaderRow(List<String> cells) {
    return TableRow(
      decoration: const BoxDecoration(color: AppColors.neutralBg),
      children: cells
          .map((c) => Padding(
                padding: const EdgeInsets.all(8),
                child: Text(c, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12)),
              ))
          .toList(),
    );
  }

  TableRow _tableRow(List<String> cells) {
    return TableRow(
      children: cells
          .map((c) => Padding(
                padding: const EdgeInsets.all(8),
                child: Text(c, style: const TextStyle(fontSize: 12)),
              ))
          .toList(),
    );
  }
}
