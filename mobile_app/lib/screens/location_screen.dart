import 'dart:io';
import 'package:flutter/material.dart';
import 'destination_screen.dart';

class LocationScreen extends StatefulWidget {
  final Map<String, dynamic> analysisResult;
  final File imageFile;

  const LocationScreen({
    super.key,
    required this.analysisResult,
    required this.imageFile,
  });

  @override
  State<LocationScreen> createState() => _LocationScreenState();
}

class _LocationScreenState extends State<LocationScreen> {
  late int? _building;
  late int? _floor;
  late List<String> _landmarks;
  late List<String> _resources;

  bool _isEditing = false;
  int _editBuilding = 1;
  int _editFloor = 0;

  static const Map<int, String> _buildingFullNames = {
    1: 'EPS — Escuela Politécnica Superior',
    2: 'CD — Centro Deportivo',
    3: 'H — Edificio H',
  };
  static const Map<int, List<int>> _buildingFloors = {
    1: [-1, 0, 1, 2],
    2: [-1, 0, 1, 2],
    3: [0, 1, 2],
  };

  @override
  void initState() {
    super.initState();
    final r = widget.analysisResult;
    _building = r['building'] as int?;
    _floor = r['floor'] as int?;
    _landmarks = (r['landmarks'] as List?)?.cast<String>() ?? [];
    _resources = (r['resources'] as List?)?.cast<String>() ?? [];
    _editBuilding = _building ?? 1;
    _editFloor = _floor ?? 0;
  }

  String _floorName(int f) {
    if (f == -1) return 'Basement (−1)';
    if (f == 0) return 'Ground Floor (0)';
    if (f == 1) return '1st Floor';
    if (f == 2) return '2nd Floor';
    if (f == 3) return '3rd Floor';
    return 'Floor $f';
  }

  void _confirm() {
    final building = _isEditing ? _editBuilding : _building;
    final floor = _isEditing ? _editFloor : _floor;

    if (building == null || floor == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Please select your building and floor'),
          backgroundColor: Color(0xFFEF4444),
        ),
      );
      return;
    }
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => DestinationScreen(
          currentBuilding: building,
          currentFloor: floor,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final detected = _building != null && _floor != null && !_isEditing;

    return Scaffold(
      backgroundColor: const Color(0xFF020817),
      appBar: AppBar(
        backgroundColor: const Color(0xFF020817),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_rounded, color: Colors.white),
          onPressed: () => Navigator.pop(context),
        ),
        title: const Text('Your Location',
            style:
                TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Image preview
            ClipRRect(
              borderRadius: BorderRadius.circular(16),
              child: Image.file(
                widget.imageFile,
                height: 190,
                width: double.infinity,
                fit: BoxFit.cover,
              ),
            ),
            const SizedBox(height: 20),

            // Status banner
            if (detected)
              _StatusBanner(
                icon: Icons.check_circle_outline,
                message: 'Location detected successfully!',
                color: const Color(0xFF10B981),
              )
            else if (!_isEditing)
              _StatusBanner(
                icon: Icons.warning_amber_outlined,
                message:
                    'Could not fully detect location. Please select manually.',
                color: const Color(0xFFF59E0B),
              ),

            const SizedBox(height: 24),

            const Text(
              'Location Details',
              style: TextStyle(
                  color: Colors.white,
                  fontSize: 20,
                  fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 14),

            // Detected view
            if (detected) ...[
              _InfoCard(
                children: [
                  _InfoRow(
                    icon: Icons.business_rounded,
                    label: 'Building',
                    value: _buildingFullNames[_building] ?? 'Unknown',
                    valueColor: const Color(0xFF3B82F6),
                  ),
                  const _Divider(),
                  _InfoRow(
                    icon: Icons.layers_rounded,
                    label: 'Floor',
                    value: _floorName(_floor!),
                    valueColor: const Color(0xFF818CF8),
                  ),
                  if (_landmarks.isNotEmpty) ...[
                    const _Divider(),
                    _InfoRow(
                      icon: Icons.location_on_outlined,
                      label: 'Nearby',
                      value: _landmarks.take(4).join(' · '),
                      valueColor: const Color(0xFF94A3B8),
                    ),
                  ],
                  if (_resources.isNotEmpty) ...[
                    const _Divider(),
                    _InfoRow(
                      icon: _resources.contains('elevator')
                          ? Icons.elevator_rounded
                          : Icons.stairs_rounded,
                      label: 'Available',
                      value: _resources
                          .map((r) => r[0].toUpperCase() + r.substring(1))
                          .join(', '),
                      valueColor: const Color(0xFF10B981),
                    ),
                  ],
                ],
              ),
              const SizedBox(height: 12),
              Center(
                child: TextButton(
                  onPressed: () => setState(() => _isEditing = true),
                  child: const Text(
                    'Not correct? Edit manually',
                    style: TextStyle(
                        color: Color(0xFF475569),
                        decoration: TextDecoration.underline,
                        decorationColor: Color(0xFF475569),
                        fontSize: 13),
                  ),
                ),
              ),
            ]

            // Manual selector
            else ...[
              const Text(
                'Select your location:',
                style: TextStyle(color: Color(0xFF94A3B8), fontSize: 14),
              ),
              const SizedBox(height: 12),
              _DropdownCard(
                icon: Icons.business_rounded,
                label: 'Building',
                child: DropdownButton<int>(
                  value: _editBuilding,
                  dropdownColor: const Color(0xFF1E293B),
                  underline: const SizedBox(),
                  isExpanded: true,
                  items: _buildingFullNames.entries
                      .map((e) => DropdownMenuItem(
                            value: e.key,
                            child: Text(e.value,
                                style: const TextStyle(
                                    color: Colors.white, fontSize: 14)),
                          ))
                      .toList(),
                  onChanged: (v) => setState(() {
                    _editBuilding = v!;
                    _editFloor = _buildingFloors[v]!.first;
                  }),
                ),
              ),
              const SizedBox(height: 10),
              _DropdownCard(
                icon: Icons.layers_rounded,
                label: 'Floor',
                child: DropdownButton<int>(
                  value: _editFloor,
                  dropdownColor: const Color(0xFF1E293B),
                  underline: const SizedBox(),
                  isExpanded: true,
                  items: (_buildingFloors[_editBuilding] ?? [0, 1, 2])
                      .map((f) => DropdownMenuItem(
                            value: f,
                            child: Text(_floorName(f),
                                style: const TextStyle(
                                    color: Colors.white, fontSize: 14)),
                          ))
                      .toList(),
                  onChanged: (v) => setState(() => _editFloor = v!),
                ),
              ),
            ],

            const SizedBox(height: 32),

            // Confirm button
            SizedBox(
              width: double.infinity,
              height: 62,
              child: ElevatedButton(
                onPressed: _confirm,
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF3B82F6),
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16)),
                ),
                child: const Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.check_rounded, size: 22),
                    SizedBox(width: 8),
                    Text('Confirm Location',
                        style: TextStyle(
                            fontSize: 17, fontWeight: FontWeight.w600)),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }
}

