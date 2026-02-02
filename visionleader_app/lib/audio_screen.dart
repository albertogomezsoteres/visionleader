import 'dart:io';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_sound/flutter_sound.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:http/http.dart' as http;

class AudioScreen extends StatefulWidget {
  final File imageFile;

  const AudioScreen({super.key, required this.imageFile});

  @override
  State<AudioScreen> createState() => _AudioScreenState();
}

class _AudioScreenState extends State<AudioScreen> {
  final FlutterSoundRecorder _recorder = FlutterSoundRecorder();
  bool isRecording = false;
  String displayedText = "Pulsa el micrófono y formula tu pregunta.";

  static const String baseUrl = "https://your-subdomain.ngrok-free.app";

  @override
  void initState() {
    super.initState();
    _initRecorder();
  }

  Future<void> _initRecorder() async {
    await Permission.microphone.request();
    await _recorder.openRecorder();
  }

  Future<void> _startRecording() async {
    setState(() => isRecording = true);
    await _recorder.startRecorder(
      toFile: 'audio.wav',
      codec: Codec.pcm16WAV,
    );
  }

  Future<void> _stopRecording() async {
    final path = await _recorder.stopRecorder();
    setState(() => isRecording = false);

    if (path != null) {
      await _sendToBackend(File(path));
    }
  }

  // 🔥 AUDIO → TEXTO → PALIGEMMA
  Future<void> _sendToBackend(File audioFile) async {
    try {
      setState(() {
        displayedText = "Procesando tu pregunta...";
      });

      // 1️⃣ TRANSCRIBIR AUDIO
      final transcribeRequest = http.MultipartRequest(
        "POST",
        Uri.parse("$baseUrl/transcribe"),
      );
      transcribeRequest.files.add(
        await http.MultipartFile.fromPath("file", audioFile.path),
      );

      final transcribeResponse = await transcribeRequest.send();
      final transcribeBody =
          await transcribeResponse.stream.bytesToString();
      final transcription = jsonDecode(transcribeBody)["text"];

      // 2️⃣ CONSULTAR PALIGEMMA
      final askRequest = http.MultipartRequest(
        "POST",
        Uri.parse("$baseUrl/ask"),
      );
      askRequest.fields["text"] = transcription;
      askRequest.files.add(
        await http.MultipartFile.fromPath("file", widget.imageFile.path),
      );

      final askResponse = await askRequest.send();
      final askBody = await askResponse.stream.bytesToString();
      final answer = jsonDecode(askBody)["answer"];

      setState(() {
        displayedText = answer;
      });
    } catch (e) {
      setState(() {
        displayedText = "Error al procesar la petición.";
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("VisionLeaderUFV")),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [
            Container(
              padding: const EdgeInsets.all(22),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(20),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.08),
                    blurRadius: 15,
                  ),
                ],
              ),
              child: Text(
                displayedText,
                style: const TextStyle(fontSize: 18),
              ),
            ),
            const SizedBox(height: 50),
            GestureDetector(
              onTap: () {
                isRecording ? _stopRecording() : _startRecording();
              },
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                height: 90,
                width: 90,
                decoration: BoxDecoration(
                  color: isRecording ? Colors.red : const Color(0xFF1E3A8A),
                  shape: BoxShape.circle,
                  boxShadow: [
                    BoxShadow(
                      color: (isRecording
                              ? Colors.red
                              : const Color(0xFF1E3A8A))
                          .withOpacity(0.35),
                      blurRadius: 18,
                    ),
                  ],
                ),
                child: Icon(
                  isRecording ? Icons.stop : Icons.mic,
                  color: Colors.white,
                  size: 42,
                ),
              ),
            ),
            const Spacer(),
          ],
        ),
      ),
    );
  }
}