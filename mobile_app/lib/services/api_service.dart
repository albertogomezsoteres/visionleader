import 'dart:io';
import 'dart:convert';
import 'package:http/http.dart' as http;

import '../core/app_config.dart';
import 'telemetry_service.dart';

class ApiService {
  static String get _base => AppConfig.baseUrl;

  /// Tag every backend call with the active scenario / turn so the backend
  /// telemetry can group its events. When validation mode is off the headers
  /// are simply absent and the request behaves exactly like before.
  static Map<String, String> _telemetryHeaders() {
    final tel = TelemetryService.instance;
    if (!tel.enabled) return const {};
    return {
      'X-Scenario-Id': tel.scenarioId!,
      'X-Turn-Idx': tel.turnIdx.toString(),
    };
  }

  static Map<String, dynamic> _decode(int statusCode, String body) {
    if (statusCode >= 200 && statusCode < 300) {
      return jsonDecode(body) as Map<String, dynamic>;
    }
    String detail;
    try {
      final parsed = jsonDecode(body);
      detail = (parsed as Map)['detail']?.toString() ?? body;
    } catch (_) {
      detail = body;
    }
    return {'success': false, 'error': 'Server error $statusCode: $detail'};
  }

  /// Run the validated VLM prompt named [promptId] on [imageFile].
  /// The mobile FSM derives [promptId] from `expect_photo` in the previous
  /// conversation response, so the backend never has to guess.
  static Future<Map<String, dynamic>> analyzeImage(
    File imageFile,
    String promptId,
  ) async {
    final request = http.MultipartRequest(
      'POST',
      Uri.parse('$_base/api/analyze-image'),
    );
    request.headers.addAll(_telemetryHeaders());
    request.fields['prompt_id'] = promptId;
    request.files.add(
      await http.MultipartFile.fromPath('file', imageFile.path),
    );
    TelemetryService.instance.markBackendRequest();
    final streamed =
        await request.send().timeout(AppConfig.analyzeImageTimeout);
    final body = await streamed.stream.bytesToString();
    TelemetryService.instance.markBackendResponse();
    return _decode(streamed.statusCode, body);
  }

  static Future<Map<String, dynamic>> sendConversationTurn({
    required String sessionId,
    String? userMessage,
    Map<String, dynamic>? imageAnalysis,
  }) async {
    final body = <String, dynamic>{
      'session_id': sessionId,
      'user_message': userMessage ?? '',
    };
    if (imageAnalysis != null) {
      body['image_analysis'] = imageAnalysis;
    }
    final headers = <String, String>{'Content-Type': 'application/json'}
      ..addAll(_telemetryHeaders());
    TelemetryService.instance.markBackendRequest();
    final response = await http
        .post(
          Uri.parse('$_base/api/conversation'),
          headers: headers,
          body: jsonEncode(body),
        )
        .timeout(AppConfig.conversationTimeout);
    TelemetryService.instance.markBackendResponse();
    return _decode(response.statusCode, response.body);
  }

  static Future<Map<String, dynamic>> getGpsRoute({
    required int fromBuilding,
    required int toBuilding,
  }) async {
    final headers = <String, String>{'Content-Type': 'application/json'}
      ..addAll(_telemetryHeaders());
    final response = await http
        .post(
          Uri.parse('$_base/api/gps-route'),
          headers: headers,
          body: jsonEncode(
              {'from_building': fromBuilding, 'to_building': toBuilding}),
        )
        .timeout(AppConfig.gpsRouteTimeout);
    return _decode(response.statusCode, response.body);
  }
}