// ---- Helper widgets ----

class _StatusBanner extends StatelessWidget {
  final IconData icon;
  final String message;
  final Color color;

  const _StatusBanner(
      {required this.icon, required this.message, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Row(
        children: [
          Icon(icon, color: color, size: 18),
          const SizedBox(width: 10),
          Expanded(
              child: Text(message,
                  style: TextStyle(
                      color: color,
                      fontSize: 13,
                      fontWeight: FontWeight.w500))),
        ],
      ),
    );
  }
}

class _InfoCard extends StatelessWidget {
  final List<Widget> children;
  const _InfoCard({required this.children});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFF0F172A),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFF1E293B)),
      ),
      child: Column(children: children),
    );
  }
}

class _InfoRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final Color valueColor;

  const _InfoRow(
      {required this.icon,
      required this.label,
      required this.value,
      required this.valueColor});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 17, color: const Color(0xFF475569)),
          const SizedBox(width: 10),
          Text(label,
              style: const TextStyle(
                  color: Color(0xFF64748B), fontSize: 13)),
          const Spacer(),
          Flexible(
            child: Text(
              value,
              style: TextStyle(
                  color: valueColor,
                  fontWeight: FontWeight.w500,
                  fontSize: 13),
              textAlign: TextAlign.right,
            ),
          ),
        ],
      ),
    );
  }
}

class _Divider extends StatelessWidget {
  const _Divider();

  @override
  Widget build(BuildContext context) =>
      const Divider(color: Color(0xFF1E293B), height: 16);
}

class _DropdownCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final Widget child;

  const _DropdownCard(
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
          Icon(icon, color: const Color(0xFF3B82F6), size: 19),
          const SizedBox(width: 10),
          SizedBox(
              width: 64,
              child: Text(label,
                  style: const TextStyle(
                      color: Color(0xFF64748B), fontSize: 13))),
          Expanded(child: child),
        ],
      ),
    );
  }
}
