"""The paid demo: one Underdog Story film for the barber-shop preset on Veo 3.1 lite + Nano Banana 2 + Sonilo, through the
app's own ComfyUI. The founder runs this himself.

  python3 tools/run_paid_demo.py                       # dry run: stage sheets, build, check graph, estimate. $0, no key read
  python3 tools/run_paid_demo.py --confirm-spend       # the paid run (hard cap $10)

Money rules built in:
- the estimate comes from the partner nodes' own price badges on the live ComfyUI (it aborts if a badge changed);
- the run is refused when the estimate is over --cap, and --cap can never be above $10;
- before anything is queued, a ledger row with the estimate is appended to runs/paid/ledger.jsonl;
- a retry only re-runs what has no saved output (ComfyUI re-uses finished steps), and only while the worst-case total
  stays under the cap; auth or balance errors stop at once (no top-ups).
The Comfy API key is read from ~/.config/jk/comfy_api_key by this process only, only after --confirm-spend, sent only as
extra_data.api_key_comfy_org in the /prompt body, and scrubbed from every log, ledger row and receipt. It is never printed."""
import argparse, json, os, re, shutil, stat, subprocess, sys, time, urllib.error, urllib.request, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import underdog_core as core  # noqa: E402

HARD_CAP = 12.5  # founder raised 10 -> 12.50 on 10-30 01:30 PT to finish the barber demo
VEO_PPS = {"veo-3.1-lite": 0.05, "veo-3.1-fast-generate": 0.10, "veo-3.1-generate": 0.40}   # 720p, audio on (badge)
NB2_1K = 0.0835
SONILO_PPS = 0.009
BADGE_TERMS = {"Veo3VideoGenerationNode": ['"lite"', "($a ? 0.05 : 0.03)", "($a ? 0.10 : 0.08)"],
               "GeminiNanoBanana2": ['"1k": 0.0835'],
               "SoniloVideoToMusic": ['"usd":0.009']}


def check_badges(info):
    changed = [f"{cls}: {t}" for cls, terms in BADGE_TERMS.items() for t in terms
               if t not in json.dumps(info.get(cls, {}).get("price_badge") or {}).replace('\\"', '"')]
    if changed:
        raise SystemExit(f"price badge changed ({changed}); re-derive the estimate before spending")


def script_for(g):
    b = next(n for n in g.values() if n["class_type"] == "UnderdogBrief")["inputs"]
    brief = core.make_brief(b["business_name"], b["business_type"], b["owner"], b["rival"], b["regular"], b["hero_1"], b["hero_2"],
                            b["tone"], b["model"], b["script_source"])
    if not brief["preset"]:
        raise SystemExit("the paid demo runs a preset only (no Gemini)")
    return core.build_script(brief, core.story_from_preset(brief["preset"])), brief


def estimate(g, script, brief):
    """Per-node worst-case USD from the badge prices, and the scene each node belongs to."""
    if brief["model"] not in VEO_PPS:
        raise SystemExit(f"unknown Veo model {brief['model']}")
    scene_of, cost = {}, {}
    for k, n in g.items():
        if n["class_type"] == "UnderdogScene":
            s = n["inputs"]["scene"]
            for k2, n2 in g.items():
                if n2["class_type"] == "GeminiNanoBanana2" and n2["inputs"]["prompt"][0] == k:
                    scene_of[k2] = s
                    for k3, n3 in g.items():
                        if n3["class_type"] == "Veo3VideoGenerationNode" and n3["inputs"]["image"][0] == k2:
                            scene_of[k3] = s
    for k, n in g.items():
        i = n["inputs"]
        if n["class_type"] == "GeminiNanoBanana2":
            assert i["resolution"] == "1K"; cost[k] = NB2_1K
        elif n["class_type"] == "Veo3VideoGenerationNode":
            assert i["resolution"] == "720p" and i["generate_audio"] is True
            cost[k] = VEO_PPS[brief["model"]] * script["scenes"][scene_of[k] - 1]["seconds"]
        elif n["class_type"] == "SoniloVideoToMusic":
            cost[k] = SONILO_PPS * core.film_seconds(script)
        elif n["class_type"] == "GeminiNode":
            cost[k] = 0.0   # lazy: never runs for a preset
    return round(sum(cost.values()), 4), cost, scene_of


