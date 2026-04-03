import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_sound/flutter_sound.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:image_picker/image_picker.dart';
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';
import '../services/api_service.dart';

/// ConversationScreen – the single interactive screen that drives the entire
/// navigation flow: welcome → location → destination → plan → step-by-step.
class ConversationScreen extends StatefulWidget {
  final String sessionId;

  /// When set (e.g. from [CameraScreen]), sent as the first conversation turn
  /// instead of the default welcome, using the same payload as in-app photo pick.
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
  final FlutterTts _tts = FlutterTts();
  final FlutterSoundRecorder _recorder = FlutterSoundRecorder();

  String _ttsMessage = '';
  String _nextInput = 'voice';
  String _currentAction = '';
  bool _isProcessing = false;
  String _processingMsg = '';
  bool _isRecording = false;
  String _transcription = '';

  String? _knownBuilding;
  int? _knownFloor;
  String? _destination;
  int _currentStep = 0;
  int _totalSteps = 0;
  DateTime? _recordingStartedAt;
  String? _currentRecordingPath;

  late AnimationController _pulseCtrl;
  late Animation<double> _pulseAnim;

  static const Map<int, String> _buildingNames = {
    1: 'G',
    2: 'CD',
    3: 'H',
  };

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
    _recorder.closeRecorder();
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
        'voice',
        'error',
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

  /// Sends the very first (empty) turn to trigger the WELCOME greeting.
  Future<void> _fetchWelcome() async {
    setState(() {
      _isProcessing = true;
      _processingMsg = 'Starting assistant...';
    });
    try {
      final result = await ApiService.sendConversationTurn(
        sessionId: widget.sessionId,
      );
      if (!mounted) return;
      _handleResult(result);
    } catch (e) {
      if (!mounted) return;
      _setMessage(
        'Could not connect to the server. Please make sure the backend is running.',
        'voice',
        'error',
      );
    } finally {
      if (mounted) setState(() => _isProcessing = false);
    }
  }

  // ── Conversation turns ──────────────────────────────────────────────────

  Future<void> _sendVoice(String text) async {
    setState(() {
      _isProcessing = true;
      _processingMsg = 'Processing...';
    });
    try {
      final result = await ApiService.sendConversationTurn(
        sessionId: widget.sessionId,
        userMessage: text,
      );
      if (!mounted) return;
      _handleResult(result);
    } catch (e) {
      if (!mounted) return;
      _setMessage('Something went wrong. Please try again.', _nextInput, _currentAction);
    } finally {
      if (mounted) setState(() => _isProcessing = false);
    }
  }

  Future<void> _sendPhoto(Map<String, dynamic> analysis) async {
    setState(() {
      _isProcessing = true;
      _processingMsg = 'Analyzing photo...';
    });
    try {
      final result = await ApiService.sendConversationTurn(
        sessionId: widget.sessionId,
        imageAnalysis: analysis,
      );
      if (!mounted) return;
      _handleResult(result);
    } catch (e) {
      if (!mounted) return;
      _setMessage('Could not process the image. Try again.', 'photo', _currentAction);
    } finally {
      if (mounted) setState(() => _isProcessing = false);
    }
  }

  Future<void> _sendConfirmation(bool confirmed) async {
    await _sendVoice(confirmed ? 'yes' : 'no');
  }

  void _handleResult(Map<String, dynamic> result) {
    final tts = (result['tts_message'] as String?) ??
        (result['response'] as String?) ??
        '';
    final nextInput = (result['next_input'] as String?) ?? 'voice';
    final action = (result['action'] as String?) ?? '';

    _updateChips(result);

    // Track navigation progress
    final ctx = result['context'] as Map<String, dynamic>?;
    if (ctx != null) {
      final steps = ctx['plan_steps'] as List?;
      final stepIdx = ctx['current_step_idx'] as int?;
      if (steps != null && steps.isNotEmpty) {
        setState(() {
          _totalSteps = steps.length;
          _currentStep = (stepIdx ?? 0) + 1;
        });
      }
      final goal = ctx['goal'] as Map<String, dynamic>?;
      if (goal != null) {
        final label = goal['label'] as String?;
        if (label != null) {
          setState(() => _destination = label);
        }
      }
    }

    _setMessage(tts, nextInput, action);
    _speakTts(tts);
  }

