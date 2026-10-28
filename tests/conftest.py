import os, shutil, subprocess, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"


def make_clip(path, secs, w=360, h=640, audio=True, freq=440):
    """A dummy scene clip: ffmpeg test pattern + sine tone (no AI generation)."""
    cmd = [FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc=size={w}x{h}:rate=24:duration={secs}"]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency={freq}:sample_rate=48000:duration={secs}"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p"] + (["-c:a", "aac", "-shortest"] if audio else []) + [str(path)]
    subprocess.run(cmd, check=True)
    return Path(path)


@pytest.fixture(scope="session")
def clips(tmp_path_factory):
    d = tmp_path_factory.mktemp("clips")
    return [make_clip(d / "s1.mp4", 2.0), make_clip(d / "s2.mp4", 2.5, w=480, h=854, audio=False),
            make_clip(d / "s3.mp4", 2.0, freq=660)]


@pytest.fixture(scope="session")
def comfy_path():
    p = Path(os.environ.get("COMFYUI_DIR", Path.home() / "ComfyUI"))
    if not (p / "comfy_api").exists():
        pytest.skip("ComfyUI not found (set COMFYUI_DIR)")
    sys.path.insert(0, str(p))
    return p
