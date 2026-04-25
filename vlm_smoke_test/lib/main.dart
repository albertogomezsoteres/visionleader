// Smoke test app for on-device Gemma 3n E2B INT4.
//
// Flow:
//   1. User taps "Download model" (first run only, ~3 GB, needs WiFi + HF token).
//   2. User taps "Load model into memory".
//   3. User picks an image from the Pixel gallery.
//   4. User picks one of the 5 canonical prompts (Stage 1 classifier or one
//      of the 4 stage-2 prompts for sign / door / elevator / stairs).
//   5. Tap "Run" -> the raw model response and wall-clock latency are shown
//      and appended to the run history.
//
// The history can be exported as CSV for later analysis.

import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:path_provider/path_provider.dart';

import 'gemma_service.dart';
import 'prompts.dart';

void main() {
  runApp(const VlmSmokeTestApp());
}

class VlmSmokeTestApp extends StatelessWidget {
  const VlmSmokeTestApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'VLM Smoke Test',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.teal),
        useMaterial3: true,
      ),
      home: const HomeScreen(),
    );
  }
}

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

enum _AppStage { idle, downloading, ready, inferring }

class _HistoryEntry {
  final String imageName;
  final String promptId;
  final String response;
  final int latencyMs;
  const _HistoryEntry({
    required this.imageName,
    required this.promptId,
    required this.response,
    required this.latencyMs,
  });
}

class _HomeScreenState extends State<HomeScreen> {
  final GemmaService _gemma = GemmaService();
  final ImagePicker _picker = ImagePicker();

  _AppStage _stage = _AppStage.idle;
  double _downloadProgress = 0.0;
  String? _statusMessage;

  XFile? _selectedImage;
  Uint8List? _selectedImageBytes;
  NamedPrompt _selectedPrompt = kPrompts.first;

  final List<_HistoryEntry> _history = [];

  @override
  void initState() {
    super.initState();
    _checkModelInstalled();
  }

  Future<void> _checkModelInstalled() async {
    final installed = await _gemma.isModelInstalled();
    if (installed) {
      setState(() => _statusMessage =
          'Model file present on device. Tap "Load model".');
    } else {
      setState(() => _statusMessage =
          'Model not downloaded yet. Tap "Download model".');
    }
  }

  Future<void> _downloadModel() async {
    setState(() {
      _stage = _AppStage.downloading;
      _downloadProgress = 0.0;
      _statusMessage = 'Downloading ~3.14 GB from HuggingFace...';
    });
    try {
      await _gemma.downloadModel(onProgress: (p) {
        setState(() => _downloadProgress = p);
      });
      setState(() {
        _stage = _AppStage.idle;
        _statusMessage = 'Download complete. Tap "Load model".';
      });
    } catch (e) {
      setState(() {
        _stage = _AppStage.idle;
        _statusMessage = 'Download failed: $e';
      });
    }
  }

  Future<void> _loadModel() async {
    setState(() => _statusMessage = 'Loading model into memory...');
    try {
      await _gemma.loadModel();
      setState(() {
        _stage = _AppStage.ready;
        _statusMessage =
            'Model loaded. Pick an image and a prompt, then tap "Run".';
      });
    } catch (e) {
      setState(() => _statusMessage = 'Load failed: $e');
    }
  }

  Future<void> _pickImage() async {
    // Resize at pick time so the JPEG we feed into flutter_gemma is already
    // small. The plugin downscales to 512x512 internally before the vision
    // encoder, so any larger resolution only adds JPEG-decode work. 1024
    // leaves some headroom without affecting model output.
    final picked = await _picker.pickImage(
      source: ImageSource.gallery,
      maxWidth: 1024,
      maxHeight: 1024,
    );
    if (picked == null) return;
    final bytes = await picked.readAsBytes();
    setState(() {
      _selectedImage = picked;
      _selectedImageBytes = bytes;
    });
  }

  Future<void> _runInference() async {
    if (_selectedImageBytes == null) return;
    setState(() {
      _stage = _AppStage.inferring;
      _statusMessage = 'Running inference...';
    });
    try {
      final result = await _gemma.infer(
        prompt: _selectedPrompt.prompt,
        imageBytes: _selectedImageBytes!,
      );
      final entry = _HistoryEntry(
        imageName: _selectedImage?.name ?? 'unknown',
        promptId: _selectedPrompt.id,
        response: result.response,
        latencyMs: result.latencyMs,
      );
      setState(() {
        _stage = _AppStage.ready;
        _history.insert(0, entry);
        _statusMessage = 'Done in ${result.latencyMs} ms.';
      });
    } catch (e) {
      setState(() {
        _stage = _AppStage.ready;
        _statusMessage = 'Inference failed: $e';
      });
    }
  }

