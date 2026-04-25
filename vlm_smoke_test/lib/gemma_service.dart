// Thin wrapper around flutter_gemma that hides the plugin boilerplate from
// the UI. All methods return plain Dart types. The model file is a single
// .task file downloaded once to the device, then reused across runs.
//
// Note on auth: the .task file lives in a gated HuggingFace repo, so we
// download it manually with a Bearer token (flutter_gemma 0.9.0 does not
// expose an auth header option in its downloader). Once the file is on the
// device, we hand the local path to the plugin via setModelPath.

import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_gemma/flutter_gemma.dart';
import 'package:flutter_gemma/core/model.dart';
import 'package:flutter_gemma/pigeon.g.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';

import 'secrets.dart';

/// One inference result exposed to the UI layer.
class InferenceResult {
  final String prompt;
  final String response;
  final int latencyMs;

  const InferenceResult({
    required this.prompt,
    required this.response,
    required this.latencyMs,
  });
}

/// Coordinates model download, load, and inference against Gemma 3n E2B.
/// Instances are cheap; the heavy state lives inside the underlying plugin.
class GemmaService {
  /// Canonical HuggingFace URL for the INT4-quantised .task file.
  /// Official Google DeepMind LiteRT preview (dynamic_int4). Size ~3.14 GB.
  static const String _modelUrl =
      'https://huggingface.co/google/gemma-3n-E2B-it-litert-preview/resolve/main/gemma-3n-E2B-it-int4.task';

  /// Local filename under the app documents directory.
  static const String _modelFileName = 'gemma-3n-E2B-it-int4.task';

  InferenceModel? _model;

  /// True once the .task file has been downloaded and registered with the
  /// plugin. Checks both the plugin state and the file on disk in case the
  /// app was reinstalled but the file survived on external storage.
  Future<bool> isModelInstalled() async {
    final manager = FlutterGemmaPlugin.instance.modelManager;
    final pluginSaysInstalled = await manager.isModelInstalled;
    if (pluginSaysInstalled) return true;

    final file = await _localModelFile();
    if (await file.exists()) {
      await manager.setModelPath(file.path);
      return true;
    }
    return false;
  }

  /// Downloads the Gemma 3n E2B INT4 checkpoint from HuggingFace.
  /// Single ~3.14 GB file. First-run latency is dominated by the download;
  /// subsequent runs skip it because the file is cached on device storage.
  ///
  /// [onProgress] receives values in [0.0, 1.0].
  Future<void> downloadModel({
    void Function(double progress)? onProgress,
  }) async {
    final file = await _localModelFile();
    if (await file.exists() && (await file.length()) > 1024 * 1024 * 100) {
      // Assume anything over 100 MB is a previously completed download.
      await FlutterGemmaPlugin.instance.modelManager.setModelPath(file.path);
      if (onProgress != null) onProgress(1.0);
      return;
    }

    final request = http.Request('GET', Uri.parse(_modelUrl));
    request.headers['Authorization'] = 'Bearer $hfToken';

    final response = await http.Client().send(request);
    if (response.statusCode != 200) {
      throw Exception(
        'Download failed: HTTP ${response.statusCode}. '
        'Check that the Gemma license is accepted on your HF account '
        'and the token in secrets.dart is valid.',
      );
    }

    final totalBytes = response.contentLength ?? 0;
    int bytesWritten = 0;

    final sink = file.openWrite();
    await for (final chunk in response.stream) {
      sink.add(chunk);
      bytesWritten += chunk.length;
      if (onProgress != null && totalBytes > 0) {
        onProgress(bytesWritten / totalBytes);
      }
    }
    await sink.flush();
    await sink.close();

    await FlutterGemmaPlugin.instance.modelManager.setModelPath(file.path);
    if (onProgress != null) onProgress(1.0);
  }

  /// Loads the model into memory. Safe to call multiple times; the first call
  /// is expensive (tens of seconds), subsequent calls are no-ops.
  Future<void> loadModel() async {
    if (_model != null) return;
    _model = await FlutterGemmaPlugin.instance.createModel(
      modelType: ModelType.gemmaIt,
      // maxTokens is the TOTAL context budget (prompt + image tokens + response),
      // not just the generation cap. A long structured prompt (~700 tokens) plus
      // the image (~257 tokens) plus the response can exceed 1000 tokens easily,
      // so 512 is too tight. 2048 covers every prompt in prompts.dart with
      // generous headroom and has no measurable latency cost on Gemma 3n E2B.
      maxTokens: 2048,
      // GPU backend tested on Pixel 10 Pro: model loads but multimodal
      // inference crashes the app (flutter_gemma 0.9.0 + INT4 + vision
      // combination is unstable; still crashes with 0.13.6 as of 2026-04-23,
      // now after the first inference completes instead of immediately).
      // CPU backend is the stable path here.
      preferredBackend: PreferredBackend.cpu,
      supportImage: true,
    );
  }

  /// Runs one multimodal inference with [prompt] and [imageBytes]. Each call
  /// opens a fresh session and closes it at the end so native MediaPipe
  /// resources are released between runs — otherwise sessions accumulate and
  /// the second inference onwards hangs.
  ///
  /// Returns the raw model response and wall-clock latency. The response is
  /// not parsed — the caller decides what to do with it.
  Future<InferenceResult> infer({
    required String prompt,
    required Uint8List imageBytes,
  }) async {
    if (_model == null) {
      throw StateError('Model not loaded. Call loadModel() first.');
    }

    final stopwatch = Stopwatch()..start();

    // Deterministic decoding (temperature 0, topK 1, fixed seed) so repeated
    // runs on the same image+prompt give identical output and latency numbers
    // stay comparable across the test set.
    final InferenceModelSession session = await _model!.createSession(
      temperature: 0.0,
      randomSeed: 42,
      topK: 1,
      enableVisionModality: true,
    );

    try {
      await session.addQueryChunk(
        Message.withImage(
          text: prompt,
          imageBytes: imageBytes,
          isUser: true,
        ),
      );
      final response = await session.getResponse();
      stopwatch.stop();
      return InferenceResult(
        prompt: prompt,
        response: response.trim(),
        latencyMs: stopwatch.elapsedMilliseconds,
      );
    } finally {
      // Release native resources so the next infer() does not pile up on top
      // of a stale session.
      await session.close();
    }
  }

  /// Absolute path where the downloaded model lives.
  Future<File> _localModelFile() async {
    final dir = await getApplicationDocumentsDirectory();
    return File('${dir.path}/$_modelFileName');
  }
}
