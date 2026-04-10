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
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(
          color: const Color(0xFF0F172A),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: const Color(0xFF1E293B), width: 1),
        ),
        child: SingleChildScrollView(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: iconColor.withValues(alpha: 0.10),
                  border: Border.all(
                    color: iconColor.withValues(alpha: 0.20),
                    width: 1,
                  ),
                ),
                child: Icon(iconData, color: iconColor, size: 24),
              ),
              const SizedBox(height: 18),
              Text(
                message.isEmpty
                    ? 'Starting navigation assistant...'
                    : message,
                style: const TextStyle(
                  color: Color(0xFFF1F5F9),
                  fontSize: 16,
                  height: 1.6,
                  fontWeight: FontWeight.w400,
                  letterSpacing: 0.1,
                ),
                textAlign: TextAlign.center,
              ),
              if (message.isNotEmpty) ...[
                const SizedBox(height: 18),
                Semantics(
                  button: true,
                  label: 'Replay the assistant message',
                  child: GestureDetector(
                    onTap: onTapReplay,
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.volume_up_outlined,
                            size: 14, color: const Color(0xFF3B82F6).withValues(alpha: 0.6)),
                        const SizedBox(width: 5),
                        const Text(
                          'Tap to hear again',
                          style: TextStyle(
                            color: Color(0xFF475569),
                            fontSize: 12,
                            letterSpacing: 0.2,
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
    );
  }
}
