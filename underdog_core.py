"""Underdog Story core: the 12-beat script (preset or Gemini-written), prompt building, validation and the final cut.
Pure Python + Pillow + ffmpeg, no ComfyUI imports, so it can be tested on its own. Apache-2.0."""
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
PRESETS_DIR = ROOT / "presets"
FONT = ROOT / "fonts" / "Inter.ttf"

# ---------------------------------------------------------------- the arc
BEATS = [   # the v6 spine: every beat joins the next with BUT or THEREFORE, one speaker per scene
    (1, "last one", "Hook. The owner alone with the last unsold item and a CLOSING SUNDAY card. A two-word line."),
    (2, "the rival", "The rival drops by and insults the shop sweetly. The owner keeps a tight smile."),
    (3, "the doubter", "The partner states one dry fact about how bad sales are."),
    (4, "alone", "The partner leaves for a 'real job'. The owner sends him off without looking at him."),
    (5, "strangers", "The hero duo walks in; the talker points at the last item."),
    (6, "the taste", "The talker tastes it in silence; the quiet one, filming, asks for it again, slower."),
    (7, "the heart", "The owner shows the family craft behind the business (a recipe, an old photo)."),
    (8, "who are you", "The owner looks up at the camera. The quiet one: they make ads."),
    (9, "the reveal", "Next morning the owner opens up to a huge line outside: the video went viral."),
    (10, "back of the line", "The rival tries to cut the line. The owner puts him in his place without stopping work."),
    (11, "the car", "The partner, now in a rival-brand visor at the curb, as a supercar with no badges roars up."),
    (12, "last one", "The owner in the car, smug and brief; ends on the line that loops back to scene 1."),
]
ROLES = ["owner", "rival", "partner", "hero1", "hero2", "location"]       # reference image slots, in this order
CHARACTERS = ROLES[:5]
SPEAKERS = set(CHARACTERS) | {"offscreen", "staff", "customer", "crowd", "robot"}
PLACEHOLDERS = set(CHARACTERS) | {"business"}
TRANSITIONS = {"cut": ("fade", 0.05), "fade": ("fade", 0.5), "fadeblack": ("fadeblack", 0.6), "fadewhite": ("fadewhite", 0.3),
               "dissolve": ("dissolve", 0.5), "whip_left": ("slideleft", 0.3), "whip_right": ("slideright", 0.3)}
TONES = {"funny": "Dry comedy timing, natural understated delivery, reactions carry the laughs.",
         "heartfelt": "Sincere, warm performances; let the quiet moments breathe."}
VEO_MODELS = ["veo-3.1-lite", "veo-3.1-fast-generate", "veo-3.1-generate"]   # exact Veo3VideoGenerationNode values
MAX_LINE_WORDS = 20          # one spoken line must fit comfortably in an 8 s take
MAX_SCENE_WORDS = 32         # everything spoken in one 8 s take
STYLE = "Glossy 3D animated family-film style"
KEYFRAME_HEAD = (f"Keyframe for an animated film. {STYLE}, vertical 9:16 cinematic frame. Keep every character's face, hair, "
                 "facial hair, glasses, build and outfit exactly as in the reference images. No captions, no subtitles, no real brand logos.")
MOTION_TAIL = (f"{STYLE}. Keep every character, face, outfit and the setting exactly as in the start frame. "
               "One continuous take, no cuts. No captions, no subtitles, no on-screen text except signs already in the frame.")
SILENT_VERBS = ("says", "shouts", "yells", "whispers", "asks", "replies", "mutters")
# Real people never appear by name. Brand names never appear (no real logos, no real car models).
# Stored as SHA-256 of the lower-case first name, so the repo itself holds no real names.
REAL_NAME_SHA256 = {"102cf10b5286bad9fcfe5e275ace3ddd7dcc23931fb0ca93dc223daf9877cabd",
                    "b8cca97395d6540ab952aee96f21521c2688b804d97357697e9dd7d0b49b6bb2"}
