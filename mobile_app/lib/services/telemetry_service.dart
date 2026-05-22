import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import '../core/app_config.dart';

/// Client-side telemetry for the end-to-end validation runs.
///
/// Holds the active scenario id (S1 / S2 / S3) and the current turn index
/// — both injected as ``X-Scenario-Id`` / ``X-Turn-Idx`` headers by
/// [ApiService] on every backend request, so the backend telemetry can
/// tag its events. While a turn is active, the service collects
/// per-event timestamps using a single [Stopwatch] anchored at
/// "user input finished" (i.e. mic released or photo submitted) and
/// flushes them as one ``CLIENT`` event posted to ``/api/_client_metric``
/// when the TTS for that turn completes.
///
/// Validation is OFF by default — when [scenarioId] is ``null`` every
/// method is a cheap no-op and the app behaves exactly like before.
class TelemetryService {
  TelemetryService._();
  static final TelemetryService instance = TelemetryService._();

  String? _scenarioId;
  int _turnIdx = 0;

  String? get scenarioId => _scenarioId;
  int get turnIdx => _turnIdx;
  bool get enabled => _scenarioId != null;

  /// Activate a scenario (or pass ``null`` to disable telemetry). Resets the
  /// turn index so each scenario starts at turn 0.
  void setScenario(String? id) {
    _scenarioId = id;
    _turnIdx = 0;
    _resetTurnState();
    debugPrint('[TELEMETRY] scenario=${id ?? "off"}');
  }

  // ---- per-turn state ----
  Stopwatch? _sw;
  String? _turnType; // "voice" | "image" | "init"
  bool _active = false;

  int? _sttStartMs;
  int? _sttEndMs;
  int? _backendReqMs;
  int? _backendResMs;
  int? _photoSubmittedMs;
  int? _ttsCalledMs;
  int? _ttsStartedMs;
  int? _ttsCompletedMs;

  void _resetTurnState() {
    _sw = null;
    _turnType = null;
    _active = false;
    _sttStartMs = null;
    _sttEndMs = null;
    _backendReqMs = null;
    _backendResMs = null;
    _photoSubmittedMs = null;
    _ttsCalledMs = null;
    _ttsStartedMs = null;
    _ttsCompletedMs = null;
  }

  int? _now() => _sw?.elapsedMilliseconds;

  /// Start a new turn. ``type`` is "voice" / "image" / "init". Runs
  /// regardless of whether validation tagging is on, so the backend log
  /// still receives turn data even with the chip in Off: the scenario id
  /// is simply absent on the outgoing payload in that case.
  /// Always ends the previous turn first to avoid orphan stopwatches.
  void startTurn(String type) {
    _resetTurnState();
    _sw = Stopwatch()..start();
    _turnType = type;
    _active = true;
  }

  void markSttStart() { if (_active) _sttStartMs = _now(); }
  void markSttEnd()   { if (_active) _sttEndMs   = _now(); }
  void markBackendRequest()  { if (_active) _backendReqMs = _now(); }
  void markBackendResponse() { if (_active) _backendResMs = _now(); }
  void markPhotoSubmitted()  { if (_active) _photoSubmittedMs = _now(); }
  void markTtsCalled()    { if (_active) _ttsCalledMs    = _now(); }
  void markTtsStarted()   { if (_active) _ttsStartedMs   = _now(); }
  void markTtsCompleted() { if (_active) _ttsCompletedMs = _now(); }

  /// Post a single ``[STT]`` event with the transcribed text, the on-device
  /// latency, and the duration of the captured audio. Always fires (even
  /// when validation is off) so the demo log in the backend terminal
  /// always shows what Whisper transcribed — otherwise STT looks
  /// invisible because it runs on the phone.
  Future<void> logStt(String text, int latencyMs, {int? audioMs}) async {
    final audio = audioMs != null
        ? '  ·  audio=${(audioMs / 1000).toStringAsFixed(1)}s'
        : '';
    final payload = <String, dynamic>{
      'scenario_id': _scenarioId,
      'turn_idx': _turnIdx,
      'category': 'STT',
      'message': "'$text'$audio",
      'duration_ms': latencyMs,
      'fields': {
        'transcription': text,
        'audio_ms': audioMs,
      },
    };
    try {
      await http.post(
        Uri.parse('${AppConfig.baseUrl}/api/_client_metric'),
        headers: const {'Content-Type': 'application/json'},
        body: jsonEncode(payload),
      );
    } catch (e) {
      debugPrint('[TELEMETRY] STT log failed: $e');
    }
  }

  /// Post the collected timestamps for the current turn to the backend
  /// telemetry endpoint and bump [turnIdx]. Fire-and-forget: a network
  /// failure here never affects the user-facing flow. No-op when telemetry
  /// is disabled or no turn is active.
  Future<void> flushTurn() async {
    if (!_active) return;
    final scenario = _scenarioId;
    final turn = _turnIdx;

    final sttMs = (_sttStartMs != null && _sttEndMs != null)
        ? _sttEndMs! - _sttStartMs! : null;
    final backendMs = (_backendReqMs != null && _backendResMs != null)
        ? _backendResMs! - _backendReqMs! : null;
    final ttsStartDelayMs = (_ttsCalledMs != null && _ttsStartedMs != null)
        ? _ttsStartedMs! - _ttsCalledMs! : null;
    final ttsDurationMs = (_ttsStartedMs != null && _ttsCompletedMs != null)
        ? _ttsCompletedMs! - _ttsStartedMs! : null;
    final endToEndMs = _ttsStartedMs;

    final fields = <String, dynamic>{
      'turn_type': _turnType,
      'stt_latency_ms': sttMs,
      'backend_round_trip_ms': backendMs,
      'tts_start_delay_ms': ttsStartDelayMs,
      'tts_duration_ms': ttsDurationMs,
      'end_to_end_ms': endToEndMs,
      'photo_submitted_ms': _photoSubmittedMs,
    }..removeWhere((_, v) => v == null);

    String fmt(int? ms) => ms == null
        ? '—'
        : (ms >= 1000 ? '${(ms / 1000).toStringAsFixed(1)}s' : '${ms}ms');

    final breakdown = StringBuffer()
      ..write('turn ${_turnType ?? "?"} done  ·  ');
    final parts = <String>[];
    if (endToEndMs != null) parts.add('end-to-end ${fmt(endToEndMs)}');
    if (sttMs != null) parts.add('STT ${fmt(sttMs)}');
    if (backendMs != null) parts.add('backend ${fmt(backendMs)}');
    if (ttsStartDelayMs != null) parts.add('TTS-delay ${fmt(ttsStartDelayMs)}');
    if (ttsDurationMs != null) parts.add('TTS-speech ${fmt(ttsDurationMs)}');
    breakdown.write(parts.join('  ·  '));

    final body = <String, dynamic>{
      'scenario_id': scenario,
      'turn_idx': turn,
      'category': 'CLIENT',
      'message': breakdown.toString(),
      'duration_ms': endToEndMs,
      'fields': fields,
    };

    _turnIdx += 1;
    _resetTurnState();

    try {
      await http.post(
        Uri.parse('${AppConfig.baseUrl}/api/_client_metric'),
        headers: const {'Content-Type': 'application/json'},
        body: jsonEncode(body),
      );
    } catch (e) {
      debugPrint('[TELEMETRY] flush failed for $scenario/T$turn: $e');
    }
  }
}
