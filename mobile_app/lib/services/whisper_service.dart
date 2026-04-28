import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';

/// On-device speech-to-text service backed by `whisper-server` (whisper.cpp).
///
/// At [init] the service:
///   1. Copies the bundled `ggml-tiny-q5_0.bin` from app assets to the app's
///      file system (whisper-server cannot read from inside the APK).
///   2. Locates the bundled `libwhisper-server.so` via the platform channel
///      `visionleader/native`, where Android's package manager has unpacked
///      it as an executable file.
///   3. Spawns the binary as a subprocess listening on `127.0.0.1:8080`.
///   4. Warms up the model with a 5-second silent WAV so the first real
///      transcription does not pay the model-load cost.
///
/// [transcribe] then POSTs WAV files to `/inference` and returns the cleaned
/// text. The hallucination filter rejects loops and absurdly long outputs
/// that whisper.cpp occasionally produces on short or noisy audio.
class WhisperService {
  WhisperService._();
  static final WhisperService instance = WhisperService._();

  static const _channel = MethodChannel('visionleader/native');
  static const _modelAsset = 'assets/models/ggml-tiny-q5_0.bin';
  static const _serverHost = '127.0.0.1';
  static const _serverPort = 8080;

  /// Bias whisper towards campus vocabulary so room codes and POI names are
  /// transcribed correctly. Same prompt the on-device validation harness
  /// (`whisper_smoke_test`) used to reach its accuracy numbers.
  static const _domainPrompt =
      'UFV campus navigation assistant. '
      'classroom 0.1, classroom 0.3, classroom 1.1, classroom 1.4, classroom 2.1, '
      'building G, building CD, '
      'main entrance, ground floor, first floor, second floor, floor 1, floor 2, '
      'elevator, stairs, cafeteria, gym, restroom, '
      'AI laboratory, mentoring room, EPS faculty offices, secretary office, directory sign, '
      'I want to go to, take me to, I am in, I am at, I am next to, I am lost, '
      'yes, no, repeat, cancel, stop, done, '
      'I am in a hurry, I have arrived, my destination, the doors are open.';

  Process? _server;
  Future<void>? _initFuture;

  Future<void> init() {
    return _initFuture ??= _startOnce();
  }

  Future<void> _startOnce() async {
    final modelPath = await _materializeAsset(_modelAsset, 'ggml-tiny-q5_0.bin');
    final serverBin = await _findServerBinary();
    final nativeDir = File(serverBin).parent.path;

    _server = await Process.start(
      serverBin,
      [
        '-m', modelPath,
        '--host', _serverHost,
        '--port', _serverPort.toString(),
        '-l', 'en',
        '-bs', '1', '-bo', '1',
        '-nf',
      ],
      environment: {'LD_LIBRARY_PATH': nativeDir},
      includeParentEnvironment: true,
    );

    // Drain stdout/stderr so the OS pipe buffers do not fill up and stall the
    // subprocess. Drop the data — we only care that the socket comes up.
    _server!.stdout.transform(const SystemEncoding().decoder).listen((_) {});
    _server!.stderr.transform(const SystemEncoding().decoder).listen((_) {});

    var processExited = false;
    unawaited(_server!.exitCode.then((_) => processExited = true));

    final deadline = DateTime.now().add(const Duration(seconds: 30));
    while (DateTime.now().isBefore(deadline)) {
      if (processExited) {
        throw StateError('whisper-server exited before accepting connections');
      }
      try {
        final socket = await Socket.connect(
          _serverHost, _serverPort,
          timeout: const Duration(milliseconds: 500),
        );
        await socket.close();
        await _warmup();
        return;
      } catch (_) {
        await Future.delayed(const Duration(milliseconds: 500));
      }
    }
    throw StateError('whisper-server did not bind in 30 s');
  }

  Future<void> _warmup() async {
    final dir = await getTemporaryDirectory();
    final wav = File('${dir.path}/whisper_warmup.wav');
    if (!wav.existsSync()) {
      await wav.writeAsBytes(_silentWav(durationSeconds: 5));
    }
    try {
      await _postInference(wav.path);
    } catch (_) {
      // First inference may still be starting up; ignore warmup errors.
    }
  }

