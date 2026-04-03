import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import '../services/api_service.dart';
import 'conversation_screen.dart';

class CameraScreen extends StatefulWidget {
  const CameraScreen({super.key});

  @override
  State<CameraScreen> createState() => _CameraScreenState();
}

class _CameraScreenState extends State<CameraScreen> {
  bool _isLoading = false;

  Future<void> _pickImage(ImageSource source) async {
    final picker = ImagePicker();
    final picked = await picker.pickImage(
      source: source,
      imageQuality: 85,
      requestFullMetadata: false,
    );
    if (picked == null) return;

    setState(() => _isLoading = true);

    try {
      final result = await ApiService.analyzeImage(File(picked.path));
      if (!mounted) return;
      setState(() => _isLoading = false);
      final sessionId = DateTime.now().millisecondsSinceEpoch.toString();
      Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => ConversationScreen(
            sessionId: sessionId,
            seedImageAnalysis: result,
          ),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() => _isLoading = false);
      _showError(
          'Could not connect to the server.\nMake sure the backend is running on port 8000.\n\nError: $e');
    }
  }

  void _showError(String msg) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF1E293B),
        shape:
            RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Row(
          children: [
            Icon(Icons.error_outline, color: Color(0xFFEF4444), size: 20),
            SizedBox(width: 8),
            Text('Connection Error',
                style: TextStyle(color: Colors.white, fontSize: 16)),
          ],
        ),
        content: Text(msg,
            style:
                const TextStyle(color: Color(0xFF94A3B8), height: 1.5)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('OK',
                style: TextStyle(color: Color(0xFF3B82F6))),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF020817),
      appBar: AppBar(
        backgroundColor: const Color(0xFF020817),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_rounded, color: Colors.white),
          onPressed: () => Navigator.pop(context),
        ),
        title: const Text(
          'Find Your Location',
          style:
              TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
        ),
      ),
      body: Stack(
        children: [
          Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              children: [
                // Info banner
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: const Color(0xFF3B82F6).withOpacity(0.08),
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(
                        color: const Color(0xFF3B82F6).withOpacity(0.25)),
                  ),
                  child: const Row(
                    children: [
                      Icon(Icons.lightbulb_outline,
                          color: Color(0xFF3B82F6), size: 18),
                      SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          'Take a photo of a building directory sign. PaliGemma AI will detect your building and floor automatically.',
                          style: TextStyle(
                              color: Color(0xFF93C5FD),
                              fontSize: 13,
                              height: 1.4),
                        ),
                      ),
                    ],
                  ),
                ),

                const Spacer(),

                // Icon
                Container(
                  width: 110,
                  height: 110,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: const Color(0xFF0F172A),
                    border: Border.all(
                        color: const Color(0xFF1E293B), width: 2),
                  ),
                  child: const Icon(Icons.photo_camera_outlined,
                      size: 50, color: Color(0xFF3B82F6)),
                ),
                const SizedBox(height: 28),
                const Text(
                  'Choose image source',
                  style: TextStyle(
                      color: Colors.white,
                      fontSize: 22,
                      fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 6),
                const Text(
                  'Point at a building directory sign for best results',
                  style: TextStyle(color: Color(0xFF64748B), fontSize: 14),
                  textAlign: TextAlign.center,
                ),

                const Spacer(),

                // Camera button
                _PickButton(
                  icon: Icons.camera_alt_rounded,
                  title: 'Take Photo',
                  subtitle: 'Use your camera now',
                  isPrimary: true,
                  onTap: () => _pickImage(ImageSource.camera),
                ),
                const SizedBox(height: 12),
                // Gallery button
                _PickButton(
                  icon: Icons.photo_library_outlined,
                  title: 'Choose from Gallery',
                  subtitle: 'Select an existing photo',
                  isPrimary: false,
                  onTap: () => _pickImage(ImageSource.gallery),
                ),

                const SizedBox(height: 32),
              ],
            ),
          ),

          // Loading overlay
          if (_isLoading)
            Container(
              color: Colors.black.withOpacity(0.82),
              child: Center(
                child: Container(
                  margin: const EdgeInsets.symmetric(horizontal: 48),
                  padding: const EdgeInsets.all(32),
                  decoration: BoxDecoration(
                    color: const Color(0xFF1E293B),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: const Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      CircularProgressIndicator(
                          color: Color(0xFF3B82F6), strokeWidth: 3),
                      SizedBox(height: 20),
                      Text(
                        'Analyzing building sign...',
                        style: TextStyle(
                            color: Colors.white,
                            fontSize: 15,
                            fontWeight: FontWeight.w500),
                      ),
                      SizedBox(height: 6),
                      Text(
                        'PaliGemma AI is working',
                        style: TextStyle(
                            color: Color(0xFF64748B), fontSize: 13),
                      ),
                    ],
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _PickButton extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final bool isPrimary;
  final VoidCallback onTap;

  const _PickButton({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.isPrimary,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: isPrimary
                ? const Color(0xFF3B82F6)
                : const Color(0xFF0F172A),
            borderRadius: BorderRadius.circular(16),
            border: isPrimary
                ? null
                : Border.all(color: const Color(0xFF1E293B)),
          ),
          child: Row(
            children: [
              Icon(icon,
                  color: isPrimary
                      ? Colors.white
                      : const Color(0xFF3B82F6),
                  size: 28),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title,
                        style: const TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.w600,
                            fontSize: 16)),
                    Text(subtitle,
                        style: TextStyle(
                            color: isPrimary
                                ? Colors.white70
                                : const Color(0xFF64748B),
                            fontSize: 13)),
                  ],
                ),
              ),
              Icon(Icons.arrow_forward_ios_rounded,
                  color: isPrimary
                      ? Colors.white70
                      : const Color(0xFF475569),
                  size: 16),
            ],
          ),
        ),
      ),
    );
  }
}
