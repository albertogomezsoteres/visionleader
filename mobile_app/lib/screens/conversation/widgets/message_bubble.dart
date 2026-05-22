import 'package:flutter/material.dart';

import 'tts_waveform.dart';

/// Compact assistant indicator: icon (walking / assistant / arrival),
/// optional step badge, and a TTS waveform when the assistant is speaking.
///
/// The full TTS text is intentionally not rendered on screen - the user
/// hears the message through the speaker. The Semantics label still
/// carries the full text so accessibility tools can read it on demand.
class MessageBubble extends StatelessWidget {
  final String message;
  final String currentAction;
  final int? currentStep;
  final int? totalSteps;
  final bool isTtsActive;
  final VoidCallback onTapReplay;

  const MessageBubble({
    super.key,
    required this.message,
    required this.currentAction,
    this.currentStep,
    this.totalSteps,
    this.isTtsActive = false,
    required this.onTapReplay,
  });

  bool get _isNavigating =>
      currentAction == 'navigation_step' ||
      currentAction == 'navigation_step_outdoor' ||
      currentAction == 'awaiting_step_done' ||
      currentAction == 'waiting_step_photo' ||
      currentAction == 'retry_step_photo' ||
      currentAction == 'step_after_photo_confirm' ||
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
    final showStepBadge =
        (currentStep ?? 0) > 0 && (totalSteps ?? 0) > 0;

    final bubble = ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 360),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 30),
        decoration: BoxDecoration(
          color: const Color(0xFF0F172A),
          borderRadius: BorderRadius.circular(22),
          border: Border.all(color: const Color(0xFF1E293B), width: 1),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (showStepBadge) ...[
              Container(
                padding: const EdgeInsets.symmetric(
                    horizontal: 14, vertical: 7),
                decoration: BoxDecoration(
                  color: const Color(0xFF3B82F6).withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(
                    color: const Color(0xFF3B82F6).withValues(alpha: 0.35),
                  ),
                ),
                child: Text(
                  'Step ${currentStep!} / ${totalSteps!}',
                  style: const TextStyle(
                    color: Color(0xFF3B82F6),
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 0.3,
                  ),
                ),
              ),
              const SizedBox(height: 22),
            ],
            Container(
              width: 72,
              height: 72,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: iconColor.withValues(alpha: 0.10),
                border: Border.all(
                  color: iconColor.withValues(alpha: 0.22),
                  width: 1.5,
                ),
              ),
              child: Icon(iconData, color: iconColor, size: 36),
            ),
            const SizedBox(height: 22),
            if (isTtsActive)
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const TtsWaveform(active: true),
                  const SizedBox(width: 12),
                  Text(
                    'Speaking…',
                    style: TextStyle(
                      color:
                          const Color(0xFF3B82F6).withValues(alpha: 0.9),
                      fontSize: 14,
                      fontWeight: FontWeight.w500,
                      letterSpacing: 0.4,
                    ),
                  ),
                ],
              )
            else if (message.isNotEmpty)
              Semantics(
                button: true,
                label: 'Replay the assistant message',
                child: GestureDetector(
                  onTap: onTapReplay,
                  behavior: HitTestBehavior.opaque,
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        Icons.volume_up_outlined,
                        size: 18,
                        color:
                            const Color(0xFF3B82F6).withValues(alpha: 0.7),
                      ),
                      const SizedBox(width: 7),
                      const Text(
                        'Tap to repeat',
                        style: TextStyle(
                          color: Color(0xFF64748B),
                          fontSize: 13,
                          fontWeight: FontWeight.w500,
                          letterSpacing: 0.3,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
          ],
        ),
      ),
    );

    return Semantics(
      liveRegion: true,
      label: message.isEmpty ? 'Starting navigation assistant' : message,
      // FittedBox scales the bubble down (never up) when the parent gives
      // less vertical room than its natural size - needed when the
      // Symbolic Plan card is expanded and eats into the available space.
      child: Center(
        child: FittedBox(
          fit: BoxFit.scaleDown,
          alignment: Alignment.center,
          child: bubble,
        ),
      ),
    );
  }
}