BRANDS = {"ferrari", "lamborghini", "lambo", "porsche", "mclaren", "bugatti", "tesla", "bmw", "mercedes", "audi", "starbucks",
          "mcdonald's", "mcdonalds", "dunkin", "nike", "adidas", "apple", "iphone", "instagram", "tiktok", "youtube", "facebook",
          "google", "coca-cola", "pepsi", "gucci", "louis vuitton", "rolex", "uber", "doordash"}


# ---------------------------------------------------------------- presets
def list_presets():
    return sorted(p.name for p in PRESETS_DIR.iterdir() if (p / "preset.json").exists()) if PRESETS_DIR.exists() else []


def load_preset(name):
    return json.loads((PRESETS_DIR / name / "preset.json").read_text())


# ---------------------------------------------------------------- validation
def _words(s):
    return len(re.findall(r"[A-Za-z0-9']+", s))


def _outside_quotes(s):
    return re.sub(r'"[^"]*"', " ", s)


def _has_word(text, word):
    return re.search(r"(?<![A-Za-z])" + re.escape(word) + r"(?![A-Za-z])", text, re.I) is not None


def real_names_in(text):
    return sorted({w for w in re.findall(r"[A-Za-z]+", text) if hashlib.sha256(w.lower().encode()).hexdigest() in REAL_NAME_SHA256})


def _check_text(where, text, banned_names, errors, dialogue=False):
    for w in real_names_in(text):
        errors.append(f"{where}: real person's name '{w}'")
    for b in BRANDS:
        if _has_word(text, b):
            errors.append(f"{where}: brand name '{b}'")
    if not dialogue:
        for n in banned_names:
            if _has_word(_outside_quotes(text), n):
                errors.append(f"{where}: character name '{n}' (describe characters, never name them)")
        for ph in re.findall(r"\{(\w+)\}", text):
            if ph not in PLACEHOLDERS:
                errors.append(f"{where}: unknown placeholder {{{ph}}}")


def validate_script(script, banned_names=()):
    """Return a list of problems (empty = valid). Same rules for the preset and for Gemini's reply."""
    errors = []
    if not isinstance(script, dict) or not isinstance(script.get("scenes"), list):
        return ["script must be an object with a 'scenes' list"]
    scenes = script["scenes"]
    if len(scenes) != len(BEATS):
        errors.append(f"need exactly {len(BEATS)} scenes, got {len(scenes)}")
    for i, sc in enumerate(scenes):
        w = f"scene {i + 1}"
        if not isinstance(sc, dict):
            errors.append(f"{w}: not an object"); continue
        if sc.get("beat") != i + 1:
            errors.append(f"{w}: beat must be {i + 1}")
        for k in ("keyframe", "camera", "music"):
            if not isinstance(sc.get(k), str) or not sc[k].strip():
                errors.append(f"{w}: '{k}' must be a non-empty string")
            else:
                _check_text(f"{w} {k}", sc[k], banned_names, errors)
        refs = sc.get("refs")
        if not isinstance(refs, list) or not refs or any(r not in ROLES for r in refs):
            errors.append(f"{w}: refs must be a non-empty list of {ROLES}")
        if sc.get("transition", "cut") not in TRANSITIONS:
            errors.append(f"{w}: transition must be one of {sorted(TRANSITIONS)}")
        perf = sc.get("performance")
        if not isinstance(perf, list) or not (1 <= len(perf) <= 8):
            errors.append(f"{w}: performance must be a list of 1 to 8 steps"); continue
        spoken, speakers = 0, set()
        for j, st in enumerate(perf):
            pw = f"{w} step {j + 1}"
            if not isinstance(st, dict) or not isinstance(st.get("how"), str) or not st["how"].strip():
                errors.append(f"{pw}: needs a non-empty 'how'"); continue
            if st.get("who") is not None and st["who"] not in SPEAKERS:
                errors.append(f"{pw}: who must be one of {sorted(SPEAKERS)} or null")
            _check_text(pw, st["how"], banned_names, errors)
            line = st.get("line")
            if line is None and any(_has_word(st["how"], v) for v in SILENT_VERBS):
                errors.append(f"{pw}: a silent step must not speak ('{st['how']}')")
            if line is not None:
                speakers.add(st.get("who"))
                if not isinstance(line, str) or not line.strip():
                    errors.append(f"{pw}: line must be a non-empty string or null"); continue
                if '"' in line:
                    errors.append(f"{pw}: line must not contain double quotes")
                n = _words(line)
                spoken += n
                if n > MAX_LINE_WORDS:
                    errors.append(f"{pw}: line has {n} words (max {MAX_LINE_WORDS}): {line!r}")
                _check_text(pw, line, banned_names, errors, dialogue=True)
        if len(speakers) != 1 or not speakers <= set(CHARACTERS):
            errors.append(f"{w}: exactly one on-screen speaker per scene (a cast member), got {sorted(map(str, speakers))}")
        if spoken > MAX_SCENE_WORDS:
            errors.append(f"{w}: {spoken} spoken words won't fit 8 s (max {MAX_SCENE_WORDS})")
    return errors


