import 'dart:io';
import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiService {
  // 10.0.2.2 maps to localhost on the host machine from Android emulator
  static const String baseUrl = 'http://10.0.2.2:8000';

  static Future<Map<String, dynamic>> analyzeImage(File imageFile) async {
    final request = http.MultipartRequest(
      'POST',
      Uri.parse('$baseUrl/api/analyze-image'),
    );
    request.files.add(
      await http.MultipartFile.fromPath('file', imageFile.path),
    );
    final response =
        await request.send().timeout(const Duration(seconds: 60));
    final body = await response.stream.bytesToString();
    return jsonDecode(body) as Map<String, dynamic>;
  }

  static Future<Map<String, dynamic>> transcribeAudio(File audioFile) async {
    final request = http.MultipartRequest(
      'POST',
      Uri.parse('$baseUrl/api/transcribe-audio'),
    );
    request.files.add(
      await http.MultipartFile.fromPath('file', audioFile.path),
    );
    final response =
        await request.send().timeout(const Duration(seconds: 45));
    final body = await response.stream.bytesToString();
    return jsonDecode(body) as Map<String, dynamic>;
  }

  static Future<Map<String, dynamic>> generatePlan({
    required int initialBuilding,
    required int initialFloor,
    int? goalBuilding,
    int? goalFloor,
    String? goalFunctional,
    bool humanoDisponible = true,
  }) async {
    final body = <String, dynamic>{
      'initial_state': {'building': initialBuilding, 'floor': initialFloor},
      'humano_disponible': humanoDisponible,
    };
    if (goalFunctional != null) {
      body['goal_functional'] = goalFunctional;
    } else {
      body['goal_state'] = {'building': goalBuilding!, 'floor': goalFloor!};
    }
    final response = await http
        .post(
          Uri.parse('$baseUrl/api/plan'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode(body),
        )
        .timeout(const Duration(seconds: 60));
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
          Uri.parse('$baseUrl/api/conversation'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode(body),
        )
        .timeout(const Duration(seconds: 30));
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  static Future<Map<String, dynamic>> getGpsRoute({
    required int fromBuilding,
    required int toBuilding,
  }) async {
    final response = await http
        .post(
          Uri.parse('$baseUrl/api/gps-route'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode(
              {'from_building': fromBuilding, 'to_building': toBuilding}),
        )
        .timeout(const Duration(seconds: 15));
    return jsonDecode(response.body) as Map<String, dynamic>;
  }
}
