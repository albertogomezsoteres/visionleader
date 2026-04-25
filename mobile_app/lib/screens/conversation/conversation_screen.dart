import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_sound/flutter_sound.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:image_picker/image_picker.dart';
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';

import '../../core/building_locations.dart';
import '../../core/file_utils.dart';
import '../../services/api_service.dart';
import '../../services/image_processing.dart';
import 'widgets/action_area.dart';
import 'widgets/message_bubble.dart';
import 'widgets/nav_quick_actions.dart';
import 'widgets/outdoor_route_view.dart';
import 'widgets/processing_overlay.dart';
import 'widgets/status_row.dart';

/// The single interactive screen that drives the entire navigation flow:
/// welcome → location → destination → plan → step-by-step guidance.
class ConversationScreen extends StatefulWidget {
  final String sessionId;

  /// When set, used as the first conversation turn instead of the default
  /// welcome (same payload shape as after in-app photo analysis).
  final Map<String, dynamic>? seedImageAnalysis;

  const ConversationScreen({
    super.key,
    required this.sessionId,
    this.seedImageAnalysis,
  });

  @override
  State<ConversationScreen> createState() => _ConversationScreenState();
}

class _ConversationScreenState extends State<ConversationScreen>
    with SingleTickerProviderStateMixin {
  // Core services
  final FlutterTts _tts = FlutterTts();
  final FlutterSoundRecorder _recorder = FlutterSoundRecorder();

  // UI state
  String _ttsMessage = '';
  String _nextInput = 'voice';
  String _currentAction = '';
  bool _isProcessing = false;
  String _processingMsg = '';
  bool _isRecording = false;
  String _transcription = '';

  // Location / navigation progress
  String? _knownBuilding;
  int? _knownFloor;
  String? _knownLocationId;
  String? _goalBuilding;
  int? _goalFloor;
  String? _goalLocationId;
  int _currentStep = 0;
  int _totalSteps = 0;

  // Recording helpers
  DateTime? _recordingStartedAt;
  String? _currentRecordingPath;

  // Pulse animation for the mic button
  late AnimationController _pulseCtrl;
  late Animation<double> _pulseAnim;


  // Lifecycle

  @override
  void initState() {
    super.initState();
    _pulseCtrl = AnimationController(
      duration: const Duration(milliseconds: 900),
      vsync: this,
    );
    _pulseAnim = Tween<double>(begin: 1.0, end: 1.18)
        .animate(CurvedAnimation(parent: _pulseCtrl, curve: Curves.easeInOut));
    _initTtsAndRecorder();
  }

  @override
  void dispose() {
    _tts.stop();
    _recorder.closeRecorder().catchError((_) {});
    _pulseCtrl.dispose();
    super.dispose();
  }

  Future<void> _initTtsAndRecorder() async {
    await _tts.setLanguage('en-US');
    await _tts.setSpeechRate(0.42);
    await _tts.setVolume(1.0);
    await _tts.setPitch(1.0);

    final micStatus = await Permission.microphone.request();
    if (!micStatus.isGranted) {
      _setMessage(
        'Microphone permission is required to use voice input. Please enable it in app settings.',
        'voice', 'error',
      );
      return;
    }
    await _recorder.openRecorder();
    await _recorder.setSubscriptionDuration(const Duration(milliseconds: 100));

    if (mounted) {
      if (widget.seedImageAnalysis != null) {
        await _sendPhoto(widget.seedImageAnalysis!);
      } else {
        _fetchWelcome();
      }
    }
  }

  // Conversation turns - each method talks to ApiService and updates state

  Future<void> _fetchWelcome() async {
    setState(() { _isProcessing = true; _processingMsg = 'Starting assistant...'; });
    try {
      final result = await ApiService.sendConversationTurn(sessionId: widget.sessionId);
      if (!mounted) return;
      _handleResult(result);
    } catch (_) {
      if (!mounted) return;
      _setMessage('Could not connect to the server. Please make sure the backend is running.', 'voice', 'error');
    } finally {
      if (mounted) setState(() => _isProcessing = false);
    }
  }

  Future<void> _sendVoice(String text) async {
    setState(() { _isProcessing = true; _processingMsg = 'Processing...'; });
    try {
      final result = await ApiService.sendConversationTurn(sessionId: widget.sessionId, userMessage: text);
      if (!mounted) return;
      _handleResult(result);
    } catch (_) {
      if (!mounted) return;
      _setMessage('Something went wrong. Please try again.', _nextInput, _currentAction);
    } finally {
      if (mounted) setState(() => _isProcessing = false);
    }
  }

  Future<void> _sendPhoto(Map<String, dynamic> analysis) async {
    setState(() { _isProcessing = true; _processingMsg = 'Analyzing photo...'; });
    try {
      final result = await ApiService.sendConversationTurn(sessionId: widget.sessionId, imageAnalysis: analysis);
      if (!mounted) return;
      _handleResult(result);
    } catch (_) {
      if (!mounted) return;
      _setMessage('Could not process the image. Try again.', 'photo', _currentAction);
    } finally {
      if (mounted) setState(() => _isProcessing = false);
    }
  }

  Future<void> _sendConfirmation(bool confirmed) async => _sendVoice(confirmed ? 'yes' : 'no');
  Future<void> _goNextStep() async => _sendVoice('done');

  // Result handling

  void _handleResult(Map<String, dynamic> result) {
    final tts = (result['tts_message'] as String?) ?? (result['response'] as String?) ?? '';
    final nextInput = (result['next_input'] as String?) ?? 'voice';
    final action = (result['action'] as String?) ?? '';
    _updateLocationChips(result);

    final ctx = result['context'] as Map<String, dynamic>?;
    if (ctx != null) {
      final steps = ctx['plan_steps'] as List?;
      final stepIdx = ctx['current_step_idx'] as int?;
      if (steps != null && steps.isNotEmpty) {
        setState(() { _totalSteps = steps.length; _currentStep = (stepIdx ?? 0) + 1; });
      } else {
        setState(() { _totalSteps = 0; _currentStep = 0; });
      }
    }

    final gpsRoute = result['gps_route'] as Map<String, dynamic>?;
    if (gpsRoute != null) {
      final fromBld = gpsRoute['from_building'] as int?;
      final toBld = gpsRoute['to_building'] as int?;
      if (fromBld != null) {
        _pendingGpsOrigin = fromBld;
      }
      if (toBld != null) {
        _pendingGpsDestination = toBld;
      }
    } else {
      _pendingGpsOrigin = null;
      _pendingGpsDestination = null;
    }

    _setMessage(tts, nextInput, action);
    _speakTts(tts);

    if (action == 'navigation_step_outdoor' && _pendingGpsDestination != null) {
      final step = _currentStep;
      if (_lastAutoOpenedOutdoorStep != step) {
        _lastAutoOpenedOutdoorStep = step;
        // Open the map right after TTS likely finishes this short outdoor step.
        final textLen = tts.trim().length;
        final delayMs = (textLen * 55).clamp(1800, 6500);
        Future.delayed(Duration(milliseconds: delayMs), () {
          if (mounted) _openOutdoorRouteInApp();
        });
      }
    }
  }

  int? _pendingGpsOrigin;
  int? _pendingGpsDestination;
  int? _lastAutoOpenedOutdoorStep;

  Future<void> _openOutdoorRouteInApp() async {
    final from = _pendingGpsOrigin;
    final dest = _pendingGpsDestination;
    if (from == null || dest == null) return;
    final fromCoords = BuildingLocations.gps[from];
    final toCoords = BuildingLocations.gps[dest];
    if (fromCoords == null || toCoords == null) return;
    setState(() {
      _isProcessing = true;
      _processingMsg = 'Loading outdoor route...';
    });
    final route = await ApiService.getGpsRoute(
      fromBuilding: from,
      toBuilding: dest,
    );
    if (!mounted) return;
    setState(() => _isProcessing = false);

    final rawSteps = (route['steps'] as List?) ?? const [];
    final steps = rawSteps.map<Map<String, dynamic>>((s) {
      final m = s as Map<String, dynamic>;
      return {
        'instruction': (m['instruction'] as String?) ?? '',
        'distance': (m['distance'] as String?) ?? '',
        'startLocation': m['startLocation'],
        'endLocation': m['endLocation'],
      };
    }).toList();

    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => OutdoorRouteView(
          originLat: fromCoords['lat']!,
          originLng: fromCoords['lng']!,
          destinationLat: toCoords['lat']!,
          destinationLng: toCoords['lng']!,
          polylineEncoded: (route['polyline'] as String?) ?? '',
          destinationLabel: BuildingLocations.nameOf(dest),
          steps: steps,
          onArrived: _goNextStep,
        ),
      ),
    );
  }

  void _updateLocationChips(Map<String, dynamic> result) {
    final partial = result['location_partial'] as Map<String, dynamic>?;
    final ctx = result['context'] as Map<String, dynamic>?;
    final loc = partial ?? (ctx?['current_location'] as Map<String, dynamic>?);
    final goal = ctx?['goal'] as Map<String, dynamic>?;
    if (loc != null) {
      final building = loc['building'] as int?;
      final floor = loc['floor'] as int?;
      final locationId = loc['location_id'] as String?;
      setState(() {
        if (building != null) _knownBuilding = BuildingLocations.nameOf(building);
        if (floor != null) _knownFloor = floor;
        if (locationId != null && locationId.isNotEmpty) _knownLocationId = locationId;
      });
    }
    if (goal != null) {
      final building = goal['building'] as int?;
      final floor = goal['floor'] as int?;
      final locationId = goal['location_id'] as String?;
      setState(() {
        if (building != null) _goalBuilding = BuildingLocations.nameOf(building);
        if (floor != null) _goalFloor = floor;
        if (locationId != null && locationId.isNotEmpty) _goalLocationId = locationId;
      });
    } else {
      setState(() {
        _goalBuilding = null;
        _goalFloor = null;
        _goalLocationId = null;
      });
    }
  }

  void _setMessage(String message, String nextInput, String action) {
    setState(() { _ttsMessage = message; _nextInput = nextInput; _currentAction = action; _transcription = ''; });
  }

  Future<void> _speakTts(String text) async {
    if (text.isEmpty) return;
    await _tts.stop();
    await Future.delayed(const Duration(milliseconds: 150));
    if (mounted) await _tts.speak(text);
  }

  // Photo actions

  Future<void> _pickPhoto(ImageSource source) async {
    XFile? picked;
    try {
      picked = await ImagePicker().pickImage(
        source: source,
        imageQuality: 92,
        requestFullMetadata: false,
      );
    } catch (e) {
      _setMessage(
        'Could not open the ${source == ImageSource.gallery ? 'gallery' : 'camera'}: $e',
        _nextInput,
        _currentAction,
      );
      return;
    }
    if (picked == null) return;

    setState(() { _isProcessing = true; _processingMsg = 'Analyzing image...'; });
    try {
      final cropped = await ImageProcessing.cropToSquare(File(picked.path));
      final analysis = await ApiService.analyzeImage(cropped);
      if (!mounted) return;
      await _sendPhoto(analysis);
    } catch (_) {
      if (!mounted) return;
      setState(() => _isProcessing = false);
      _setMessage('Could not analyze the image. Please try again.', 'photo', _currentAction);
    }
  }

  // Voice recording

  Future<void> _startRecording() async {
    await _tts.stop();
    final micStatus = await Permission.microphone.status;
    if (!micStatus.isGranted) {
      final req = await Permission.microphone.request();
      if (!req.isGranted) {
        _setMessage('Microphone permission is required to record audio.', _nextInput, _currentAction);
        return;
      }
    }
    final dir = await getTemporaryDirectory();
    final ts = DateTime.now().millisecondsSinceEpoch;
    final filePath = '${dir.path}/conv_audio_$ts.wav';
    _currentRecordingPath = filePath;
    _recordingStartedAt = DateTime.now();
    setState(() => _isRecording = true);
    _pulseCtrl.repeat(reverse: true);
    await _recorder.startRecorder(toFile: filePath, codec: Codec.pcm16WAV, sampleRate: 16000, numChannels: 1);
  }

  Future<void> _stopRecording() async {
    if (!_isRecording) return;
    final path = await _recorder.stopRecorder();
    _pulseCtrl.stop();
    _pulseCtrl.reset();
    setState(() { _isRecording = false; _isProcessing = true; _processingMsg = 'Transcribing your voice...'; });

    final elapsedMs = _recordingStartedAt == null ? 0 : DateTime.now().difference(_recordingStartedAt!).inMilliseconds;
    final finalPath = path ?? _currentRecordingPath;
    final tempFile = finalPath != null ? File(finalPath) : null;

    if (elapsedMs < 1800) {
      await safeDelete(tempFile);
      setState(() => _isProcessing = false);
      _setMessage(
        'Please hold the microphone longer (at least 2 seconds) and speak clearly.',
        _nextInput,
        _currentAction,
      );
      return;
    }
    if (tempFile == null) {
      setState(() => _isProcessing = false);
      _setMessage("I couldn't capture your audio. Please try again.", _nextInput, _currentAction);
      return;
    }
    if (!await tempFile.exists()) {
      setState(() => _isProcessing = false);
      _setMessage("I couldn't save the recorded audio. Please try again.", _nextInput, _currentAction);
      return;
    }
    if (await tempFile.length() < 20000) {
      await safeDelete(tempFile);
      setState(() => _isProcessing = false);
      _setMessage(
        "I couldn't hear your voice clearly. Speak louder, hold the button for 2-3 seconds, and keep the phone close to your mouth.",
        _nextInput,
        _currentAction,
      );
      return;
    }
    await _transcribeAndSend(tempFile);
  }

  Future<void> _transcribeAndSend(File audio) async {
    try {
      final result = await ApiService.transcribeAudio(audio);
      final success = result['success'] as bool? ?? false;
      final text = (result['text'] as String?) ?? '';
      if (success && text.isNotEmpty) {
        setState(() { _transcription = text; _processingMsg = 'Processing...'; });
        await _sendVoice(text);
      } else {
        if (!mounted) return;
        setState(() => _isProcessing = false);
        final err = (result['error'] as String?) ?? '';
        _setMessage(
          err.isNotEmpty
              ? "I couldn't hear you clearly. Please speak directly into the mic and try again."
              : "I couldn't hear anything clearly. Please try again.",
          _nextInput, _currentAction,
        );
      }
    } catch (_) {
      if (!mounted) return;
      setState(() => _isProcessing = false);
      _setMessage('Transcription failed. Please try again.', _nextInput, _currentAction);
    } finally {
      await safeDelete(audio);
    }
  }

  // Build - delegates to extracted widgets

  bool get _isNavigating =>
      _currentAction == 'navigation_step' ||
      _currentAction == 'navigation_step_outdoor' ||
      _currentAction == 'awaiting_step_done' ||
      _currentAction == 'step_after_photo_confirm' ||
      _currentAction == 'waiting_step_photo' ||
      _currentAction == 'retry_step_photo' ||
      _currentAction == 'repeat';

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
        title: const Text('Navigation Assistant',
            style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
      ),
      body: Stack(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
            child: Column(
              children: [
                const SizedBox(height: 8),
                StatusRow(
                  initialBuilding: _knownBuilding,
                  initialFloor: _knownFloor,
                  initialLocationId: _knownLocationId,
                  goalBuilding: _goalBuilding,
                  goalFloor: _goalFloor,
                  goalLocationId: _goalLocationId,
                ),
                const SizedBox(height: 16),
                Expanded(
                  child: SingleChildScrollView(
                    child: Column(
                      children: [
                        MessageBubble(
                          message: _ttsMessage,
                          currentAction: _currentAction,
                          currentStep: _isNavigating ? _currentStep : null,
                          totalSteps: _isNavigating ? _totalSteps : null,
                          onTapReplay: () => _speakTts(_ttsMessage),
                        ),
                        const SizedBox(height: 14),
                        if (_transcription.isNotEmpty)
                          Padding(
                            padding: const EdgeInsets.only(bottom: 10),
                            child: Row(
                              children: [
                                const Icon(Icons.record_voice_over_rounded, size: 14, color: Color(0xFF3B82F6)),
                                const SizedBox(width: 6),
                                Expanded(
                                  child: Text(
                                    '"$_transcription"',
                                    style: const TextStyle(color: Color(0xFF64748B), fontSize: 13, fontStyle: FontStyle.italic),
                                    maxLines: 2, overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        if (_isNavigating)
                          NavQuickActions(
                            onNext: _goNextStep,
                            onRepeat: () => _sendVoice('repeat'),
                            onLost: () => _sendVoice("I'm lost"),
                            onCancel: () => _sendVoice('cancel'),
                          ),
                        ActionArea(
                          currentAction: _currentAction,
                          nextInput: _nextInput,
                          isRecording: _isRecording,
                          pulseAnimation: _pulseAnim,
                          pendingGpsDestinationId: _pendingGpsDestination,
                          pendingGpsDestinationName: BuildingLocations.nameOf(_pendingGpsDestination),
                          onStartRecording: _startRecording,
                          onStopRecording: _stopRecording,
                          onPickPhoto: _pickPhoto,
                          onConfirmYes: () => _sendConfirmation(true),
                          onConfirmNo: () => _sendConfirmation(false),
                          onArrivedOutdoor: _goNextStep,
                          onReopenOutdoorMap: _openOutdoorRouteInApp,
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
          if (_isProcessing) ProcessingOverlay(message: _processingMsg),
        ],
      ),
    );
  }
}
