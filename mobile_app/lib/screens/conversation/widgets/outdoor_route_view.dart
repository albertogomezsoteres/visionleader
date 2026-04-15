import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';
import 'package:flutter_polyline_points/flutter_polyline_points.dart';

class OutdoorRouteView extends StatefulWidget {
  final double originLat;
  final double originLng;
  final double destinationLat;
  final double destinationLng;
  final String polylineEncoded;
  final String destinationLabel;
  final List<Map<String, dynamic>> steps;
  final VoidCallback onArrived;

  const OutdoorRouteView({
    super.key,
    required this.originLat,
    required this.originLng,
    required this.destinationLat,
    required this.destinationLng,
    required this.polylineEncoded,
    required this.destinationLabel,
    required this.steps,
    required this.onArrived,
  });

  @override
  State<OutdoorRouteView> createState() => _OutdoorRouteViewState();
}

class _OutdoorRouteViewState extends State<OutdoorRouteView> {
  final FlutterTts _tts = FlutterTts();
  GoogleMapController? _mapController;
  int _currentStepIdx = 0;

  late final Set<Polyline> _polylines;
  late final Set<Marker> _markers;
  late final LatLng _origin;
  late final LatLng _destination;
  late final CameraPosition _initialCamera;

  @override
  void initState() {
    super.initState();
    _origin = LatLng(widget.originLat, widget.originLng);
    _destination = LatLng(widget.destinationLat, widget.destinationLng);

    // Initial camera between origin and destination
    _initialCamera = CameraPosition(
      target: LatLng(
        (widget.originLat + widget.destinationLat) / 2,
        (widget.originLng + widget.destinationLng) / 2,
      ),
      zoom: 17,
    );

    _markers = {
      Marker(
        markerId: const MarkerId('origin'),
        position: _origin,
        icon: BitmapDescriptor.defaultMarkerWithHue(BitmapDescriptor.hueGreen),
        infoWindow: const InfoWindow(title: 'You are here'),
      ),
      Marker(
        markerId: const MarkerId('destination'),
        position: _destination,
        icon: BitmapDescriptor.defaultMarkerWithHue(BitmapDescriptor.hueRed),
        infoWindow: InfoWindow(title: 'Building ${widget.destinationLabel}'),
      ),
    };

    _polylines = {};
    if (widget.polylineEncoded.isNotEmpty) {
      final points = PolylinePoints()
          .decodePolyline(widget.polylineEncoded)
          .map((p) => LatLng(p.latitude, p.longitude))
          .toList();
      if (points.isNotEmpty) {
        _polylines.add(Polyline(
          polylineId: const PolylineId('route'),
          points: points,
          color: const Color(0xFF3B82F6),
          width: 5,
        ));
      }
    }

    _initTts();
  }

  @override
  void dispose() {
    _tts.stop();
    _tts.dispose();
    _mapController?.dispose();
    super.dispose();
  }