# ---------------------------------------------------------------- the brief + Gemini writer
def make_brief(business_name, business_type, owner, rival, partner, hero_1, hero_2, tone, model, source):
    preset = source.split(":", 1)[1].strip() if source.startswith("preset:") else None
    cast = {"owner": owner.strip(), "rival": rival.strip(), "partner": partner.strip() or "the owner's worried best friend in a grey cardigan",
            "hero1": hero_1.strip(), "hero2": hero_2.strip()}
    for k, v in cast.items():
        if not v:
            raise ValueError(f"Please describe the {k} (what they look like, not their name).")
        for n in real_names_in(v):
            raise ValueError(f"The {k} description contains a real person's name ('{n}'). Describe looks, not names.")
    return {"business_name": business_name.strip() or "Your Business", "business_type": business_type.strip() or "small business",
            "cast": cast, "tone": tone if tone in TONES else "funny", "model": model, "preset": preset}


def writer_prompt(brief):
    example = load_preset(list_presets()[0])["scenes"][0] if list_presets() else {}
    beats = "\n".join(f"{n}. {name}: {desc}" for n, name, desc in BEATS)
    return f"""You are a sitcom writer. Write a {len(BEATS)}-scene vertical animated short, an underdog story, for a real small business.

Business: {brief['business_name']} ({brief['business_type']}). Tone: {brief['tone']} ({TONES[brief['tone']]})
Characters, ALWAYS written as placeholders, never named:
- {{owner}}: the underdog owner. Looks: {brief['cast']['owner']}
- {{rival}}: the big flashy rival. Looks: {brief['cast']['rival']}
- {{partner}}: the owner's partner who loses faith. Looks: {brief['cast']['partner']}
- {{hero1}} and {{hero2}}: the marketing hero duo. Looks: {brief['cast']['hero1']} / {brief['cast']['hero2']}
- {{business}}: the business name, only if it must appear on a sign.

The beats, one 8-second scene each, in this order:
{beats}

Rules:
- Every scene is ONE continuous 8-second take with EXACTLY ONE speaker (a cast member); everyone else is silent. No new people enter.
- Natural dialogue: short, specific, mostly under 8 words; not a joke on every line. Laughs come from reactions. Up to 2 short spoken lines, each line at most {MAX_LINE_WORDS} words, at most {MAX_SCENE_WORDS} spoken words per scene. Jokes land fast.
- Never use any person's name anywhere outside spoken lines; use the placeholders. Spoken lines may say "babe", "boss" and the like, not names.
- No real brands, logos, products, apps or car makers. The supercar in beat 11 is a glossy original exotic with no badges.
- "keyframe": the single start frame: time of day, place, who stands where, expressions, camera framing, light. Use placeholders.
- "camera": the camera move for the take. "music": one short music/sound cue sentence.
- "performance": the take in order. Each step: "who" (one of {sorted(SPEAKERS)} or null), "how" (action and delivery, e.g. "leans in and says smugly"), "line" (the exact words spoken, no double quotes) or null for a silent action.
- "refs": which reference sheets the keyframe needs, from {ROLES}. "transition": out of the scene, one of {sorted(TRANSITIONS)}.

Reply with JSON only, no commentary, exactly this shape: {{"title": "...", "scenes": [ ...{len(BEATS)} scenes... ]}}
Example scene (a bakery; write your own for this business):
{json.dumps(example, indent=1)}
"""


