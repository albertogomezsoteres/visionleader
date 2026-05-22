#!/data/data/com.termux/files/usr/bin/python
"""Phase 2 STT on-device benchmark on the Pixel 10 Pro with whisper.cpp."""
import os, re, subprocess, time, random, csv, json, hashlib, wave, platform
from pathlib import Path

WHISPER    = Path('~/whisper.cpp/build/bin/whisper-cli').expanduser()
MODELS_DIR = Path('~/whisper.cpp/models').expanduser()
AUDIOS_DIR = Path('~/audios').expanduser()
OUT_DIR    = Path('/sdcard/Download/fase2_results')
OUT_CSV    = OUT_DIR / 'bench_fase2.csv'
OUT_JSON   = OUT_DIR / 'reproducibility_fase2.json'
WARMUP_WAV = Path('~/audios_synth/warmup_silence.wav').expanduser()
SEED = 42

PROMPT = (
    "UFV campus navigation assistant. "
    "classroom 0.1, classroom 0.3, classroom 1.1, classroom 1.4, classroom 2.1, "
    "building G, building CD, "
    "main entrance, ground floor, first floor, second floor, floor 1, floor 2, "
    "elevator, stairs, cafeteria, gym, restroom, "
    "AI laboratory, mentoring room, EPS faculty offices, secretary office, directory sign, "
    "I want to go to, take me to, I am in, I am at, I am next to, I am lost, "
    "yes, no, repeat, cancel, stop, done, "
    "I am in a hurry, I have arrived, my destination, the doors are open."
)

CONFIGS = [
    'tiny-q2_k', 'tiny-q3_k', 'tiny-q4_0', 'tiny-q5_0', 'tiny-q8_0',
    'base-q2_k', 'base-q3_k', 'base-q4_0', 'base-q5_0', 'base-q8_0',
]
N_WARMUP = 3
N_RUNS = 3
THERMAL_REST_S = 120
TIMING_RE = re.compile(r'total time\s*=\s*([\d.]+)\s*ms')


def file_sha256(path, chunk=65536):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def make_synthetic_wav(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    n = 16000 * 5
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b'\x00\x00' * n)


def get_whisper_commit():
    try:
        return subprocess.check_output(
            ['git', '-C', str(Path('~/whisper.cpp').expanduser()),
             'rev-parse', '--short', 'HEAD'],
            stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return 'unknown'


def run_inference(config, audio_path):
    cmd = [
        str(WHISPER),
        '-m', str(MODELS_DIR / f'ggml-{config}.bin'),
        '-f', str(audio_path),
        '-l', 'en',
        '--prompt', PROMPT,
        '-bs', '1', '-bo', '1',
        '--temperature', '0.0',
        '--temperature-inc', '0.0',
        '-nt',
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    m = TIMING_RE.search(r.stdout + r.stderr)
    lat_ms = float(m.group(1)) if m else None
    lines = [
        ln.strip() for ln in r.stdout.splitlines()
        if ln.strip() and not ln.startswith(('whisper_', 'main:', 'system_info:'))
    ]
    return ' '.join(lines), lat_ms


def shuffled(seed):
    rng = random.Random(seed)
    files = sorted(AUDIOS_DIR.glob('utterance_*.wav'))
    rng.shuffle(files)
    return files


def write_repro_card():
    repro = {
        'experiment': 'phase2_stt_ondevice',
        'device': {
            'model': 'Google Pixel 10 Pro',
            'cpu': 'Tensor G5',
            'android_release': platform.release(),
            'n_cpu_cores': os.cpu_count(),
        },
        'whisper_cpp_commit': get_whisper_commit(),
        'seed': SEED,
        'decoding_protocol': {
            'beam_size': 1,
            'best_of': 1,
            'temperature': 0.0,
            'temperature_inc': 0.0,
            'language': 'en',
            'task': 'transcribe',
        },
        'latency_protocol': {
            'n_warmup': N_WARMUP,
            'n_latency_runs': N_RUNS,
            'warmup_audio_file': str(WARMUP_WAV),
            'warmup_audio_sha256': file_sha256(WARMUP_WAV),
            'warmup_audio_source': 'synthetic 5-second silence, 16kHz mono 16-bit PCM, disjoint from measurement set',
            'phrase_order': 'shuffled deterministically per run (seed = SEED*1000 + run_idx)',
            'thermal_rest_between_configs_s': THERMAL_REST_S,
        },
        'models': {
            c: {
                'path': str(MODELS_DIR / f'ggml-{c}.bin'),
                'size_bytes': (MODELS_DIR / f'ggml-{c}.bin').stat().st_size,
                'sha256': file_sha256(MODELS_DIR / f'ggml-{c}.bin'),
            }
            for c in CONFIGS
        },
        'dataset_audio_hashes': {
            a.name: {
                'sha256': file_sha256(a),
                'size_bytes': a.stat().st_size,
            }
            for a in sorted(AUDIOS_DIR.glob('utterance_*.wav'))
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, 'w') as f:
        json.dump(repro, f, indent=2)
    print(f'Reproducibility card -> {OUT_JSON}', flush=True)


def main():
    print('Generating synthetic warmup WAV...', flush=True)
    make_synthetic_wav(WARMUP_WAV)
    print('Writing reproducibility card (computing hashes)...', flush=True)
    write_repro_card()
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['model', 'run', 'audio', 'latency_ms', 'transcription'])
        f.flush()
        for i, cfg in enumerate(CONFIGS):
            print(f'\n=== Config {i+1}/{len(CONFIGS)}: {cfg} ===', flush=True)
            print(f'  Warmup ({N_WARMUP} iters on synthetic WAV, discarded)...', flush=True)
            for _ in range(N_WARMUP):
                run_inference(cfg, WARMUP_WAV)
            for run in range(1, N_RUNS + 1):
                seed_run = SEED * 1000 + run
                order = shuffled(seed_run)
                print(f'  Run {run}/{N_RUNS} (seed={seed_run}, {len(order)} audios)', flush=True)
                for audio in order:
                    tr, ms = run_inference(cfg, audio)
                    w.writerow([
                        cfg, run, audio.stem,
                        f'{ms:.2f}' if ms else '',
                        tr or '',
                    ])
                    f.flush()
            if i < len(CONFIGS) - 1:
                print(f'  Thermal rest: {THERMAL_REST_S}s...', flush=True)
                time.sleep(THERMAL_REST_S)
    print(f'\n=== DONE. CSV at {OUT_CSV}, JSON at {OUT_JSON} ===', flush=True)


if __name__ == '__main__':
    main()