  Future<void> _initTts() async {
    await _tts.setLanguage('en-US');
    await _tts.setSpeechRate(0.42);
    await _tts.setVolume(1.0);
    await _tts.setPitch(1.0);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (widget.steps.isNotEmpty) {
        _speakCurrentStep();
      } else {
        _tts.speak('Follow the blue route on the map to reach Building ${widget.destinationLabel}.');
      }
    });
  }

  void _onMapCreated(GoogleMapController controller) {
    _mapController = controller;
    // Fit both markers in view with padding
    final bounds = LatLngBounds(
      southwest: LatLng(
        min(widget.originLat, widget.destinationLat) - 0.0003,
        min(widget.originLng, widget.destinationLng) - 0.0003,
      ),
      northeast: LatLng(
        max(widget.originLat, widget.destinationLat) + 0.0003,
        max(widget.originLng, widget.destinationLng) + 0.0003,
      ),
    );
    Future.delayed(const Duration(milliseconds: 300), () {
      controller.animateCamera(CameraUpdate.newLatLngBounds(bounds, 60));
    });
  }

  Future<void> _speakCurrentStep() async {
    if (widget.steps.isEmpty) return;
    final step = widget.steps[_currentStepIdx];
    final instruction = (step['instruction'] as String?) ?? '';
    final distance = _normalizeDistance((step['distance'] as String?) ?? '');
    final text = distance.isNotEmpty ? '$instruction. $distance.' : instruction;
    await _tts.stop();
    await _tts.speak('Step ${_currentStepIdx + 1}. $text');
  }

  String _normalizeDistance(String raw) {
    final text = raw.trim();
    if (text.isEmpty) return '';
    final m = RegExp(r'^(\d+(?:[.,]\d+)?)\s*m$', caseSensitive: false).firstMatch(text);
    if (m != null) {
      final value = m.group(1)!.replaceAll(',', '.');
      return '$value meters';
    }
    return text;
  }

  void _goToNextStep() {
    if (_currentStepIdx < widget.steps.length - 1) {
      setState(() => _currentStepIdx++);
    }
    _speakCurrentStep();
    // Pan map to the start location of the new step if available
    final loc = widget.steps[_currentStepIdx]['startLocation'];
    if (loc != null && _mapController != null) {
      final lat = (loc['lat'] as num?)?.toDouble();
      final lng = (loc['lng'] as num?)?.toDouble();
      if (lat != null && lng != null) {
        _mapController!.animateCamera(
          CameraUpdate.newLatLng(LatLng(lat, lng)),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF020817),
      appBar: AppBar(
        backgroundColor: const Color(0xFF020817),
        title: Text(
          'Walking to Building ${widget.destinationLabel}',
          style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w600),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.my_location_rounded, color: Color(0xFF3B82F6)),
            tooltip: 'Center on route',
            onPressed: () {
              if (_mapController == null) return;
              final bounds = LatLngBounds(
                southwest: LatLng(
                  min(widget.originLat, widget.destinationLat) - 0.0003,
                  min(widget.originLng, widget.destinationLng) - 0.0003,
                ),
                northeast: LatLng(
                  max(widget.originLat, widget.destinationLat) + 0.0003,
                  max(widget.originLng, widget.destinationLng) + 0.0003,
                ),
              );
              _mapController!.animateCamera(CameraUpdate.newLatLngBounds(bounds, 60));
            },
          ),
        ],
      ),
      body: Column(
        children: [
          // Embedded Google Map (60% height)
          Expanded(
            flex: 6,
            child: GoogleMap(
              initialCameraPosition: _initialCamera,
              onMapCreated: _onMapCreated,
              polylines: _polylines,
              markers: _markers,
              myLocationEnabled: true,
              myLocationButtonEnabled: false,
              zoomControlsEnabled: false,
              mapToolbarEnabled: false,
            ),
          ),

          // Walking guidance panel (40% height)
          Expanded(
            flex: 4,
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 30),
              decoration: const BoxDecoration(
                color: Color(0xFF0B1220),
                borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Walking guidance',
                    style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w700),
                  ),
                  const SizedBox(height: 8),
                  Expanded(
                    child: widget.steps.isEmpty
                        ? const Text(
                            'Follow the blue route on the map.',
                            style: TextStyle(color: Color(0xFF94A3B8)),
                          )
                        : ListView.builder(
                            itemCount: widget.steps.length,
                            itemBuilder: (context, idx) {
                              final step = widget.steps[idx];
                              final instruction = (step['instruction'] as String?) ?? '';
                              final distance = _normalizeDistance((step['distance'] as String?) ?? '');
                              final isActive = idx == _currentStepIdx;
                              return Semantics(
                                button: true,
                                label: 'Step ${idx + 1}: $instruction${distance.isNotEmpty ? '. $distance' : ''}',
                                child: GestureDetector(
                                onTap: () {
                                  setState(() => _currentStepIdx = idx);
                                  _speakCurrentStep();
                                },
                                child: Padding(
                                  padding: const EdgeInsets.symmetric(vertical: 4),
                                  child: Row(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Container(
                                        width: 22,
                                        height: 22,
                                        margin: const EdgeInsets.only(top: 1, right: 10),
                                        decoration: BoxDecoration(
                                          color: isActive
                                              ? const Color(0xFF3B82F6)
                                              : const Color(0xFF1E293B),
                                          shape: BoxShape.circle,
                                        ),
                                        child: Center(
                                          child: Text(
                                            '${idx + 1}',
                                            style: TextStyle(
                                              color: isActive ? Colors.white : const Color(0xFF64748B),
                                              fontSize: 10,
                                              fontWeight: FontWeight.w700,
                                            ),
                                          ),
                                        ),
                                      ),
                                      Expanded(
                                        child: Text(
                                          distance.isNotEmpty ? '$instruction ($distance)' : instruction,
                                          style: TextStyle(
                                            color: isActive ? Colors.white : const Color(0xFF94A3B8),
                                            fontSize: 14,
                                            fontWeight: isActive ? FontWeight.w500 : FontWeight.normal,
                                          ),
                                        ),
                                      ),
                                      if (isActive)
                                        const Icon(Icons.volume_up_rounded, color: Color(0xFF3B82F6), size: 18),
                                    ],
                                  ),
                                ),
                              ));
                            },
                          ),
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: _speakCurrentStep,
                          icon: const Icon(Icons.replay_rounded, size: 16),
                          label: const Text('Repeat', style: TextStyle(fontSize: 13)),
                          style: OutlinedButton.styleFrom(
                            foregroundColor: const Color(0xFF93C5FD),
                            side: const BorderSide(color: Color(0xFF334155)),
                            minimumSize: const Size.fromHeight(48),
                            padding: const EdgeInsets.symmetric(vertical: 12),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: _goToNextStep,
                          icon: const Icon(Icons.skip_next_rounded, size: 16),
                          label: const Text('Next', style: TextStyle(fontSize: 13)),
                          style: OutlinedButton.styleFrom(
                            foregroundColor: const Color(0xFFA7F3D0),
                            side: const BorderSide(color: Color(0xFF334155)),
                            minimumSize: const Size.fromHeight(48),
                            padding: const EdgeInsets.symmetric(vertical: 12),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        flex: 2,
                        child: ElevatedButton.icon(
                          onPressed: () {
                            _tts.stop();
                            Navigator.of(context).pop();
                            // Give the conversation screen a brief transition window
                            // so the next step TTS starts reliably after map close.
                            Future.delayed(const Duration(milliseconds: 900), () {
                              widget.onArrived();
                            });
                          },
                          icon: const Icon(Icons.check_circle_outline_rounded, size: 16),
                          label: const Text("Arrived", style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFF10B981),
                            foregroundColor: Colors.white,
                            minimumSize: const Size.fromHeight(48),
                            padding: const EdgeInsets.symmetric(vertical: 12),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                            elevation: 0,
                          ),
                        ),
                      ),
                    ],
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
