"""Underdog Story ComfyUI nodes. The paid generation is done by ComfyUI's own partner nodes (Gemini, Nano Banana 2,
Veo 3.1); these nodes write and check the script, pick the reference sheets per scene and cut the finished film."""
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
GEMINI_SOURCE = "write with Gemini (from your descriptions)"
DEFAULT = core.load_preset(core.list_presets()[0]) if core.list_presets() else {"cast": {}, "business_name": "", "business_type": ""}
REF_SIZE = 1024


def _is_blank(img):
    """An unused reference slot holds the blank placeholder (one flat color)."""
    return img is None or float(img[0].float().std()) < 0.01


def _fit(img, size=REF_SIZE):
    """Letterbox one reference image onto a white square so different sheets can share one batch."""
    pil = Image.fromarray((img[0].cpu().numpy() * 255).clip(0, 255).astype(np.uint8)).convert("RGB")
    pil.thumbnail((size, size), Image.LANCZOS)
    canvas = Image.new("RGB", (size, size), (255, 255, 255))
    canvas.paste(pil, ((size - pil.width) // 2, (size - pil.height) // 2))
    return torch.from_numpy(np.asarray(canvas, dtype=np.float32) / 255.0)[None]


class UnderdogBrief:
    """The story inputs: business, cast descriptions (looks, never names), tone, Veo model and where the lines come from."""
    CATEGORY = "Underdog Story"
    RETURN_TYPES = ("STRING", "STRING", core.VEO_MODELS)
    RETURN_NAMES = ("brief", "writer_prompt", "veo_model")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        c = DEFAULT["cast"]
        txt = lambda d, tip: ("STRING", {"default": d, "multiline": True, "tooltip": tip})
        return {"required": {
            "business_name": ("STRING", {"default": DEFAULT["business_name"], "tooltip": "Shown on the end card."}),
            "business_type": ("STRING", {"default": DEFAULT["business_type"], "tooltip": "e.g. family bakery, barber shop, taco truck"}),
            "owner": txt(c.get("owner", ""), "The underdog owner, one line: what they look like. No names."),
            "rival": txt(c.get("rival", ""), "The flashy rival: what they look like. No names."),
            "partner": txt(c.get("partner", ""), "Optional partner / love interest who loses faith. Empty = a worried best friend."),
            "hero_1": txt(c.get("hero1", ""), "Hero duo, first hero: what they look like. No names."),
            "hero_2": txt(c.get("hero2", ""), "Hero duo, second hero: what they look like. No names."),
            "tone": (list(core.TONES), {"default": "funny"}),
            "model": (core.VEO_MODELS, {"default": "veo-3.1-lite", "tooltip": "Veo 3.1 lite is about $0.05/s with audio at 720p."}),
            "script_source": (PRESET_SOURCES + [GEMINI_SOURCE], {"tooltip": "Preset = the built-in lines. Gemini = new lines for your business."}),
        }}

    def run(self, business_name, business_type, owner, rival, partner, hero_1, hero_2, tone, model, script_source):
        brief = core.make_brief(business_name, business_type, owner, rival, partner, hero_1, hero_2, tone, model, script_source)
        return (json.dumps(brief), core.writer_prompt(brief), model)


class UnderdogScript:
    """Builds the 12-beat script: the preset's lines, or Gemini's reply (asked for only when Gemini is picked), checked
    against the rules (12 beats, short lines that fit 8 s, no names, no brands) and turned into prompts."""
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
            raw = core.load_preset(b["preset"])
            raw = {"title": raw.get("title", ""), "scenes": raw["scenes"]}
        else:
            if not writer_reply:
                raise ValueError("Gemini returned nothing. Run again, or pick the preset.")
            raw = core.parse_reply(writer_reply)
        script = core.build_script(b, raw)
        return (json.dumps(script), core.script_text(script))


class UnderdogScene:
    """One scene: the keyframe prompt (with a legend of the attached sheets), the Veo motion prompt, the reference sheets
    this scene needs as one batch, and the caption text."""
    CATEGORY = "Underdog Story"
    RETURN_TYPES = ("STRING", "STRING", "IMAGE", "STRING")
    RETURN_NAMES = ("keyframe_prompt", "motion_prompt", "references", "caption")
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"script": ("STRING", {"forceInput": True}),
                             "scene": ("INT", {"default": 1, "min": 1, "max": len(core.BEATS)})},
                "optional": {r: ("IMAGE",) for r in core.ROLES}}

    def run(self, script, scene, **images):
        s = json.loads(script)
        sc = s["scenes"][scene - 1]
        present = [r for r in sc["refs"] if not _is_blank(images.get(r))]
        refs = torch.cat([_fit(images[r]) for r in present]) if present else None
        return (core.keyframe_prompt(s, scene - 1, present), sc["motion_prompt"], refs, " / ".join(sc["captions"]))


