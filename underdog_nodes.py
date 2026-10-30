"""Underdog Story ComfyUI nodes. The paid generation is done by ComfyUI's own partner nodes (Gemini, Nano Banana 2,
Veo 3.1, Sonilo); these nodes write and check the script, pick the reference sheets per scene, draw the free draft and
cut and mix the finished film."""
import json
import tempfile
from pathlib import Path

import numpy as np
import torch
from PIL import Image

try:
    from . import underdog_core as core
except ImportError:  # imported directly (tests)
    import underdog_core as core

try:
    from comfy_api.input_impl import VideoFromFile
except ImportError:  # older ComfyUI
    from comfy_api.latest._input_impl import VideoFromFile

PRESET_SOURCES = [f"preset: {p}" for p in core.list_presets()]
GEMINI_SOURCE = "any other business: write with Gemini"
REF_SIZE = 1024
N = len(core.ARC)


def _is_blank(img):
    """An unused reference slot holds the blank placeholder (one flat color)."""
    return img is None or float(img[0].float().std()) < 0.01


def _pil(img):
    return Image.fromarray((img[0].cpu().numpy() * 255).clip(0, 255).astype(np.uint8)).convert("RGB")


def _fit(img, size=REF_SIZE):
    """Letterbox one reference image onto a white square so different sheets can share one batch."""
    pil = _pil(img)
    pil.thumbnail((size, size), Image.LANCZOS)
    canvas = Image.new("RGB", (size, size), (255, 255, 255))
    canvas.paste(pil, ((size - pil.width) // 2, (size - pil.height) // 2))
    return torch.from_numpy(np.asarray(canvas, dtype=np.float32) / 255.0)[None]


def _out_dir(tmp):
    try:
        import folder_paths
        d = Path(folder_paths.get_temp_directory())
    except ImportError:
        d = tmp
    d.mkdir(parents=True, exist_ok=True)
    return d


class UnderdogBrief:
    """The story inputs: the business, the cast by their looks (never names; empty = the preset's or Gemini's), tone,
    Veo model and where the business details come from (a built-in preset, or Gemini for any other business)."""
    CATEGORY = "Underdog Story"
    RETURN_TYPES = ("STRING", "STRING", core.VEO_MODELS)
    RETURN_NAMES = ("brief", "writer_prompt", "veo_model")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        txt = lambda tip: ("STRING", {"default": "", "multiline": True, "tooltip": tip})
        return {"required": {
            "business_name": ("STRING", {"default": "", "tooltip": "Shown on the end card. Empty = the preset's."}),
            "business_type": ("STRING", {"default": "", "tooltip": "e.g. barber shop, taco truck, nail salon, dog groomer. "
                                         "Needed for Gemini; empty = the preset's."}),
            "owner": txt("The underdog owner: what they look like. No names. Empty = the preset's."),
            "rival": txt("The rival chain's influencer: what they look like. No names. Empty = the preset's."),
            "regular": txt("The loyal regular who never leaves: what they look like. Empty = the preset's."),
            "hero_1": txt("Agency duo, first hero: looks. Empty = the house duo."),
            "hero_2": txt("Agency duo, second hero: looks. Empty = the house duo."),
            "tone": (list(core.TONES), {"default": "funny"}),
            "model": (core.VEO_MODELS, {"default": "veo-3.1-lite", "tooltip": "Veo 3.1 lite is about $0.05/s with audio at 720p."}),
            "script_source": (PRESET_SOURCES + [GEMINI_SOURCE], {"tooltip": "A built-in business, or Gemini fills in the details for "
                                                                 "any other business type (same story)."}),
        }}

    def run(self, business_name, business_type, owner, rival, regular, hero_1, hero_2, tone, model, script_source):
        brief = core.make_brief(business_name, business_type, owner, rival, regular, hero_1, hero_2, tone, model, script_source)
        return (json.dumps(brief), core.writer_prompt(brief), model)


class UnderdogSheetCheck:
    """Reference sheets for everything: every recurring person, prop and place (and each state of the rival store) needs its
    sheet. With 'require' on (the paid app) a missing sheet stops the run before anything is paid for, listing which; with
    it off (the free draft) the same list is printed as a warning and the draft goes on with placeholders.
    brief and writer_prompt pass through, so Gemini and the script wait for this check."""
    CATEGORY = "Underdog Story"
    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("brief", "writer_prompt", "report")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"brief": ("STRING", {"forceInput": True}), "writer_prompt": ("STRING", {"forceInput": True}),
                             "require": ("BOOLEAN", {"default": True, "tooltip": "On: refuse to run (and spend) with a sheet missing."})},
                "optional": {r: ("IMAGE",) for r in core.ROLES}}

    def run(self, brief, writer_prompt, require=True, **images):
        missing = [r for r in core.ROLES if _is_blank(images.get(r))]
        msg = core.missing_sheets_message(missing)
        if missing and require:
            raise ValueError("REFUSED (nothing was paid for): " + msg)
        if missing:
            print("[Underdog Story] WARNING: " + msg)
            msg = "WARNING (free draft, placeholders used): " + msg
        return (brief, writer_prompt, msg)


