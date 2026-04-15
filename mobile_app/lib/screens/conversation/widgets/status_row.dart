import 'package:flutter/material.dart';

/// Row of chips showing detected building, floor, and navigation progress.
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
      case 'entrada_principal':
        return 'Main Entrance';
      case 'entrada_cd':
        return 'CD Entrance';
      case 'ascensor':
        return 'Elevator';
      case 'escaleras':
        return 'Stairs';
      case 'bano':
        return 'Restroom';
      case 'lab_ia':
        return 'AI Laboratory';
      case 'despachos':
        return 'Faculty Offices';
      case 'despachos_eps':
        return 'EPS Faculty Offices';
      case 'secretaria':
        return 'Secretary Office';
      case 'sala_mentorias':
        return 'Mentoring Room';
      case 'cafeteria':
        return 'Cafeteria';
      case 'gimnasio':
        return 'Gym';
      default:
        final roomMatch = RegExp(r'^aula_(\d+)_(\d+)$').firstMatch(locationId);
        if (roomMatch != null) {
          return 'Classroom ${roomMatch.group(1)}.${roomMatch.group(2)}';
        }
        return locationId.replaceAll('_', ' ');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _StateSection(
          title: 'Initial State',
          titleColor: const Color(0xFF10B981),
          chips: [
            _StatusChip(
              icon: Icons.business_rounded,
              label: initialBuilding ?? '?',
              isKnown: initialBuilding != null,
            ),
            _StatusChip(
              icon: Icons.layers_rounded,
              label: initialFloor != null ? _floorText(initialFloor!) : '?',
              isKnown: initialFloor != null,
            ),
            if (initialLocationId != null && initialLocationId!.isNotEmpty)
              _StatusChip(
                icon: Icons.place_rounded,
                label: _locationText(initialLocationId!),
                isKnown: true,
              ),
          ],
        ),
        const SizedBox(height: 8),
        _StateSection(
          title: 'Goal State',
          titleColor: const Color(0xFF3B82F6),
          chips: [
            _StatusChip(
              icon: Icons.flag_rounded,
              label: goalBuilding ?? '?',
              isKnown: goalBuilding != null,
            ),
            _StatusChip(
              icon: Icons.layers_rounded,
              label: goalFloor != null ? _floorText(goalFloor!) : '?',
              isKnown: goalFloor != null,
            ),
            if (goalLocationId != null && goalLocationId!.isNotEmpty)
              _StatusChip(
                icon: Icons.place_rounded,
                label: _locationText(goalLocationId!),
                isKnown: true,
              ),
          ],
        ),
      ],
    );
  }
}

class _StateSection extends StatelessWidget {
  final String title;
  final Color titleColor;
  final List<Widget> chips;

  const _StateSection({
    required this.title,
    required this.titleColor,
    required this.chips,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: const Color(0xFF0F172A),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF1E293B)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: TextStyle(
              color: titleColor,
              fontSize: 12,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: chips,
          ),
        ],
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
    return Semantics(
      label: label,
      child: Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
      decoration: BoxDecoration(
        color: isKnown
            ? const Color(0xFF10B981).withValues(alpha: 0.08)
            : const Color(0xFF1E293B),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: isKnown
              ? const Color(0xFF10B981).withValues(alpha: 0.35)
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
              fontSize: 14,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    ));
  }
}
