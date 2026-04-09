import 'package:flutter/material.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:webview_flutter/webview_flutter.dart';

class OutdoorRouteView extends StatefulWidget {
  final String routeUrl;
  final String destinationLabel;
  final List<Map<String, String>> steps;
  final VoidCallback onArrived;

  const OutdoorRouteView({
    super.key,
    required this.routeUrl,
    required this.destinationLabel,
    required this.steps,
    required this.onArrived,
  });

  @override
  State<OutdoorRouteView> createState() => _OutdoorRouteViewState();
}

class _OutdoorRouteViewState extends State<OutdoorRouteView> {
  late final WebViewController _controller;
  final FlutterTts _tts = FlutterTts();
  bool _loading = true;
  int _currentStepIdx = 0;

  @override
  void initState() {
    super.initState();
    _initTts();
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setNavigationDelegate(
        NavigationDelegate(
          onPageStarted: (_) => setState(() => _loading = true),
          onPageFinished: (_) => setState(() => _loading = false),
        ),
      )
      ..loadRequest(Uri.parse(widget.routeUrl));
  }

  @override
  void dispose() {
    _tts.stop();
    super.dispose();
  }

  Future<void> _initTts() async {
    await _tts.setLanguage('en-US');
    await _tts.setSpeechRate(0.42);
    await _tts.setVolume(1.0);
    await _tts.setPitch(1.0);
    if (widget.steps.isNotEmpty) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _speakCurrentStep();
      });
    } else {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _tts.speak('Outdoor route opened. Follow the highlighted path on the map.');
      });
    }
  }

  Future<void> _speakCurrentStep() async {
    if (widget.steps.isEmpty) return;
    final step = widget.steps[_currentStepIdx];
    final instruction = step['instruction'] ?? '';
    final distance = step['distance'] ?? '';
    final text = distance.isNotEmpty ? '$instruction. $distance.' : instruction;
    await _tts.stop();
    await _tts.speak('Step ${_currentStepIdx + 1}. $text');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF020817),
      appBar: AppBar(
        backgroundColor: const Color(0xFF020817),
        title: Text(
          'Outdoor route to ${widget.destinationLabel}',
          style: const TextStyle(color: Colors.white, fontSize: 16),
        ),
      ),
      body: Column(
        children: [
          Expanded(
            flex: 3,
            child: Stack(
              children: [
                WebViewWidget(controller: _controller),
                if (_loading)
                  const Center(
                    child: CircularProgressIndicator(),
                  ),
              ],
            ),
          ),
          Expanded(
            flex: 2,
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
              decoration: const BoxDecoration(
                color: Color(0xFF0B1220),
                borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Walking guidance',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Expanded(
                    child: widget.steps.isEmpty
                        ? const Text(
                            'Follow the highlighted route on the map.',
                            style: TextStyle(color: Color(0xFF94A3B8)),
                          )
                        : ListView.separated(
                            itemCount: widget.steps.length,
                            separatorBuilder: (_, __) => const SizedBox(height: 8),
                            itemBuilder: (context, idx) {
                              final step = widget.steps[idx];
                              final instruction = step['instruction'] ?? '';
                              final distance = step['distance'] ?? '';
                              final isActive = idx == _currentStepIdx;
                              return GestureDetector(
                                onTap: () {
                                  setState(() => _currentStepIdx = idx);
                                  _speakCurrentStep();
                                },
                                child: Text(
                                  '${idx + 1}. $instruction${distance.isNotEmpty ? ' ($distance)' : ''}',
                                  style: TextStyle(
                                    color: isActive
                                        ? const Color(0xFF22D3EE)
                                        : const Color(0xFFE2E8F0),
                                    fontSize: 13,
                                  ),
                                ),
                              );
                            },
                          ),
                  ),
                  const SizedBox(height: 8),
                  if (widget.steps.isNotEmpty)
                    Row(
                      children: [
                        Expanded(
                          child: OutlinedButton.icon(
                            onPressed: _speakCurrentStep,
                            icon: const Icon(Icons.replay_rounded, size: 18),
                            label: const Text('Repeat'),
                            style: OutlinedButton.styleFrom(
                              foregroundColor: const Color(0xFF93C5FD),
                              side: const BorderSide(color: Color(0xFF334155)),
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: OutlinedButton.icon(
                            onPressed: () {
                              setState(() {
                                _currentStepIdx =
                                    (_currentStepIdx + 1) % widget.steps.length;
                              });
                              _speakCurrentStep();
                            },
                            icon: const Icon(Icons.skip_next_rounded, size: 18),
                            label: const Text('Next step'),
                            style: OutlinedButton.styleFrom(
                              foregroundColor: const Color(0xFFA7F3D0),
                              side: const BorderSide(color: Color(0xFF334155)),
                            ),
                          ),
                        ),
                      ],
                    ),
                  if (widget.steps.isNotEmpty) const SizedBox(height: 8),
                  SizedBox(
                    width: double.infinity,
                    height: 50,
                    child: ElevatedButton.icon(
                      onPressed: () {
                        Navigator.of(context).pop();
                        widget.onArrived();
                      },
                      icon: const Icon(Icons.check_circle_outline_rounded),
                      label: const Text(
                        "I've arrived",
                        style: TextStyle(fontWeight: FontWeight.w600),
                      ),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF10B981),
                        foregroundColor: Colors.white,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
