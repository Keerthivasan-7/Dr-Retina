import 'dart:io';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:image/image.dart' as img;
import 'package:image_picker/image_picker.dart';

import '../services/screening_pipeline.dart';
import '../theme/app_colors.dart';
import 'results_screen.dart';

class CaptureScreen extends StatefulWidget {
  final ScreeningPipeline pipeline;
  const CaptureScreen({super.key, required this.pipeline});

  @override
  State<CaptureScreen> createState() => _CaptureScreenState();
}

class _CaptureScreenState extends State<CaptureScreen> {
  CameraController? _cameraController;
  List<CameraDescription> _cameras = [];
  bool _cameraReady = false;
  bool _running = false;
  String _status = "Loading models...";

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    await widget.pipeline.load();
    setState(() => _status = "Ready");
    try {
      _cameras = await availableCameras();
      if (_cameras.isNotEmpty) {
        final back = _cameras.firstWhere(
          (c) => c.lensDirection == CameraLensDirection.back,
          orElse: () => _cameras.first,
        );
        _cameraController = CameraController(back, ResolutionPreset.high, enableAudio: false);
        await _cameraController!.initialize();
        if (mounted) setState(() => _cameraReady = true);
      }
    } catch (e) {
      // No camera available (e.g. some emulator configs) — gallery upload still works.
      setState(() => _status = "Camera unavailable — use gallery upload below");
    }
  }

  @override
  void dispose() {
    _cameraController?.dispose();
    super.dispose();
  }

  Future<void> _handleCapturedFile(String path) async {
    setState(() => _running = true);
    try {
      final bytes = await File(path).readAsBytes();
      final decoded = img.decodeImage(bytes);
      if (decoded == null) {
        throw Exception("Could not decode image");
      }
      final result = await widget.pipeline.run(decoded);
      if (!mounted) return;
      await Navigator.of(context).push(MaterialPageRoute(builder: (_) => ResultsScreen(result: result)));
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Error: $e")));
      }
    } finally {
      if (mounted) setState(() => _running = false);
    }
  }

  Future<void> _captureFromCamera() async {
    if (_cameraController == null || !_cameraController!.value.isInitialized) return;
    final file = await _cameraController!.takePicture();
    await _handleCapturedFile(file.path);
  }

  Future<void> _pickFromGallery() async {
    final picker = ImagePicker();
    final picked = await picker.pickImage(source: ImageSource.gallery);
    if (picked != null) {
      await _handleCapturedFile(picked.path);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bg,
      appBar: AppBar(
        backgroundColor: AppColors.accent,
        foregroundColor: Colors.white,
        title: const Text("Dr.Retina"),
      ),
      body: Column(
        children: [
          Container(
            width: double.infinity,
            color: AppColors.accent,
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 14),
            child: const Text(
              "Explainable AI Diabetic Retinopathy Screening — offline, on-device inference",
              style: TextStyle(color: Colors.white70, fontSize: 12),
            ),
          ),
          Expanded(
            child: Stack(
              alignment: Alignment.center,
              children: [
                if (_cameraReady && _cameraController != null)
                  Positioned.fill(child: CameraPreview(_cameraController!))
                else
                  Container(
                    color: const Color(0xFF0F0F12),
                    child: Center(
                      child: Text(_status, style: const TextStyle(color: Colors.white70)),
                    ),
                  ),
                // Circular alignment guide for a clip-on fundus camera attachment —
                // these are purely optical (no hardware SDK needed), so the phone's
                // normal camera + this guide is all live capture requires.
                if (_cameraReady)
                  IgnorePointer(
                    child: Container(
                      width: 260,
                      height: 260,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        border: Border.all(color: Colors.white.withValues(alpha: 0.8), width: 2),
                      ),
                    ),
                  ),
                if (_running)
                  Container(
                    color: Colors.black54,
                    child: const Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          CircularProgressIndicator(color: Colors.white),
                          SizedBox(height: 12),
                          Text("Running FIQA → DR grading → lesion segmentation...",
                              style: TextStyle(color: Colors.white)),
                        ],
                      ),
                    ),
                  ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                if (_cameraReady)
                  Expanded(
                    child: FilledButton.icon(
                      onPressed: _running ? null : _captureFromCamera,
                      icon: const Icon(Icons.camera_alt),
                      label: const Text("Capture"),
                      style: FilledButton.styleFrom(backgroundColor: AppColors.accent, padding: const EdgeInsets.all(14)),
                    ),
                  ),
                if (_cameraReady) const SizedBox(width: 10),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _running ? null : _pickFromGallery,
                    icon: const Icon(Icons.photo_library_outlined),
                    label: const Text("Upload from Gallery"),
                    style: OutlinedButton.styleFrom(foregroundColor: AppColors.accent, padding: const EdgeInsets.all(14)),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