def append_ledger(path, row):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(row) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8193")
    ap.add_argument("--comfy-base", default=str(ROOT / ".comfy-base"), help="the --base-directory of that ComfyUI")
    ap.add_argument("--preset", default="barber-shop")
    ap.add_argument("--key-file", default=str(Path.home() / ".config/jk/comfy_api_key"))
    ap.add_argument("--ledger", default=str(ROOT / "runs/paid/ledger.jsonl"))
    ap.add_argument("--confirm-spend", action="store_true", help="really queue the paid run")
    ap.add_argument("--cap", type=float, default=HARD_CAP)
    ap.add_argument("--max-attempts", type=int, default=2)
    ap.add_argument("--spent-so-far", type=float, default=0.0, help="with --resume: worst-case USD already spent on this film")
    ap.add_argument("--resume", action="store_true", help="keep saved scene clips; count them (plus every keyframe) as already spent")
    ap.add_argument("--whisper-model", default=str(Path.home() / ".cache/whisper.cpp/ggml-base.en.bin"))
    a = ap.parse_args(argv)
    if a.cap > HARD_CAP:
        raise SystemExit(f"--cap ${a.cap:.2f} is above the approved ${HARD_CAP:.2f}")
    out = ROOT / "runs" / "paid" / a.preset; out.mkdir(parents=True, exist_ok=True)
    base = Path(a.comfy_base)
    secret = [None]

    def redact(text):
        text = str(text)
        if secret[0]:
            text = text.replace(secret[0], "[REDACTED]")
        return re.sub(r"(?im)^(\s*(x-api-key|authorization|api[_-]?key[^:]*)\s*[:=]).*$", r"\1 [REDACTED]", text)

    def log(*parts):
        line = redact(" ".join(str(p) for p in parts))
        print(line, flush=True)
        with open(out / "run.log", "a") as f:
            f.write(time.strftime("%H:%M:%S ") + line + "\n")

    get = lambda path: json.load(urllib.request.urlopen(a.url + path, timeout=60))

    # ---------- 1. stage the sheets, build the graph, check it against the live ComfyUI ----------
    staged = subprocess.run([sys.executable, str(ROOT / "tools/stage_preset.py"), "--input-dir", str(base / "input"), "--preset",
                             a.preset]).returncode == 0
    if not staged:
        if a.confirm_spend:
            raise SystemExit(f"REFUSED: the character sheets are not all in presets/{a.preset}/assets/ (see its README.md)")
        log("sheets missing: estimating with blank sheets (a paid run will refuse until they are present)")
    api_path = out / "underdog-story-api.json"
    subprocess.run([sys.executable, str(ROOT / "tools/build_app.py"), "--preset", a.preset, "--out", str(api_path)] +
                   (["--staged"] if staged else []), check=True)
    subprocess.run([sys.executable, str(ROOT / "tools/check_graph.py"), str(api_path), "--url", a.url], check=True)
    g = json.loads(api_path.read_text())

    if a.resume:
        # never regenerate a finished scene: its Veo node becomes a LoadVideo of the saved clip, its keyframe and the
        # contact sheet are dropped (a server restart empties ComfyUI's cache, so "cached" is no guarantee)
        sdir = base / "output" / "underdog" / "scenes"

        def node_scene(k):
            n = g[k]
            if n["class_type"] == "Veo3VideoGenerationNode":
                return g[g[n["inputs"]["image"][0]]["inputs"]["prompt"][0]]["inputs"]["scene"]

        drop = set()
        for k in list(g):
            sc = node_scene(k)
            clips = sorted(sdir.glob(f"scene_{sc:02d}_*.mp4"), key=os.path.getmtime) if sc else []
            if clips:
                name = f"resume_scene_{sc:02d}.mp4"
                shutil.copy(clips[-1], base / "input" / name)
                drop.add(g[k]["inputs"]["image"][0])
                g[k] = {"class_type": "LoadVideo", "inputs": {"file": name}}
                drop |= {k2 for k2, n2 in g.items() if n2["class_type"] == "SaveVideo" and n2["inputs"].get("video", [None])[0] == k}
        drop |= {k for k, n in g.items() if n["class_type"] == "UnderdogContactSheet"}
        while True:
            more = {k for k, n in g.items() if k not in drop
                    and any(isinstance(v, list) and v and v[0] in drop for v in n["inputs"].values())}
            if not more:
                break
            drop |= more
        for k in drop:
            g.pop(k, None)
        api_path.write_text(json.dumps(g, indent=1))
        subprocess.run([sys.executable, str(ROOT / "tools/check_graph.py"), str(api_path), "--url", a.url], check=True)

    # ---------- 2. the estimate, from the live price badges ----------
    check_badges(get("/object_info"))
    script, brief = script_for(g)
    total, cost, scene_of = estimate(g, script, brief)
    n_scenes = len(script["scenes"])
    per_scene = {s: round(sum(c for k, c in cost.items() if scene_of.get(k) == s), 4) for s in range(1, n_scenes + 1)}
    sonilo = sum(c for k, c in cost.items() if g[k]["class_type"] == "SoniloVideoToMusic")
    secs = sum(sc["seconds"] for sc in script["scenes"])
    log(f"ESTIMATE {a.preset}: {n_scenes} x Nano Banana 2 1K = ${n_scenes * NB2_1K:.2f}; Veo 3.1 lite {secs} s with audio = "
        f"${secs * VEO_PPS[brief['model']]:.2f}; Sonilo ~{core.film_seconds(script):.0f} s = ${sonilo:.2f}; TOTAL ${total:.2f} (cap ${a.cap:.2f})")
    receipt = {"preset": a.preset, "estimate_usd": total, "cap_usd": a.cap, "attempts": [],
               "per_node": {k: [g[k]["class_type"], scene_of.get(k), round(c, 4)] for k, c in cost.items()}}
    if total > a.cap:
        raise SystemExit(f"REFUSED: estimate ${total:.2f} is over the ${a.cap:.2f} cap")
    if not a.confirm_spend:
        (out / "receipt.json").write_text(json.dumps(receipt, indent=1))
        log("dry run only (no --confirm-spend): nothing queued, no key read, $0 spent")
        return receipt

    # ---------- 3. the paid run ----------
    kf = Path(a.key_file)
    if not kf.is_file() or stat.S_IMODE(kf.stat().st_mode) & 0o077:
        raise SystemExit("key file missing or not chmod 600")
    secret[0] = kf.read_text().strip()
    scene_dir = base / "output" / "underdog" / "scenes"
    film_dir = base / "output" / "underdog"

    def saved_scenes():
        return {int(m.group(1)) for p in scene_dir.glob("scene_*.mp4") if (m := re.match(r"scene_(\d+)", p.name))}

    films_before = set(film_dir.glob("film*.mp4"))
    spent_worst = 0.0
    if saved_scenes() and not a.resume:
        raise SystemExit(f"old scene clips in {scene_dir}; move them away first so the accounting is exact")
    if a.resume:
        # blocked or never-run Veo clips are not charged; saved scenes and every keyframe may have been
        spent_worst = a.spent_so_far
        log(f"resume: scenes saved {sorted(saved_scenes())}; spend so far counted as ${spent_worst:.2f}")
    for attempt in range(1, a.max_attempts + 1):
        todo = [s for s in range(1, n_scenes + 1) if s not in saved_scenes()]
        add = round(sum(per_scene[s] for s in todo) + sonilo, 4)
        if spent_worst + add > a.cap:
            log(f"STOP: attempt {attempt} could cost up to ${add:.2f}; worst-case total ${spent_worst + add:.2f} > cap"); break
        append_ledger(a.ledger, {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "project": "underdog-story", "preset": a.preset,
                                 "attempt": attempt, "scenes": todo, "estimate_usd": add, "worst_case_total_usd": round(spent_worst + add, 4),
                                 "cap_usd": a.cap, "models": ["veo-3.1-lite 720p audio", "nano-banana-2 1K", "sonilo video-to-music"],
                                 "status": "about to queue"})
        body = json.dumps({"prompt": g, "client_id": str(uuid.uuid4()), "extra_data": {"api_key_comfy_org": secret[0]}}).encode()
        req = urllib.request.Request(a.url + "/prompt", data=body, headers={"Content-Type": "application/json"})
        try:
            pid = json.load(urllib.request.urlopen(req, timeout=60))["prompt_id"]
        except urllib.error.HTTPError as e:
            log("queue refused:", e.code, e.read()[:2000].decode(errors="replace"))
            append_ledger(a.ledger, {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "preset": a.preset, "attempt": attempt, "status": "refused"})
            break
        spent_worst += add
        log(f"attempt {attempt}: queued {pid}, scenes {todo}, worst-case +${add:.2f}")
        while True:
            time.sleep(15)
            h = get(f"/history/{pid}").get(pid)
            if h and h.get("status", {}).get("status_str") in ("success", "error"):
                break
        msgs = h["status"].get("messages", [])
        err = next((m[1] for m in msgs if m[0] == "execution_error"), None)
        done = sorted(saved_scenes())
        status = h["status"]["status_str"]
        receipt["attempts"].append({"prompt_id": pid, "status": status, "scenes_saved": done, "worst_case_usd": add,
                                    "error": {k: redact(err.get(k)) for k in ("node_id", "node_type", "exception_message")} if err else None})
        append_ledger(a.ledger, {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "preset": a.preset, "attempt": attempt, "prompt_id": pid,
                                 "status": status, "scenes_saved": done, "worst_case_spent_usd": round(spent_worst, 4)})
        log(f"attempt {attempt}: {status}; scenes saved {done}" + (f"; error in {err.get('node_type')}: {redact(err.get('exception_message'))[:400]}" if err else ""))
        if not err:
            break
        low = (err.get("exception_message") or "").lower()
        if any(w in low for w in ("unauthor", "401", "403", "credit", "balance", "insufficient", "payment", "402")):
            log("STOP: auth or balance problem; no retry, no top-up"); break

    # ---------- 4. collect outputs (key scrubbed everywhere) ----------
    films = sorted(set(film_dir.glob("film*.mp4")) - films_before, key=os.path.getmtime)
    if films:
        shutil.copy(films[-1], out / "underdog-barber-demo.mp4" if a.preset == "barber-shop" else out / f"underdog-{a.preset}.mp4")
    sheets = sorted((base / "temp").glob("ComfyUI_temp_*.png"), key=os.path.getmtime)
    if sheets:
        shutil.copy(sheets[-1], out / "keyframes.png")
    checks = []
    for s in sorted(saved_scenes()):
        clip = next(scene_dir.glob(f"scene_{s:02d}*.mp4"))
        wav = out / f"scene_{s:02d}.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(clip), "-ar", "16000", "-ac", "1", str(wav)], check=True)
        r = subprocess.run(["whisper-cli", "-m", a.whisper_model, "-f", str(wav), "-nt", "-np"], capture_output=True, text=True)
        heard = " ".join(r.stdout.split())
        want = " ".join(script["scenes"][s - 1]["captions"])
        norm = lambda x: re.sub(r"[^a-z ]", "", x.lower()).split()
        hit = len(set(norm(want)) & set(norm(heard))) / max(1, len(set(norm(want))))
        checks.append({"scene": s, "speaker": script["scenes"][s - 1]["speaker"], "want": want, "heard": heard, "word_match": round(hit, 2)})
        wav.unlink()
    receipt.update({"spent_worst_case_usd": round(spent_worst, 4), "whisper": checks, "film": str(films[-1]) if films else None})
    (out / "receipt.json").write_text(redact(json.dumps(receipt, indent=1)))
    log(f"done: worst-case spend ${spent_worst:.2f}; film {'saved' if films else 'MISSING'}; whisper checks {len(checks)}")
    return receipt


if __name__ == "__main__":
    main()
