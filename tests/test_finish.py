import json, re, subprocess
import pytest
import underdog_core as core
from conftest import FFMPEG


def _scenes(n):
    return [{"captions": ["First line here.", "Second one!"], "transition": t} for t in ["whip_left", "fade", "cut"][:n]]


def test_finish_three_dummy_clips(clips, tmp_path):
    out = tmp_path / "film.mp4"
    r = core.finish(clips, _scenes(3), out, tmp_path / "work", ["Test Bakery", "The Last Croissant"])
    info = core.probe(out)
    assert (info["w"], info["h"]) == (360, 640) and info["audio"]
    # 2.0 + 2.5 + 2.0 - transitions (0.3, 0.5, 0.05 capped to a third of the next clip / end card) + 3 s end card
    expect = 2.0 + 2.5 + 2.0 - sum(td for _, td in r["transitions"][:-1]) - r["transitions"][-1][1] + 3.0
    assert info["dur"] == pytest.approx(expect, abs=0.15)
    assert r["starts"][1] == pytest.approx(2.0 - r["transitions"][0][1])
    assert len(r["cues"]) == 6 and len(list((tmp_path / "work" / "ov").glob("cap*.png"))) == 6
    assert (tmp_path / "work" / "ov" / "ai.png").exists() and (tmp_path / "work" / "ov" / "endcard.png").exists()
    cmd = (tmp_path / "work" / "ffmpeg_cmd.txt").read_text()
    assert "settb=AVTB" in cmd and "xfade=transition=slideleft" in cmd and "acrossfade" in cmd
    assert "loudnorm=I=-14" in cmd and "-crf 18" in cmd and "libx264" in cmd


def test_finish_codecs_and_loudness(clips, tmp_path):
    out = tmp_path / "film.mp4"
    core.finish(clips, _scenes(3), out, tmp_path / "w", ["Shop"])
    streams = json.loads(subprocess.check_output([FFMPEG.replace("ffmpeg", "ffprobe"), "-v", "error", "-show_streams", "-of", "json", str(out)]))["streams"]
    assert {s["codec_name"] for s in streams} == {"h264", "aac"}
    log = subprocess.run([FFMPEG, "-hide_banner", "-i", str(out), "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
    integrated = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", log)[-1])
    assert integrated == pytest.approx(-14, abs=2.0)


def test_finish_without_captions_or_label(clips, tmp_path):
    sc = [{"captions": [], "transition": "dissolve"}, {"captions": [], "transition": "fadeblack"}]
    r = core.finish(clips[:2], sc, tmp_path / "f.mp4", tmp_path / "w", ["Shop"], ai_label=False, credit=False)
    assert r["cues"] == [] and not (tmp_path / "w" / "ov" / "ai.png").exists()
    assert core.probe(tmp_path / "f.mp4")["dur"] > 4
