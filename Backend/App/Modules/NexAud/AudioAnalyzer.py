"""NEX-AUD Audio Forensics: signal measurements of the first audio stream (archive §4, module 07).

NEX-AUD extracts the track itself from AUDIO or VIDEO evidence (plan conflict C-6). A video without an audio
stream ends SKIPPED / NOT_APPLICABLE, said by this module, not assumed by the planner.

Methods (each reports what it measured):
  LEVELS      RMS and peak level, clipping, DC offset.
  SILENCE     digital silence (runs of exact zero samples) and near-silence. Exact digital silence inside
              speech or ambience is a common trace of editing, but also of muting, gating and some codecs.
  BANDWIDTH   the frequency below which 99 % of the energy lies, against the stream's Nyquist frequency.
              A low limit at a high sample rate suggests the audio passed through a lower-rate or lossy stage.
  CONTINUITY  abrupt changes of the short-time spectrum (spectral flux), as candidate edit points with times.
A normalised working copy (16 kHz mono WAV) is stored for alignment (NEX-ALN). Chromaprint fingerprinting runs
only when `fpcalc` is installed. An evaluated synthetic-speech detector is not installed.
"""

import io
import json
import subprocess
import wave
from pathlib import Path

import numpy as np

from Backend.App.Contracts.Artifacts import ArtifactKind
from Backend.App.Contracts.ExecutionStates import ExecutionState
from Backend.App.Contracts.Findings import Assertion, Finding, ScoreKind, TimeRange
from Backend.App.Modules.Engine import DETECTOR_NOT_INSTALLED, ArtifactOut, EngineOutput, heatmap, png, r, robust_z
from Backend.App.Utils import MediaDecode
from Backend.App.Utils.MediaProbe import resolve_executable

VERSION = "nextron-aud/1"
MODULE = "NEX-AUD"
PARAMETERS = {"analysis_rate_max": 48_000, "working_rate": 16_000, "max_seconds": 600, "frame": 2048, "hop": 512,
              "flux_z": 8.0, "edge_s": 0.25, "digital_silence_min_s": 0.05, "silence_dbfs": -60, "max_candidates": 20}


def _db(x: float) -> float:
    return float(20 * np.log10(max(x, 1e-10)))


def _runs(mask: np.ndarray, min_len: int) -> list[tuple[int, int]]:
    if not mask.any():
        return []
    padded = np.concatenate([[False], mask, [False]])
    edges = np.flatnonzero(padded[1:] != padded[:-1])
    return [(int(a), int(b)) for a, b in zip(edges[::2], edges[1::2]) if b - a >= min_len]


