// Turn an API-format graph into a normal ComfyUI workflow with App Mode set up, using ComfyUI's own frontend (so the
// saved file is exactly what the editor writes). Then reload it in a fresh context and screenshot App Mode as proof.
// Nothing is queued here: POST /prompt is blocked.
// node tools/make_app.mjs <comfy_url> <api.json> <out_workflow.json> <screenshot.png>   (needs the playwright package)
import { chromium } from "playwright";
import fs from "fs";

const [url, apiPath, outPath, shot] = process.argv.slice(2);
const api = JSON.parse(fs.readFileSync(apiPath, "utf8"));
const ids = (cls) => Object.entries(api).filter(([, n]) => n.class_type === cls).map(([k]) => k);
const draft = ids("UnderdogDraftScene").length > 0;
const brief = ids("UnderdogBrief")[0];
const sheets = ids("LoadImage");
const ROLE = ["owner", "rival influencer", "loyal regular", "hero 1", "hero 2", "location", "rival storefront"];
const mix = ids("UnderdogScoreMix")[0];
// What a user sees in App Mode. Everything else stays locked in the graph.
const INPUTS = [
  [brief, "script_source"], [brief, "business_name"], [brief, "business_type"], [brief, "owner"], [brief, "rival"], [brief, "regular"],
  ...(draft ? [] : [[brief, "hero_1"], [brief, "hero_2"]]), ...sheets.map((s) => [s, "image"]),
  ...(draft ? [] : [[brief, "tone"], [brief, "model"], [mix, "score"]]), [ids("UnderdogFinish")[0], "captions"],
];
const film = ids("SaveVideo").find((k) => api[api[k].inputs.video[0]].class_type === "UnderdogScoreMix");   // not the per-scene saves
const OUTPUTS = [film, ...ids("PreviewImage"), ids("PreviewAny")[0]];

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1300 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.route("**/prompt", (r) => (r.request().method() === "POST" ? r.abort() : r.continue()));   // never queue
await page.goto(url, { waitUntil: "load", timeout: 120000 });
await page.waitForFunction(() => window.app && window.app.graph, null, { timeout: 120000 });
const wf = await page.evaluate(async ({ api, INPUTS, OUTPUTS, sheets, ROLE, draft }) => {
  await window.app.loadApiJson(api, draft ? "underdog-story-draft" : "underdog-story");
  const g = window.app.graph;
  if (g.arrange) g.arrange(80);
  const LABELS = { script_source: "Business", business_name: "Business name", business_type: "Business type (for Gemini)",
    owner: "Owner: looks, no names", rival: "Rival influencer: looks", regular: "Loyal regular: looks",
    hero_1: "Hero 1: looks", hero_2: "Hero 2: looks", tone: "Tone", model: "Video model", score: "Sonilo score",
    captions: "Burn in captions" };
  for (const node of g.nodes) {
    const api_node = api[String(node.id)];
    if (api_node && api_node._meta && api_node._meta.title) node.title = api_node._meta.title;
    const si = sheets.indexOf(String(node.id));
    // Fixed seeds: a re-run after one failed scene re-uses every finished (already paid) step from ComfyUI's cache.
    for (const w of node.widgets || []) if (w.name === "control_after_generate") w.value = "fixed";
    for (const w of node.widgets || []) {
      let lab = null;
      if (si >= 0 && w.name === "image") lab = `Sheet: ${ROLE[si]}`;
      else if (INPUTS.some(([n, name]) => String(n) === String(node.id) && name === w.name)) lab = LABELS[w.name];
      if (lab) { w.label = lab; for (const inp of node.inputs || []) if (inp.widget && inp.widget.name === w.name) inp.label = lab; }
    }
  }
  const w = g.serialize();
  w.extra = w.extra || {};
  w.extra.linearMode = true;
  w.extra.linearData = { inputs: INPUTS.map(([n, name]) => [Number(n), name]), outputs: OUTPUTS.map(Number) };
  return w;
}, { api, INPUTS, OUTPUTS, sheets, ROLE, draft });
const randomized = wf.nodes.filter((n) => (n.widgets_values || []).includes("randomize")).map((n) => n.type);
console.log("seed widgets still on randomize:", JSON.stringify(randomized));
console.log(`nodes ${wf.nodes.length}, links ${wf.links.length}, app inputs ${INPUTS.length}, outputs ${OUTPUTS.length}`);
fs.writeFileSync(outPath, JSON.stringify(wf, null, 1));
await page.close();
const page2 = await (await browser.newContext({ viewport: { width: 1440, height: 1300 } })).newPage();
page2.on("pageerror", (e) => errors.push(e.message));
await page2.route("**/prompt", (r) => (r.request().method() === "POST" ? r.abort() : r.continue()));
await page2.goto(url, { waitUntil: "load", timeout: 120000 });
await page2.waitForFunction(() => window.app && window.app.graph, null, { timeout: 120000 });
await page2.evaluate(async (w) => { await window.app.loadGraphData(w, true, true, "underdog-story"); }, wf);
await page2.waitForTimeout(4000);
try { await page2.click("text=Skip", { timeout: 5000 }); } catch {}   // first-visit App Mode tour
await page2.waitForTimeout(1500);
const text = await page2.evaluate(() => document.body.innerText);
await page2.screenshot({ path: shot });
console.log("app mode form visible", /Business name/.test(text), "page errors", errors.length, JSON.stringify(errors.slice(0, 3)));
await browser.close();
