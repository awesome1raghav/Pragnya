"""Peak memory of one detector (load + 20 items), for runs whose memory reading failed (RunBenchmark before its fix).

    .\\.venv\\Scripts\\python.exe -m Benchmarks.Detectors.MeasureMemory CommunityForensics   (or SSL-AASIST-DF)
Adds `peak_working_set_mb` and `peak_memory_note` to that detector's Benchmarks/Results JSON.
"""

import io
import json
import sys
import tempfile
import zipfile
from pathlib import Path

from Benchmarks.Detectors.RunBenchmark import DATA, RESULTS, peak_memory_mb

which = sys.argv[1]
if which == "CommunityForensics":
    import pyarrow.parquet as pq

    from Backend.App.Detectors.ImageDetectors import CommunityForensics

    detector, result = CommunityForensics(), "CommunityForensics-ViT-S16-384"
    shard = sorted((DATA / "CommunityForensicsEval" / "data").glob("*.parquet"))[0]
    folder = Path(tempfile.mkdtemp())
    for i, r in enumerate(pq.read_table(shard, columns=["image_data"]).to_pylist()[:20]):
        p = folder / f"{i}"
        p.write_bytes(r["image_data"]["bytes"] if isinstance(r["image_data"], dict) else r["image_data"])
        detector.score(p)
else:
    from Backend.App.Detectors.SpeechDetectors import RATE, SslAasist
    from Backend.App.Utils import MediaDecode

    detector, result = SslAasist(which.removeprefix("SSL-AASIST-")), which
    archive = zipfile.ZipFile(DATA / "InTheWild" / "release_in_the_wild.zip")
    folder = Path(tempfile.mkdtemp())
    for name in [n for n in archive.namelist() if n.endswith(".wav")][:20]:
        p = folder / Path(name).name
        p.write_bytes(archive.read(name))
        detector.score_samples(MediaDecode.decode_audio(p, "ffmpeg", 60, sample_rate=RATE, max_seconds=10))

path = RESULTS / f"{result}.json"
data = json.loads(path.read_text(encoding="utf-8"))
data["peak_working_set_mb"] = round(peak_memory_mb(), 0)
data["peak_memory_note"] = "measured separately (load + 20 items) because the original run's reading failed"
path.write_text(json.dumps(data, indent=1), encoding="utf-8")
print(result, data["peak_working_set_mb"], "MB")
