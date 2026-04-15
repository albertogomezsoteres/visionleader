import 'package:flutter/material.dart';

/// Card displayed during outdoor (inter-building) navigation steps. Tells
/// the user that Google Maps is guiding them, and exposes the "I've arrived"
/// confirmation plus a button to re-open the route map.
class OutdoorWalkingCard extends StatelessWidget {
  final String destinationName;
  final VoidCallback onArrived;
  final VoidCallback onReopenMap;

  const OutdoorWalkingCard({
    super.key,
    required this.destinationName,
    required this.onArrived,
    required this.onReopenMap,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF0C2E1F), Color(0xFF0A1F16)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: const Color(0xFF10B981).withValues(alpha: 0.25),
        ),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: const Color(0xFF10B981).withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: const Icon(
                  Icons.directions_walk_rounded,
                  color: Color(0xFF10B981),
                  size: 28,
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Walking to Building $destinationName',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 3),
                    const Text(
                      'Google Maps is guiding you',
                      style: TextStyle(
                        color: Color(0xFF10B981),
                        fontSize: 13,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          SizedBox(
            width: double.infinity,
            height: 54,
            child: ElevatedButton.icon(
              onPressed: onArrived,
              icon: const Icon(
                Icons.check_circle_outline_rounded,
                size: 22,
              ),
              label: const Text(
                "I've arrived",
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                ),
              ),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF10B981),
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14),
                ),
                elevation: 0,
              ),
            ),
          ),
          const SizedBox(height: 10),
          SizedBox(
            width: double.infinity,
            height: 40,
            child: TextButton.icon(
              onPressed: onReopenMap,
              icon: const Icon(Icons.map_outlined, size: 16),
              label: const Text(
                'Re-open route map',
                style: TextStyle(fontSize: 13),
              ),
              style: TextButton.styleFrom(
                foregroundColor:
                    const Color(0xFF10B981).withValues(alpha: 0.8),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
