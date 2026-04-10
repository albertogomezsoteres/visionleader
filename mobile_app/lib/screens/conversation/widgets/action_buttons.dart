import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

/// All the bottom-area input widgets: voice button, photo button,
/// confirm buttons, and their combinations.
///
/// The parent passes callbacks; this file owns only the visual layout.

// ── Voice (large microphone) ────────────────────────────────────────────

class VoiceButton extends StatelessWidget {
  final bool isRecording;
  final Animation<double> pulseAnimation;
  final VoidCallback onTapDown;
  final VoidCallback onTapUp;

  const VoiceButton({
    super.key,
    required this.isRecording,
    required this.pulseAnimation,
    required this.onTapDown,
    required this.onTapUp,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Center(
          child: Semantics(
            button: true,
            label: isRecording ? 'Release to stop recording' : 'Hold to speak',
            child: GestureDetector(
            onTapDown: (_) => onTapDown(),
            onTapUp: (_) => onTapUp(),
            onTapCancel: onTapUp,
            child: AnimatedBuilder(
              animation: pulseAnimation,
              builder: (_, _) => Transform.scale(
                scale: isRecording ? pulseAnimation.value : 1.0,
                child: Container(
                  width: 90,
                  height: 90,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: isRecording
                        ? const Color(0xFFEF4444)
                        : const Color(0xFF3B82F6),
                    boxShadow: [
                      BoxShadow(
                        color: (isRecording
                                ? const Color(0xFFEF4444)
                                : const Color(0xFF3B82F6))
                            .withValues(alpha: 0.4),
                        blurRadius: isRecording ? 28 : 16,
                        spreadRadius: isRecording ? 6 : 2,
                      ),
                    ],
                  ),
                  child: Icon(
                    isRecording ? Icons.mic_rounded : Icons.mic_none_rounded,
                    size: 40,
                    color: Colors.white,
                  ),
                ),
              ),
            ),
          ),
          ),
        ),
        const SizedBox(height: 10),
        Text(
          isRecording ? 'Listening... release to stop' : 'Hold to speak',
          style: TextStyle(
            color: isRecording
                ? const Color(0xFFEF4444)
                : const Color(0xFF64748B),
            fontSize: 13,
            fontWeight: isRecording ? FontWeight.w500 : FontWeight.normal,
          ),
        ),
      ],
    );
  }
}

// ── Compact mic (used alongside photo or confirm buttons) ───────────────

class CompactMicButton extends StatelessWidget {
  final bool isRecording;
  final Animation<double> pulseAnimation;
  final VoidCallback onTapDown;
  final VoidCallback onTapUp;

  const CompactMicButton({
    super.key,
    required this.isRecording,
    required this.pulseAnimation,
    required this.onTapDown,
    required this.onTapUp,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTapDown: (_) => onTapDown(),
      onTapUp: (_) => onTapUp(),
      onTapCancel: onTapUp,
      child: AnimatedBuilder(
        animation: pulseAnimation,
        builder: (_, _) => Transform.scale(
          scale: isRecording ? pulseAnimation.value : 1.0,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                width: 52,
                height: 52,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: isRecording
                      ? const Color(0xFFEF4444).withValues(alpha: 0.15)
                      : const Color(0xFF1E293B),
                  border: Border.all(
                    color: isRecording
                        ? const Color(0xFFEF4444)
                        : const Color(0xFF334155),
                  ),
                ),
                child: Icon(
                  isRecording ? Icons.mic_rounded : Icons.mic_none_rounded,
                  size: 24,
                  color: isRecording
                      ? const Color(0xFFEF4444)
                      : const Color(0xFF64748B),
                ),
              ),
              const SizedBox(width: 10),
              Text(
                isRecording ? 'Listening...' : 'Hold to speak',
                style: TextStyle(
                  color: isRecording
                      ? const Color(0xFFEF4444)
                      : const Color(0xFF64748B),
                  fontSize: 13,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ── Photo button ────────────────────────────────────────────────────────

class PhotoButton extends StatelessWidget {
  final VoidCallback onTap;

  const PhotoButton({super.key, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      height: 60,
      child: ElevatedButton.icon(
        onPressed: onTap,
        icon: const Icon(Icons.photo_camera_outlined, size: 22),
        label: const Text('Take Photo',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
        style: ElevatedButton.styleFrom(
          backgroundColor: const Color(0xFF3B82F6),
          foregroundColor: Colors.white,
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        ),
      ),
    );
  }
}

// ── Confirm / deny row ──────────────────────────────────────────────────

class ConfirmButtons extends StatelessWidget {
  final bool isConfirmPlan;
  final VoidCallback onConfirm;
  final VoidCallback onDeny;

  const ConfirmButtons({
    super.key,
    required this.isConfirmPlan,
    required this.onConfirm,
    required this.onDeny,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: OutlinedButton(
            onPressed: onDeny,
            style: OutlinedButton.styleFrom(
              foregroundColor: const Color(0xFF94A3B8),
              side: const BorderSide(color: Color(0xFF334155)),
              padding: const EdgeInsets.symmetric(vertical: 16),
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14)),
            ),
            child: Text(isConfirmPlan ? 'Change' : 'No',
                style:
                    const TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
          ),
        ),
        const SizedBox(width: 14),
        Expanded(
          flex: 2,
          child: ElevatedButton(
            onPressed: onConfirm,
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF3B82F6),
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(vertical: 16),
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14)),
              elevation: 0,
            ),
            child: Text(
                isConfirmPlan ? 'Start navigation' : 'Yes, correct',
                style:
                    const TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
          ),
        ),
      ],
    );
  }
}

// ── "or" divider ────────────────────────────────────────────────────────

class DividerOr extends StatelessWidget {
  final String label;

  const DividerOr({super.key, this.label = 'or'});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        const Expanded(child: Divider(color: Color(0xFF334155))),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12),
          child: Text(label,
              style:
                  const TextStyle(color: Color(0xFF475569), fontSize: 12)),
        ),
        const Expanded(child: Divider(color: Color(0xFF334155))),
      ],
    );
  }
}

// ── Photo-source bottom sheet ───────────────────────────────────────────

void showPhotoSourceSheet(BuildContext context, void Function(ImageSource) onPick) {
  showModalBottomSheet(
    context: context,
    backgroundColor: const Color(0xFF1E293B),
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (ctx) => SafeArea(
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: const Color(0xFF475569),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(height: 16),
            ListTile(
              leading: const Icon(Icons.camera_alt_rounded,
                  color: Color(0xFF3B82F6)),
              title: const Text('Take Photo',
                  style: TextStyle(color: Colors.white)),
              onTap: () {
                Navigator.pop(ctx);
                onPick(ImageSource.camera);
              },
            ),
            ListTile(
              leading: const Icon(Icons.photo_library_outlined,
                  color: Color(0xFF3B82F6)),
              title: const Text('Choose from Gallery',
                  style: TextStyle(color: Colors.white)),
              onTap: () {
                Navigator.pop(ctx);
                onPick(ImageSource.gallery);
              },
            ),
          ],
        ),
      ),
    ),
  );
}