  /// Run the model on [audio] (16 kHz mono WAV) and return the recognised text.
  /// Returns an empty string when whisper.cpp produces a hallucinated loop.
  Future<String> transcribe(File audio) async {
    await init();
    final size = await audio.length();
    debugPrint('[STT] file=${audio.path.split('/').last} size=$size bytes');
    final stopwatch = Stopwatch()..start();
    final raw = await _postInference(audio.path);
    final elapsed = stopwatch.elapsedMilliseconds / 1000;
    final cleaned = raw.trim();
    debugPrint('[STT][RAW] ${cleaned.isEmpty ? "<empty>" : cleaned}  (${elapsed.toStringAsFixed(2)}s)');
    if (_isHallucination(cleaned)) {
      debugPrint('[STT][REJECTED] hallucination filter triggered');
      return '';
    }
    return cleaned;
  }

  Future<String> _postInference(String audioPath) async {
    final uri = Uri.parse('http://$_serverHost:$_serverPort/inference');
    final req = http.MultipartRequest('POST', uri);
    req.files.add(await http.MultipartFile.fromPath('file', audioPath));
    req.fields['response_format'] = 'text';
    req.fields['prompt'] = _domainPrompt;
    req.fields['temperature'] = '0.0';

    final streamed = await req.send();
    final body = await streamed.stream.bytesToString();
    if (streamed.statusCode != 200) {
      throw HttpException('whisper-server HTTP ${streamed.statusCode}: $body');
    }
    return body;
  }

  Future<String> _materializeAsset(String assetPath, String filename) async {
    final dir = await getTemporaryDirectory();
    final file = File('${dir.path}/$filename');
    if (!file.existsSync()) {
      final bytes = await rootBundle.load(assetPath);
      await file.writeAsBytes(bytes.buffer.asUint8List());
    }
    return file.path;
  }

  Future<String> _findServerBinary() async {
    const binary = 'libwhisper-server.so';
    final dir = await _channel.invokeMethod<String>('getNativeLibraryDir');
    if (dir == null) {
      throw StateError('getNativeLibraryDir returned null');
    }
    final path = '$dir/$binary';
    if (!File(path).existsSync()) {
      throw StateError('whisper-server not found at $path');
    }
    return path;
  }

  /// Detect repetitive or absurdly long outputs that whisper.cpp produces
  /// on near-silent or out-of-distribution audio. Mirrors the heuristic the
  /// previous server-side router applied so the FSM sees the same shape of
  /// rejection.
  bool _isHallucination(String text) {
    if (text.isEmpty) return false;
    final words = text.toLowerCase().split(RegExp(r'\s+'));
    if (words.length < 4) return false;

    if (words.length >= 10) {
      final trigrams = <String>[
        for (var i = 0; i <= words.length - 3; i++)
          '${words[i]} ${words[i + 1]} ${words[i + 2]}',
      ];
      final uniqueRatio = trigrams.toSet().length / trigrams.length;
      if (uniqueRatio < 0.25) return true;
    }

    final counts = <String, int>{};
    for (final w in words) {
      counts[w] = (counts[w] ?? 0) + 1;
    }
    final topCount = counts.values.fold<int>(0, (a, b) => a > b ? a : b);
    if (topCount > words.length * 0.6 && words.length > 6) return true;

    if (words.length > 60) return true;
    return false;
  }

  /// Build a silent 16 kHz mono 16-bit PCM WAV of [durationSeconds].
  Uint8List _silentWav({required int durationSeconds}) {
    const sampleRate = 16000;
    final numSamples = sampleRate * durationSeconds;
    final dataSize = numSamples * 2;
    final totalSize = 44 + dataSize;

    final b = BytesBuilder();
    b.add([0x52, 0x49, 0x46, 0x46]);  // RIFF
    b.add(_le32(totalSize - 8));
    b.add([0x57, 0x41, 0x56, 0x45]);  // WAVE
    b.add([0x66, 0x6d, 0x74, 0x20]);  // fmt␠
    b.add(_le32(16));
    b.add(_le16(1));                  // PCM
    b.add(_le16(1));                  // mono
    b.add(_le32(sampleRate));
    b.add(_le32(sampleRate * 2));     // byte rate
    b.add(_le16(2));                  // block align
    b.add(_le16(16));                 // bits per sample
    b.add([0x64, 0x61, 0x74, 0x61]);  // data
    b.add(_le32(dataSize));
    b.add(Uint8List(dataSize));
    return b.toBytes();
  }

  List<int> _le16(int v) => [v & 0xff, (v >> 8) & 0xff];
  List<int> _le32(int v) =>
      [v & 0xff, (v >> 8) & 0xff, (v >> 16) & 0xff, (v >> 24) & 0xff];
}
