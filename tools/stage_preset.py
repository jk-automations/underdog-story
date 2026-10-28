"""Copy a preset's reference sheets (presets/<name>/assets/, git-ignored) into ComfyUI's input folder as underdog_<role>.png.
python3 tools/stage_preset.py --input-dir ~/ComfyUI/input [--preset small-business-rescue-bakery]"""
import argparse, sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import underdog_core as core  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--input-dir", required=True); ap.add_argument("--preset", default=core.list_presets()[0])
a = ap.parse_args()
p = core.load_preset(a.preset)
missing = []
for role, rel in p["assets"].items():
    src = core.PRESETS_DIR / a.preset / rel
    if not src.exists():
        missing.append(str(src)); continue
    Image.open(src).convert("RGB").save(Path(a.input_dir).expanduser() / f"underdog_{role}.png")
    print("staged", role)
if missing:
    sys.exit("missing sheets (see the preset README):\n  " + "\n  ".join(missing))
print("now build with: python3 tools/build_app.py --staged")
