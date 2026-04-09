import 'package:flutter/material.dart';

ThemeData buildAppTheme() {
  return ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    scaffoldBackgroundColor: const Color(0xFF020817),
    colorScheme: const ColorScheme.dark(
      primary: Color(0xFF3B82F6),
      secondary: Color(0xFF818CF8),
      surface: Color(0xFF0F172A),
      onPrimary: Colors.white,
      onSecondary: Colors.white,
      onSurface: Color(0xFFF1F5F9),
    ),
    appBarTheme: const AppBarTheme(
      backgroundColor: Color(0xFF020817),
      foregroundColor: Color(0xFFF1F5F9),
      elevation: 0,
      centerTitle: true,
    ),
  );
}