def parse_reply(text):
    """Gemini's reply -> {"title", "scenes"}. Tolerates code fences and chatter around the JSON."""
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    data = None
    for a, b in ((t.find("{"), t.rfind("}")), (t.find("["), t.rfind("]"))):
        if 0 <= a < b:
            try:
                data = json.loads(t[a:b + 1]); break
            except json.JSONDecodeError:
                continue
    if data is None:
        raise ValueError("Gemini's reply had no readable JSON. Run again (or switch to the preset).")
    if isinstance(data, list):
        data = {"title": "", "scenes": data}
    return data


# ---------------------------------------------------------------- rendering prompts
def _cap(s):
    return s[:1].upper() + s[1:]


def _fill(text, brief):
    cast = dict(brief["cast"], business=brief["business_name"])
    return re.sub(r"\{(\w+)\}", lambda m: cast.get(m.group(1), m.group(0)), text)


def build_script(brief, raw):
    """Validate a raw script (preset or Gemini) and render every scene's prompts. Raises ValueError on any problem."""
    banned = set()
    for p in list_presets():
        banned |= {n.lower() for n in load_preset(p).get("cast_names", [])}
    errs = validate_script(raw, banned)
    if errs:
        raise ValueError("The script broke the rules:\n- " + "\n- ".join(errs[:20]))
    scenes = []
    for sc in raw["scenes"]:
        steps = []
        for st in sc["performance"]:
            s = _fill(st["how"], brief)
            if st.get("who") in CHARACTERS:
                s = _fill("{" + st["who"] + "} ", brief) + s
            elif st.get("who") == "offscreen" and "off-screen" not in s.lower():
                s = "A voice off-screen " + s
            s = _cap(s)
            steps.append(f'{s}: "{st["line"]}"' if st.get("line") else s.rstrip(".") + ".")
        speaker = next(st["who"] for st in sc["performance"] if st.get("line"))
        only = (f"Only {_fill('{' + speaker + '}', brief)} speaks in this shot; everyone else stays silent with mouth closed and "
                "no lip movement. No new people enter the frame.")
        motion = " ".join([f"Animate this start frame: {_fill(sc['camera'], brief).rstrip('.')}."] + steps +
                          [only, _cap(_fill(sc["music"], brief).rstrip(".")) + ".", TONES[brief["tone"]], MOTION_TAIL])
        scenes.append({"beat": sc["beat"], "name": BEATS[sc["beat"] - 1][1],
                       "keyframe_body": _cap(_fill(sc["keyframe"], brief)), "motion_prompt": motion, "refs": sc["refs"], "speaker": speaker,
                       "captions": [st["line"] for st in sc["performance"] if st.get("line")],
                       "transition": sc.get("transition", "cut")})
        for k in ("keyframe_body", "motion_prompt"):   # descriptions typed by the user are checked once filled in
            for n in real_names_in(scenes[-1][k]):
                raise ValueError(f"scene {sc['beat']}: a real person's name ('{n}') ended up in the prompt")
    return {"title": raw.get("title", ""), "brief": brief, "scenes": scenes}


REF_LABEL = {"owner": "the character sheet of {owner}", "rival": "the character sheet of {rival}",
             "partner": "the character sheet of {partner}", "hero1": "the character sheet of {hero1}",
             "hero2": "the character sheet of {hero2}", "location": "the location ({business})"}


def keyframe_prompt(script, scene_idx, present_refs):
    """present_refs: the roles whose reference image is really attached, in the order they are sent."""
    sc = script["scenes"][scene_idx]
    legend = ""
    if present_refs:
        legend = " Reference images, in order: " + "; ".join(
            f"{k + 1}) {_fill(REF_LABEL[r], script['brief'])}" for k, r in enumerate(present_refs)) + "."
    return f"{KEYFRAME_HEAD}{legend}\n{sc['keyframe_body']}"


def script_text(script):
    lines = [f"{script['brief']['business_name']}: {script.get('title') or 'Underdog Story'}"]
    for sc in script["scenes"]:
        lines.append(f"\n{sc['beat']:>2}. {sc['name'].upper()}")
        lines += [f'    "{c}"' for c in sc["captions"]]
    return "\n".join(lines)