class UnderdogScript:
    """Builds the 15-beat script: the preset's slots, or Gemini's (asked for only when Gemini is picked), checked against
    the rules (one speaker per scene, lines that fit the take, no names, no brands, locked-off camera on the landmark,
    title cards on time jumps, no bare answers, no crowds through doors) and turned into prompts."""
    CATEGORY = "Underdog Story"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("script", "script_text")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"brief": ("STRING", {"forceInput": True})},
                "optional": {"writer_reply": ("STRING", {"forceInput": True, "lazy": True})}}

    def check_lazy_status(self, brief, writer_reply=None):
        b = json.loads(brief)
        return ["writer_reply"] if not b.get("preset") and writer_reply is None else []

    def run(self, brief, writer_reply=None):
        b = json.loads(brief)
        if b.get("preset"):
            story = core.story_from_preset(b["preset"])
        else:
            if not writer_reply:
                raise ValueError("Gemini returned nothing (the free draft has no Gemini). Run again, or pick a preset.")
            story = core.parse_reply(writer_reply)
        script = core.build_script(b, story)
        return (json.dumps(script), core.script_text(script))


class UnderdogScene:
    """One scene: the keyframe prompt (with a legend of the attached sheets), the Veo motion prompt, the reference sheets
    this scene needs as one batch, the caption text and the take length."""
    CATEGORY = "Underdog Story"
    RETURN_TYPES = ("STRING", "STRING", "IMAGE", "STRING", "INT")
    RETURN_NAMES = ("keyframe_prompt", "motion_prompt", "references", "caption", "seconds")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"script": ("STRING", {"forceInput": True}),
                             "scene": ("INT", {"default": 1, "min": 1, "max": N})},
                "optional": {r: ("IMAGE",) for r in core.ROLES}}

    def run(self, script, scene, **images):
        s = json.loads(script)
        sc = s["scenes"][scene - 1]
        present = [r for r in sc["refs"] if not _is_blank(images.get(r))][:core.MAX_REFS]   # refs are in on-screen priority order
        refs = torch.cat([_fit(images[r]) for r in present]) if present else None
        return (core.keyframe_prompt(s, scene - 1, present), sc["motion_prompt"], refs, " / ".join(sc["captions"]), sc["seconds"])


class UnderdogDraftScene:
    """The free draft: one storyboard clip per scene (the scene's location, rival-store or car sheet as the backdrop, the shot and the
    lines), at the scene's real length, with a quiet ambience bed. Nothing is generated and nothing is paid for."""
    CATEGORY = "Underdog Story"
    RETURN_TYPES = ("VIDEO",)
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"script": ("STRING", {"forceInput": True}),
                             "scene": ("INT", {"default": 1, "min": 1, "max": N})},
                "optional": {r: ("IMAGE",) for r in core.ROLES}}

    def run(self, script, scene, **images):
        s = json.loads(script)
        sc = s["scenes"][scene - 1]
        stores = ["rival_store_closed", "rival_store_open"]
        order = (stores + ["location"] if sc["landmark"] else ["location"] + stores) + ["old_car", "prize_car"] + core.CHARACTERS
        bg = next((_pil(images[r]) for r in order if r in sc["refs"] and not _is_blank(images.get(r))), None)
        tmp = Path(tempfile.mkdtemp(prefix="underdog_draft_"))
        out = core.draft_clip(_out_dir(tmp) / f"underdog_draft_{tmp.name}_{scene:02d}.mp4", sc, s, bg)
        return (VideoFromFile(str(out)),)


