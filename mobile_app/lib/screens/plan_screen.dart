import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:image_picker/image_picker.dart';
import 'package:url_launcher/url_launcher.dart';
import '../models/navigation_step.dart';
import '../services/api_service.dart';

class PlanScreen extends StatefulWidget {
  final List<String> plan;
  final int fromBuilding;
  final int fromFloor;
  final int toBuilding;
  final int toFloor;
  final String goalLabel;

  const PlanScreen({
    super.key,
    required this.plan,
    required this.fromBuilding,
    required this.fromFloor,
    required this.toBuilding,
    required this.toFloor,
    required this.goalLabel,
  });

  @override
  State<PlanScreen> createState() => _PlanScreenState();
}

class _PlanScreenState extends State<PlanScreen> {
  late List<NavigationStep> _steps;
  late FlutterTts _tts;
  final _picker = ImagePicker();
  int _currentStep = 0;
  bool _isSpeaking = false;
  bool _isVerifying = false;  // true while analyzing a verification photo
  String? _verifyFeedback;    // last verification feedback message

  // Outdoor navigation state
  // stepIndex → list of GPS direction strings (instruction + distance)
  final Map<int, List<String>> _outdoorDirections = {};
  // stepIndex → which GPS direction is currently active
  final Map<int, int> _currentOutdoorDir = {};
  // stepIndex → still loading from API
  final Map<int, bool> _outdoorLoading = {};

  static const Map<int, String> _buildingNames = {1: 'EPS', 2: 'CD', 3: 'H'};
  static const Map<int, _LatLng> _buildingCoords = {
    1: _LatLng(40.44162, -3.83368),
    2: _LatLng(40.44139, -3.83350),
    3: _LatLng(40.44189, -3.83444),
  };

  @override
  void initState() {
    super.initState();
    _steps = widget.plan.map(NavigationStep.fromRawAction).toList();
    _tts = FlutterTts();
    _tts.setCompletionHandler(() {
      if (mounted) setState(() => _isSpeaking = false);
    });
    _loadOutdoorDirections();
    _initTtsAndSpeak();
  }

  @override
  void dispose() {
    _tts.stop();
    super.dispose();
  }

  // ── TTS setup ────────────────────────────────────────────────────────────

  Future<void> _initTtsAndSpeak() async {
    await _tts.setLanguage('en-US');
    await _tts.setSpeechRate(0.42);
    await _tts.setVolume(1.0);
    await _tts.setPitch(1.0);
    await Future.delayed(const Duration(milliseconds: 1200));
    if (mounted) _speakStep(_currentStep);
  }

  Future<void> _speakText(String text) async {
    await _tts.stop();
    if (mounted) setState(() => _isSpeaking = true);
    await _tts.speak(text);
  }

  Future<void> _stopSpeaking() async {
    await _tts.stop();
    if (mounted) setState(() => _isSpeaking = false);
  }

  /// Speaks the current state of a step.
  /// For outdoor steps: reads the current GPS direction.
  /// For indoor steps: reads the step instruction.
  Future<void> _speakStep(int index) async {
    if (index >= _steps.length) return;
    final step = _steps[index];

    if (step.isOutdoor) {
      final dirs = _outdoorDirections[index];
      if (dirs == null || dirs.isEmpty) {
        // Still loading or fallback
        final to = _buildingNames[step.toBuildingId] ?? 'destination';
        await _speakText('Walking to $to. Follow the outdoor path.');
      } else {
        final dirIdx = _currentOutdoorDir[index] ?? 0;
        final total = dirs.length;
        await _speakText('Direction ${dirIdx + 1} of $total: ${dirs[dirIdx]}');
      }
    } else {
      await _speakText('Step ${index + 1}: ${step.instruction}');
    }
  }

  // ── Outdoor route loading ─────────────────────────────────────────────────

