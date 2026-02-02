import 'package:flutter/material.dart';
import 'photo_screen.dart';

void main() {
  runApp(const VisionLeaderUFV());
}

class VisionLeaderUFV extends StatelessWidget {
  const VisionLeaderUFV({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'VisionLeaderUFV',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        scaffoldBackgroundColor: const Color(0xFFF8FAFC),
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF1E3A8A),
          primary: const Color(0xFF1E3A8A),
        ),
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFF1E3A8A),
          foregroundColor: Colors.white,
          centerTitle: true,
          elevation: 0,
        ),
        elevatedButtonTheme: ElevatedButtonThemeData(
          style: ElevatedButton.styleFrom(
            backgroundColor: const Color(0xFF1E3A8A),
            foregroundColor: Colors.white,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(14),
            ),
          ),
        ),
      ),
      home: const PhotoScreen(),
    );
  }
}