  void _updateChips(Map<String, dynamic> result) {
    final partial = result['location_partial'] as Map<String, dynamic>?;
    final ctx = result['context'] as Map<String, dynamic>?;
    final loc = partial ??
        (ctx != null ? ctx['current_location'] as Map<String, dynamic>? : null);

    if (loc != null) {
      final building = loc['building'] as int?;
      final floor = loc['floor'] as int?;
      setState(() {
        if (building != null) {
          _knownBuilding = _buildingNames[building] ?? 'B$building';
        }
        if (floor != null) _knownFloor = floor;
      });
    }
  }

  void _setMessage(String message, String nextInput, String action) {
    setState(() {
      _ttsMessage = message;
      _nextInput = nextInput;
      _currentAction = action;
      _transcription = '';
    });
  }

  Future<void> _speakTts(String text) async {
    if (text.isEmpty) return;
    await _tts.stop();
    await Future.delayed(const Duration(milliseconds: 150));
    if (mounted) await _tts.speak(text);
  }

  // ── Photo actions ──────────────────────────────────────────────────────

  Future<void> _pickPhoto(ImageSource source) async {
    final picker = ImagePicker();
    final picked = await picker.pickImage(
      source: source,
      imageQuality: 85,
      requestFullMetadata: false,
    );
    if (picked == null) return;

    setState(() {
      _isProcessing = true;
      _processingMsg = 'Analyzing image...';
    });
    try {
      final analysisResult = await ApiService.analyzeImage(File(picked.path));
      if (!mounted) return;
      await _sendPhoto(analysisResult);
    } catch (e) {
      if (!mounted) return;
      setState(() => _isProcessing = false);
      _setMessage('Could not analyze the image. Please try again.', 'photo', _currentAction);
    }
  }