  Future<void> _loadOutdoorDirections() async {
    for (int i = 0; i < _steps.length; i++) {
      final s = _steps[i];
      if (!s.isOutdoor || s.fromBuildingId == null || s.toBuildingId == null) {
        continue;
      }

      if (mounted) setState(() => _outdoorLoading[i] = true);

      try {
        final result = await ApiService.getGpsRoute(
          fromBuilding: s.fromBuildingId!,
          toBuilding: s.toBuildingId!,
        ).timeout(const Duration(seconds: 10));

        if (result['success'] == true) {
          final rawSteps = result['steps'] as List?;
          if (rawSteps != null && rawSteps.isNotEmpty) {
            final directions = rawSteps.map((step) {
              final instruction = step['instruction'] as String? ?? '';
              final distance = step['distance'] as String? ?? '';
              return distance.isNotEmpty
                  ? '$instruction — $distance'
                  : instruction;
            }).where((s) => s.isNotEmpty).toList();

            if (mounted) {
              setState(() {
                _outdoorDirections[i] = directions;
                _currentOutdoorDir[i] = 0;
                _outdoorLoading[i] = false;
              });
              // If this is the current step, re-speak with real directions
              if (i == _currentStep) _speakStep(i);
            }
            continue;
          }
        }
      } catch (_) {}

      // Fallback: single direction with building names
      final from = _buildingNames[s.fromBuildingId] ?? 'current building';
      final to = _buildingNames[s.toBuildingId] ?? 'destination';
      if (mounted) {
        setState(() {
          _outdoorDirections[i] = ['Walk from $from to $to following the outdoor path'];
          _currentOutdoorDir[i] = 0;
          _outdoorLoading[i] = false;
        });
      }
    }
  }

  // ── Navigation logic ──────────────────────────────────────────────────────

  void _completeStep(int index) {
    setState(() {
      _steps[index].isCompleted = true;
      _verifyFeedback = null;
      if (index < _steps.length - 1) {
        _currentStep = index + 1;
        Future.delayed(
            const Duration(milliseconds: 400), () => _speakStep(_currentStep));
      }
    });
  }

  /// Advance to the next GPS direction within an outdoor step.
  /// Completes the step when all directions are done.
  void _nextOutdoorDirection(int stepIndex) {
    final dirs = _outdoorDirections[stepIndex];
    final current = _currentOutdoorDir[stepIndex] ?? 0;

    if (dirs == null || current >= dirs.length - 1) {
      _completeStep(stepIndex);
    } else {
      setState(() => _currentOutdoorDir[stepIndex] = current + 1);
      _speakStep(stepIndex);
    }
  }

  Future<void> _openGoogleMaps(int? fromId, int? toId) async {
    final from = _buildingCoords[fromId];
    final to = _buildingCoords[toId];
    if (from == null || to == null) return;
    final uri = Uri.parse(
      'https://www.google.com/maps/dir/?api=1'
      '&origin=${from.lat},${from.lng}'
      '&destination=${to.lat},${to.lng}'
      '&travelmode=walking',
    );
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }

  // ── Photo verification ────────────────────────────────────────────────────

  /// Returns the expected image_type string for a step, or null if no photo needed.
  String? _expectedImageType(NavigationStep step) {
    switch (step.type) {
      case StepType.elevatorRequest:
      case StepType.elevatorUse:
        return 'elevator';
      case StepType.stairsPrepare:
      case StepType.stairsUp:
      case StepType.stairsDown:
        return 'stairs';
      default:
        return null;
    }
  }

