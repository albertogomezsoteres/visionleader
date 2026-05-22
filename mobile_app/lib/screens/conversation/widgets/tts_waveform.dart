import 'dart:math' as math;

import 'package:flutter/material.dart';

/// Live audio-bar visualiser shown while the TTS engine is speaking.
///
/// Seven thin vertical bars pulse independently with phase-offset sine
/// waves so the row reads as a "live" speech indicator rather than a
/// metronome. When [active] is false the bars collapse to a flat dotted
/// rest state — no animation work is performed and no frames are
/// scheduled, so this widget is cheap to keep in the tree at all times.
class TtsWaveform extends StatefulWidget {
  final bool active;
  final Color color;
  final double height;
  final int barCount;

  const TtsWaveform({
    super.key,
    required this.active,
    this.color = const Color(0xFF3B82F6),
    this.height = 18,
    this.barCount = 7,
  });

  @override
  State<TtsWaveform> createState() => _TtsWaveformState();
}

class _TtsWaveformState extends State<TtsWaveform>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;

  // Phase offset per bar so the row pulses non-uniformly.
  late final List<double> _phases;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 760),
    );
    final rand = math.Random(42);
    _phases = List.generate(widget.barCount, (_) => rand.nextDouble());
    if (widget.active) _ctrl.repeat();
  }

  @override
  void didUpdateWidget(TtsWaveform oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.active && !_ctrl.isAnimating) {
      _ctrl.repeat();
    } else if (!widget.active && _ctrl.isAnimating) {
      _ctrl.stop();
      _ctrl.value = 0.0;
    }
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    const barWidth = 3.0;
    const barSpacing = 3.0;
    return SizedBox(
      height: widget.height,
      child: AnimatedBuilder(
        animation: _ctrl,
        builder: (context, _) {
          return Row(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.center,
            children: List.generate(widget.barCount, (i) {
              final scale = widget.active
                  ? _amplitude(_ctrl.value, _phases[i])
                  : 0.18;
              return Padding(
                padding: EdgeInsets.only(
                  right: i == widget.barCount - 1 ? 0 : barSpacing,
                ),
                child: Container(
                  width: barWidth,
                  height: widget.height * scale,
                  decoration: BoxDecoration(
                    color: widget.color,
                    borderRadius: BorderRadius.circular(barWidth / 2),
                  ),
                ),
              );
            }),
          );
        },
      ),
    );
  }

  double _amplitude(double t, double phase) {
    final shifted = (t + phase) % 1.0;
    final wave = 0.5 + 0.5 * math.sin(shifted * 2 * math.pi);
    return 0.22 + 0.78 * wave;
  }
}
