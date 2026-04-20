import 'dart:async';
import 'dart:io';
import 'dart:math';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:path_provider/path_provider.dart';
import 'package:http/http.dart' as http;

const MethodChannel _nativeChannel = MethodChannel('whisper_smoke_test/native');

// --- Pinned protocol (mirrors Phase 1 / Phase 2) ---
const String DOMAIN_PROMPT =
    "UFV campus navigation assistant. "
    "classroom 0.1, classroom 0.3, classroom 1.1, classroom 1.4, classroom 2.1, "
    "building G, building CD, "
    "main entrance, ground floor, first floor, second floor, floor 1, floor 2, "
    "elevator, stairs, cafeteria, gym, restroom, "
    "AI laboratory, mentoring room, EPS faculty offices, secretary office, directory sign, "
    "I want to go to, take me to, I am in, I am at, I am next to, I am lost, "
    "yes, no, repeat, cancel, stop, done, "
    "I am in a hurry, I have arrived, my destination, the doors are open.";

const String MODEL_ASSET = 'assets/models/ggml-tiny-q5_0.bin';
const String SERVER_HOST = '127.0.0.1';
const int SERVER_PORT = 8080;

const int SEED = 42;
const int N_WARMUP = 3;
const int N_RUNS = 3;

const List<Map<String, String>> AUDIOS = [
  {'id': 'utterance_01', 'ground_truth': 'I am in classroom 0.3 building G'},
  {'id': 'utterance_02', 'ground_truth': 'I am in classroom 2.1 on the second floor'},
  {'id': 'utterance_03', 'ground_truth': 'I am at the main entrance of building G'},
  {'id': 'utterance_04', 'ground_truth': 'I am in the AI laboratory on the ground floor of building G'},
  {'id': 'utterance_05', 'ground_truth': 'I am next to the elevator on floor 1 of building G'},
  {'id': 'utterance_06', 'ground_truth': 'I want to go to classroom 1.4'},
  {'id': 'utterance_07', 'ground_truth': 'Take me to the gym in building CD'},
  {'id': 'utterance_08', 'ground_truth': 'I want to go to the cafeteria'},
  {'id': 'utterance_09', 'ground_truth': 'Take me to the nearest restroom on this floor'},
  {'id': 'utterance_10', 'ground_truth': 'Could you guide me to the EPS faculty offices please'},
  {'id': 'utterance_11', 'ground_truth': 'I am in a hurry please use the stairs'},
  {'id': 'utterance_12', 'ground_truth': 'Repeat the instructions please'},
  {'id': 'utterance_13', 'ground_truth': 'I am lost I need help'},
  {'id': 'utterance_14', 'ground_truth': 'Cancel navigation and start again'},
  {'id': 'utterance_15', 'ground_truth': 'Stop and tell me where I am'},
  {'id': 'utterance_16', 'ground_truth': 'Yes I am ready to continue'},
  {'id': 'utterance_17', 'ground_truth': 'No that is not my location'},
  {'id': 'utterance_18', 'ground_truth': 'I have arrived at the elevator on floor 2'},
  {'id': 'utterance_19', 'ground_truth': 'Done I have reached my destination'},
  {'id': 'utterance_20', 'ground_truth': 'Yes I can see the elevator and the doors are open'},
  {'id': 'utterance_21', 'ground_truth': 'I am in classroom 1.1 and I want to go to the EPS faculty offices'},
  {'id': 'utterance_22', 'ground_truth': 'Take me from classroom 0.1 to the AI laboratory on the ground floor'},
  {'id': 'utterance_23', 'ground_truth': 'I just came out of the elevator on the first floor of building G'},
  {'id': 'utterance_24', 'ground_truth': 'I do not know where I am I need help finding my location'},
  {'id': 'utterance_25', 'ground_truth': 'I am at the directory sign in building G next to the mentoring room'},
  {'id': 'utterance_26', 'ground_truth': 'How do I get from building CD to building G'},
  {'id': 'utterance_27', 'ground_truth': 'Where is the secretary office in building G'},
  {'id': 'utterance_28', 'ground_truth': 'I need to find classroom 0.3 quickly'},
  {'id': 'utterance_29', 'ground_truth': 'Could you tell me how to reach the AI laboratory from here'},
  {'id': 'utterance_30', 'ground_truth': 'My destination is classroom 1.4 in building G please'},
];