  /// Opens camera, sends photo to backend, and checks if it matches the expected type.
  Future<void> _verifyStepWithPhoto(int stepIndex) async {
    final expected = _expectedImageType(_steps[stepIndex]);
    if (expected == null) return;

    final XFile? picked = await _picker.pickImage(
      source: ImageSource.camera,
      imageQuality: 80,
    );
    if (picked == null || !mounted) return;

    setState(() {
      _isVerifying = true;
      _verifyFeedback = null;
    });

    try {
      final result = await ApiService.analyzeImage(File(picked.path))
          .timeout(const Duration(seconds: 60));

      if (!mounted) return;

      final imageType = result['image_type'] as String?;
      final building = result['building'];
      final floor = result['floor'];

      // ── Verification logic ──
      // image_type is inferred by the backend from the chain result:
      //   "sign"     → building + floor found (a directory sign)
      //   "non_sign" → building found but no floor (elevator button, door area)
      //   "other"    → nothing useful found
      //
      // For elevator steps: accept "non_sign" (PaliGemma reads the 'H'/'EPS' button
      //   on the elevator but finds no floor number → that IS the elevator area).
      // For stairs steps: accept "non_sign" too (similar reasoning).
      // Also accept "sign" in both cases (there might be a sign near the elevator/stairs).

      final bool verified = imageType == expected ||
          imageType == 'sign' ||
          (expected == 'elevator' && imageType == 'non_sign') ||
          (expected == 'stairs' && imageType == 'non_sign') ||
          (expected == 'elevator' && building != null && floor == null) ||
          (expected == 'stairs' && building != null && floor == null);

      if (verified) {
        // ✅ Confirmed
        String feedback;
        if (expected == 'elevator') {
          feedback = 'I can see the elevator area. You found it! Step in when the doors open.';
        } else {
          feedback = 'I can see the stairs. You found them!';
        }

        setState(() {
          _verifyFeedback = feedback;
          _isVerifying = false;
        });
        await _speakText(feedback);
        await Future.delayed(const Duration(milliseconds: 600));
        _completeStep(stepIndex);
      } else {
        // ❌ Nothing useful detected
        final feedback = 'I could not confirm the $expected in this photo. '
            'Please take another photo closer to the $expected, or press the check button to continue.';
        setState(() {
          _verifyFeedback = feedback;
          _isVerifying = false;
        });
        await _speakText(feedback);
      }
    } catch (_) {
      if (!mounted) return;
      const feedback = 'Could not analyze the photo. Please try again.';
      setState(() {
        _verifyFeedback = feedback;
        _isVerifying = false;
      });
      await _speakText(feedback);
    }
  }

  // ── Build ─────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final done = _steps.where((s) => s.isCompleted).length;
    final progress = _steps.isEmpty ? 0.0 : done / _steps.length;
    final allDone = done == _steps.length;

