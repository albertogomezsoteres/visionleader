import 'package:flutter/material.dart';
import '../services/telemetry_service.dart';
import 'conversation/conversation_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

// Toggle to surface the Off/S1/S2/S3 chips on the home screen for a
// validation pass. Kept off during demo recordings so the home stays
// clean.
const bool _kShowScenarioChips = false;

class _HomeScreenState extends State<HomeScreen> {
  String? _scenario; // null = validation off

  @override
  void initState() {
    super.initState();
    _scenario = TelemetryService.instance.scenarioId;
  }

  void _selectScenario(String? id) {
    setState(() => _scenario = id);
    TelemetryService.instance.setScenario(id);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF020817), Color(0xFF0F172A), Color(0xFF020817)],
          ),
        ),
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 28),
            child: Column(
              children: [
                const Spacer(flex: 2),

                // Logo
                Container(
                  width: 104,
                  height: 104,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: const LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [Color(0xFF3B82F6), Color(0xFF818CF8)],
                    ),
                    boxShadow: [
                      BoxShadow(
                        color: const Color(0xFF3B82F6).withValues(alpha: 0.35),
                        blurRadius: 40,
                        spreadRadius: 8,
                      ),
                    ],
                  ),
                  child: const Icon(
                    Icons.navigation_rounded,
                    size: 52,
                    color: Colors.white,
                  ),
                ),

                const SizedBox(height: 36),

                // Title - single solid wordmark
                FittedBox(
                  fit: BoxFit.scaleDown,
                  child: const Text(
                    'VisionLeaderUFV',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 38,
                      fontWeight: FontWeight.bold,
                      letterSpacing: -1.0,
                      height: 1.1,
                    ),
                  ),
                ),

                const SizedBox(height: 18),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                  decoration: BoxDecoration(
                    border: Border.all(color: const Color(0xFF1E293B)),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: const Text(
                    'AI Campus Navigation Assistant',
                    style: TextStyle(
                      fontSize: 11,
                      color: Color(0xFF475569),
                      letterSpacing: 0.3,
                    ),
                  ),
                ),

                const Spacer(flex: 2),

                // Feature chips - 2x2 grid of the main technical pillars
                const Column(
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: _FeatureChip(
                              icon: Icons.account_tree_outlined,
                              title: 'Automated Planning',
                              subtitle: 'Fast Downward'),
                        ),
                        SizedBox(width: 12),
                        Expanded(
                          child: _FeatureChip(
                              icon: Icons.visibility_outlined,
                              title: 'Vision-Language',
                              subtitle: 'Gemma 4 E4B-it'),
                        ),
                      ],
                    ),
                    SizedBox(height: 12),
                    Row(
                      children: [
                        Expanded(
                          child: _FeatureChip(
                              icon: Icons.graphic_eq_outlined,
                              title: 'Speech-to-Text',
                              subtitle: 'Whisper Tiny'),
                        ),
                        SizedBox(width: 12),
                        Expanded(
                          child: _FeatureChip(
                              icon: Icons.public_outlined,
                              title: 'Outdoor Routing',
                              subtitle: 'Google Maps'),
                        ),
                      ],
                    ),
                  ],
                ),

                const Spacer(flex: 3),

                // Validation scenario selector. Hidden during demo
                // recordings: flip _kShowScenarioChips to true to bring
                // them back for tagging telemetry events with
                // X-Scenario-Id during a validation pass.
                if (_kShowScenarioChips) ...[
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      _ScenarioChip(label: 'Off', selected: _scenario == null,
                          onTap: () => _selectScenario(null)),
                      const SizedBox(width: 6),
                      _ScenarioChip(label: 'S1', selected: _scenario == 'S1',
                          onTap: () => _selectScenario('S1')),
                      const SizedBox(width: 6),
                      _ScenarioChip(label: 'S2', selected: _scenario == 'S2',
                          onTap: () => _selectScenario('S2')),
                      const SizedBox(width: 6),
                      _ScenarioChip(label: 'S3', selected: _scenario == 'S3',
                          onTap: () => _selectScenario('S3')),
                    ],
                  ),
                  const SizedBox(height: 16),
                ],

                // Start button
                SizedBox(
                  width: double.infinity,
                  height: 64,
                  child: ElevatedButton(
                    onPressed: () {
                      final sessionId =
                          DateTime.now().millisecondsSinceEpoch.toString();
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) =>
                              ConversationScreen(sessionId: sessionId),
                        ),
                      );
                    },
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF3B82F6),
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(18),
                      ),
                      elevation: 0,
                    ),
                    child: const Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.navigation_rounded, size: 22),
                        SizedBox(width: 10),
                        Text(
                          'Start Navigation',
                          style: TextStyle(
                              fontSize: 18, fontWeight: FontWeight.w600),
                        ),
                      ],
                    ),
                  ),
                ),

                const SizedBox(height: 32),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _ScenarioChip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;

  const _ScenarioChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final color = selected ? const Color(0xFF3B82F6) : const Color(0xFF334155);
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(16),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: selected ? color.withValues(alpha: 0.18) : Colors.transparent,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: color, width: selected ? 1.4 : 1.0),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: selected ? Colors.white : const Color(0xFF94A3B8),
            fontSize: 12,
            fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
            letterSpacing: 0.4,
          ),
        ),
      ),
    );
  }
}


class _FeatureChip extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;

  const _FeatureChip({
    required this.icon,
    required this.title,
    required this.subtitle,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
      decoration: BoxDecoration(
        color: const Color(0xFF0F172A),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFF1E293B)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 24, color: const Color(0xFF3B82F6)),
          const SizedBox(height: 10),
          Text(
            title,
            style: const TextStyle(
              color: Color(0xFFE2E8F0),
              fontSize: 14,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.1,
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: 3),
          Text(
            subtitle,
            style: const TextStyle(
              color: Color(0xFF64748B),
              fontSize: 12,
              fontWeight: FontWeight.w500,
              letterSpacing: 0.3,
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }
}
