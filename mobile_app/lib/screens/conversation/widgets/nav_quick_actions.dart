import 'package:flutter/material.dart';

/// Row of quick-action chips shown during active navigation.
class NavQuickActions extends StatelessWidget {
  final VoidCallback onNext;
  final VoidCallback onRepeat;
  final VoidCallback onLost;
  final VoidCallback onCancel;

  const NavQuickActions({
    super.key,
    required this.onNext,
    required this.onRepeat,
    required this.onLost,
    required this.onCancel,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Row(
        children: [
          // Next - primary action, most prominent
          Expanded(
            flex: 3,
            child: _NavChip(
              icon: Icons.skip_next_rounded,
              label: 'Next step',
              color: const Color(0xFF3B82F6),
              filled: true,
              onTap: onNext,
              semanticLabel: 'Go to next navigation step',
            ),
          ),
          const SizedBox(width: 8),
          // Repeat - utility
          Expanded(
            flex: 3,
            child: _NavChip(
              icon: Icons.replay_rounded,
              label: 'Repeat',
              color: const Color(0xFF64748B),
              onTap: onRepeat,
              semanticLabel: 'Repeat the last instruction',
            ),
          ),
          const SizedBox(width: 8),
          // Lost - warning
          Expanded(
            flex: 3,
            child: _NavChip(
              icon: Icons.help_outline_rounded,
              label: 'Lost',
              color: const Color(0xFFD97706),
              onTap: onLost,
              semanticLabel: 'Tell the assistant you are lost',
            ),
          ),
          const SizedBox(width: 8),
          // Cancel - destructive, least prominent
          Expanded(
            flex: 3,
            child: _NavChip(
              icon: Icons.close_rounded,
              label: 'Cancel',
              color: const Color(0xFFEF4444),
              onTap: onCancel,
              semanticLabel: 'Cancel the current navigation',
            ),
          ),
        ],
      ),
    );
  }
}

class _NavChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;
  final bool filled;
  final VoidCallback onTap;
  final String semanticLabel;

  const _NavChip({
    required this.icon,
    required this.label,
    required this.color,
    required this.onTap,
    required this.semanticLabel,
    this.filled = false,
  });

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: semanticLabel,
      child: Material(
        color: filled
            ? color.withValues(alpha: 0.20)
            : const Color(0xFF1E293B),
        borderRadius: BorderRadius.circular(10),
        child: InkWell(
          borderRadius: BorderRadius.circular(10),
          onTap: onTap,
          child: Container(
            padding: const EdgeInsets.symmetric(vertical: 11),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(10),
              border: Border.all(
                color: filled
                    ? color.withValues(alpha: 0.50)
                    : const Color(0xFF334155),
                width: 1,
              ),
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(icon, size: 18, color: color),
                const SizedBox(height: 3),
                Text(
                  label,
                  style: TextStyle(
                    color: filled ? color : const Color(0xFF94A3B8),
                    fontSize: 12,
                    fontWeight: FontWeight.w500,
                    letterSpacing: 0.2,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
