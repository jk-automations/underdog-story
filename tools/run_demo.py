"""One reproducible demo run of the whole app through a running ComfyUI (partner nodes run on Comfy's API).

  python3 tools/run_demo.py --url http://127.0.0.1:8193 --comfy-base .comfy-base            # dry run: stage, build, check, quote
  python3 tools/run_demo.py ... --confirm-spend --cap 10 --quote-limit 9                    # the paid run (needs founder OK)

Money rules built in: the quote comes from the partner nodes' own price badges (and aborts if a badge changed), the run
is refused when the quote is over --quote-limit, and a retry only re-runs scenes with no saved clip, and only while the
worst-case total stays under --cap. The Comfy API key is read from --key-file only inside this process, sent only in
the /prompt body (extra_data.api_key_comfy_org, the field ComfyUI's partner nodes read), and scrubbed from every log,
receipt and copied API log. It is never printed."""
import argparse, json, os, re, shutil, stat, subprocess, sys, time, urllib.request, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import underdog_core as core  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--url", default="http://127.0.0.1:8193")
ap.add_argument("--comfy-base", default=str(ROOT / ".comfy-base"), help="the --base-directory of that ComfyUI")
ap.add_argument("--preset", default="small-business-rescue-bakery")
ap.add_argument("--key-file", default=str(Path.home() / ".config/jk/comfy_api_key"))
ap.add_argument("--confirm-spend", action="store_true", help="really queue the paid run")
ap.add_argument("--cap", type=float, default=10.0); ap.add_argument("--quote-limit", type=float, default=9.0)
ap.add_argument("--max-attempts", type=int, default=3)
ap.add_argument("--whisper-model", default=str(Path.home() / ".cache/whisper.cpp/ggml-base.en.bin"))
a = ap.parse_args()

PDIR = core.PRESETS_DIR / a.preset
OUT = PDIR / "out"; OUT.mkdir(parents=True, exist_ok=True)
BASE = Path(a.comfy_base)
SECRET = None


def redact(text):
    text = str(text)
    if SECRET:
        text = text.replace(SECRET, "[REDACTED]")
    return re.sub(r"(?im)^(\s*(x-api-key|authorization|api[_-]?key[^:]*)\s*[:=]).*$", r"\1 [REDACTED]", text)


def log(*parts):
    line = redact(" ".join(str(p) for p in parts))
    print(line, flush=True)
    with open(OUT / "run.log", "a") as f:
        f.write(time.strftime("%H:%M:%S ") + line + "\n")


def get(path):
    return json.load(urllib.request.urlopen(a.url + path, timeout=60))


# ---------- 1. stage the sheets, build the graph, check it ----------
subprocess.run([sys.executable, str(ROOT / "tools/stage_preset.py"), "--input-dir", str(BASE / "input"), "--preset", a.preset], check=True)
api_path = OUT / "underdog-story-api.json"
subprocess.run([sys.executable, str(ROOT / "tools/build_app.py"), "--staged", "--out", str(api_path)], check=True)
subprocess.run([sys.executable, str(ROOT / "tools/check_graph.py"), str(api_path), "--url", a.url], check=True)
g = json.loads(api_path.read_text())
brief = next(n for n in g.values() if n["class_type"] == "UnderdogBrief")["inputs"]

# ---------- 2. quote from the price badges ----------
info = get("/object_info")
veo_expr = info["Veo3VideoGenerationNode"]["price_badge"]["expr"]
nb_expr = info["GeminiNanoBanana2"]["price_badge"]["expr"]
# The badges are JSONata. Check the exact terms this quote relies on are still in them; abort if Comfy changed prices.
need = {'"lite"': veo_expr, '($a ? 0.05 : 0.03)': veo_expr, '"1k": 0.0835': nb_expr}
changed = [k for k, e in need.items() if k not in e]
if changed:
    sys.exit(f"price badge changed ({changed}); re-derive the quote before spending")
VEO_PPS = {"veo-3.1-lite": 0.05, "veo-3.1-fast-generate": 0.10, "veo-3.1-generate": 0.40}   # 720p, audio on (badge)
if brief["model"] != "veo-3.1-lite":
    sys.exit("this demo quote is for veo-3.1-lite only")
