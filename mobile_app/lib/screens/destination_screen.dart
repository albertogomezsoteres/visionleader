import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_sound/flutter_sound.dart';
import 'package:permission_handler/permission_handler.dart';
import '../services/api_service.dart';
import 'plan_screen.dart';

class DestinationScreen extends StatefulWidget {
  final int currentBuilding;
  final int currentFloor;

  const DestinationScreen({
    super.key,
    required this.currentBuilding,
    required this.currentFloor,
  });

  @override
  State<DestinationScreen> createState() => _DestinationScreenState();
}

class _DestinationScreenState extends State<DestinationScreen>
    with SingleTickerProviderStateMixin {
  final FlutterSoundRecorder _recorder = FlutterSoundRecorder();

  bool _isRecording = false;
  bool _isProcessing = false;
  String _processingMsg = '';
  String _transcription = '';

  late AnimationController _pulseCtrl;
  late Animation<double> _pulseAnim;

  // Destination
  int _goalBuilding = 1;
  int _goalFloor = 0;
  String? _goalFunctional;
  bool _showManual = false;

  static const Map<int, String> _buildingNames = {
    1: 'EPS',
    2: 'CD',
    3: 'H',
  };
  static const Map<int, List<int>> _buildingFloors = {
    1: [-1, 0, 1, 2],
    2: [-1, 0, 1, 2],
    3: [0, 1, 2],
  };
  static const List<Map<String, dynamic>> _quickGoals = [
    {
      'id': 'cafeteria',
      'label': 'Cafeteria',
      'building': 2,
      'floor': 0,
      'icon': Icons.restaurant_outlined,
    },
    {
      'id': 'gimnasio',
      'label': 'Gym',
      'building': 2,
      'floor': -1,
      'icon': Icons.fitness_center_outlined,
    },
  ];

  @override
  void initState() {
    super.initState();
    _pulseCtrl = AnimationController(
      duration: const Duration(milliseconds: 900),
      vsync: this,
    );
    _pulseAnim = Tween<double>(begin: 1.0, end: 1.18).animate(
        CurvedAnimation(parent: _pulseCtrl, curve: Curves.easeInOut));
    _initRecorder();
  }

  Future<void> _initRecorder() async {
    await Permission.microphone.request();
    await _recorder.openRecorder();
  }

  @override
  void dispose() {
    _recorder.closeRecorder();
    _pulseCtrl.dispose();
    super.dispose();
  }

  Future<void> _startRecording() async {
    setState(() => _isRecording = true);
    _pulseCtrl.repeat(reverse: true);
    await _recorder.startRecorder(
        toFile: 'dest_audio.wav', codec: Codec.pcm16WAV);
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
    if (path != null) await _processAudio(File(path));
  }

  Future<void> _processAudio(File audio) async {
    try {
      final result = await ApiService.transcribeAudio(audio);
      final text = (result['text'] as String?) ?? '';
      setState(() {
        _transcription = text;
        _processingMsg = 'Understanding destination...';
      });
      _parseDestination(text);
      setState(() => _isProcessing = false);
    } catch (e) {
      setState(() {
        _isProcessing = false;
        _transcription = 'Transcription failed. Try again or select manually.';
      });
    }
  }

  void _parseDestination(String text) {
    final lower = text.toLowerCase();

    // Functional goals
    if (lower.contains('cafeteria') ||
        lower.contains('café') ||
        lower.contains('cafe')) {
      setState(() {
        _goalFunctional = 'cafeteria';
        _goalBuilding = 2;
        _goalFloor = 0;
      });
      return;
    }
    if (lower.contains('gym') ||
        lower.contains('gimnasio') ||
        lower.contains('sport')) {
      setState(() {
        _goalFunctional = 'gimnasio';
        _goalBuilding = 2;
        _goalFloor = -1;
      });
      return;
    }

    // Building
    int? building;
    if (lower.contains('eps') ||
        lower.contains('polytechnic') ||
        lower.contains('politec')) {
      building = 1;
    } else if (lower.contains(' cd') ||
        lower.contains('deportivo') ||
        lower.contains('sports center')) {
      building = 2;
    } else if (RegExp(r'\bh\b').hasMatch(lower) ||
        lower.contains('building h') ||
        lower.contains('edificio h')) {
      building = 3;
    }

    // Floor
    int? floor;
    if (lower.contains('basement') ||
        lower.contains('minus one') ||
        lower.contains('-1')) {
      floor = -1;
    } else if (lower.contains('ground') ||
        lower.contains('zero') ||
        lower.contains('floor 0')) {
      floor = 0;
    } else if (lower.contains('first') ||
        lower.contains('floor 1') ||
        lower.contains('1st')) {
      floor = 1;
    } else if (lower.contains('second') ||
        lower.contains('floor 2') ||
        lower.contains('2nd')) {
      floor = 2;
    } else if (lower.contains('third') ||
        lower.contains('floor 3') ||
        lower.contains('3rd')) {
      floor = 3;
    }

    if (building != null || floor != null) {
      setState(() {
        _goalFunctional = null;
        _goalBuilding = building ?? _goalBuilding;
        _goalFloor = floor ?? 0;
      });
    }
  }

  String _floorName(int f) {
    if (f == -1) return 'Basement';
    if (f == 0) return 'Ground Floor';
    if (f == 1) return '1st Floor';
    if (f == 2) return '2nd Floor';
    return 'Floor $f';
  }

  String get _goalDescription {
    if (_goalFunctional != null) {
      final g = _quickGoals.firstWhere(
          (g) => g['id'] == _goalFunctional,
          orElse: () => {'label': _goalFunctional!});
      return '${g['label']} (${_buildingNames[_goalBuilding]}, ${_floorName(_goalFloor)})';
    }
    return '${_buildingNames[_goalBuilding]}, ${_floorName(_goalFloor)}';
  }

  Future<void> _navigate() async {
    setState(() {
      _isProcessing = true;
      _processingMsg = 'Generating navigation plan...';
    });
    try {
      final result = await ApiService.generatePlan(
        initialBuilding: widget.currentBuilding,
        initialFloor: widget.currentFloor,
        goalBuilding: _goalFunctional == null ? _goalBuilding : null,
        goalFloor: _goalFunctional == null ? _goalFloor : null,
        goalFunctional: _goalFunctional,
      );
      if (!mounted) return;
      setState(() => _isProcessing = false);

      if (result['success'] == true) {
        final plan = (result['plan'] as List).cast<String>();
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) => PlanScreen(
              plan: plan,
              fromBuilding: widget.currentBuilding,
              fromFloor: widget.currentFloor,
              toBuilding: _goalBuilding,
              toFloor: _goalFloor,
              goalLabel: _goalDescription,
            ),
          ),
        );
      } else {
        _showError(result['error'] ??
            'No route found for this destination. Check buildings and floors.');
      }
    } catch (e) {
      setState(() => _isProcessing = false);
      _showError('Could not connect to server. Make sure the backend is running.\n\n$e');
    }
  }

  void _showError(String msg) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF1E293B),
        shape:
            RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Row(
          children: [
            Icon(Icons.error_outline, color: Color(0xFFEF4444), size: 20),
            SizedBox(width: 8),
            Text('Navigation Error',
                style: TextStyle(color: Colors.white, fontSize: 16)),
          ],
        ),
        content: Text(msg,
            style:
                const TextStyle(color: Color(0xFF94A3B8), height: 1.5)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('OK',
                style: TextStyle(color: Color(0xFF3B82F6))),
          ),
        ],
      ),
    );
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
        title: const Text('Where to Go?',
            style: TextStyle(
                color: Colors.white, fontWeight: FontWeight.w600)),
      ),
      body: Stack(
        children: [
          SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(24, 16, 24, 24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // From chip
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
                  decoration: BoxDecoration(
                    color: const Color(0xFF0F172A),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: const Color(0xFF1E293B)),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.my_location_rounded,
                          size: 15, color: Color(0xFF10B981)),
                      const SizedBox(width: 8),
                      Text(
                        'From: ${_buildingNames[widget.currentBuilding]}, ${_floorName(widget.currentFloor)}',
                        style: const TextStyle(
                            color: Color(0xFF94A3B8), fontSize: 13),
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 32),

                // Voice section
                const Text('Say your destination',
                    style: TextStyle(
                        color: Colors.white,
                        fontSize: 22,
                        fontWeight: FontWeight.bold)),
                const SizedBox(height: 6),
                const Text(
                  '"Take me to the cafeteria"  ·  "Building H, floor 2"',
                  style: TextStyle(color: Color(0xFF64748B), fontSize: 13),
                ),

                const SizedBox(height: 40),

                // Mic button
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
                          width: 114,
                          height: 114,
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
                                blurRadius: _isRecording ? 32 : 20,
                                spreadRadius: _isRecording ? 8 : 4,
                              ),
                            ],
                          ),
                          child: Icon(
                            _isRecording ? Icons.mic_rounded : Icons.mic_none_rounded,
                            size: 46,
                            color: Colors.white,
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                Center(
                  child: Text(
                    _isRecording
                        ? 'Listening... release to stop'
                        : 'Hold to speak',
                    style: TextStyle(
                      color: _isRecording
                          ? const Color(0xFFEF4444)
                          : const Color(0xFF64748B),
                      fontSize: 14,
                      fontWeight: _isRecording
                          ? FontWeight.w500
                          : FontWeight.normal,
                    ),
                  ),
                ),

                // Transcription result
                if (_transcription.isNotEmpty) ...[
                  const SizedBox(height: 28),
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: const Color(0xFF0F172A),
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(color: const Color(0xFF1E293B)),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Row(
                          children: [
                            Icon(Icons.record_voice_over_rounded,
                                size: 15, color: Color(0xFF3B82F6)),
                            SizedBox(width: 7),
                            Text('Heard:',
                                style: TextStyle(
                                    color: Color(0xFF64748B),
                                    fontSize: 12)),
                          ],
                        ),
                        const SizedBox(height: 6),
                        Text('"$_transcription"',
                            style: const TextStyle(
                                color: Colors.white,
                                fontSize: 14,
                                fontStyle: FontStyle.italic,
                                height: 1.4)),
                        const SizedBox(height: 10),
                        const Divider(color: Color(0xFF1E293B), height: 1),
                        const SizedBox(height: 10),
                        Row(
                          children: [
                            const Icon(Icons.navigation_rounded,
                                size: 15, color: Color(0xFF10B981)),
                            const SizedBox(width: 7),
                            Expanded(
                              child: Text(
                                '→ $_goalDescription',
                                style: const TextStyle(
                                    color: Color(0xFF10B981),
                                    fontSize: 13,
                                    fontWeight: FontWeight.w500),
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ],

                const SizedBox(height: 28),

                // Quick goals
                const Text('Quick destinations:',
                    style: TextStyle(
                        color: Color(0xFF64748B), fontSize: 13)),
                const SizedBox(height: 10),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: _quickGoals
                      .map((goal) => GestureDetector(
                            onTap: () => setState(() {
                              _goalFunctional = goal['id'] as String;
                              _goalBuilding = goal['building'] as int;
                              _goalFloor = goal['floor'] as int;
                            }),
                            child: Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 14, vertical: 10),
                              decoration: BoxDecoration(
                                color: _goalFunctional == goal['id']
                                    ? const Color(0xFF3B82F6)
                                        .withOpacity(0.15)
                                    : const Color(0xFF0F172A),
                                borderRadius: BorderRadius.circular(10),
                                border: Border.all(
                                  color: _goalFunctional == goal['id']
                                      ? const Color(0xFF3B82F6)
                                      : const Color(0xFF1E293B),
                                ),
                              ),
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Icon(goal['icon'] as IconData,
                                      size: 16,
                                      color: const Color(0xFF3B82F6)),
                                  const SizedBox(width: 7),
                                  Text(goal['label'] as String,
                                      style: const TextStyle(
                                          color: Colors.white,
                                          fontSize: 14,
                                          fontWeight: FontWeight.w500)),
                                ],
                              ),
                            ),
                          ))
                      .toList(),
                ),

                const SizedBox(height: 20),

                // Manual toggle
                Row(
                  children: [
                    const Expanded(
                        child: Divider(color: Color(0xFF1E293B))),
                    TextButton(
                      onPressed: () =>
                          setState(() => _showManual = !_showManual),
                      child: Text(
                        _showManual
                            ? 'Hide manual selector'
                            : 'Select manually',
                        style: const TextStyle(
                            color: Color(0xFF475569), fontSize: 13),
                      ),
                    ),
                    const Expanded(
                        child: Divider(color: Color(0xFF1E293B))),
                  ],
                ),

                if (_showManual) ...[
                  const SizedBox(height: 12),
                  _DropdownRow(
                    icon: Icons.business_rounded,
                    label: 'Building',
                    child: DropdownButton<int>(
                      value: _goalBuilding,
                      dropdownColor: const Color(0xFF1E293B),
                      underline: const SizedBox(),
                      isExpanded: true,
                      items: _buildingNames.entries
                          .map((e) => DropdownMenuItem(
                                value: e.key,
                                child: Text(e.value,
                                    style: const TextStyle(
                                        color: Colors.white,
                                        fontSize: 14)),
                              ))
                          .toList(),
                      onChanged: (v) => setState(() {
                        _goalBuilding = v!;
                        _goalFunctional = null;
                        _goalFloor = _buildingFloors[v]!.first;
                      }),
                    ),
                  ),
                  const SizedBox(height: 10),
                  _DropdownRow(
                    icon: Icons.layers_rounded,
                    label: 'Floor',
                    child: DropdownButton<int>(
                      value: _goalFloor,
                      dropdownColor: const Color(0xFF1E293B),
                      underline: const SizedBox(),
                      isExpanded: true,
                      items: (_buildingFloors[_goalBuilding] ?? [0, 1, 2])
                          .map((f) => DropdownMenuItem(
                                value: f,
                                child: Text(_floorName(f),
                                    style: const TextStyle(
                                        color: Colors.white,
                                        fontSize: 14)),
                              ))
                          .toList(),
                      onChanged: (v) => setState(() {
                        _goalFloor = v!;
                        _goalFunctional = null;
                      }),
                    ),
                  ),
                ],

                const SizedBox(height: 36),

                // Generate button
                SizedBox(
                  width: double.infinity,
                  height: 62,
                  child: ElevatedButton(
                    onPressed: _navigate,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF4F46E5),
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(16)),
                      elevation: 0,
                    ),
                    child: const Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.route_rounded, size: 22),
                        SizedBox(width: 10),
                        Text('Generate Navigation Plan',
                            style: TextStyle(
                                fontSize: 17,
                                fontWeight: FontWeight.w600)),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 24),
              ],
            ),
          ),

          // Processing overlay
          if (_isProcessing)
            Container(
              color: Colors.black.withOpacity(0.82),
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
                      const SizedBox(height: 18),
                      Text(_processingMsg,
                          style: const TextStyle(
                              color: Colors.white, fontSize: 15),
                          textAlign: TextAlign.center),
                    ],
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _DropdownRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final Widget child;

  const _DropdownRow(
      {required this.icon, required this.label, required this.child});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      decoration: BoxDecoration(
        color: const Color(0xFF0F172A),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF1E293B)),
      ),
      child: Row(
        children: [
          Icon(icon, color: const Color(0xFF3B82F6), size: 18),
          const SizedBox(width: 10),
          SizedBox(
              width: 62,
              child: Text(label,
                  style: const TextStyle(
                      color: Color(0xFF64748B), fontSize: 13))),
          Expanded(child: child),
        ],
      ),
    );
  }
}