  Future<void> _exportCsv() async {
    if (_history.isEmpty) return;
    final dir = await getApplicationDocumentsDirectory();
    final file = File('${dir.path}/vlm_smoke_test_history.csv');
    final buffer = StringBuffer('image,prompt_id,latency_ms,response\n');
    for (final e in _history.reversed) {
      final safeResponse =
          e.response.replaceAll('\n', ' ').replaceAll(',', ';');
      buffer.writeln(
          '${e.imageName},${e.promptId},${e.latencyMs},"$safeResponse"');
    }
    await file.writeAsString(buffer.toString());
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('CSV saved to ${file.path}')),
    );
  }

  @override
  Widget build(BuildContext context) {
    final canInfer =
        _stage == _AppStage.ready && _selectedImageBytes != null;

    return Scaffold(
      appBar: AppBar(
        title: const Text('VLM Smoke Test - Gemma 3n E2B INT4'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _buildStatusCard(),
            const SizedBox(height: 16),
            _buildSetupButtons(),
            const SizedBox(height: 16),
            _buildImageSection(),
            const SizedBox(height: 16),
            _buildPromptSelector(),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: canInfer ? _runInference : null,
              icon: const Icon(Icons.play_arrow),
              label: Text(_stage == _AppStage.inferring
                  ? 'Inferring...'
                  : 'Run inference'),
            ),
            const SizedBox(height: 24),
            _buildHistorySection(),
          ],
        ),
      ),
    );
  }

  Widget _buildStatusCard() {
    return Card(
      color: Theme.of(context).colorScheme.surfaceContainerHighest,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.info_outline, size: 18),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    _statusMessage ?? '...',
                    style: const TextStyle(fontWeight: FontWeight.w500),
                  ),
                ),
              ],
            ),
            if (_stage == _AppStage.downloading) ...[
              const SizedBox(height: 8),
              LinearProgressIndicator(value: _downloadProgress),
              Text('${(_downloadProgress * 100).toStringAsFixed(1)}%'),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildSetupButtons() {
    return Row(
      children: [
        Expanded(
          child: OutlinedButton.icon(
            onPressed:
                _stage == _AppStage.downloading ? null : _downloadModel,
            icon: const Icon(Icons.cloud_download_outlined),
            label: const Text('Download model'),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: OutlinedButton.icon(
            onPressed: (_stage == _AppStage.idle) ? _loadModel : null,
            icon: const Icon(Icons.memory),
            label: const Text('Load model'),
          ),
        ),
      ],
    );
  }

  Widget _buildImageSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        OutlinedButton.icon(
          onPressed: _pickImage,
          icon: const Icon(Icons.photo_library_outlined),
          label: const Text('Pick image from gallery'),
        ),
        const SizedBox(height: 8),
        if (_selectedImageBytes != null)
          ClipRRect(
            borderRadius: BorderRadius.circular(8),
            child: Image.memory(
              _selectedImageBytes!,
              height: 220,
              fit: BoxFit.cover,
            ),
          ),
        if (_selectedImage != null)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(
              _selectedImage!.name,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
      ],
    );
  }

  Widget _buildPromptSelector() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Prompt',
                style: TextStyle(fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            DropdownButton<NamedPrompt>(
              isExpanded: true,
              value: _selectedPrompt,
              onChanged: (v) {
                if (v != null) setState(() => _selectedPrompt = v);
              },
              items: [
                for (final p in kPrompts)
                  DropdownMenuItem(value: p, child: Text(p.label)),
              ],
            ),
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.surfaceContainerHigh,
                borderRadius: BorderRadius.circular(6),
              ),
              child: Text(
                _selectedPrompt.prompt,
                style:
                    const TextStyle(fontFamily: 'monospace', fontSize: 12),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHistorySection() {
    if (_history.isEmpty) {
      return const Padding(
        padding: EdgeInsets.all(12),
        child: Text('No runs yet.', textAlign: TextAlign.center),
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            Text('Run history (${_history.length})',
                style: Theme.of(context).textTheme.titleMedium),
            const Spacer(),
            TextButton.icon(
              onPressed: _exportCsv,
              icon: const Icon(Icons.download),
              label: const Text('Export CSV'),
            ),
          ],
        ),
        const SizedBox(height: 8),
        for (final entry in _history) _buildHistoryCard(entry),
      ],
    );
  }

  Widget _buildHistoryCard(_HistoryEntry e) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Chip(
                  label: Text(e.promptId),
                  visualDensity: VisualDensity.compact,
                ),
                const SizedBox(width: 8),
                Text('${e.latencyMs} ms',
                    style: Theme.of(context).textTheme.bodySmall),
                const Spacer(),
                Expanded(
                  child: Text(
                    e.imageName,
                    style: Theme.of(context).textTheme.bodySmall,
                    textAlign: TextAlign.right,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(e.response,
                style: const TextStyle(fontFamily: 'monospace')),
          ],
        ),
      ),
    );
  }
}
