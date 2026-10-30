"""Build the Underdog Story app graph (ComfyUI API format).
python3 tools/build_app.py [--out workflows/underdog-story-api.json] [--preset barber-shop] [--staged] [--draft]
--draft: the $0 draft: storyboard clips instead of Nano Banana / Veo, no Gemini, no Sonilo. Nothing in it costs money.
--staged: the reference slots point at underdog_<role>.png (copied into ComfyUI/input by tools/stage_preset.py)
instead of the blank placeholder."""
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import underdog_core as core  # noqa: E402

PARTNER_NODES = {"GeminiNode", "GeminiNanoBanana2", "Veo3VideoGenerationNode", "SoniloVideoToMusic"}


def build(preset=None, staged=False, draft=False, writer_model="gemini-3-1-pro"):
    preset = preset or core.list_presets()[0]
    g = {}
    nid = iter(range(1, 1000))

    def node(cls, title=None, **inputs):
        i = str(next(nid)); g[i] = {"class_type": cls, "inputs": inputs}
        if title:
            g[i]["_meta"] = {"title": title}
        return i

    o = lambda i, k=0: [i, k]
    # ---------- user inputs (cast fields empty = the preset's cast) ----------
    brief = node("UnderdogBrief", "Your story", business_name="", business_type="", owner="", rival="", regular="", hero_1="",
                 hero_2="", tone="funny", model="veo-3.1-lite", script_source=f"preset: {preset}")
    refs = {r: node("LoadImage", f"Sheet: {r}", image=(f"underdog_{r}.png" if staged else "underdog_blank.png")) for r in core.ROLES}
    # ---------- 1. script (Gemini only runs when picked: the Script node asks for its reply lazily) ----------
    if draft:
        script = node("UnderdogScript", "Script", brief=o(brief, 0))
    else:
        writer = node("GeminiNode", "Business details (Gemini)", prompt=o(brief, 1), model=writer_model, seed=42, system_prompt="")
        script = node("UnderdogScript", "Script", brief=o(brief, 0), writer_reply=o(writer, 0))
    node("PreviewAny", "Script preview", source=o(script, 1))
    # ---------- 2 + 3. per scene: keyframe (Nano Banana 2 + sheets) -> Veo 3.1 image-to-video with audio ----------
    keyframes, videos = [], []
    for k in range(1, len(core.ARC) + 1):
        sheets = {r: o(refs[r]) for r in core.ROLES}
        if draft:
            videos.append(node("UnderdogDraftScene", f"Draft scene {k}", script=o(script), scene=k, **sheets))
            continue
        sc = node("UnderdogScene", f"Scene {k}", script=o(script), scene=k, **sheets)
        kf = node("GeminiNanoBanana2", f"Keyframe {k}", prompt=o(sc, 0), model="Nano Banana 2 (Gemini 3.1 Flash Image)", seed=42 + k,
                  aspect_ratio="9:16", resolution="1K", response_modalities="IMAGE", thinking_level="MINIMAL", images=o(sc, 2))
        vid = node("Veo3VideoGenerationNode", f"Video {k}", prompt=o(sc, 1), aspect_ratio="9:16", resolution="720p", negative_prompt="",
                   duration_seconds=o(sc, 4), enhance_prompt=True, person_generation="ALLOW", seed=k, image=o(kf, 0),
                   model=o(brief, 2), generate_audio=True)
        node("SaveVideo", f"Save scene {k}", video=o(vid), filename_prefix=f"underdog/scenes/scene_{k:02d}", format="mp4",
             **{"format.codec": "auto"})
        keyframes.append(kf); videos.append(vid)
    if keyframes:
        sheet = node("UnderdogContactSheet", "Keyframes", **{f"keyframe_{k:02d}": o(kf) for k, kf in enumerate(keyframes, 1)})
        node("PreviewImage", "Keyframe preview", images=o(sheet))
    # ---------- 4. final cut (v9 recipe) -> 5. score (Sonilo, lazy) + master ----------
    fin = node("UnderdogFinish", "Final cut", script=o(script), captions=True, ai_label=True, credit=True,
               **{f"scene_{k:02d}": o(v) for k, v in enumerate(videos, 1)})
    if draft:
        mix = node("UnderdogScoreMix", "Master", video=o(fin), score=False, music_path="")
    else:
        son = node("SoniloVideoToMusic", "Score (Sonilo)", video=o(fin), prompt="", seed=0)
        mix = node("UnderdogScoreMix", "Score mix + master", video=o(fin), score=True, music_path="", music=o(son))
    node("SaveVideo", "Your film", video=o(mix), filename_prefix="underdog/draft" if draft else "underdog/film", format="mp4",
         **{"format.codec": "auto"})
    return g


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--preset")
    ap.add_argument("--staged", action="store_true")
    ap.add_argument("--draft", action="store_true")
    ap.add_argument("--writer-model", default="gemini-3-1-pro")
    a = ap.parse_args()
    out = Path(a.out or ROOT / ("workflows/underdog-story-draft-api.json" if a.draft else "workflows/underdog-story-api.json"))
    g = build(a.preset, a.staged, a.draft, a.writer_model)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(g, indent=1) + "\n")
    print(f"{len(g)} nodes -> {out}")
