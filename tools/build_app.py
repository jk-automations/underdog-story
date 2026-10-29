"""Build the one-graph Underdog Story app (ComfyUI API format).
python3 tools/build_app.py [--out workflows/underdog-story-api.json] [--staged]
--staged: the 6 reference slots point at underdog_<role>.png (copied into ComfyUI/input by tools/stage_preset.py)
instead of the blank placeholder."""
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import underdog_core as core  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--out", default=str(ROOT / "workflows/underdog-story-api.json"))
ap.add_argument("--staged", action="store_true")
ap.add_argument("--writer-model", default="gemini-3-1-pro")
a = ap.parse_args()

g = {}
nid = iter(range(1, 1000))
def node(cls, title=None, **inputs):
    i = str(next(nid)); g[i] = {"class_type": cls, "inputs": inputs}
    if title: g[i]["_meta"] = {"title": title}
    return i
def o(i, k=0): return [i, k]

preset = core.load_preset(core.list_presets()[0])
c = preset["cast"]
# ---------- user inputs ----------
brief = node("UnderdogBrief", "Your story", business_name=preset["business_name"], business_type=preset["business_type"],
             owner=c["owner"], rival=c["rival"], partner=c["partner"], hero_1=c["hero1"], hero_2=c["hero2"],
             tone="funny", model="veo-3.1-lite", script_source=f"preset: {preset['name']}")
refs = {r: node("LoadImage", f"Sheet: {r}", image=(f"underdog_{r}.png" if a.staged else "underdog_blank.png")) for r in core.ROLES}
# ---------- 1. script (Gemini only runs when picked: the Script node asks for its reply lazily) ----------
writer = node("GeminiNode", "Script writer (Gemini)", prompt=o(brief, 1), model=a.writer_model, seed=42, system_prompt="")
script = node("UnderdogScript", "Script", brief=o(brief, 0), writer_reply=o(writer, 0))
node("PreviewAny", "Script preview", source=o(script, 1))
# ---------- 2 + 3. per scene: keyframe (Nano Banana 2 + sheets) -> 8 s Veo 3.1 image-to-video with audio ----------
keyframes, videos = [], []
for k in range(1, len(core.BEATS) + 1):
    sc = node("UnderdogScene", f"Scene {k}", script=o(script), scene=k, **{r: o(refs[r]) for r in core.ROLES})
    kf = node("GeminiNanoBanana2", f"Keyframe {k}", prompt=o(sc, 0), model="Nano Banana 2 (Gemini 3.1 Flash Image)", seed=42 + k,
              aspect_ratio="9:16", resolution="1K", response_modalities="IMAGE", thinking_level="MINIMAL", images=o(sc, 2))
    vid = node("Veo3VideoGenerationNode", f"Video {k}", prompt=o(sc, 1), aspect_ratio="9:16", resolution="720p", negative_prompt="",
               duration_seconds=8, enhance_prompt=True, person_generation="ALLOW", seed=0, image=o(kf, 0), model=o(brief, 2),
               generate_audio=True)
    node("SaveVideo", f"Save scene {k}", video=o(vid), filename_prefix=f"underdog/scenes/scene_{k:02d}", format="mp4", **{"format.codec": "auto"})
    keyframes.append(kf); videos.append(vid)
sheet = node("UnderdogContactSheet", "Keyframes", **{f"keyframe_{k:02d}": o(kf) for k, kf in enumerate(keyframes, 1)})
node("PreviewImage", "Keyframe preview", images=o(sheet))
# ---------- 4. final cut ----------
fin = node("UnderdogFinish", "Final cut", script=o(script), captions=True, ai_label=True, credit=True, music_path="",
           **{f"scene_{k:02d}": o(v) for k, v in enumerate(videos, 1)})
save = node("SaveVideo", "Your film", video=o(fin), filename_prefix="underdog/film", format="mp4", **{"format.codec": "auto"})
Path(a.out).parent.mkdir(parents=True, exist_ok=True)
Path(a.out).write_text(json.dumps(g, indent=1) + "\n")
print(f"{len(g)} nodes -> {a.out}")