class UnderdogContactSheet:
    """All keyframes on one image, so you can check the film's look before (and while) the videos render."""
    CATEGORY = "Underdog Story"
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}, "optional": {f"keyframe_{i:02d}": ("IMAGE",) for i in range(1, N + 1)}}

    def run(self, **frames):
        tiles = [frames[k] for k in sorted(frames) if frames[k] is not None]
        if not tiles:
            raise ValueError("No keyframes to show.")
        tw, th, cols = 270, 480, 5
        rows = (len(tiles) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * tw, rows * th), (20, 18, 16))
        for k, t in enumerate(tiles):
            pil = _pil(t)
            pil.thumbnail((tw, th), Image.LANCZOS)
            sheet.paste(pil, ((k % cols) * tw + (tw - pil.width) // 2, (k // cols) * th + (th - pil.height) // 2))
        return (torch.from_numpy(np.asarray(sheet, dtype=np.float32) / 255.0)[None],)


class UnderdogFinish:
    """The final cut, the v9 recipe: dissolves (video and audio), the time-jump title cards, the view counter, the next-episode
    DM from another business, classic captions, an 'AI-generated' label and an end card. Dialogue and sound only; the
    Score Mix node adds the score and masters."""
    CATEGORY = "Underdog Story"
    RETURN_TYPES = ("VIDEO",)
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"script": ("STRING", {"forceInput": True}),
                             "captions": ("BOOLEAN", {"default": True}),
                             "ai_label": ("BOOLEAN", {"default": True, "tooltip": "Keep this on when you post: the film is AI-generated."}),
                             "credit": ("BOOLEAN", {"default": True, "tooltip": "Small 'made with Underdog Story' on the end card"})},
                "optional": {f"scene_{i:02d}": ("VIDEO",) for i in range(1, N + 1)}}

    def run(self, script, captions=True, ai_label=True, credit=True, **videos):
        s = json.loads(script)
        keys = [k for k in sorted(videos) if videos[k] is not None]
        if not keys:
            raise ValueError("No scene videos to cut.")
        tmp = Path(tempfile.mkdtemp(prefix="underdog_"))
        clips, scenes = [], []
        for k in keys:
            p = tmp / f"{k}.mp4"
            videos[k].save_to(str(p))
            clips.append(p)
            sc = dict(s["scenes"][int(k.split("_")[1]) - 1])
            if not captions:
                sc["captions"] = []
            scenes.append(sc)
        out = _out_dir(tmp) / f"underdog_cut_{tmp.name}.mp4"
        b = s["brief"]
        core.finish(clips, scenes, out, tmp, [b["business_name"], s.get("title") or "An Underdog Story"], overlay=s.get("overlay"),
                    ai_label=ai_label, credit=credit)
        return (VideoFromFile(str(out)),)


class UnderdogScoreMix:
    """The score and the master. With 'score' on, Sonilo's score for this cut is levelled (-27 LUFS), ducked under the
    dialogue (sidechain) and mixed; then the film is mastered to -14 LUFS / -1 dBTP. Sonilo is only asked for when 'score'
    is on. music_path: a track you own or licensed, used instead of Sonilo."""
    CATEGORY = "Underdog Story"
    RETURN_TYPES = ("VIDEO",)
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"video": ("VIDEO",),
                             "score": ("BOOLEAN", {"default": True, "tooltip": "Add a Sonilo score made for this cut (about $0.009/s)."}),
                             "music_path": ("STRING", {"default": "", "tooltip": "Optional: a track you OWN or licensed, instead of "
                                                       "Sonilo. Never a copyrighted song."})},
                "optional": {"music": ("AUDIO", {"lazy": True})}}

    def check_lazy_status(self, video, score=True, music_path="", music=None):
        return ["music"] if score and not music_path.strip() and music is None else []

    def run(self, video, score=True, music_path="", music=None):
        tmp = Path(tempfile.mkdtemp(prefix="underdog_mix_"))
        src = tmp / "cut.mp4"
        video.save_to(str(src))
        track = None
        if music_path.strip():
            track = Path(music_path.strip()).expanduser()
            if not track.is_file():
                raise ValueError(f"music_path does not exist: {track}")
        elif score and music is not None:
            track = core.write_wav(tmp / "score.wav", music["waveform"], music["sample_rate"])
        out = _out_dir(tmp) / f"underdog_film_{tmp.name}.mp4"
        core.score_mix(src, out, tmp, music=track)
        return (VideoFromFile(str(out)),)


NODE_CLASS_MAPPINGS = {"UnderdogBrief": UnderdogBrief, "UnderdogSheetCheck": UnderdogSheetCheck, "UnderdogScript": UnderdogScript, "UnderdogScene": UnderdogScene,
                       "UnderdogDraftScene": UnderdogDraftScene, "UnderdogContactSheet": UnderdogContactSheet,
                       "UnderdogFinish": UnderdogFinish, "UnderdogScoreMix": UnderdogScoreMix}
NODE_DISPLAY_NAME_MAPPINGS = {"UnderdogBrief": "Underdog Story: Brief", "UnderdogSheetCheck": "Underdog Story: Sheet Check", "UnderdogScript": "Underdog Story: Script",
                              "UnderdogScene": "Underdog Story: Scene", "UnderdogDraftScene": "Underdog Story: Draft Scene ($0)",
                              "UnderdogContactSheet": "Underdog Story: Keyframe Sheet", "UnderdogFinish": "Underdog Story: Final Cut",
                              "UnderdogScoreMix": "Underdog Story: Score Mix"}
