import 'package:flutter/material.dart';

/// The main message card showing the assistant's latest TTS text.
class MessageBubble extends StatelessWidget {
  final String message;
  final String currentAction;
  final VoidCallback onTapReplay;

  const MessageBubble({
    super.key,
    required this.message,
    required this.currentAction,
    required this.onTapReplay,
  });

  bool get _isNavigating =>
      currentAction == 'navigation_step' ||
      currentAction == 'awaiting_step_done' ||
      currentAction == 'waiting_step_photo' ||
      currentAction == 'retry_step_photo' ||
      currentAction == 'repeat';

  @override
  Widget build(BuildContext context) {
    final isComplete = currentAction == 'navigation_complete';
    final iconData = isComplete
        ? Icons.check_circle_outline_rounded
        : (_isNavigating
            ? Icons.directions_walk_rounded
            : Icons.assistant_rounded);
    final iconColor =
        isComplete ? const Color(0xFF10B981) : const Color(0xFF3B82F6);

    return Semantics(
      liveRegion: true,
      label: message.isEmpty ? 'Starting navigation assistant' : message,
      child: Center(
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(
          color: const Color(0xFF0F172A),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: const Color(0xFF1E293B)),
        ),
        child: SingleChildScrollView(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                width: 52,
                height: 52,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: iconColor.withValues(alpha: 0.12),
                ),
                child: Icon(iconData, color: iconColor, size: 28),
              ),
              const SizedBox(height: 20),
              Text(
                message.isEmpty
                    ? 'Starting navigation assistant...'
                    : message,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 16,
                  height: 1.55,
                  fontWeight: FontWeight.w400,
                ),
                textAlign: TextAlign.center,
              ),
              if (message.isNotEmpty) ...[
                const SizedBox(height: 20),
                Semantics(
                  button: true,
                  label: 'Replay the assistant message',
                  child: GestureDetector(
                  onTap: onTapReplay,
                  child: const Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.volume_up_outlined,
                          size: 16, color: Color(0xFF475569)),
                      SizedBox(width: 6),
                      Text(
                        'Tap to hear again',
                        style: TextStyle(
                          color: Color(0xFF475569),
                          fontSize: 12,
                        ),
                      ),
                    ],
                  ),
                ),
                ),
              ],
            ],
          ),
        ),
      ),
      ),
    );
  }
}
