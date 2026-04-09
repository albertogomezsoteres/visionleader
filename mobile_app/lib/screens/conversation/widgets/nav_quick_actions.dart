import 'package:flutter/material.dart';

/// Row of quick-action buttons shown during active navigation:
/// Repeat, Lost, and Cancel.
class NavQuickActions extends StatelessWidget {
  final VoidCallback onNext;
  final VoidCallback onPhoto;
  final VoidCallback onRepeat;
  final VoidCallback onLost;
  final VoidCallback onCancel;

  const NavQuickActions({
    super.key,
    required this.onNext,
    required this.onPhoto,
    required this.onRepeat,
    required this.onLost,
    required this.onCancel,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Wrap(
        spacing: 10,
        runSpacing: 10,
        children: [
          _QuickChip(
            icon: Icons.skip_next_rounded,
            label: 'Next',
            color: const Color(0xFF22C55E),
            onTap: onNext,
            semanticLabel: 'Go to next step',
          ),
          _QuickChip(
            icon: Icons.photo_camera_rounded,
            label: 'Photo',
            color: const Color(0xFF8B5CF6),
            onTap: onPhoto,
            semanticLabel: 'Take a verification photo',
          ),
          _QuickChip(
            icon: Icons.replay_rounded,
            label: 'Repeat',
            color: const Color(0xFF3B82F6),
            onTap: onRepeat,
            semanticLabel: 'Repeat the last instruction',
          ),
          const SizedBox(width: 10),
          _QuickChip(
            icon: Icons.help_outline_rounded,
            label: "I'm lost",
            color: const Color(0xFFF59E0B),
            onTap: onLost,
            semanticLabel: 'Tell the assistant you are lost',
          ),
          const SizedBox(width: 10),
          _QuickChip(
            icon: Icons.close_rounded,
            label: 'Cancel',
            color: const Color(0xFFEF4444),
            onTap: onCancel,
            semanticLabel: 'Cancel the current navigation',
          ),
        ],
      ),
    );
  }
}

class _QuickChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;
  final VoidCallback onTap;
  final String semanticLabel;

  const _QuickChip({
    required this.icon,
    required this.label,
    required this.color,
    required this.onTap,
    required this.semanticLabel,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 104,
      child: Semantics(
        button: true,
        label: semanticLabel,
        child: Material(
          color: color.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(12),
          child: InkWell(
            borderRadius: BorderRadius.circular(12),
            onTap: onTap,
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 10),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(icon, size: 16, color: color),
                  const SizedBox(width: 4),
                  Text(
                    label,
                    style: TextStyle(
                      color: color,
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