cost = {}
for k, n in g.items():
    if n["class_type"] == "GeminiNanoBanana2":
        assert n["inputs"]["resolution"] == "1K"; cost[k] = 0.0835
    elif n["class_type"] == "Veo3VideoGenerationNode":
        i = n["inputs"]; assert i["resolution"] == "720p" and i["generate_audio"] is True
        cost[k] = VEO_PPS[brief["model"]] * i["duration_seconds"]
    elif n["class_type"] == "GeminiNode":
        cost[k] = 0.0 if brief["script_source"].startswith("preset:") else 0.05   # lazy: never runs for the preset
quote = round(sum(cost.values()), 4)
scene_of = {}
for k, n in g.items():
    if n["class_type"] == "UnderdogScene":
        s = n["inputs"]["scene"]
        for k2, n2 in g.items():
            if n2["class_type"] == "GeminiNanoBanana2" and n2["inputs"]["prompt"][0] == k:
                scene_of[k2] = s
                for k3, n3 in g.items():
                    if n3["class_type"] == "Veo3VideoGenerationNode" and n3["inputs"]["image"][0] == k2:
                        scene_of[k3] = s
per_scene = {s: round(sum(c for k, c in cost.items() if scene_of.get(k) == s), 4) for s in range(1, 13)}
log(f"QUOTE: 12 x Nano Banana 2 1K = ${12 * 0.0835:.2f}; 12 x Veo 3.1 lite 8 s audio = ${12 * 8 * VEO_PPS['veo-3.1-lite']:.2f}; "
    f"Gemini = ${sum(c for k, c in cost.items() if g[k]['class_type'] == 'GeminiNode'):.2f}; TOTAL ${quote:.2f} "
    f"(limit ${a.quote_limit:.2f}, cap ${a.cap:.2f})")
receipt = {"preset": a.preset, "quote_usd": quote, "cap_usd": a.cap, "per_node_quote": {k: [g[k]["class_type"], scene_of.get(k), c] for k, c in cost.items()},
           "attempts": []}
if quote > a.quote_limit:
    sys.exit(f"ABORT: quote ${quote:.2f} is over ${a.quote_limit:.2f}")
if not a.confirm_spend:
    (OUT / "receipt.json").write_text(json.dumps(receipt, indent=1))
    log("dry run only (no --confirm-spend): nothing queued, $0 spent")
    sys.exit(0)

# ---------- 3. the paid run ----------
kf = Path(a.key_file)
if not kf.is_file() or stat.S_IMODE(kf.stat().st_mode) & 0o077:
    sys.exit("key file missing or not chmod 600")
SECRET = kf.read_text().strip()
scene_dir = BASE / "output" / "underdog" / "scenes"


def saved_scenes():
    return {int(m.group(1)) for p in scene_dir.glob("scene_*.mp4") if (m := re.match(r"scene_(\d+)", p.name))}


before = saved_scenes()
if before:
    sys.exit(f"old scene clips in {scene_dir}; move them away first so the accounting is exact")