# ---------------------------------------------------------------- final cut (ported from the pilot v3 edit)
def _ff():
    return shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg", shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"


def probe(path):
    _, fp = _ff()
    out = json.loads(subprocess.check_output([fp, "-v", "error", "-show_streams", "-of", "json", str(path)]))
    v = next(s for s in out["streams"] if s["codec_type"] == "video")
    return {"w": int(v["width"]), "h": int(v["height"]), "dur": float(v["duration"]),
            "audio": any(s["codec_type"] == "audio" for s in out["streams"])}


def _font(size):
    try:
        return ImageFont.truetype(str(FONT), size)
    except OSError:
        return ImageFont.load_default(size)


def text_png(path, txt, size, w, pad=40):
    f = _font(size)
    d = ImageDraw.Draw(Image.new("RGBA", (w, 10)))
    lines, cur = [], ""
    for wd in txt.split():
        trial = (cur + " " + wd).strip()
        if d.textlength(trial, font=f) > w - 2 * pad and cur:
            lines.append(cur); cur = wd
        else:
            cur = trial
    lines.append(cur)
    img = Image.new("RGBA", (w, int(size * 1.25 * len(lines)) + 12), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    for k, ln in enumerate(lines):
        d.text(((w - d.textlength(ln, font=f)) / 2, k * size * 1.25), ln, font=f, fill="white",
               stroke_width=max(2, size // 12), stroke_fill="black")
    img.save(path)


def caption_cues(lines, start, dur, lead=0.3, tail=0.4):
    """Spread a scene's spoken lines over its take, in proportion to their length."""
    if not lines:
        return []
    span = max(0.5, dur - lead - tail)
    weights = [max(1, _words(t)) for t in lines]
    tot, t, cues = sum(weights), start + lead, []
    for txt, wgt in zip(lines, weights):
        d = span * wgt / tot
        cues.append((round(t, 3), round(t + d, 3), txt)); t += d
    return cues


def finish(clips, scenes, out, work, end_lines, ai_label=True, credit=True, end_secs=3.0, fps=24, music_path=None, music_db=-20):
    """clips: mp4 paths in order; scenes: the matching rendered scenes (captions + transition). Returns a receipt.
    No music is added unless music_path points at a track you own or have licensed; it is looped under the dialogue."""
    ffmpeg, _ = _ff()
    work = Path(work); ov = work / "ov"; ov.mkdir(parents=True, exist_ok=True)
    info = [probe(c) for c in clips]
    W, H = info[0]["w"] - info[0]["w"] % 2, info[0]["h"] - info[0]["h"] % 2
    dur = [i["dur"] for i in info]
    trans = []
    for k, sc in enumerate(scenes):
        name, td = TRANSITIONS.get(sc.get("transition", "cut"), TRANSITIONS["cut"])
        trans.append((name, min(td, dur[k] / 3, (dur[k + 1] / 3) if k + 1 < len(dur) else end_secs / 3)))
    starts, t = [], 0.0
    for d, (_, td) in zip(dur, trans):
        starts.append(t); t += d - td
    end_start = t
    total = end_start + end_secs
    cues = []
    for k, sc in enumerate(scenes):
        cues += caption_cues(sc.get("captions", []), starts[k], dur[k] - trans[k][1])
    cap_size = max(28, W // 16)
    for k, (_, _, txt) in enumerate(cues):
        text_png(ov / f"cap{k:02d}.png", txt, cap_size, W)
    if ai_label:
        f = _font(max(16, W // 34)); tw = int(ImageDraw.Draw(Image.new("RGBA", (1, 1))).textlength("AI-generated", font=f))
        lab = Image.new("RGBA", (tw + 24, max(16, W // 34) + 18), (0, 0, 0, 110))
        ImageDraw.Draw(lab).text((12, 7), "AI-generated", font=f, fill="white"); lab.save(ov / "ai.png")
    card = Image.new("RGB", (W, H), (24, 20, 18)); d = ImageDraw.Draw(card)
    rows = [(end_lines[0], W // 12, .40)] + [(ln, W // 20, .40 + .07 * (k + 1)) for k, ln in enumerate(end_lines[1:])]
    rows.append(("AI-generated animation", W // 30, .86))
    if credit:
        rows.append(("made with Underdog Story for ComfyUI", W // 36, .90))
    for txt, size, y in rows:
        fo = _font(size)
        if d.textlength(txt, font=fo) > W * .9:
            fo = _font(int(size * W * .9 / d.textlength(txt, font=fo)))
        d.text(((W - d.textlength(txt, font=fo)) / 2, H * y), txt, font=fo, fill=(244, 234, 220))
    card.save(ov / "endcard.png")

    inp, fc, n = [], [], len(clips)
    for c in clips:
        inp += ["-i", str(c)]
    inp += ["-loop", "1", "-t", f"{end_secs}", "-i", str(ov / "endcard.png"),
            "-f", "lavfi", "-t", f"{max(dur) + end_secs}", "-i", "anullsrc=r=48000:cl=stereo"]
    silent = n + 1
    for i in range(n):
        fc.append(f"[{i}:v]fps={fps},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,format=yuv420p,"
                  f"settb=AVTB,setpts=PTS-STARTPTS[v{i}]")
        src = f"[{i}:a]" if info[i]["audio"] else f"[{silent}:a]"
        if not info[i]["audio"]:
            fc.append(f"[{silent}:a]atrim=0:{dur[i]:.3f}[s{i}]"); src = f"[s{i}]"
        fc.append(f"{src}aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,apad,atrim=0:{dur[i]:.3f},asetpts=PTS-STARTPTS[a{i}]")
    fc.append(f"[{n}:v]fps={fps},scale={W}:{H},format=yuv420p,setsar=1,settb=AVTB,setpts=PTS-STARTPTS[v{n}]")
    fc.append(f"[{silent}:a]atrim=0:{end_secs},aformat=sample_fmts=fltp:channel_layouts=stereo,asetpts=PTS-STARTPTS[a{n}]")
    vprev, aprev = "v0", "a0"
    for i in range(1, n + 1):
        name, td = trans[i - 1]
        off = starts[i] if i < n else end_start
        fc.append(f"[{vprev}][v{i}]xfade=transition={name}:duration={td:.3f}:offset={off:.3f}[x{i}]")
        fc.append(f"[{aprev}][a{i}]acrossfade=d={td:.3f}:c1=tri:c2=tri[y{i}]")
        vprev, aprev = f"x{i}", f"y{i}"
    base, idx, extra = vprev, n + 2, []
    if ai_label:
        extra += ["-i", str(ov / "ai.png")]
        fc.append(f"[{base}][{idx}:v]overlay=24:24:enable='lt(t,{end_start:.3f})'[o0]"); base = "o0"; idx += 1
    for k, (a, b, _) in enumerate(cues):
        extra += ["-i", str(ov / f"cap{k:02d}.png")]
        fc.append(f"[{base}][{idx}:v]overlay=(W-w)/2:H*0.74:enable='between(t,{a:.3f},{b:.3f})'[c{k}]"); base = f"c{k}"; idx += 1
    if music_path:
        mi = idx
        extra += ["-stream_loop", "-1", "-i", str(music_path)]
        fc.append(f"[{mi}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,atrim=0:{total:.3f},"
                  f"volume={music_db}dB,afade=t=out:st={max(0, total - 1.5):.3f}:d=1.5[mus]")
        fc.append(f"[{aprev}][mus]amix=inputs=2:duration=first:normalize=0[mix]")
        aprev = "mix"
    fc.append(f"[{aprev}]loudnorm=I=-14:TP=-1.5:LRA=9,aresample=48000[aout]")
    cmd = [ffmpeg, "-v", "error", "-y"] + inp + extra + ["-filter_complex", ";".join(fc), "-map", f"[{base}]", "-map", "[aout]",
           "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
           "-movflags", "+faststart", str(out)]
    (work / "ffmpeg_cmd.txt").write_text(" ".join(cmd))
    subprocess.run(cmd, check=True)
    receipt = {"music": str(music_path) if music_path else None, "starts": starts, "end_start": end_start, "total": total, "size": [W, H], "transitions": trans, "cues": cues}
    (work / "receipt.json").write_text(json.dumps(receipt, indent=1))
    return receipt
