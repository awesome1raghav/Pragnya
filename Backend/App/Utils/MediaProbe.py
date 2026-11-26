"""FFprobe adapter, shared by acquisition validation (NEX-CAP) and metadata extraction (NEX-MET).

FFprobe runs as a separate process with an argument list (never a shell string), a timeout,
and no window, so a malformed file can stall or crash only that process.
"""

import json
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
MAX_STDERR_CHARS = 500


class ProbeUnavailable(Exception):
    """FFprobe is not installed or not found."""


class ProbeFailed(Exception):
    """FFprobe ran but could not read the file."""


def resolve_executable(configured: str) -> str | None:
    if Path(configured).is_file():
        return str(Path(configured))
    return shutil.which(configured)


@lru_cache(maxsize=8)
def ffprobe_version(executable: str) -> str:
    result = subprocess.run(
        [executable, "-hide_banner", "-version"], capture_output=True, text=True, timeout=15, creationflags=_NO_WINDOW
    )
    first_line = (result.stdout or "").splitlines()[:1]
    return first_line[0].strip()[:200] if first_line else "ffprobe (version unknown)"


def run_ffprobe(path: Path, configured_executable: str, timeout_seconds: float) -> tuple[dict, str]:
    """Return (ffprobe JSON, version string)."""
    executable = resolve_executable(configured_executable)
    if executable is None:
        raise ProbeUnavailable(f"FFprobe was not found ({configured_executable!r})")
    try:
        result = subprocess.run(
            [executable, "-v", "error", "-hide_banner", "-print_format", "json", "-show_format", "-show_streams", str(path)],
            capture_output=True,
            timeout=timeout_seconds,
            creationflags=_NO_WINDOW,
        )
    except subprocess.TimeoutExpired as exc:
        raise ProbeFailed(f"FFprobe timed out after {timeout_seconds:g}s") from exc
    except OSError as exc:
        raise ProbeUnavailable(f"FFprobe could not be started: {type(exc).__name__}") from exc

    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", "replace").strip()
        raise ProbeFailed(stderr[:MAX_STDERR_CHARS] or f"FFprobe exited with code {result.returncode}")
    try:
        data = json.loads(result.stdout.decode("utf-8", "replace"))
    except json.JSONDecodeError as exc:
        raise ProbeFailed("FFprobe returned invalid JSON") from exc
    return data, ffprobe_version(executable)