  void _showPhotoOptions() {
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
                  _pickPhoto(ImageSource.camera);
                },
              ),
              ListTile(
                leading: const Icon(Icons.photo_library_outlined,
                    color: Color(0xFF3B82F6)),
                title: const Text('Choose from Gallery',
                    style: TextStyle(color: Colors.white)),
                onTap: () {
                  Navigator.pop(ctx);
                  _pickPhoto(ImageSource.gallery);
                },
              ),
            ],
          ),
        ),
      ),
    );
  }

  // ── Voice recording ────────────────────────────────────────────────────

  Future<void> _startRecording() async {
    await _tts.stop();
    final micStatus = await Permission.microphone.status;
    if (!micStatus.isGranted) {
      final requested = await Permission.microphone.request();
      if (!requested.isGranted) {
        _setMessage(
          'Microphone permission is required to record audio.',
          _nextInput,
          _currentAction,
        );
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
    await _recorder.startRecorder(
      toFile: filePath,
      codec: Codec.pcm16WAV,
      sampleRate: 16000,
      numChannels: 1,
    );
  }

  Future<void> _stopRecording() async {
    if (!_isRecording) return;
    final path = await _recorder.stopRecorder();
    _pulseCtrl.stop();
    _pulseCtrl.reset();
    setState(() {
      _isRecording = false;
      _isProcessing = true;
      _processingMsg = 'Transcribing your voice...';
    });
    final elapsedMs = _recordingStartedAt == null
        ? 0
        : DateTime.now().difference(_recordingStartedAt!).inMilliseconds;
    final finalPath = path ?? _currentRecordingPath;
    if (elapsedMs < 800) {
      setState(() => _isProcessing = false);
      _setMessage(
        "Please hold the microphone a bit longer (at least 1 second).",
        _nextInput,
        _currentAction,
      );
      return;
    }
    if (finalPath != null) {
      final audioFile = File(finalPath);
      if (!await audioFile.exists()) {
        setState(() => _isProcessing = false);
        _setMessage(
          "I couldn't save the recorded audio. Please try again.",
          _nextInput,
          _currentAction,
        );
        return;
      }
      final audioBytes = await audioFile.length();
      if (audioBytes < 12000) {
        setState(() => _isProcessing = false);
        _setMessage(
          "I couldn't hear your voice clearly. Please speak louder and keep holding the button.",
          _nextInput,
          _currentAction,
        );
        return;
      }
      await _transcribeAndSend(audioFile);
    } else {
      setState(() => _isProcessing = false);
      _setMessage(
          "I couldn't capture your audio. Please try again.", _nextInput, _currentAction);
    }
  }

  Future<void> _transcribeAndSend(File audio) async {
    try {
      final result = await ApiService.transcribeAudio(audio);
      final success = result['success'] as bool? ?? false;
      final text = (result['text'] as String?) ?? '';
      if (success && text.isNotEmpty) {
        setState(() {
          _transcription = text;
          _processingMsg = 'Processing...';
        });
        await _sendVoice(text);
      } else {
        if (!mounted) return;
        setState(() => _isProcessing = false);
        final errorMsg = (result['error'] as String?) ?? '';
        _setMessage(
          errorMsg.isNotEmpty
              ? "I couldn't hear you clearly. Please speak directly into the mic and try again."
              : "I couldn't hear anything clearly. Please try again.",
          _nextInput,
          _currentAction,
        );
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _isProcessing = false);
      _setMessage('Transcription failed. Please try again.', _nextInput, _currentAction);
    }
  }

  // ── Error dialog ──────────────────────────────────────────────────────

  void _showError(String msg) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF1E293B),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Row(
          children: [
            Icon(Icons.error_outline, color: Color(0xFFEF4444), size: 20),
            SizedBox(width: 8),
            Text('Error',
                style: TextStyle(color: Colors.white, fontSize: 16)),
          ],
        ),
        content: Text(msg,
            style: const TextStyle(color: Color(0xFF94A3B8), height: 1.5)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child:
                const Text('OK', style: TextStyle(color: Color(0xFF3B82F6))),
          ),
        ],
      ),
    );
  }

  String _floorText(int floor) {
    if (floor == -1) return 'Basement';
    if (floor == 0) return 'Ground Floor';
    if (floor == 1) return '1st Floor';
    if (floor == 2) return '2nd Floor';
    return 'Floor $floor';
  }

  // ── Build ─────────────────────────────────────────────────────────────

  bool get _isNavigating {
    return _currentAction == 'navigation_step' ||
        _currentAction == 'awaiting_step_done' ||
        _currentAction == 'waiting_step_photo' ||
        _currentAction == 'retry_step_photo' ||
        _currentAction == 'repeat';
  }

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
        title: const Text(
          'Navigation Assistant',
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
        ),
      ),
      body: Stack(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
            child: Column(
              children: [
                const SizedBox(height: 8),
                _buildStatusRow(),
                const SizedBox(height: 16),
                Expanded(child: _buildMessageBubble()),
                const SizedBox(height: 16),
                if (_transcription.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Row(
                      children: [
                        const Icon(Icons.record_voice_over_rounded,
                            size: 14, color: Color(0xFF3B82F6)),
                        const SizedBox(width: 6),
                        Expanded(
                          child: Text(
                            '"$_transcription"',
                            style: const TextStyle(
                              color: Color(0xFF64748B),
                              fontSize: 12,
                              fontStyle: FontStyle.italic,
                            ),
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ],
                    ),
                  ),
                _buildActionArea(),
              ],
            ),
          ),
          if (_isProcessing)
            Container(
              color: Colors.black.withOpacity(0.80),
              child: Center(
                child: Container(
                  margin: const EdgeInsets.symmetric(horizontal: 48),
                  padding: const EdgeInsets.all(28),
                  decoration: BoxDecoration(
                    color: const Color(0xFF1E293B),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const CircularProgressIndicator(
                          color: Color(0xFF3B82F6), strokeWidth: 3),
                      const SizedBox(height: 16),
                      Text(
                        _processingMsg,
                        style: const TextStyle(
                            color: Colors.white, fontSize: 14),
                        textAlign: TextAlign.center,
                      ),
                    ],
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildStatusRow() {
    return Row(
      children: [
        _StatusChip(
          icon: Icons.business_rounded,
          label: _knownBuilding ?? '?',
          isKnown: _knownBuilding != null,
        ),
        const SizedBox(width: 8),
        _StatusChip(
          icon: Icons.layers_rounded,
          label: _knownFloor != null ? _floorText(_knownFloor!) : '?',
          isKnown: _knownFloor != null,
        ),
        if (_isNavigating && _totalSteps > 0) ...[
          const Spacer(),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
            decoration: BoxDecoration(
              color: const Color(0xFF3B82F6).withOpacity(0.10),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(
                  color: const Color(0xFF3B82F6).withOpacity(0.35)),
            ),
            child: Text(
              'Step $_currentStep / $_totalSteps',
              style: const TextStyle(
                color: Color(0xFF3B82F6),
                fontSize: 13,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ],
    );
  }

  Widget _buildMessageBubble() {
    final isNavComplete = _currentAction == 'navigation_complete';
    final iconData = isNavComplete
        ? Icons.check_circle_outline_rounded
        : (_isNavigating
            ? Icons.directions_walk_rounded
            : Icons.assistant_rounded);
    final iconColor = isNavComplete
        ? const Color(0xFF10B981)
        : const Color(0xFF3B82F6);

    return Center(
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
                  color: iconColor.withOpacity(0.12),
                ),
                child: Icon(iconData, color: iconColor, size: 28),
              ),
              const SizedBox(height: 20),
              Text(
                _ttsMessage.isEmpty
                    ? 'Starting navigation assistant...'
                    : _ttsMessage,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 16,
                  height: 1.55,
                  fontWeight: FontWeight.w400,
                ),
                textAlign: TextAlign.center,
              ),
              if (_ttsMessage.isNotEmpty) ...[
                const SizedBox(height: 20),
                GestureDetector(
                  onTap: () => _speakTts(_ttsMessage),
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
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildActionArea() {
    if (_currentAction == 'goodbye' || _currentAction == 'error') {
      return const SizedBox.shrink();
    }

    switch (_nextInput) {
      case 'voice':
        return _buildVoiceButton();
      case 'photo':
        return _buildPhotoWithVoiceFallback();
      case 'confirm':
        return _buildConfirmWithVoice();
      case 'voice_or_photo':
        return _buildVoiceOrPhotoButtons();
      case 'none':
        return const SizedBox.shrink();
      default:
        return _buildVoiceButton();
    }
  }

  Widget _buildPhotoWithVoiceFallback() {
    return Column(
      children: [
        _buildPhotoButton(),
        const SizedBox(height: 16),
        _buildDividerOr('or speak'),
        const SizedBox(height: 12),
        _buildMicCompact(),
      ],
    );
  }

  Widget _buildConfirmWithVoice() {
    final isConfirmPlan = _currentAction == 'confirm_plan';
    return Column(
      children: [
        Row(
          children: [
            Expanded(
              child: OutlinedButton(
                onPressed: () => _sendConfirmation(false),
                style: OutlinedButton.styleFrom(
                  foregroundColor: const Color(0xFFEF4444),
                  side: const BorderSide(color: Color(0xFFEF4444)),
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14)),
                ),
                child: Text(isConfirmPlan ? 'Change' : 'No',
                    style: const TextStyle(
                        fontSize: 16, fontWeight: FontWeight.w600)),
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              flex: 2,
              child: ElevatedButton(
                onPressed: () => _sendConfirmation(true),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF10B981),
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14)),
                ),
                child: Text(isConfirmPlan ? 'Start navigation' : 'Yes, correct',
                    style: const TextStyle(
                        fontSize: 16, fontWeight: FontWeight.w600)),
              ),
            ),
          ],
        ),
        const SizedBox(height: 16),
        _buildDividerOr('or speak'),
        const SizedBox(height: 12),
        _buildMicCompact(),
      ],
    );
  }

  Widget _buildVoiceOrPhotoButtons() {
    return Column(
      children: [
        _buildVoiceButton(),
        const SizedBox(height: 16),
        _buildDividerOr('or'),
        const SizedBox(height: 16),
        SizedBox(
          width: double.infinity,
          height: 54,
          child: OutlinedButton.icon(
            onPressed: _showPhotoOptions,
            icon: const Icon(Icons.photo_camera_outlined, size: 20),
            label: const Text('Take a photo instead',
                style:
                    TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
            style: OutlinedButton.styleFrom(
              foregroundColor: const Color(0xFF3B82F6),
              side: const BorderSide(color: Color(0xFF3B82F6)),
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14)),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildDividerOr(String label) {
    return Row(
      children: [
        const Expanded(child: Divider(color: Color(0xFF334155))),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12),
          child: Text(label,
              style: const TextStyle(color: Color(0xFF475569), fontSize: 12)),
        ),
        const Expanded(child: Divider(color: Color(0xFF334155))),
      ],
    );
  }

  Widget _buildPhotoButton() {
    return SizedBox(
      width: double.infinity,
      height: 60,
      child: ElevatedButton.icon(
        onPressed: _showPhotoOptions,
        icon: const Icon(Icons.photo_camera_outlined, size: 22),
        label: const Text('Take Photo',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
        style: ElevatedButton.styleFrom(
          backgroundColor: const Color(0xFF3B82F6),
          foregroundColor: Colors.white,
          shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(16)),
        ),
      ),
    );
  }

  Widget _buildVoiceButton() {
    return Column(
      children: [
        Center(
          child: GestureDetector(
            onTapDown: (_) => _startRecording(),
            onTapUp: (_) => _stopRecording(),
            onTapCancel: () => _stopRecording(),
            child: AnimatedBuilder(
              animation: _pulseAnim,
              builder: (_, __) => Transform.scale(
                scale: _isRecording ? _pulseAnim.value : 1.0,
                child: Container(
                  width: 90,
                  height: 90,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: _isRecording
                        ? const Color(0xFFEF4444)
                        : const Color(0xFF3B82F6),
                    boxShadow: [
                      BoxShadow(
                        color: (_isRecording
                                ? const Color(0xFFEF4444)
                                : const Color(0xFF3B82F6))
                            .withOpacity(0.4),
                        blurRadius: _isRecording ? 28 : 16,
                        spreadRadius: _isRecording ? 6 : 2,
                      ),
                    ],
                  ),
                  child: Icon(
                    _isRecording
                        ? Icons.mic_rounded
                        : Icons.mic_none_rounded,
                    size: 40,
                    color: Colors.white,
                  ),
                ),
              ),
            ),
          ),
        ),
        const SizedBox(height: 10),
        Text(
          _isRecording ? 'Listening... release to stop' : 'Hold to speak',
          style: TextStyle(
            color: _isRecording
                ? const Color(0xFFEF4444)
                : const Color(0xFF64748B),
            fontSize: 13,
            fontWeight: _isRecording ? FontWeight.w500 : FontWeight.normal,
          ),
        ),
      ],
    );
  }

  Widget _buildMicCompact() {
    return GestureDetector(
      onTapDown: (_) => _startRecording(),
      onTapUp: (_) => _stopRecording(),
      onTapCancel: () => _stopRecording(),
      child: AnimatedBuilder(
        animation: _pulseAnim,
        builder: (_, __) => Transform.scale(
          scale: _isRecording ? _pulseAnim.value : 1.0,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                width: 52,
                height: 52,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: _isRecording
                      ? const Color(0xFFEF4444).withOpacity(0.15)
                      : const Color(0xFF1E293B),
                  border: Border.all(
                    color: _isRecording
                        ? const Color(0xFFEF4444)
                        : const Color(0xFF334155),
                  ),
                ),
                child: Icon(
                  _isRecording ? Icons.mic_rounded : Icons.mic_none_rounded,
                  size: 24,
                  color: _isRecording
                      ? const Color(0xFFEF4444)
                      : const Color(0xFF64748B),
                ),
              ),
              const SizedBox(width: 10),
              Text(
                _isRecording ? 'Listening...' : 'Hold to speak',
                style: TextStyle(
                  color: _isRecording
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

class _StatusChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool isKnown;

  const _StatusChip({
    required this.icon,
    required this.label,
    required this.isKnown,
  });

  @override
  Widget build(BuildContext context) {
    final color = isKnown ? const Color(0xFF10B981) : const Color(0xFF94A3B8);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
      decoration: BoxDecoration(
        color: isKnown
            ? const Color(0xFF10B981).withOpacity(0.08)
            : const Color(0xFF1E293B),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: isKnown
              ? const Color(0xFF10B981).withOpacity(0.35)
              : const Color(0xFF334155),
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 6),
          Text(
            label,
            style: TextStyle(
              color: color,
              fontSize: 13,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }
}