    return Scaffold(
      backgroundColor: const Color(0xFF020817),
      appBar: AppBar(
        backgroundColor: const Color(0xFF020817),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_rounded, color: Colors.white),
          onPressed: () => Navigator.pop(context),
        ),
        title: Column(
          children: [
            const Text('Navigation Plan',
                style: TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w600,
                    fontSize: 16)),
            Text(
              'To: ${widget.goalLabel}',
              style: const TextStyle(color: Color(0xFF64748B), fontSize: 11),
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: Icon(
              _isSpeaking ? Icons.volume_off_rounded : Icons.volume_up_rounded,
              color: const Color(0xFF3B82F6),
            ),
            onPressed: _isSpeaking
                ? _stopSpeaking
                : () => _speakStep(_currentStep),
          ),
        ],
      ),
      body: Column(
        children: [
          // Progress bar
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
            child: Column(
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      '$done of ${_steps.length} steps completed',
                      style: const TextStyle(
                          color: Color(0xFF94A3B8), fontSize: 13),
                    ),
                    Text(
                      '${(progress * 100).round()}%',
                      style: const TextStyle(
                          color: Color(0xFF3B82F6),
                          fontWeight: FontWeight.w600,
                          fontSize: 13),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    value: progress,
                    backgroundColor: const Color(0xFF1E293B),
                    valueColor: const AlwaysStoppedAnimation<Color>(
                        Color(0xFF3B82F6)),
                    minHeight: 6,
                  ),
                ),
              ],
            ),
          ),

          Expanded(
            child: allDone
                ? _buildArrivalScreen()
                : ListView.builder(
                    padding: const EdgeInsets.symmetric(horizontal: 20),
                    itemCount: _steps.length,
                    itemBuilder: (_, i) => _buildStepCard(i),
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildStepCard(int i) {
    final step = _steps[i];
    final isCurrent = i == _currentStep && !step.isCompleted;
    final isDone = step.isCompleted;

    // Outdoor current step gets a special full-screen card
    if (step.isOutdoor && isCurrent) {
      return _buildOutdoorCard(i, step);
    }

    // Standard indoor step card
    return AnimatedContainer(
      duration: const Duration(milliseconds: 300),
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: isDone
            ? const Color(0xFF051410)
            : isCurrent
                ? const Color(0xFF0B1629)
                : const Color(0xFF0F172A),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: isDone
              ? const Color(0xFF10B981).withOpacity(0.3)
              : isCurrent
                  ? step.accentColor.withOpacity(0.5)
                  : const Color(0xFF1E293B),
          width: isCurrent ? 1.5 : 1,
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: 42,
                  height: 42,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: isDone
                        ? const Color(0xFF10B981).withOpacity(0.15)
                        : isCurrent
                            ? step.accentColor.withOpacity(0.15)
                            : const Color(0xFF1E293B),
                  ),
                  child: Icon(
                    isDone ? Icons.check_rounded : step.icon,
                    size: 20,
                    color: isDone
                        ? const Color(0xFF10B981)
                        : isCurrent
                            ? step.accentColor
                            : const Color(0xFF475569),
                  ),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Text(
                            'Step ${i + 1}',
                            style: TextStyle(
                              color: isDone
                                  ? const Color(0xFF10B981).withOpacity(0.7)
                                  : const Color(0xFF64748B),
                              fontSize: 11,
                              fontWeight: FontWeight.w600,
                              letterSpacing: 0.5,
                            ),
                          ),
                          if (isCurrent) ...[
                            const SizedBox(width: 8),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 7, vertical: 2),
                              decoration: BoxDecoration(
                                color: step.accentColor.withOpacity(0.15),
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(
                                'NOW',
                                style: TextStyle(
                                    color: step.accentColor,
                                    fontSize: 9,
                                    fontWeight: FontWeight.bold,
                                    letterSpacing: 0.8),
                              ),
                            ),
                          ],
                        ],
                      ),
                      const SizedBox(height: 4),
                      Text(
                        step.instruction,
                        style: TextStyle(
                          color: isDone
                              ? const Color(0xFF10B981).withOpacity(0.6)
                              : Colors.white,
                          fontSize: 14,
                          height: 1.45,
                          decoration:
                              isDone ? TextDecoration.lineThrough : null,
                          decorationColor: const Color(0xFF10B981),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            if (isCurrent) ...[
              const SizedBox(height: 14),
              // Verification feedback banner
              if (_verifyFeedback != null) ...[
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  margin: const EdgeInsets.only(bottom: 10),
                  decoration: BoxDecoration(
                    color: const Color(0xFF0F172A),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: const Color(0xFF1E293B)),
                  ),
                  child: Text(
                    _verifyFeedback!,
                    style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 13),
                  ),
                ),
              ],
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: () => _speakStep(i),
                      icon: const Icon(Icons.volume_up_rounded, size: 16),
                      label: const Text('Repeat'),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: const Color(0xFF3B82F6),
                        side: const BorderSide(color: Color(0xFF1E293B)),
                        padding: const EdgeInsets.symmetric(vertical: 12),
                        shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(10)),
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  // Camera verification button for elevator/stairs
                  if (_expectedImageType(step) != null) ...[
                    Expanded(
                      flex: 2,
                      child: _isVerifying
                          ? const Center(
                              child: SizedBox(
                                width: 24,
                                height: 24,
                                child: CircularProgressIndicator(
                                    color: Color(0xFF3B82F6), strokeWidth: 2),
                              ),
                            )
                          : ElevatedButton.icon(
                              onPressed: () => _verifyStepWithPhoto(i),
                              icon: const Icon(Icons.camera_alt_rounded, size: 16),
                              label: Text(
                                'Take Photo (${_expectedImageType(step)})',
                                style: const TextStyle(fontSize: 13),
                              ),
                              style: ElevatedButton.styleFrom(
                                backgroundColor: step.accentColor,
                                foregroundColor: Colors.white,
                                padding: const EdgeInsets.symmetric(vertical: 12),
                                elevation: 0,
                                shape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(10)),
                              ),
                            ),
                    ),
                    const SizedBox(width: 6),
                    // Manual done button (fallback)
                    SizedBox(
                      width: 48,
                      height: 46,
                      child: OutlinedButton(
                        onPressed: () => _completeStep(i),
                        style: OutlinedButton.styleFrom(
                          foregroundColor: const Color(0xFF64748B),
                          side: const BorderSide(color: Color(0xFF1E293B)),
                          padding: EdgeInsets.zero,
                          shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(10)),
                        ),
                        child: const Icon(Icons.check_rounded, size: 18),
                      ),
                    ),
                  ] else ...[
                    // Standard done button for non-verification steps
                    Expanded(
                      flex: 2,
                      child: ElevatedButton.icon(
                        onPressed: () => _completeStep(i),
                        icon: Icon(
                          i == _steps.length - 1
                              ? Icons.flag_rounded
                              : Icons.check_rounded,
                          size: 16,
                        ),
                        label: Text(
                            i == _steps.length - 1 ? 'Arrived!' : 'Done →'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: step.accentColor,
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(vertical: 12),
                          elevation: 0,
                          shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(10)),
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  /// Full outdoor navigation card — voice-driven, no map.
  Widget _buildOutdoorCard(int i, NavigationStep step) {
    final isLoading = _outdoorLoading[i] == true;
    final dirs = _outdoorDirections[i] ?? [];
    final dirIdx = _currentOutdoorDir[i] ?? 0;
    final total = dirs.length;
    final isLastDir = dirIdx >= total - 1;
    final currentDirText =
        dirs.isNotEmpty ? dirs[dirIdx] : 'Preparing route...';

    final fromName = _buildingNames[step.fromBuildingId] ?? '?';
    final toName = _buildingNames[step.toBuildingId] ?? '?';

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: const Color(0xFF0C1525),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: const Color(0xFFF59E0B).withOpacity(0.5),
          width: 1.5,
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: const Color(0xFFF59E0B).withOpacity(0.15),
                  ),
                  child: const Icon(Icons.directions_walk_rounded,
                      color: Color(0xFFF59E0B), size: 22),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          const Text('OUTDOOR WALK',
                              style: TextStyle(
                                  color: Color(0xFFF59E0B),
                                  fontSize: 10,
                                  fontWeight: FontWeight.bold,
                                  letterSpacing: 1)),
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 7, vertical: 2),
                            decoration: BoxDecoration(
                              color: const Color(0xFFF59E0B).withOpacity(0.15),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: const Text('NOW',
                                style: TextStyle(
                                    color: Color(0xFFF59E0B),
                                    fontSize: 9,
                                    fontWeight: FontWeight.bold,
                                    letterSpacing: 0.8)),
                          ),
                        ],
                      ),
                      const SizedBox(height: 2),
                      Text(
                        '$fromName  →  $toName',
                        style: const TextStyle(
                            color: Colors.white,
                            fontSize: 15,
                            fontWeight: FontWeight.w600),
                      ),
                    ],
                  ),
                ),
              ],
            ),

            const SizedBox(height: 20),
            const Divider(color: Color(0xFF1E293B), height: 1),
            const SizedBox(height: 20),

            // Direction counter
            if (!isLoading && dirs.isNotEmpty) ...[
              Text(
                'Direction ${dirIdx + 1} of $total',
                style: const TextStyle(
                    color: Color(0xFF64748B),
                    fontSize: 12,
                    fontWeight: FontWeight.w500,
                    letterSpacing: 0.5),
              ),
              const SizedBox(height: 10),
            ],

            // Current direction text — large and prominent
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                color: const Color(0xFF0F172A),
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: const Color(0xFF1E293B)),
              ),
              child: isLoading
                  ? const Row(
                      children: [
                        SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(
                              color: Color(0xFFF59E0B), strokeWidth: 2),
                        ),
                        SizedBox(width: 12),
                        Text('Fetching route from Google Maps...',
                            style: TextStyle(
                                color: Color(0xFF64748B), fontSize: 14)),
                      ],
                    )
                  : Text(
                      currentDirText,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 18,
                        fontWeight: FontWeight.w600,
                        height: 1.4,
                      ),
                    ),
            ),

            const SizedBox(height: 20),

            // Action buttons
            if (!isLoading) ...[
              // Repeat button
              SizedBox(
                width: double.infinity,
                height: 52,
                child: OutlinedButton.icon(
                  onPressed: () => _speakStep(i),
                  icon: const Icon(Icons.volume_up_rounded, size: 18),
                  label: const Text('Repeat direction',
                      style: TextStyle(fontSize: 15)),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: const Color(0xFFF59E0B),
                    side: const BorderSide(color: Color(0xFFF59E0B), width: 1),
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12)),
                  ),
                ),
              ),
              const SizedBox(height: 10),

              // Next / Arrived button
              SizedBox(
                width: double.infinity,
                height: 60,
                child: ElevatedButton.icon(
                  onPressed: () => _nextOutdoorDirection(i),
                  icon: Icon(
                    isLastDir
                        ? Icons.check_circle_rounded
                        : Icons.arrow_forward_rounded,
                    size: 20,
                  ),
                  label: Text(
                    isLastDir
                        ? 'I\'ve arrived at $toName'
                        : 'Next direction',
                    style: const TextStyle(
                        fontSize: 16, fontWeight: FontWeight.w700),
                  ),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: isLastDir
                        ? const Color(0xFF10B981)
                        : const Color(0xFFF59E0B),
                    foregroundColor: Colors.white,
                    elevation: 0,
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(14)),
                  ),
                ),
              ),

              const SizedBox(height: 12),

              // Open in Google Maps (secondary option)
              Center(
                child: TextButton.icon(
                  onPressed: () =>
                      _openGoogleMaps(step.fromBuildingId, step.toBuildingId),
                  icon: const Icon(Icons.open_in_new_rounded, size: 14),
                  label: const Text('Open full map in Google Maps'),
                  style: TextButton.styleFrom(
                    foregroundColor: const Color(0xFF475569),
                    textStyle: const TextStyle(fontSize: 12),
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildArrivalScreen() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 106,
              height: 106,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: const Color(0xFF10B981).withOpacity(0.12),
                border: Border.all(color: const Color(0xFF10B981), width: 2),
              ),
              child: const Icon(Icons.check_rounded,
                  size: 52, color: Color(0xFF10B981)),
            ),
            const SizedBox(height: 28),
            const Text(
              'You have arrived!',
              style: TextStyle(
                  color: Colors.white,
                  fontSize: 28,
                  fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Text(
              widget.goalLabel,
              style: const TextStyle(color: Color(0xFF10B981), fontSize: 16),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 40),
            SizedBox(
              width: double.infinity,
              height: 56,
              child: ElevatedButton(
                onPressed: () =>
                    Navigator.of(context).popUntil((r) => r.isFirst),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF3B82F6),
                  foregroundColor: Colors.white,
                  elevation: 0,
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14)),
                ),
                child: const Text('Start New Navigation',
                    style:
                        TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Simple coordinate holder (avoids importing google_maps_flutter just for coordinates).
class _LatLng {
  final double lat;
  final double lng;
  const _LatLng(this.lat, this.lng);
}