spent_worst = 0.0
for attempt in range(1, a.max_attempts + 1):
    todo = [s for s in range(1, 13) if s not in saved_scenes()]
    add = sum(per_scene[s] for s in todo) + (cost.get(next((k for k in g if g[k]["class_type"] == "GeminiNode"), ""), 0) if attempt == 1 else 0)
    if spent_worst + add > a.cap:
        log(f"STOP: attempt {attempt} could cost up to ${add:.2f}; worst-case total would be ${spent_worst + add:.2f} > cap")
        break
    body = json.dumps({"prompt": g, "client_id": str(uuid.uuid4()), "extra_data": {"api_key_comfy_org": SECRET}}).encode()
    req = urllib.request.Request(a.url + "/prompt", data=body, headers={"Content-Type": "application/json"})
    try:
        pid = json.load(urllib.request.urlopen(req, timeout=60))["prompt_id"]
    except urllib.error.HTTPError as e:
        log("queue refused:", e.code, e.read()[:2000].decode(errors="replace")); break
    log(f"attempt {attempt}: queued {pid}, scenes {todo}, worst-case +${add:.2f}")
    spent_worst += add
    while True:
        time.sleep(15)
        h = get(f"/history/{pid}").get(pid)
        if h and h.get("status", {}).get("completed") is not None and (h["status"].get("status_str") in ("success", "error")):
            break
    msgs = h["status"].get("messages", [])
    err = next((m[1] for m in msgs if m[0] == "execution_error"), None)
    done = sorted(saved_scenes())
    receipt["attempts"].append({"prompt_id": pid, "status": h["status"]["status_str"], "scenes_saved": done,
                                "worst_case_usd": round(add, 4),
                                "error": {k: redact(err.get(k)) for k in ("node_id", "node_type", "exception_message")} if err else None})
    log(f"attempt {attempt}: {h['status']['status_str']}; scenes saved {done}" + (f"; error in {err.get('node_type')}: {redact(err.get('exception_message'))[:400]}" if err else ""))
    if not err:
        break
    low = (err.get("exception_message") or "").lower()
    if any(w in low for w in ("unauthor", "401", "403", "credit", "balance", "insufficient", "payment", "402")):
        log("STOP: auth or balance problem; no retry, no top-up"); break

# ---------- 4. collect outputs (key scrubbed everywhere) ----------
api_logs = BASE / "temp" / "api_logs"
meta = []
for p in sorted(api_logs.glob("*")) if api_logs.exists() else []:
    t = redact(p.read_text(errors="replace"))
    t = re.sub(r'"bytesBase64Encoded":\s*"[^"]{200,}"', '"bytesBase64Encoded": "<omitted>"', t)
    t = re.sub(r'"data":\s*"[A-Za-z0-9+/=]{200,}"', '"data": "<omitted>"', t)
    meta.append({"file": p.name, "head": t[:3000]})
(OUT / "api_response_meta.json").write_text(json.dumps(meta, indent=1))
films = sorted((BASE / "output" / "underdog").glob("film*.mp4"), key=os.path.getmtime)
if films:
    shutil.copy(films[-1], OUT / "underdog-app-demo.mp4")
sheets = sorted((BASE / "temp").glob("ComfyUI_temp_*.png"), key=os.path.getmtime)
if sheets:
    shutil.copy(sheets[-1], OUT / "keyframes.png")
script = core.build_script(core.make_brief(brief["business_name"], brief["business_type"], brief["owner"], brief["rival"], brief["partner"],
                                           brief["hero_1"], brief["hero_2"], brief["tone"], brief["model"], brief["script_source"]),
                           {"title": "", "scenes": core.load_preset(a.preset)["scenes"]})
checks = []
for s in sorted(saved_scenes()):
    clip = next(scene_dir.glob(f"scene_{s:02d}*.mp4"))
    wav = OUT / f"scene_{s:02d}.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(clip), "-ar", "16000", "-ac", "1", str(wav)], check=True)
    r = subprocess.run(["whisper-cli", "-m", a.whisper_model, "-f", str(wav), "-nt", "-np"], capture_output=True, text=True)
    heard = " ".join(r.stdout.split())
    want = " ".join(script["scenes"][s - 1]["captions"])
    norm = lambda x: re.sub(r"[^a-z ]", "", x.lower()).split()
    hit = len(set(norm(want)) & set(norm(heard))) / max(1, len(set(norm(want))))
    checks.append({"scene": s, "speaker": script["scenes"][s - 1]["speaker"], "want": want, "heard": heard, "word_match": round(hit, 2)})
    wav.unlink()
receipt.update({"spent_worst_case_usd": round(spent_worst, 4), "whisper": checks,
                "film": str(OUT / "underdog-app-demo.mp4") if films else None})
(OUT / "receipt.json").write_text(redact(json.dumps(receipt, indent=1)))
log(f"done: worst-case spend ${spent_worst:.2f}; film {'saved' if films else 'MISSING'}; whisper checks {len(checks)}")
