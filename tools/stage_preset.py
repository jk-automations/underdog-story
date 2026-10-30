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
    """[(role, path, ok, why)] for every sheet the preset needs (people, places, props and each prop state).
    A sheet is accepted when it opens as an image of at least 512 px."""
    rows = []
    for role, rel, _ in core.sheet_rows(preset):
        src = (core.PRESETS_DIR / preset / rel).resolve()
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
    use = core.sheet_use()
    for role, src, ok, why in rows:
        print(f"{'ok ' if ok else 'NO '} {role:<18} {why:<14} {src.name:<22} scenes {','.join(map(str, use[role]))}")
    bad = [r for r in rows if not r[2]]
    if bad:
        print(core.missing_sheets_message([r[0] for r in bad]))
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
