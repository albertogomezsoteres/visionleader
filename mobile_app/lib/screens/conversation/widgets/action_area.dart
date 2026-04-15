import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import 'action_buttons.dart';
import 'outdoor_walking_card.dart';

/// Renders the bottom action area of the conversation screen, picking the
/// right control set (voice / photo / confirm / outdoor walking card) for
/// the current FSM action and next_input hint coming from the backend.
class ActionArea extends StatelessWidget {
  final String currentAction;
  final String nextInput;
  final bool isRecording;
  final Animation<double> pulseAnimation;

  final int? pendingGpsDestinationId;
  final String pendingGpsDestinationName;

  final VoidCallback onStartRecording;
  final VoidCallback onStopRecording;
  final void Function(ImageSource source) onPickPhoto;
  final VoidCallback onConfirmYes;
  final VoidCallback onConfirmNo;
  final VoidCallback onArrivedOutdoor;
  final VoidCallback onReopenOutdoorMap;

  const ActionArea({
    super.key,
    required this.currentAction,
    required this.nextInput,
    required this.isRecording,
    required this.pulseAnimation,
    required this.pendingGpsDestinationId,
    required this.pendingGpsDestinationName,
    required this.onStartRecording,
    required this.onStopRecording,
    required this.onPickPhoto,
    required this.onConfirmYes,
    required this.onConfirmNo,
    required this.onArrivedOutdoor,
    required this.onReopenOutdoorMap,
  });

  @override
  Widget build(BuildContext context) {
    if (currentAction == 'goodbye' || currentAction == 'error') {
      return const SizedBox.shrink();
    }

    if (currentAction == 'navigation_step_outdoor' &&
        pendingGpsDestinationId != null) {
      return OutdoorWalkingCard(
        destinationName: pendingGpsDestinationName,
        onArrived: onArrivedOutdoor,
        onReopenMap: onReopenOutdoorMap,
      );
    }

    switch (nextInput) {
      case 'voice':
        return VoiceButton(
          isRecording: isRecording,
          pulseAnimation: pulseAnimation,
          onTapDown: onStartRecording,
          onTapUp: onStopRecording,
        );

      case 'photo':
        return Column(
          children: [
            PhotoButton(onTap: () => showPhotoSourceSheet(context, onPickPhoto)),
            const SizedBox(height: 10),
            CompactMicButton(
              isRecording: isRecording,
              pulseAnimation: pulseAnimation,
              onTapDown: onStartRecording,
              onTapUp: onStopRecording,
            ),
          ],
        );

      case 'confirm':
        return Column(
          children: [
            ConfirmButtons(
              isConfirmPlan: currentAction == 'confirm_plan',
              onConfirm: onConfirmYes,
              onDeny: onConfirmNo,
            ),
            const SizedBox(height: 16),
            const DividerOr(label: 'or speak'),
            const SizedBox(height: 12),
            CompactMicButton(
              isRecording: isRecording,
              pulseAnimation: pulseAnimation,
              onTapDown: onStartRecording,
              onTapUp: onStopRecording,
            ),
          ],
        );

      case 'voice_or_photo':
        return Column(
          children: [
            VoiceButton(
              isRecording: isRecording,
              pulseAnimation: pulseAnimation,
              onTapDown: onStartRecording,
              onTapUp: onStopRecording,
            ),
            const SizedBox(height: 16),
            const DividerOr(),
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              height: 54,
              child: OutlinedButton.icon(
                onPressed: () => showPhotoSourceSheet(context, onPickPhoto),
                icon: const Icon(Icons.photo_camera_outlined, size: 20),
                label: const Text(
                  'Take a photo instead',
                  style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
                ),
                style: OutlinedButton.styleFrom(
                  foregroundColor: const Color(0xFF3B82F6),
                  side: const BorderSide(color: Color(0xFF3B82F6)),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14),
                  ),
                ),
              ),
            ),
          ],
        );

      case 'none':
        return const SizedBox.shrink();

      default:
        return VoiceButton(
          isRecording: isRecording,
          pulseAnimation: pulseAnimation,
          onTapDown: onStartRecording,
          onTapUp: onStopRecording,
        );
    }
  }
}