void main() => runApp(const SmokeTestApp());

class SmokeTestApp extends StatelessWidget {
  const SmokeTestApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'whisper-server validation (30 audios x 3 runs)',
      theme: ThemeData(colorScheme: ColorScheme.fromSeed(seedColor: Colors.green)),
      home: const SmokeTestPage(),
    );
  }
}

class SmokeTestPage extends StatefulWidget {
  const SmokeTestPage({super.key});

  @override
  State<SmokeTestPage> createState() => _SmokeTestPageState();
}

class _SmokeTestPageState extends State<SmokeTestPage> {
  final List<String> _log = [];
  bool _running = false;
  Process? _server;

  void _append(String line) {
    setState(() => _log.add(line));
  }

  Future<String> _copyAssetToFile(String assetPath, String filename) async {
    final dir = await getTemporaryDirectory();
    final file = File('${dir.path}/$filename');
    if (!file.existsSync()) {
      final bytes = await rootBundle.load(assetPath);
      await file.writeAsBytes(bytes.buffer.asUint8List());
    }
    return file.path;
  }

  /// Generate a 5-second silent WAV (16 kHz mono 16-bit PCM) for warmup.
  /// Byte-identical across runs (all zeros), disjoint from the measurement set
  /// so no measured audio has a pre-warm disk cache advantage.
  Future<String> _generateWarmupWav() async {
    final dir = await getTemporaryDirectory();
    final path = '${dir.path}/warmup_silence.wav';
    final file = File(path);
    if (file.existsSync()) return path;

    const sampleRate = 16000;
    const duration = 5;
    const numSamples = sampleRate * duration;
    const dataSize = numSamples * 2;
    const totalSize = 44 + dataSize;

    final b = BytesBuilder();
    b.add([0x52, 0x49, 0x46, 0x46]);      // "RIFF"
    b.add(_le32(totalSize - 8));
    b.add([0x57, 0x41, 0x56, 0x45]);      // "WAVE"
    b.add([0x66, 0x6d, 0x74, 0x20]);      // "fmt "
    b.add(_le32(16));
    b.add(_le16(1));                      // PCM
    b.add(_le16(1));                      // mono
    b.add(_le32(sampleRate));
    b.add(_le32(sampleRate * 2));         // byte rate
    b.add(_le16(2));                      // block align
    b.add(_le16(16));                     // bits per sample
    b.add([0x64, 0x61, 0x74, 0x61]);      // "data"
    b.add(_le32(dataSize));
    b.add(Uint8List(dataSize));           // silence
    await file.writeAsBytes(b.toBytes());
    return path;
  }

  List<int> _le16(int v) => [v & 0xff, (v >> 8) & 0xff];
  List<int> _le32(int v) => [
        v & 0xff,
        (v >> 8) & 0xff,
        (v >> 16) & 0xff,
        (v >> 24) & 0xff,
      ];

  Future<String> _findServerBinary() async {
    const binary = 'libwhisper-server.so';
    final dir = await _nativeChannel.invokeMethod<String>('getNativeLibraryDir');
    if (dir == null) {
      throw Exception('nativeLibraryDir returned null from platform channel');
    }
    final path = '$dir/$binary';
    if (!File(path).existsSync()) {
      throw Exception('whisper-server not found at $path');
    }
    return path;
  }