class UnderdogContactSheet:
    """All keyframes on one image, so you can check the film's look before (and while) the videos render."""
    CATEGORY = "Underdog Story"
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}, "optional": {f"keyframe_{i:02d}": ("IMAGE",) for i in range(1, len(core.BEATS) + 1)}}

    def run(self, **frames):
        tiles = [frames[k] for k in sorted(frames) if frames[k] is not None]
        if not tiles:
            raise ValueError("No keyframes to show.")
        tw, th, cols = 270, 480, 6
        rows = (len(tiles) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * tw, rows * th), (20, 18, 16))
        for k, t in enumerate(tiles):
            pil = Image.fromarray((t[0].cpu().numpy() * 255).clip(0, 255).astype(np.uint8)).convert("RGB")
            pil.thumbnail((tw, th), Image.LANCZOS)
            sheet.paste(pil, ((k % cols) * tw + (tw - pil.width) // 2, (k // cols) * th + (th - pil.height) // 2))
        return (torch.from_numpy(np.asarray(sheet, dtype=np.float32) / 255.0)[None],)


class UnderdogFinish:
    """The final cut: scenes joined with short transitions (video and audio), classic burned-in captions, an
    'AI-generated' label, an end card, loudness -14 LUFS, H.264 CRF 18. One MP4."""
    CATEGORY = "Underdog Story"
    RETURN_TYPES = ("VIDEO",)
    FUNCTION = "run"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"script": ("STRING", {"forceInput": True}),
                             "captions": ("BOOLEAN", {"default": True}),
                             "ai_label": ("BOOLEAN", {"default": True, "tooltip": "Keep this on when you post: the film is AI-generated."}),
                             "credit": ("BOOLEAN", {"default": True, "tooltip": "Small 'made with Underdog Story' on the end card"}),
                             "music_path": ("STRING", {"default": "", "tooltip": "Optional: path to a music track you OWN or licensed, mixed "
                                                       "low under the dialogue. Empty = Veo's own sound only. Never a copyrighted song."})},
                "optional": {f"scene_{i:02d}": ("VIDEO",) for i in range(1, len(core.BEATS) + 1)}}

    def run(self, script, captions=True, ai_label=True, credit=True, music_path="", **videos):
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
        try:
            import folder_paths
            out_dir = Path(folder_paths.get_temp_directory())
        except ImportError:
            out_dir = tmp
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"underdog_{tmp.name}.mp4"
        b = s["brief"]
        end = [b["business_name"], s.get("title") or "An Underdog Story"]
        music = Path(music_path.strip()).expanduser() if music_path.strip() else None
        if music and not music.is_file():
            raise ValueError(f"music_path does not exist: {music}")
        core.finish(clips, scenes, out, tmp, end, ai_label=ai_label, credit=credit, music_path=music)
        return (VideoFromFile(str(out)),)


NODE_CLASS_MAPPINGS = {"UnderdogBrief": UnderdogBrief, "UnderdogScript": UnderdogScript, "UnderdogScene": UnderdogScene,
                       "UnderdogContactSheet": UnderdogContactSheet, "UnderdogFinish": UnderdogFinish}
NODE_DISPLAY_NAME_MAPPINGS = {"UnderdogBrief": "Underdog Story: Brief", "UnderdogScript": "Underdog Story: Script",
                              "UnderdogScene": "Underdog Story: Scene", "UnderdogContactSheet": "Underdog Story: Keyframe Sheet",
                              "UnderdogFinish": "Underdog Story: Final Cut"}
