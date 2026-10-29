# Underdog Story

**Describe a small business, its flashy rival and a hero duo → get a 12-scene underdog sitcom, about 95 seconds, vertical, with voices, captions and an end card. Ready to post.**

A ComfyUI App Mode app. Fill in a short form, add up to 6 reference sheets, press **Run**. Every film follows the same
proven arc, so it always lands: the threat, the slide, the low point, the heroes, the bad ideas, the heart, the viral ad,
the showdown, the comeback, the supercar, and a final joke.

Built for the Comfy *Open Source Higgsfield* challenge, 2026. Apache-2.0.

<p align="center"><img src="docs/img/app-mode.png" width="720" alt="Underdog Story in ComfyUI App Mode: business name, cast descriptions, six reference sheets, tone, video model and a Run button"></p>

## How it works

1. **Script.** `Underdog Story: Script` builds the 12 beats. Pick the built-in preset (*The Last Croissant*, a family
   bakery) or let **Gemini** (ComfyUI partner node) write new lines for your business. Either way the script is checked
   before anything is drawn: exactly 12 beats, exactly one on-screen speaker per scene (everyone else silent, mouths
   closed, nobody new enters), every spoken line 20 words or fewer and at most 32 per scene (fits an 8 s take),
   characters described by their looks and named only inside spoken lines, no real brands or logos. A broken script stops the
   run before any image or video is paid for.
2. **Keyframes.** For each scene, **Nano Banana 2** (partner node) draws the start frame, 9:16, from the reference sheets
   that scene needs (owner, rival, partner, hero 1, hero 2, location) plus the keyframe prompt.
3. **Animation.** For each scene, **Veo 3.1** (partner node) turns the keyframe into an 8 s, 9:16 clip with dialogue and
   sound. Every motion prompt quotes the lines and ends with *One continuous take, no cuts. No captions, no subtitles…*
4. **Final cut.** `Underdog Story: Final Cut` joins the 12 clips with short video and audio transitions, burns in
   classic captions, adds an *AI-generated* label and an end card, normalises loudness to −14 LUFS and writes one
   H.264 MP4 to `output/underdog/`. Sound is Veo's own dialogue and effects. No music is added unless you set
   `music_path` to a track you own or licensed (it is looped low under the dialogue). Never use a copyrighted song.
   Every scene clip is also saved to `output/underdog/scenes/`.

The App Mode outputs: the film, a sheet of all 12 keyframes, and the script as text.

## Install

Needs ComfyUI 0.42+ with frontend 1.41.13+ (App Mode) and `ffmpeg` on PATH. No model downloads, no GPU: all
generation runs on Comfy's partner API.

```bash
cd ComfyUI/custom_nodes
git clone <this repo> underdog-story
```

Restart ComfyUI and open `workflows/underdog-story.json`. It opens in App Mode.

### Comfy account and API key (partner nodes)

Gemini, Nano Banana 2 and Veo are ComfyUI **partner nodes**: they run on Comfy's API and are paid with Comfy credits.

1. Make a Comfy account and buy credits at [platform.comfy.org](https://platform.comfy.org).
2. In ComfyUI, click **Sign in to run** (top right) and sign in with that account, or with an API key created on the
   platform.
3. Running from a script instead of the UI? Send the key with the prompt: `{"prompt": ..., "extra_data": {"api_key_comfy_org": "<your key>"}}`.
   Never commit the key.

## Cost

| Step | Per film |
|---|---|
| Veo 3.1 **lite**, 720p, audio on: about $0.05/s × 12 scenes × 8 s | about **$4.80** |
| Nano Banana 2, 1K: about $0.08 × 12 keyframes | about $1.00 |
| Gemini script (only when picked) | a few cents |
| **Total with lite** | **about $6** |

`fast` is about $0.10/s (about $10 of video), `full` about $0.40/s (about $38 of video). Seeds are fixed, so if one
scene fails (for example a safety filter), fix it and press Run again: ComfyUI re-uses every finished step and you only
pay for what runs again.

## Use it

1. **Business name** and **type** (`family bakery`, `barber shop`, `taco truck`…).
2. Describe the **owner**, the **rival**, the optional **partner**, and **hero 1** and **hero 2** by their looks, one
   line each (*the baker in round glasses and a yellow headscarf*). No names: the models don't know who "Rosa" is,
   and the app refuses real people's names.
3. Add **reference sheets** (character sheets and one location image). Empty slots keep the blank placeholder and are skipped.
4. **Tone**: `funny` (default) or `heartfelt`. **Video model**: `veo-3.1-lite` (default), `fast` or `full`.
5. **Script**: the preset, or *write with Gemini* for new lines about your business.
6. **Run.** The script text shows first, then the keyframe sheet, then the finished film.

Only use sheets of fictional characters, or of real people who gave you permission. Keep the AI label on when you post.

## For developers

```bash
python3 tools/build_app.py                       # -> workflows/underdog-story-api.json (API format)
python3 tools/check_graph.py workflows/underdog-story-api.json --url http://127.0.0.1:8188   # checks, never queues
node tools/make_app.mjs http://127.0.0.1:8188 workflows/underdog-story-api.json workflows/underdog-story.json docs/img/app-mode.png
python3 tools/write_preset.py                    # regenerate the preset from its source
python3 -m pytest                                # unit tests (partner nodes mocked; ffmpeg test clips)
python3 tools/run_demo.py --url http://127.0.0.1:8188   # dry run: stage preset sheets, build, check, price quote; $0
python3 tools/run_demo.py --url ... --confirm-spend --cap 10 --quote-limit 9   # the paid demo run (owner approval first)
```

`make_app.mjs` needs the `playwright` npm package. It loads the graph in the real ComfyUI frontend, saves it with App
Mode on, and blocks `POST /prompt`, so nothing is ever queued.

## Licences and credits

Code, workflows and the preset: Apache-2.0. Font: Inter (SIL OFL, `fonts/OFL.txt`). Generation: Google Gemini, Nano
Banana 2 and Veo 3.1 through ComfyUI partner nodes (their terms apply to what you generate). Built by JK Automations.
