import 'dart:io';
import 'dart:convert';
import 'package:http/http.dart' as http;

import '../core/app_config.dart';

class ApiService {
  static String get _base => AppConfig.baseUrl;

  static Future<Map<String, dynamic>> analyzeImage(File imageFile) async {
    final request = http.MultipartRequest(
      'POST',
      Uri.parse('$_base/api/analyze-image'),
    );
    request.files.add(
      await http.MultipartFile.fromPath('file', imageFile.path),
    );
    final response =
        await request.send().timeout(AppConfig.analyzeImageTimeout);
    final body = await response.stream.bytesToString();
    return jsonDecode(body) as Map<String, dynamic>;
  }

  static Future<Map<String, dynamic>> transcribeAudio(File audioFile) async {
    final request = http.MultipartRequest(
      'POST',
      Uri.parse('$_base/api/transcribe-audio'),
    );
    request.files.add(
      await http.MultipartFile.fromPath('file', audioFile.path),
    );
    final response =
        await request.send().timeout(AppConfig.transcribeTimeout);
    final body = await response.stream.bytesToString();
    return jsonDecode(body) as Map<String, dynamic>;
  }

  static Future<Map<String, dynamic>> generatePlan({
    required int initialBuilding,
    required int initialFloor,
    int? goalBuilding,
    int? goalFloor,
    String? goalFunctional,
    bool hurryMode = false,
  }) async {
    final body = <String, dynamic>{
      'initial_state': {'building': initialBuilding, 'floor': initialFloor},
      'hurry_mode': hurryMode,
    };
    if (goalFunctional != null) {
      body['goal_functional'] = goalFunctional;
    } else {
      body['goal_state'] = {'building': goalBuilding!, 'floor': goalFloor!};
    }
    final response = await http
        .post(
          Uri.parse('$_base/api/plan'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode(body),
        )
        .timeout(AppConfig.planTimeout);
    return jsonDecode(response.body) as Map<String, dynamic>;
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
    final response = await http
        .post(
          Uri.parse('$_base/api/conversation'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode(body),
        )
        .timeout(AppConfig.conversationTimeout);
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  static Future<Map<String, dynamic>> getGpsRoute({
    required int fromBuilding,
    required int toBuilding,
  }) async {
    final response = await http
        .post(
          Uri.parse('$_base/api/gps-route'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode(
              {'from_building': fromBuilding, 'to_building': toBuilding}),
        )
        .timeout(AppConfig.gpsRouteTimeout);
    return jsonDecode(response.body) as Map<String, dynamic>;
  }
}