  Future<void> _startServer(String modelPath) async {
    final serverBin = await _findServerBinary();
    _append('      server binary: $serverBin');

    final nativeDir = File(serverBin).parent.path;

    _server = await Process.start(
      serverBin,
      [
        '-m', modelPath,
        '--host', SERVER_HOST,
        '--port', SERVER_PORT.toString(),
        '-l', 'en',
        '-bs', '1', '-bo', '1',
        '-nf',
      ],
      environment: {'LD_LIBRARY_PATH': nativeDir},
      includeParentEnvironment: true,
    );

    _server!.stdout.transform(const SystemEncoding().decoder).listen((data) {
      for (final line in data.split('\n')) {
        final t = line.trim();
        if (t.isNotEmpty && _log.length < 300) _append('      [srv-out] $t');
      }
    });
    _server!.stderr.transform(const SystemEncoding().decoder).listen((data) {
      for (final line in data.split('\n')) {
        final t = line.trim();
        if (t.isNotEmpty && _log.length < 300) _append('      [srv-err] $t');
      }
    });

    bool processExited = false;
    unawaited(_server!.exitCode.then((code) {
      processExited = true;
      _append('      [srv] process exited with code $code');
    }));

    final deadline = DateTime.now().add(const Duration(seconds: 30));
    while (DateTime.now().isBefore(deadline)) {
      if (processExited) {
        throw Exception('whisper-server exited before accepting connections');
      }
      try {
        final socket = await Socket.connect(
          SERVER_HOST, SERVER_PORT,
          timeout: const Duration(milliseconds: 500),
        );
        await socket.close();
        return;
      } catch (_) {
        await Future.delayed(const Duration(milliseconds: 500));
      }
    }
    throw Exception('whisper-server did not accept TCP connections within 30 s');
  }

  Future<String> _transcribeOverHttp(String audioPath) async {
    final uri = Uri.parse('http://$SERVER_HOST:$SERVER_PORT/inference');
    final req = http.MultipartRequest('POST', uri);
    req.files.add(await http.MultipartFile.fromPath('file', audioPath));
    req.fields['response_format'] = 'text';
    req.fields['prompt'] = DOMAIN_PROMPT;
    req.fields['temperature'] = '0.0';

    final streamed = await req.send();
    final body = await streamed.stream.bytesToString();
    if (streamed.statusCode != 200) {
      throw Exception('HTTP ${streamed.statusCode}: $body');
    }
    return body.trim();
  }

  String _csvField(String v) {
    final escaped = v.replaceAll('"', '""');
    return '"$escaped"';
  }

  Future<String> _writeCsv(List<Map<String, dynamic>> rows) async {
    // Write to app's external files directory. Accessible via Android Files app
    // under Android/data/com.example.whisper_smoke_test/files/
    // and pullable via: adb pull /storage/emulated/0/Android/data/.../files/
    final dir = await getExternalStorageDirectory();
    final file = File('${dir!.path}/fase_flutter_results.csv');
    final buffer = StringBuffer();
    buffer.writeln('model,run,audio,latency_ms,transcription');
    for (final r in rows) {
      buffer.writeln([
        _csvField(r['model'] as String),
        r['run'].toString(),
        _csvField(r['audio'] as String),
        (r['latency_ms'] as double).toStringAsFixed(2),
        _csvField(r['transcription'] as String),
      ].join(','));
    }
    await file.writeAsString(buffer.toString());
    return file.path;
  }

