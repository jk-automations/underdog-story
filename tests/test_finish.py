import json, re, subprocess
import pytest
import underdog_core as core
from conftest import FFMPEG

OVERLAY = {"rival_brand": "MEGAFADE", "dm_business": "nail salon", "business_name": "Corner Chair Barbershop"}


def _scenes():
    return [{"captions": ["First line here.", "Second one!"], "transition": "dissolve", "card": None},
            {"captions": ["Look at the razor."], "transition": "dissolve_long", "card": "SIX MONTHS LATER", "views": True},
            {"captions": ["Hmm. No."], "transition": "dissolve", "card": None, "dm": True}]


def _lufs(path):
    log = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", log)[-1])


def test_finish_v9_recipe(clips, tmp_path):
    out = tmp_path / "film.mp4"
    r = core.finish(clips, _scenes(), out, tmp_path / "work", ["Corner Chair Barbershop", "The Last Chair"], overlay=OVERLAY)
    info = core.probe(out)
    assert (info["w"], info["h"]) == (360, 640) and info["audio"]
    expect = 2.0 + 2.5 + 2.0 - sum(td for _, td in r["transitions"][:-1]) - r["transitions"][-1][1] + 3.0
    assert info["dur"] == pytest.approx(expect, abs=0.15)
    assert [n for n, _ in r["transitions"]] == ["fade"] * 3                 # dissolves, as in cut_v9d
    assert len(r["cues"]) == 4 and len(list((tmp_path / "work" / "ov").glob("cap*.png"))) == 4
    kinds = [o["kind"] for o in r["overlays"]]
    assert kinds == ["card", "views", "views", "views", "dm"]
    assert [o["text"] for o in r["overlays"] if o["kind"] == "views"] == ["1,204 views", "48K views", "2.1M views"]
    assert r["overlays"][0]["start"] == pytest.approx(r["starts"][1])        # the title card opens the jumped scene
    cmd = (tmp_path / "work" / "ffmpeg_cmd.txt").read_text()
    assert "xfade=transition=fade" in cmd and "acrossfade" in cmd and "settb=AVTB" in cmd and "-crf 18" in cmd
    assert (tmp_path / "work" / "ov" / "ai.png").exists() and (tmp_path / "work" / "ov" / "endcard.png").exists()
    assert len(r["cut_lint"]) == 3 and all("quiet_tail" in x for x in r["cut_lint"])


def test_overlays_use_the_business_slots(clips, tmp_path):
    r = core.finish(clips, _scenes(), tmp_path / "a.mp4", tmp_path / "a", ["Corner Chair Barbershop"], overlay=OVERLAY)
    dm = next(o["text"] for o in r["overlays"] if o["kind"] == "dm")
    assert "Help. A MEGAFADE just opened" in dm and "next to my nail salon." in dm and "Episode 2" in dm
    other = dict(OVERLAY, rival_brand="MEGATACO", dm_business="barbershop")
    r2 = core.finish(clips, _scenes(), tmp_path / "b.mp4", tmp_path / "b", ["La Esquina Tacos"], overlay=other)
    dm2 = next(o["text"] for o in r2["overlays"] if o["kind"] == "dm")
    assert "MEGATACO" in dm2 and "barbershop" in dm2 and "MEGAFADE" not in dm2
    assert (tmp_path / "a" / "ov" / "dm.png").read_bytes() != (tmp_path / "b" / "ov" / "dm.png").read_bytes()
    assert core.bakery_words_in(json.dumps(r["overlays"])) == []


def test_finish_without_captions_or_label(clips, tmp_path):
    sc = [{"captions": [], "transition": "dissolve"}, {"captions": [], "transition": "fadeblack"}]
    r = core.finish(clips[:2], sc, tmp_path / "f.mp4", tmp_path / "w", ["Shop"], ai_label=False, credit=False)
    assert r["cues"] == [] and r["overlays"] == [] and not (tmp_path / "w" / "ov" / "ai.png").exists()
    assert core.probe(tmp_path / "f.mp4")["dur"] > 4


def test_score_mix_chain_levels_ducks_and_masters(clips, tmp_path):
    cut = tmp_path / "cut.mp4"
    core.finish(clips, _scenes(), cut, tmp_path / "w", ["Shop"], overlay=OVERLAY)
    track = tmp_path / "score.wav"   # stands in for Sonilo's score: a generated tone
    subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=30", str(track)], check=True)
    out = tmp_path / "film.mp4"
    m = core.score_mix(cut, out, tmp_path / "m", music=track)
    f = m["filter"]
    # the v9 order: level the score first, then duck it under the dialogue, then master the film
    assert f.index("loudnorm=I=-27:LRA=3:TP=-6") < f.index("sidechaincompress=threshold=0.02:ratio=12:attack=40:release=450") \
        < f.index("loudnorm=I=-14:TP=-1:LRA=11")
    assert "[mus][key]sidechaincompress" in f and "asplit[dia][key]" in f and "afade=t=out" in f
    assert "-c:v copy" in (tmp_path / "m" / "mix_cmd.txt").read_text()
    assert core.probe(out)["dur"] == pytest.approx(core.probe(cut)["dur"], abs=0.1)
    assert _lufs(out) == pytest.approx(-14, abs=2.0)


def test_score_mix_without_score_masters_dialogue(clips, tmp_path):
    cut = tmp_path / "cut.mp4"
    core.finish(clips[:2], _scenes()[:2], cut, tmp_path / "w", ["Shop"])
    m = core.score_mix(cut, tmp_path / "film.mp4", tmp_path / "m")
    assert m["music"] is None and "sidechaincompress" not in m["filter"] and "loudnorm=I=-14:TP=-1" in m["filter"]
    streams = json.loads(subprocess.check_output([FFMPEG.replace("ffmpeg", "ffprobe"), "-v", "error", "-show_streams", "-of", "json",
                                                  str(tmp_path / "film.mp4")]))["streams"]
    assert {s["codec_name"] for s in streams} == {"h264", "aac"}
    assert _lufs(tmp_path / "film.mp4") == pytest.approx(-14, abs=2.0)


def test_write_wav_from_comfy_audio(tmp_path):
    import numpy as np
    wf = np.sin(np.linspace(0, 400, 48000, dtype="float32"))[None, None].repeat(2, axis=1)   # [batch, channels, samples]
    p = core.write_wav(tmp_path / "a.wav", wf, 48000)
    import wave
    with wave.open(str(p)) as w:
        assert (w.getnchannels(), w.getframerate(), w.getnframes()) == (2, 48000, 48000)


def test_draft_clip_is_free_and_scene_length(tmp_path):
    from test_script import script
    s = script("barber-shop")
    sc = s["scenes"][8]
    p = core.draft_clip(tmp_path / "d.mp4", sc, s, W=360, H=640)
    info = core.probe(p)
    assert (info["w"], info["h"]) == (360, 640) and info["audio"] and info["dur"] == pytest.approx(sc["seconds"], abs=0.2)
