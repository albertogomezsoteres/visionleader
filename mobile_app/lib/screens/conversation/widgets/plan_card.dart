import 'package:flutter/material.dart';

/// Compact card that surfaces the raw PDDL plan emitted by Fast Downward.
///
/// The TTS layer reads the friendly merged steps; this card sits beside
/// the conversation bubble so the user (or anyone watching the demo)
/// can see what the symbolic planner actually produced — action-level,
/// with the per-action and total costs that drove the choice. Hidden
/// when no plan is active.
class PlanCard extends StatefulWidget {
  final List<String> actions;
  final int totalCost;
  final double? searchTimeS;
  final int? currentStepIdx;
  /// Fires after the user toggles the expand chevron, so the parent can
  /// reclaim the conversation bubble's vertical slot when the plan grows.
  final void Function(bool expanded)? onExpansionChanged;

  const PlanCard({
    super.key,
    required this.actions,
    required this.totalCost,
    this.searchTimeS,
    this.currentStepIdx,
    this.onExpansionChanged,
  });

  @override
  State<PlanCard> createState() => _PlanCardState();
}

class _PlanCardState extends State<PlanCard> {
  bool _expanded = false;

  static const _accent = Color(0xFFA78BFA);

  /// Strip the trailing ``"(N)"`` cost annotation Fast Downward appends
  /// and return ``(verb, args, cost)``.
  ({String verb, String args, int? cost}) _parse(String raw) {
    final s = raw.trim();
    final m = RegExp(r'^(.*?)\s*\((\d+)\)\s*$').firstMatch(s);
    final body = m != null ? m.group(1)!.trim() : s;
    final cost = m != null ? int.tryParse(m.group(2)!) : null;
    final parts = body.split(RegExp(r'\s+'));
    final verb = parts.isNotEmpty ? parts.first : body;
    // Drop the leading "user" agent token so the visible args are just nodes.
    final argParts = parts.length > 2 && parts[1] == 'user'
        ? parts.sublist(2)
        : parts.skip(1).toList();
    final args = argParts.join(' → ');
    return (verb: verb, args: args, cost: cost);
  }

  @override
  Widget build(BuildContext context) {
    if (widget.actions.isEmpty) return const SizedBox.shrink();

    final summary = StringBuffer()
      ..write('${widget.actions.length} actions  ·  cost ${widget.totalCost}');
    if (widget.searchTimeS != null) {
      final ms = (widget.searchTimeS! * 1000).round();
      summary.write('  ·  $ms ms');
    }

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
      decoration: BoxDecoration(
        color: const Color(0xFF0F172A),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF1E293B)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          InkWell(
            onTap: () {
              setState(() => _expanded = !_expanded);
              widget.onExpansionChanged?.call(_expanded);
            },
            borderRadius: BorderRadius.circular(8),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 2),
              child: Row(
                children: [
                  const Icon(Icons.account_tree_rounded,
                      size: 16, color: _accent),
                  const SizedBox(width: 7),
                  const Text(
                    'Symbolic Plan',
                    style: TextStyle(
                      color: _accent,
                      fontSize: 13,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 0.5,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      summary.toString(),
                      style: const TextStyle(
                        color: Color(0xFF94A3B8),
                        fontSize: 12,
                        fontWeight: FontWeight.w500,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  Icon(
                    _expanded
                        ? Icons.keyboard_arrow_up_rounded
                        : Icons.keyboard_arrow_down_rounded,
                    color: const Color(0xFF94A3B8),
                    size: 18,
                  ),
                ],
              ),
            ),
          ),
          if (_expanded) ...[
            const SizedBox(height: 8),
            ConstrainedBox(
              constraints: const BoxConstraints(maxHeight: 220),
              child: SingleChildScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: List.generate(widget.actions.length, (i) {
                    final p = _parse(widget.actions[i]);
                    final num = (i + 1).toString().padLeft(2, ' ');
                    return Padding(
                      padding: const EdgeInsets.symmetric(vertical: 3),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.center,
                        children: [
                          SizedBox(
                            width: 22,
                            child: Text(
                              '$num.',
                              style: const TextStyle(
                                color: Color(0xFF64748B),
                                fontSize: 11,
                                fontFamily: 'monospace',
                              ),
                            ),
                          ),
                          Expanded(
                            child: RichText(
                              text: TextSpan(
                                style: const TextStyle(
                                  fontSize: 11,
                                  fontFamily: 'monospace',
                                  height: 1.35,
                                ),
                                children: [
                                  TextSpan(
                                    text: p.verb,
                                    style: const TextStyle(
                                      color: _accent,
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                  if (p.args.isNotEmpty)
                                    TextSpan(
                                      text: '  ${p.args}',
                                      style: const TextStyle(
                                        color: Color(0xFFCBD5E1),
                                      ),
                                    ),
                                ],
                              ),
                              softWrap: true,
                            ),
                          ),
                          if (p.cost != null) ...[
                            const SizedBox(width: 8),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 6, vertical: 1),
                              decoration: BoxDecoration(
                                color: _accent.withValues(alpha: 0.12),
                                borderRadius: BorderRadius.circular(6),
                                border: Border.all(
                                    color: _accent.withValues(alpha: 0.35)),
                              ),
                              child: Text(
                                '${p.cost}',
                                style: const TextStyle(
                                  color: _accent,
                                  fontSize: 10,
                                  fontWeight: FontWeight.w600,
                                  fontFamily: 'monospace',
                                ),
                              ),
                            ),
                          ],
                        ],
                      ),
                    );
                  }),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
