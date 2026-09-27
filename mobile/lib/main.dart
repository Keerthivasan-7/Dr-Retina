import 'package:flutter/material.dart';

import 'screens/capture_screen.dart';
import 'services/screening_pipeline.dart';
import 'theme/app_colors.dart';

void main() {
  runApp(const DrRetinaApp());
}

class DrRetinaApp extends StatelessWidget {
  const DrRetinaApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Dr.Retina',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        scaffoldBackgroundColor: AppColors.bg,
        colorScheme: ColorScheme.fromSeed(seedColor: AppColors.accent, brightness: Brightness.light),
      ),
      home: CaptureScreen(pipeline: ScreeningPipeline()),
    );
  }
}
