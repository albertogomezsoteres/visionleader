import 'package:flutter/material.dart';

/// Row of chips showing detected building, floor, and navigation progress.
class StatusRow extends StatelessWidget {
  final String? knownBuilding;
  final int? knownFloor;
  final String? knownLocationId;
  final bool isNavigating;
  final int currentStep;
  final int totalSteps;

  const StatusRow({
    super.key,
    required this.knownBuilding,
    required this.knownFloor,
    required this.knownLocationId,
    required this.isNavigating,
    required this.currentStep,
    required this.totalSteps,
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
    return Row(
      children: [
        Expanded(
          child: Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              _StatusChip(
                icon: Icons.business_rounded,
                label: knownBuilding ?? '?',
                isKnown: knownBuilding != null,
              ),
              _StatusChip(
                icon: Icons.layers_rounded,
                label: knownFloor != null ? _floorText(knownFloor!) : '?',
                isKnown: knownFloor != null,
              ),
              if (knownLocationId != null && knownLocationId!.isNotEmpty)
                _StatusChip(
                  icon: Icons.place_rounded,
                  label: _locationText(knownLocationId!),
                  isKnown: true,
                ),
            ],
          ),
        ),
        if (isNavigating && totalSteps > 0) ...[
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
            decoration: BoxDecoration(
              color: const Color(0xFF3B82F6).withValues(alpha: 0.10),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(
                  color: const Color(0xFF3B82F6).withValues(alpha: 0.35)),
            ),
            child: Text(
              'Step $currentStep / $totalSteps',
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
              fontSize: 13,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }
}