def _stft_summary(x: np.ndarray, n: int, hop: int, *, chunk: int = 1024, columns: int = 1200, bins: int = 256) -> dict:
    """Short-time spectra in chunks (bounded memory): total energy per bin, spectral flux and RMS per frame, and a
    reduced log spectrogram (at most `columns` frames by `bins` frequency bands) for display."""
    count = 1 + (x.size - n) // hop
    window = np.hanning(n)
    energy = np.zeros(n // 2 + 1)
    flux = np.empty(max(count - 1, 0))
    level = np.empty(count)
    keep = set(np.linspace(0, count - 1, min(columns, count)).astype(int).tolist())
    shown, previous, reference = [], None, None
    for start in range(0, count, chunk):
        idx = np.arange(start, min(start + chunk, count))
        frames = x[idx[:, None] * hop + np.arange(n)[None, :]].astype(np.float64)
        level[idx] = np.sqrt((frames ** 2).mean(axis=1))
        power = np.abs(np.fft.rfft(frames * window, axis=1)) ** 2
        energy += power.sum(axis=0)
        if reference is None:
            reference = max(float(power.max()), 1e-20)
        logp = np.log1p(power / reference * 1e6)
        stacked = logp if previous is None else np.vstack([previous, logp])
        diffs = np.sqrt((np.diff(stacked, axis=0).clip(min=0) ** 2).sum(axis=1))
        first = idx[0] - (0 if previous is None else 1)
        flux[first: first + diffs.size] = diffs
        previous = logp[-1:]
        for row, i in zip(logp, idx):
            if i in keep:
                shown.append(row[: (row.size // bins) * bins].reshape(bins, -1).mean(axis=1))
    return {"energy": energy, "flux": flux, "level": level, "columns": np.asarray(shown)}


def _wav(samples: np.ndarray, rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())
    return buf.getvalue()


def _chromaprint(path: Path, fpcalc: str, timeout: float) -> tuple[dict | None, str | None]:
    executable = resolve_executable(fpcalc)
    if executable is None:
        return None, f"Chromaprint (fpcalc) is not installed ({fpcalc!r}); no acoustic fingerprint was computed"
    try:
        done = subprocess.run([executable, "-json", "-length", "600", str(path)], capture_output=True, timeout=timeout)
        data = json.loads(done.stdout or b"{}")
        return ({"duration_s": data.get("duration"), "fingerprint": data.get("fingerprint")} if data.get("fingerprint") else None,
                None if data.get("fingerprint") else "fpcalc returned no fingerprint")
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        return None, f"fpcalc failed: {type(exc).__name__}"


def analyze(path: Path, evidence_id, *, settings) -> EngineOutput:
    ffprobe = settings.FFPROBE_PATH
    ffmpeg = MediaDecode.ffmpeg_for(ffprobe)
    timeout = settings.MODULE_TIMEOUT_SECONDS
    tools = {"ffprobe": MediaDecode.tool_version(ffprobe), "ffmpeg": MediaDecode.tool_version(ffmpeg), "numpy": np.__version__}
    audio = [s for s in MediaDecode.streams(path, ffprobe, timeout) if s.get("codec_type") == "audio"]
    if not audio:
        return EngineOutput(ExecutionState.SKIPPED, "NOT_APPLICABLE", "The file has no audio stream", tool_versions=tools)
    stream = audio[0]
    native = int(stream.get("sample_rate") or 0) or PARAMETERS["working_rate"]
    rate = min(native, PARAMETERS["analysis_rate_max"])
    x = MediaDecode.decode_audio(path, ffmpeg, timeout, sample_rate=rate, max_seconds=PARAMETERS["max_seconds"])
    out = EngineOutput(ExecutionState.PARTIALLY_COMPLETED, DETECTOR_NOT_INSTALLED,
                       "No evaluated synthetic-speech detector is installed, so no voice-cloning assessment was made; "
                       "the signal measurements below ran.", tool_versions=tools)
    ev = [evidence_id]
    if len(audio) > 1:
        out.limitations.append(f"The file has {len(audio)} audio streams; only the first was analysed")
    duration = x.size / rate
    if duration >= PARAMETERS["max_seconds"] - 0.01:
        out.limitations.append(f"Only the first {PARAMETERS['max_seconds']} s were analysed")

    def finding(kind, title, description, measurement, *, score=None, time_range=None, limitations=(), artifacts=()):
        out.findings.append(Finding(
            module_id=MODULE, evidence_ids=ev, assertion=Assertion.OBSERVATION, finding_type=kind, title=title, description=description,
            measurement=measurement, score=score, score_kind=ScoreKind.METHOD_SPECIFIC if score is not None else None, time_range=time_range,
            limitations=list(limitations), supporting_artifact_ids=[a.artifact_id for a in artifacts], parameters=PARAMETERS))

    if x.size < PARAMETERS["frame"] * 2:
        out.limitations.append("Under 0.2 s of audio: only levels were measured")
    peak = float(np.abs(x).max()) if x.size else 0.0
    rms = float(np.sqrt(np.mean(x.astype(np.float64) ** 2))) if x.size else 0.0
    clipped = float((np.abs(x) >= 0.999).mean()) if x.size else 0.0
    finding("AUDIO_LEVELS", "Audio levels measured", f"{duration:.2f} s at {native} Hz ({stream.get('codec_name')}, {stream.get('channels')} ch), analysed mixed to mono.",
            {"duration_s": r(duration, 3), "native_sample_rate_hz": native, "analysis_rate_hz": rate, "codec": stream.get("codec_name"),
             "channels": stream.get("channels"), "rms_dbfs": r(_db(rms), 2), "peak_dbfs": r(_db(peak), 2),
             "clipped_fraction": r(clipped, 6), "dc_offset": r(float(x.mean()) if x.size else 0.0, 6)})

    # digital silence and near-silence
    zero_runs = _runs(x == 0.0, int(PARAMETERS["digital_silence_min_s"] * rate))
    interior = [(a, b) for a, b in zero_runs if a > 0 and b < x.size]
    sil_lim = ["Muting, noise gates, fades and some codecs also produce exact digital silence"]
    for a, b in interior[: PARAMETERS["max_candidates"]]:
        finding("DIGITAL_SILENCE", f"Digital silence at {a / rate:.2f} s", f"{(b - a) / rate:.3f} s of exact zero samples inside the recording.",
                {"length_s": r((b - a) / rate, 4)}, time_range=TimeRange(start_seconds=r(a / rate, 4), end_seconds=r(b / rate, 4)), limitations=sil_lim)

    if x.size >= PARAMETERS["frame"] * 2:
        n, hop = PARAMETERS["frame"], PARAMETERS["hop"]
        stft = _stft_summary(x, n, hop)
        freqs = np.fft.rfftfreq(n, 1 / rate)
        cumulative = np.cumsum(stft["energy"]) / max(stft["energy"].sum(), 1e-20)
        bandwidth = float(freqs[min(np.searchsorted(cumulative, 0.99), freqs.size - 1)])
        nyquist = rate / 2
        finding("EFFECTIVE_BANDWIDTH", f"99 % of the energy lies below {bandwidth / 1000:.1f} kHz",
                f"Nyquist frequency of the analysed rate is {nyquist / 1000:.1f} kHz.",
                {"bandwidth_99_hz": r(bandwidth, 1), "nyquist_hz": nyquist, "ratio": r(bandwidth / nyquist, 4)},
                score=r(bandwidth / nyquist, 4),
                limitations=["Speech and many sounds are naturally band-limited; a low ratio is a clue to processing history, not proof"])
        flux, level = stft["flux"], stft["level"]
        z = robust_z(flux)
        loud = level[1:] > 10 ** (PARAMETERS["silence_dbfs"] / 20)
        t_of = (np.arange(flux.size) + 1) * hop / rate
        loud &= (t_of > PARAMETERS["edge_s"]) & (t_of < duration - PARAMETERS["edge_s"])  # encoder start-up and fade-out transients
        picks = [int(i) for i in np.argsort(-z) if z[i] > PARAMETERS["flux_z"] and loud[i]][: PARAMETERS["max_candidates"]]
        flux_lim = ["Plosives, music onsets and door slams change the spectrum abruptly too",
                    f"The first and last {PARAMETERS['edge_s']} s are not searched (encoder transients)",
                    f"Located to one analysis hop ({hop / rate * 1000:.0f} ms)"]
        for i in sorted(picks):
            t = (i + 1) * hop / rate
            finding("SPECTRAL_DISCONTINUITY", f"Abrupt spectral change at {t:.2f} s", "The short-time spectrum changes much more than elsewhere in the recording.",
                    {"flux": r(flux[i], 3), "median_flux": r(np.median(flux), 3)}, score=r(z[i], 2),
                    time_range=TimeRange(start_seconds=r(max(0.0, t - hop / rate), 4), end_seconds=r(t + hop / rate, 4)), limitations=flux_lim)
        spectrogram = ArtifactOut(ArtifactKind.HEATMAP, "image/png", "png", png(heatmap(stft["columns"].T[::-1])),
                                  {"method": "SPECTROGRAM", "rate_hz": rate, "frame": n, "hop": hop, "duration_s": r(duration, 3), "top_hz": nyquist})
        out.artifacts.append(spectrogram)
        finding("SPECTRAL_CONTINUITY", "Spectral continuity measured", f"{len(picks)} abrupt spectral change(s) above the threshold.",
                {"frames": int(flux.size + 1), "candidates": len(picks), "max_robust_z": r(z.max(), 2) if z.size else 0.0},
                score=r(z.max(), 2) if z.size else 0.0, limitations=flux_lim, artifacts=[spectrogram])

    working = x if rate == PARAMETERS["working_rate"] else MediaDecode.decode_audio(
        path, ffmpeg, timeout, sample_rate=PARAMETERS["working_rate"], max_seconds=PARAMETERS["max_seconds"])
    out.artifacts.append(ArtifactOut(ArtifactKind.AUDIO_TRACK, "audio/wav", "wav", _wav(working, PARAMETERS["working_rate"]),
                                     {"rate_hz": PARAMETERS["working_rate"], "channels": 1, "source_stream": stream.get("index"), "duration_s": r(working.size / PARAMETERS["working_rate"], 3)}))
    fingerprint, problem = _chromaprint(path, getattr(settings, "FPCALC_PATH", "fpcalc"), timeout)
    if fingerprint:
        out.tool_versions["fpcalc"] = "chromaprint"
        finding("ACOUSTIC_FINGERPRINT", "Chromaprint fingerprint computed", "Features for similarity search (NEX-FPM); not evidence on its own.", fingerprint)
    else:
        out.limitations.append(problem)
    out.limitations.append("No evaluated synthetic-speech detector is installed: voice cloning or synthesis was not assessed")
    return out
