"""Copy a preset's reference sheets (presets/<name>/assets/, git-ignored) into ComfyUI's input folder as underdog_<role>.png.
python3 tools/stage_preset.py --input-dir <ComfyUI>/input [--preset barber-shop] [--check]
--check: only report which sheets are present; copy nothing."""
import argparse, sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import underdog_core as core  # noqa: E402


def sheet_status(preset):
    """[(role, path, ok, why)] for every sheet the preset needs. A sheet is accepted when it opens as an image of at least 512 px."""
    p = core.load_preset(preset)
    rows = []
    for role in core.ROLES:
        src = (core.PRESETS_DIR / preset / p["assets"][role]).resolve()
        if not src.exists():
            rows.append((role, src, False, "missing")); continue
        try:
            with Image.open(src) as im:
                ok = min(im.size) >= 512
                rows.append((role, src, ok, f"{im.size[0]}x{im.size[1]}" if ok else f"too small {im.size}"))
        except Exception as e:  # not an image
            rows.append((role, src, False, f"unreadable: {e}"))
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir"); ap.add_argument("--preset", default=core.list_presets()[0]); ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    rows = sheet_status(a.preset)
    for role, src, ok, why in rows:
        print(f"{'ok ' if ok else 'NO '} {role:<12} {why:<14} {src}")
    bad = [r for r in rows if not r[2]]
    if a.check:
        sys.exit(1 if bad else 0)
    if bad:
        sys.exit(f"{len(bad)} sheet(s) missing or not usable (see presets/{a.preset}/assets/README.md)")
    if not a.input_dir:
        sys.exit("--input-dir is required to stage")
    for role, src, _, _ in rows:
        Image.open(src).convert("RGB").save(Path(a.input_dir).expanduser() / f"underdog_{role}.png")
        print("staged", role)
    print("now build with: python3 tools/build_app.py --staged --preset", a.preset)
