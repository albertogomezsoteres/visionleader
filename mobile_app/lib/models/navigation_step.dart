import 'package:flutter/material.dart';

enum StepType {
  outdoorWalk,
  elevatorRequest,
  elevatorUse,
  stairsPrepare,
  stairsUp,
  stairsDown,
}

class NavigationStep {
  final StepType type;
  final String instruction;
  final String rawAction;
  final IconData icon;
  final Color accentColor;
  bool isCompleted;

  // Only for outdoor steps
  final int? fromBuildingId;
  final int? toBuildingId;

  NavigationStep({
    required this.type,
    required this.instruction,
    required this.rawAction,
    required this.icon,
    required this.accentColor,
    this.isCompleted = false,
    this.fromBuildingId,
    this.toBuildingId,
  });

  bool get isOutdoor => type == StepType.outdoorWalk;

  // ----- Parsing helpers -----

  static int? _extractBuildingId(String token) {
    final m = RegExp(r'edificio_(\d+)').firstMatch(token);
    return m != null ? int.tryParse(m.group(1)!) : null;
  }

  static int? _extractFloor(String token) {
    // handles planta_m1 or planta_-1 for basement
    final neg = RegExp(r'planta_(?:m|-)(\d+)').firstMatch(token);
    if (neg != null) return -(int.tryParse(neg.group(1)!) ?? 0);
    final pos = RegExp(r'planta_(\d+)').firstMatch(token);
    return pos != null ? int.tryParse(pos.group(1)!) : null;
  }

  static String _bn(int? id) {
    const names = {1: 'EPS', 2: 'CD', 3: 'H'};
    return names[id] ?? 'Building ${id ?? '?'}';
  }

  static String _fn(int? floor) {
    if (floor == null) return 'unknown floor';
    if (floor == -1) return 'Basement';
    if (floor == 0) return 'Ground Floor';
    if (floor == 1) return '1st Floor';
    if (floor == 2) return '2nd Floor';
    if (floor == 3) return '3rd Floor';
    return 'Floor $floor';
  }

  // ----- Factory from PDDL action string -----

  factory NavigationStep.fromRawAction(String rawAction) {
    final parts = rawAction.toLowerCase().trim().split(RegExp(r'\s+'));
    final action = parts.isNotEmpty ? parts[0] : '';

    switch (action) {
      case 'mover_edificio':
        // mover_edificio robot1 edificio_origen edificio_destino planta tipo
        final from = parts.length > 2 ? _extractBuildingId(parts[2]) : null;
        final to = parts.length > 3 ? _extractBuildingId(parts[3]) : null;
        return NavigationStep(
          type: StepType.outdoorWalk,
          instruction:
              'Walk outdoors from ${_bn(from)} to ${_bn(to)} — follow the outdoor route on the map',
          rawAction: rawAction,
          icon: Icons.directions_walk,
          accentColor: const Color(0xFFF59E0B),
          fromBuildingId: from,
          toBuildingId: to,
        );

      case 'pedir_ayuda_ascensor':
        // pedir_ayuda_ascensor robot1 edificio_X planta_Y
        final b = parts.length > 2 ? _extractBuildingId(parts[2]) : null;
        final f = parts.length > 3 ? _extractFloor(parts[3]) : null;
        return NavigationStep(
          type: StepType.elevatorRequest,
          instruction:
              'Request elevator assistance in ${_bn(b)} at ${_fn(f)}',
          rawAction: rawAction,
          icon: Icons.elevator_outlined,
          accentColor: const Color(0xFF818CF8),
        );

      case 'usar_ascensor':
        // usar_ascensor robot1 edificio_X planta_Y planta_Z elevator
        final b = parts.length > 2 ? _extractBuildingId(parts[2]) : null;
        final from = parts.length > 3 ? _extractFloor(parts[3]) : null;
        final to = parts.length > 4 ? _extractFloor(parts[4]) : null;
        return NavigationStep(
          type: StepType.elevatorUse,
          instruction:
              'Take the elevator in ${_bn(b)} from ${_fn(from)} to ${_fn(to)}',
          rawAction: rawAction,
          icon: Icons.elevator,
          accentColor: const Color(0xFF3B82F6),
        );

      case 'preparar_escaleras':
        // preparar_escaleras robot1 edificio_X planta_Y
        final b = parts.length > 2 ? _extractBuildingId(parts[2]) : null;
        final f = parts.length > 3 ? _extractFloor(parts[3]) : null;
        return NavigationStep(
          type: StepType.stairsPrepare,
          instruction: 'Locate the stairs in ${_bn(b)} at ${_fn(f)}',
          rawAction: rawAction,
          icon: Icons.stairs_outlined,
          accentColor: const Color(0xFF10B981),
        );

      case 'subir_escaleras':
        // subir_escaleras robot1 edificio_X planta_Y planta_Z stairs
        final b = parts.length > 2 ? _extractBuildingId(parts[2]) : null;
        final from = parts.length > 3 ? _extractFloor(parts[3]) : null;
        final to = parts.length > 4 ? _extractFloor(parts[4]) : null;
        return NavigationStep(
          type: StepType.stairsUp,
          instruction:
              'Go up the stairs in ${_bn(b)} from ${_fn(from)} to ${_fn(to)}',
          rawAction: rawAction,
          icon: Icons.arrow_upward,
          accentColor: const Color(0xFF10B981),
        );

      case 'bajar_escaleras':
        // bajar_escaleras robot1 edificio_X planta_Y planta_Z stairs
        final b = parts.length > 2 ? _extractBuildingId(parts[2]) : null;
        final from = parts.length > 3 ? _extractFloor(parts[3]) : null;
        final to = parts.length > 4 ? _extractFloor(parts[4]) : null;
        return NavigationStep(
          type: StepType.stairsDown,
          instruction:
              'Go down the stairs in ${_bn(b)} from ${_fn(from)} to ${_fn(to)}',
          rawAction: rawAction,
          icon: Icons.arrow_downward,
          accentColor: const Color(0xFF10B981),
        );

      case 'verificar_seguridad_escaleras':
        // verificar_seguridad_escaleras robot1 edificio_X planta_Y
        final b = parts.length > 2 ? _extractBuildingId(parts[2]) : null;
        final f = parts.length > 3 ? _extractFloor(parts[3]) : null;
        return NavigationStep(
          type: StepType.stairsPrepare,
          instruction: 'Check stairs safety in ${_bn(b)} at ${_fn(f)}',
          rawAction: rawAction,
          icon: Icons.stairs_outlined,
          accentColor: const Color(0xFF10B981),
        );

      default:
        return NavigationStep(
          type: StepType.stairsPrepare,
          instruction: rawAction,
          rawAction: rawAction,
          icon: Icons.navigation,
          accentColor: const Color(0xFF94A3B8),
        );
    }
  }
}
