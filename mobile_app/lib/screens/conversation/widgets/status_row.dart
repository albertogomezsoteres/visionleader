import 'package:flutter/material.dart';

/// Two compact panels that show the agent's current understanding of the
/// initial location and the goal - both as natural text and as the
/// underlying PDDL atom that will be sent to the symbolic planner.
class StatusRow extends StatelessWidget {
  final String? initialBuilding;
  final int? initialFloor;
  final String? initialLocationId;
  final String? goalBuilding;
  final int? goalFloor;
  final String? goalLocationId;
  const StatusRow({
    super.key,
    required this.initialBuilding,
    required this.initialFloor,
    required this.initialLocationId,
    required this.goalBuilding,
    required this.goalFloor,
    required this.goalLocationId,
  });

  String _floorText(int floor) {
    if (floor == -1) return 'Basement';
    if (floor == 0) return 'Ground Floor';
    if (floor == 1) return '1st Floor';
    if (floor == 2) return '2nd Floor';
    return 'Floor $floor';
  }

  String _locationText(String locationId) {
    switch (locationId) {
      case 'entrance_main': return 'Main Entrance';
      case 'entrance_1':    return 'Entrance 1';
      case 'entrance_2':    return 'Entrance 2';
      case 'entrance_cd':   return 'CD Entrance';
      case 'elevator':      return 'Elevator';
      case 'stairs':        return 'Stairs';
      case 'bathroom':      return 'Restroom';
      case 'ai_lab':        return 'AI Laboratory';
      case 'offices':       return 'Faculty Offices';
      case 'eps_offices':   return 'EPS Faculty Offices';
      case 'admin_office':  return 'Secretary Office';
      case 'mentoring_room':return 'Mentoring Room';
      case 'cafeteria':     return 'Cafeteria';
      case 'gym':           return 'Gym';
    }
    final gMatch = RegExp(r'^classroom_g_(\d+)_(\d+)$').firstMatch(locationId);
    if (gMatch != null) return 'Classroom ${gMatch.group(1)}.${gMatch.group(2)}';
    final cdMatch = RegExp(r'^classroom_cd_(\d+)$').firstMatch(locationId);
    if (cdMatch != null) return 'Classroom ${cdMatch.group(1)} (CD)';
    final dirMatch = RegExp(r'^directory_sign_g_(\w+)$').firstMatch(locationId);
    if (dirMatch != null) return 'Directory G ${dirMatch.group(1)!.toUpperCase()}';
    return locationId.replaceAll('_', ' ');
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _StatePanel(
          title: 'Initial State',
          accent: const Color(0xFF10B981),
          icon: Icons.my_location_rounded,
          building: initialBuilding,
          floor: initialFloor,
          locationId: initialLocationId,
          floorTextFn: _floorText,
          locationTextFn: _locationText,
        ),
        const SizedBox(height: 14),
        _StatePanel(
          title: 'Goal State',
          accent: const Color(0xFF3B82F6),
          icon: Icons.flag_rounded,
          building: goalBuilding,
          floor: goalFloor,
          locationId: goalLocationId,
          floorTextFn: _floorText,
          locationTextFn: _locationText,
        ),
      ],
    );
  }
}

class _StatePanel extends StatelessWidget {
  final String title;
  final Color accent;
  final IconData icon;
  final String? building;
  final int? floor;
  final String? locationId;
  final String Function(int) floorTextFn;
  final String Function(String) locationTextFn;

  const _StatePanel({
    required this.title,
    required this.accent,
    required this.icon,
    required this.building,
    required this.floor,
    required this.locationId,
    required this.floorTextFn,
    required this.locationTextFn,
  });

  @override
  Widget build(BuildContext context) {
    final parts = <String>[];
    parts.add(building ?? '?');
    parts.add(floor != null ? floorTextFn(floor!) : '?');
    if (locationId != null && locationId!.isNotEmpty) {
      parts.add(locationTextFn(locationId!));
    }
    final summary = parts.join('  ·  ');

    final atom = (locationId != null && locationId!.isNotEmpty)
        ? '(at user $locationId)'
        : null;

    return Semantics(
      label: '$title: $summary',
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        decoration: BoxDecoration(
          color: const Color(0xFF0F172A),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: const Color(0xFF1E293B)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, size: 16, color: accent),
                const SizedBox(width: 7),
                Text(
                  title,
                  style: TextStyle(
                    color: accent,
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 0.5,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              summary,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 16,
                fontWeight: FontWeight.w500,
                letterSpacing: 0.1,
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            if (atom != null) ...[
              const SizedBox(height: 6),
              Text(
                atom,
                style: const TextStyle(
                  color: Color(0xFF94A3B8),
                  fontSize: 14,
                  fontFamily: 'monospace',
                  letterSpacing: 0.3,
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ],
        ),
      ),
    );
  }
}