  Future<void> _runValidation() async {
    if (_running) return;
    setState(() {
      _running = true;
      _log.clear();
    });

    try {
      _append('[1/6] Preparing assets on local filesystem...');
      final modelPath = await _copyAssetToFile(MODEL_ASSET, 'ggml-tiny-q5_0.bin');
      _append('      model at $modelPath');
      final audioPaths = <String, String>{};
      for (final entry in AUDIOS) {
        final id = entry['id']!;
        audioPaths[id] = await _copyAssetToFile('assets/audios/$id.wav', '$id.wav');
      }
      final warmupWav = await _generateWarmupWav();
      _append('      ${audioPaths.length} audios copied + warmup silence generated');

      _append('[2/6] Launching whisper-server as subprocess...');
      await _startServer(modelPath);
      _append('      server ready on $SERVER_HOST:$SERVER_PORT');

      _append('[3/6] Warmup ($N_WARMUP iters on synthetic WAV, discarded)...');
      for (int w = 0; w < N_WARMUP; w++) {
        await _transcribeOverHttp(warmupWav);
      }
      _append('      warmup done');

      _append('[4/6] Measurement: $N_RUNS runs x ${AUDIOS.length} audios = ${N_RUNS * AUDIOS.length} inferences...');
      final rows = <Map<String, dynamic>>[];
      for (int run = 1; run <= N_RUNS; run++) {
        final rng = Random(SEED * 1000 + run);
        final order = List<int>.generate(AUDIOS.length, (i) => i);
        // Fisher-Yates deterministic shuffle
        for (int i = order.length - 1; i > 0; i--) {
          final j = rng.nextInt(i + 1);
          final tmp = order[i];
          order[i] = order[j];
          order[j] = tmp;
        }

        _append('      [run $run/$N_RUNS] seed=${SEED * 1000 + run}');
        for (final i in order) {
          final id = AUDIOS[i]['id']!;
          final audioPath = audioPaths[id]!;
          final sw = Stopwatch()..start();
          String pred;
          try {
            pred = await _transcribeOverHttp(audioPath);
          } catch (e) {
            pred = 'ERROR: $e';
          }
          sw.stop();
          rows.add({
            'model': 'tiny-q5_0',
            'run': run,
            'audio': id,
            'latency_ms': sw.elapsedMilliseconds.toDouble(),
            'transcription': pred,
          });
        }
        _append('      run $run complete (${AUDIOS.length} audios transcribed)');
      }

      _append('[5/6] Writing CSV...');
      // Write rows sorted by (audio, run) for stable output
      rows.sort((a, b) {
        final c = (a['audio'] as String).compareTo(b['audio'] as String);
        return c != 0 ? c : (a['run'] as int).compareTo(b['run'] as int);
      });
      final csvPath = await _writeCsv(rows);
      _append('      saved ${rows.length} rows to: $csvPath');

      _append('[6/6] Summary');
      // Compute per-audio mean latency + show one transcription per audio
      final byAudio = <String, List<double>>{};
      final sampleTranscription = <String, String>{};
      for (final r in rows) {
        final id = r['audio'] as String;
        byAudio.putIfAbsent(id, () => []).add(r['latency_ms'] as double);
        if (r['run'] == 1) sampleTranscription[id] = r['transcription'] as String;
      }
      _append('  ${'AUDIO'.padRight(14)} ${'LAT_MEAN_MS'.padRight(12)} TRANSCRIPTION');
      for (final e in AUDIOS) {
        final id = e['id']!;
        final lats = byAudio[id] ?? [];
        final mean = lats.isEmpty ? 0.0 : lats.reduce((a, b) => a + b) / lats.length;
        final text = sampleTranscription[id] ?? '';
        final tshort = text.length > 60 ? '${text.substring(0, 57)}...' : text;
        _append('  ${id.padRight(14)} ${mean.toStringAsFixed(0).padRight(12)} $tshort');
      }

      _append('');
      _append('VALIDATION FINISHED.');
      _append('CSV: $csvPath');
      _append('Pull with: adb pull "${csvPath.replaceAll('\\', '/')}" ./');
    } catch (e, st) {
      _append('ERROR: $e');
      _append(st.toString().split('\n').take(8).join('\n'));
    } finally {
      _server?.kill();
      _server = null;
      setState(() => _running = false);
    }
  }

  @override
  void dispose() {
    _server?.kill();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('whisper-server validation (30x3)')),
      body: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            ElevatedButton(
              onPressed: _running ? null : _runValidation,
              child: Text(_running ? 'Running...' : 'Run validation (30 audios x 3 runs)'),
            ),
            const SizedBox(height: 12),
            Expanded(
              child: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Colors.black,
                  borderRadius: BorderRadius.circular(6),
                ),
                child: SingleChildScrollView(
                  child: SelectableText(
                    _log.join('\n'),
                    style: const TextStyle(
                      color: Colors.greenAccent,
                      fontFamily: 'monospace',
                      fontSize: 11,
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
