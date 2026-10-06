// Phase-2 deck for Team 6 -- "Cutting the Cord"
// node build.js   (writes RIS PROJECT/phase2/Phase2_Team6_Cutting_the_Cord.pptx)
const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");
const gi = require("react-icons/gi");
const { applyTheme } = require("C:/Users/swara/.claude/skills/synced/28c86da8-eece-47e1-987f-1dfbfc307d4d_55386f7d-1114-4cf3-bb1c-4d654eceea26/pptx/scripts/apply_theme.js");

const ROOT = "C:/Users/swara/Desktop/RIS PROJECT/phase2";
const OUT = path.join(ROOT, "Phase2_Team6_Cutting_the_Cord.pptx");

const HEX = { ink: "1F2933", deep: "0B3954", soft: "F2F6F8", teal: "087E8B", violet: "6A4C93",
              amber: "E07A1F", red: "C81D25", green: "2A9D3F", grey: "5B6770", grid: "E3E8EC" };
const THEME = {
  name: "Cutting the Cord", headFontFace: "Cambria", bodyFontFace: "Calibri",
  colors: { dk1: HEX.ink, lt1: "FFFFFF", dk2: HEX.deep, lt2: HEX.soft, accent1: HEX.teal, accent2: HEX.violet,
            accent3: HEX.amber, accent4: HEX.red, accent5: HEX.green, accent6: HEX.grey, hlink: HEX.teal, folHlink: HEX.violet } };

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";            // 13.33 x 7.5
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "Cutting the Cord - Phase 2"; pres.author = "Team 6";
const C = pres.SchemeColor;
const COL = { deep: C.text2, ink: C.text1, white: C.background1, soft: C.background2, teal: C.accent1,
              violet: C.accent2, amber: C.accent3, red: C.accent4, green: C.accent5, grey: C.accent6 };

// ---------- data ----------
function csv(name) {
  const [h, ...rows] = fs.readFileSync(path.join(ROOT, "data", name), "utf8").trim().split(/\r?\n/);
  const keys = h.split(",");
  return rows.map(r => Object.fromEntries(r.split(",").map((v, i) => [keys[i], Number(v)])));
}
const ga = csv("ga_cost.csv"), e2e = csv("e2e.csv"), kb = csv("keybytes.csv");

// ---------- icons ----------
async function icon(Comp, hex, size = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Comp, { color: "#" + hex, size: String(size) }));
  const buf = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

// ---------- rich text: a_{b} subscripts, a^{b} superscripts ----------
function rich(str, opts = {}) {
  if (str.includes("\n")) {
    const lines = str.split("\n"); const out = [];
    lines.forEach((ln, i) => { const r = richLine(ln, opts); if (!r.length) r.push({ text: "", options: { ...opts } });
      if (i < lines.length - 1) r[r.length - 1].options.breakLine = true; out.push(...r); });
    return out;
  }
  return richLine(str, opts);
}
function richLine(str, opts = {}) {
  const runs = []; const re = /_\{([^}]*)\}|\^\{([^}]*)\}|_([A-Za-z0-9])/g; let last = 0, m;
  while ((m = re.exec(str))) {
    if (m.index > last) runs.push({ text: str.slice(last, m.index), options: { ...opts } });
    if (m[2] !== undefined) runs.push({ text: m[2], options: { ...opts, superscript: true } });
    else runs.push({ text: m[1] !== undefined ? m[1] : m[3], options: { ...opts, subscript: true } });
    last = re.lastIndex;
  }
  if (last < str.length) runs.push({ text: str.slice(last), options: { ...opts } });
  return runs;
}

// ---------- layouts ----------
pres.defineSlideMaster({
  title: "TITLE_DARK", background: { color: HEX.deep },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.8, y: 2.2, w: 11.7, h: 1.4, fontSize: 54, bold: true, color: COL.white, valign: "middle" }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.8, y: 3.6, w: 11.0, h: 1.2, fontSize: 22, color: COL.white, valign: "top" }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "SECTION", background: { color: HEX.deep },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.8, y: 2.9, w: 11.7, h: 1.2, fontSize: 44, bold: true, color: COL.white }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.8, y: 4.1, w: 11.7, h: 1.0, fontSize: 20, color: COL.white }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT", background: { color: "FFFFFF" },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.3, w: 12.1, h: 0.9, fontSize: 32, bold: true, color: COL.deep, valign: "middle" }, text: "" } },
    { text: { text: "Cutting the Cord  ·  Phase 2  ·  Team 6", options: { x: 0.6, y: 7.02, w: 6, h: 0.3, fontSize: 10, color: COL.grey } } },
  ],
  slideNumber: { x: 12.2, y: 7.02, w: 0.6, h: 0.3, fontSize: 10, color: COL.grey, align: "right" },
});

// ---------- drawing helpers ----------
let N = 0;
const nm = (s) => `${s}-${++N}`;
function txt(slide, t, o) { slide.addText(typeof t === "string" ? rich(t) : t, { isTextBox: true, fontSize: 16, color: COL.ink, valign: "top", margin: 0.05, objectName: nm("text"), ...o }); }
function box(slide, x, y, w, h, color, o = {}) {
  if (o.solid) slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: COL.white }, line: { color: COL.white }, objectName: nm("under") });
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color, transparency: o.tint ?? 88 },
    line: { color, width: o.lw ?? 1.25, dashType: o.dash }, objectName: nm("box") });
}
function card(slide, x, y, w, h, color, head, body, o = {}) {
  box(slide, x, y, w, h, color, o);
  txt(slide, head, { x: x + 0.2, y: y + 0.15, w: w - 0.4, h: 0.45, fontSize: o.hs ?? 18, bold: true, color });
  if (body) txt(slide, body, { x: x + 0.2, y: y + 0.62, w: w - 0.4, h: h - 0.75, fontSize: o.bs ?? 15 });
}
function pill(slide, x, y, w, h, color, label, o = {}) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.1, fill: { color }, line: { color }, objectName: nm("pill") });
  txt(slide, label, { x, y, w, h, fontSize: o.fs ?? 15, bold: true, color: COL.white, align: "center", valign: "middle", margin: 0.02 });
}
function arrow(slide, x1, y1, x2, y2, color, o = {}) {
  slide.addShape(pres.shapes.LINE, { x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1) || 0.001, h: Math.abs(y2 - y1) || 0.001,
    flipH: x2 < x1, flipV: y2 < y1, line: { color, width: o.w ?? 2, dashType: o.dash, endArrowType: o.noHead ? undefined : "triangle",
    beginArrowType: o.both ? "triangle" : undefined }, objectName: nm("arrow") });
}
function msg(slide, x1, x2, y, color, label, o = {}) {
  arrow(slide, x1, y, x2, y, color, o);
  txt(slide, label, { x: Math.min(x1, x2) + 0.1, y: y - 0.36, w: Math.abs(x2 - x1) - 0.2, h: 0.32, fontSize: o.fs ?? 13, align: "center", color: o.lc ?? COL.ink });
}
function lifeline(slide, x, y1, y2) { slide.addShape(pres.shapes.LINE, { x, y: y1, w: 0.001, h: y2 - y1, line: { color: COL.grey, width: 1, dashType: "dash" }, objectName: nm("life") }); }
async function iconCircle(slide, x, y, d, color, Comp) {
  slide.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color }, line: { color }, objectName: nm("iconbg") });
  slide.addImage({ data: await icon(Comp, "FFFFFF"), x: x + d * 0.22, y: y + d * 0.22, w: d * 0.56, h: d * 0.56, objectName: nm("icon") });
}
function stat(slide, x, y, w, big, label, color) {
  txt(slide, big, { x, y, w, h: 0.95, fontSize: 48, bold: true, color, fontFace: "Cambria", margin: 0 });
  txt(slide, label, { x, y: y + 0.95, w, h: 0.7, fontSize: 14, color: COL.grey, margin: 0 });
}
const content = (sec, title) => { const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: sec }); s.addText(title, { placeholder: "title" }); return s; };
const section = (sec, title, sub) => { const s = pres.addSlide({ masterName: "SECTION", sectionTitle: sec }); s.addText(title, { placeholder: "title" }); s.addText(sub, { placeholder: "body" }); return s; };
const chartText = { catAxisLabelColor: HEX.grey, valAxisLabelColor: HEX.grey, catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt",
  legendFontFace: "+mn-lt", titleFontFace: "+mn-lt", catAxisLabelFontSize: 12, valAxisLabelFontSize: 12, legendFontSize: 12,
  valGridLine: { color: HEX.grid, size: 0.75 }, catGridLine: { style: "none" }, catAxisTitleFontSize: 13, valAxisTitleFontSize: 13,
  catAxisTitleColor: HEX.grey, valAxisTitleColor: HEX.grey };

(async () => {
// =====================================================================
pres.addSection({ title: "Opening" });
{ const s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "Opening" });
  s.addText("Cutting the Cord", { placeholder: "title" });
  s.addText("A three-tier, authority-independent authentication and key management framework for TUAV-assisted infrastructure-less IoV", { placeholder: "body" });
  txt(s, "PHASE 2  ·  RESEARCH GAP, PROPOSED FRAMEWORK AND ANALYSIS", { x: 0.8, y: 1.55, w: 11, h: 0.4, fontSize: 14, bold: true, color: COL.amber, charSpacing: 2 });
  txt(s, "Swaraj Kumar (2025202016)   ·   Hritik Ranjan (2025202031)   ·   Harsh Raj (2025202005)", { x: 0.8, y: 5.6, w: 11.5, h: 0.4, fontSize: 16, color: COL.white });
  txt(s, "Building on: Tan, Zheng & Vijayakumar, IEEE T-ITS 24(6), 6389–6400, 2023", { x: 0.8, y: 6.05, w: 11.5, h: 0.4, fontSize: 13, color: COL.white, italic: true });
  for (const [x, c, Ic] of [[10.4, COL.teal, gi.GiDeliveryDrone], [11.25, COL.violet, fa.FaCarSide], [12.1, COL.amber, fa.FaBroadcastTower]]) await iconCircle(s, x, 0.55, 0.7, c, Ic);
  s.addNotes("Good morning. In Phase 1 we explained the paper by Tan, Zheng and Vijayakumar: a tethered drone that replaces broken roadside units after a disaster. Today, in Phase 2, we show three things. First, what we found when we checked the paper equation by equation. Second, our proposed framework, which we call Cutting the Cord. Third, why it is more secure and also faster. The one sentence to remember: the drone must be able to verify everyone on its own, without the cloud.");
}
{ const s = content("Opening", "Phase 1 in thirty seconds");
  const items = [[COL.amber, gi.GiDeliveryDrone, "A drone replaces the pole", "A tethered UAV (TUAV), powered by cable from an emergency vehicle, acts as a flying roadside unit."],
                 [COL.teal, fa.FaCheckDouble, "One equation verifies all", "All n UAVs are batch-verified together. Reported: 151 ms for 120 UAVs."],
                 [COL.violet, fa.FaKey, "One broadcast gives the key", "A CRT polynomial delivers the group key; UAVs can join or leave cheaply."]];
  items.forEach(([c, Ic, h, b], i) => { const x = 0.6 + i * 4.1; card(s, x, 1.6, 3.85, 3.6, c, "", ""); });
  for (let i = 0; i < 3; i++) { const [c, Ic, h, b] = items[i]; const x = 0.6 + i * 4.1;
    await iconCircle(s, x + 0.25, 1.85, 0.8, c, Ic);
    txt(s, h, { x: x + 0.25, y: 2.8, w: 3.4, h: 0.5, fontSize: 19, bold: true, color: c });
    txt(s, b, { x: x + 0.25, y: 3.35, w: 3.4, h: 1.7, fontSize: 15 }); }
  box(s, 0.6, 5.5, 12.15, 1.15, COL.deep, { tint: 92 });
  txt(s, [{ text: "Today: ", options: { bold: true, color: COL.deep } }, { text: "we tested every equation and every number. The architecture is good, but the protocol does not deliver what the title promises. Then we fix it." }],
      { x: 0.85, y: 5.65, w: 11.7, h: 0.9, fontSize: 17, valign: "middle" });
  s.addNotes("A quick recap, thirty seconds only. One: a tethered drone replaces the broken roadside unit. Two: one equation verifies all the UAVs together, reported as 151 milliseconds for 120 UAVs. Three: one broadcast gives every UAV the group key using the Chinese Remainder Theorem. We still think the architecture is a good idea. But when we checked every equation and every number, we found the protocol does not deliver what its title promises.");
}
{ const s = content("Opening", "The claim under test");
  box(s, 0.6, 1.5, 12.15, 2.2, COL.deep, { tint: 93 });
  txt(s, "“The proposed design deploys the tethered UAV (TUAV) as the specific mobilized base station so that the active edge IoV infrastructure is not needed.”",
      { x: 0.9, y: 1.65, w: 11.6, h: 1.4, fontSize: 22, italic: true, color: COL.deep, fontFace: "Cambria" });
  txt(s, "— Tan, Zheng & Vijayakumar, Abstract", { x: 0.9, y: 3.1, w: 11.6, h: 0.4, fontSize: 14, color: COL.grey });
  txt(s, "The word that carries the whole paper", { x: 0.6, y: 4.1, w: 7, h: 0.5, fontSize: 20, bold: true, color: COL.ink });
  pill(s, 0.6, 4.75, 4.6, 0.8, COL.amber, "infrastructure-less", { fs: 24 });
  txt(s, "It is in the title, the abstract, the introduction and the conclusion. It is the reason the paper is a contribution and not just another signature scheme.\nSo we tested exactly this sentence.",
      { x: 5.6, y: 4.6, w: 7.1, h: 1.6, fontSize: 16 });
  s.addNotes("Here is the paper's own sentence, quoted exactly. The word that carries the whole paper is infrastructure-less. It appears in the title, abstract, introduction and conclusion. So we tested exactly this sentence: does the scheme really work without infrastructure?");
}

// =====================================================================
pres.addSection({ title: "Part A - Findings" });
section("Part A - Findings", "Part A · What we found", "Six findings, each with what fails, where in the paper, why, and the impact");

{ const s = content("Part A - Findings", "Finding 1: the TUAV cannot verify anyone alone");
  const xT = 1.4, xU = 5.6, xA = 9.8, y0 = 1.5;
  pill(s, xT - 0.9, y0, 1.8, 0.55, COL.deep, "TA (cloud)"); pill(s, xU - 0.9, y0, 1.8, 0.55, COL.amber, "TUAV"); pill(s, xA - 0.9, y0, 1.8, 0.55, COL.teal, "n UAVs");
  [xT, xU, xA].forEach(x => lifeline(s, x, y0 + 0.55, 6.2));
  msg(s, xA, xU, 2.6, COL.teal, "US3  n signed requests");
  msg(s, xU, xT, 3.4, COL.red, "GA1  upload over satellite", { w: 3, lc: COL.red });
  box(s, 0.4, 3.65, 2.0, 0.65, COL.deep, { tint: 85, solid: true }); txt(s, "GA2: 3n pairings, needs every s_i", { x: 0.45, y: 3.68, w: 1.9, h: 0.6, fontSize: 12, align: "center" });
  msg(s, xT, xU, 4.7, COL.red, "GA2  results back over satellite", { w: 3, lc: COL.red });
  box(s, xU - 1.1, 5.0, 2.2, 0.55, COL.amber, { tint: 85, solid: true }); txt(s, "GA3: one equation", { x: xU - 1.1, y: 5.05, w: 2.2, h: 0.45, fontSize: 13, align: "center" });
  msg(s, xU, xA, 5.95, COL.amber, "GD4  ACK + key");
  card(s, 10.75, 2.4, 2.0, 3.4, COL.red, "Cut the link", "GA3 has no other input. Nothing in the paper gives a local fallback.", { hs: 16, bs: 13 });

  txt(s, [{ text: "Success probability = A ", options: { bold: true, color: COL.red } }, { text: "(the availability of the TA link). When the link is lost, authentication does not slow down. It stops." }],
      { x: 0.6, y: 6.3, w: 12.1, h: 0.55, fontSize: 16 });
  s.addNotes("Finding 1. Look at steps GA1 and GA2. The TUAV receives the requests but cannot check them. It uploads everything over the satellite link to the TA. The TA computes all the pairings, which need every UAV's secret, and sends the results back. Only then can GA3 run. If the link is cut, GA3 has no input. So the success probability equals the availability of the link. When the link is lost, authentication does not slow down. It stops. The dependency on infrastructure was not removed; it was moved from a pole to a satellite link.");
}
{ const s = content("Part A - Findings", "Finding 2: the TA can impersonate every UAV");
  box(s, 0.6, 1.45, 12.15, 1.3, COL.deep, { tint: 93 });
  txt(s, "Step US2:   Γ_i = [ s_i·h_3(ID_i, ts_2, s_i)·R_{tu} − h_1(s_iξ_i) ]·P − υ_i·h_1(r_i)·Q_{tu}", { x: 0.9, y: 1.55, w: 11.6, h: 0.55, fontSize: 20, fontFace: "Cambria" });
  txt(s, "But step US1 defined ξ_i = h_1(r_i), and ξ_i is sent in clear. So the UAV's own random value adds no secret.", { x: 0.9, y: 2.12, w: 11.6, h: 0.5, fontSize: 16, color: COL.red });
  card(s, 0.6, 3.05, 3.9, 2.55, COL.teal, "What Γ_i really uses", "Only s_i (issued and stored by the TA) and public values. The TA can build a valid request for any UAV, in any session.", { bs: 15 });
  card(s, 4.72, 3.05, 3.9, 2.55, COL.red, "Claim F4 fails", "Key-escrow resilience: the TA can sign for anyone, and it also computes every σ_i, so it can read the group key.", { bs: 15 });
  card(s, 8.85, 3.05, 3.9, 2.55, COL.red, "Claim F10 fails", "Non-repudiation: verification needs s_i, so any credential could have come from the TA. A UAV can always deny it.", { bs: 15 });
  txt(s, "Why: real certificateless crypto needs a user secret the authority never sees. Here that secret is effectively published.", { x: 0.6, y: 5.85, w: 12.1, h: 0.6, fontSize: 16, italic: true, color: COL.deep });
  s.addNotes("Finding 2. This is the credential formula from step US2. The last term uses h1 of r i. But step US1 defined xi i as exactly h1 of r i, and xi i is sent in clear. So the UAV's own random value adds nothing secret. The credential depends only on s i, which the TA issued and stores, and public values. That means the TA, or anyone who hacks the TA, can create a valid request for any UAV. So claim F4, key-escrow resilience, fails. And claim F10, non-repudiation, fails too, because only the holder of s i can verify, so any credential could have come from the TA.");
}
{ const s = content("Part A - Findings", "Finding 4: a removed UAV still gets the new key");
  txt(s, "The polynomial Λ(x) = C + ∏(x − σ_i) has a constant C. Any member computes C = Λ(σ_k), so Λ(x) − C = ∏(x − σ_i). Its roots are everyone's keys.",
      { x: 0.6, y: 1.35, w: 12.1, h: 0.85, fontSize: 17 });
  const steps = [[COL.amber, "1", "TUAV broadcasts", "coefficients {a_k} of Λ(x)"], [COL.red, "2", "Member k factors", "Λ(x) − Λ(σ_k)  →  every σ_j"],
                 [COL.amber, "3", "k is revoked (DU1)", "new Λ*(x), same σ_j for those who stay"], [COL.red, "4", "k still decrypts", "κ* = Λ*(σ_j) mod σ_j"]];
  steps.forEach(([c, n, h, b], i) => { const x = 0.6 + i * 3.1; box(s, x, 2.4, 2.8, 1.9, c);
    pill(s, x + 0.2, 2.55, 0.5, 0.5, c, n, { fs: 16 });
    txt(s, h, { x: x + 0.8, y: 2.55, w: 1.95, h: 0.5, fontSize: 16, bold: true, color: c, valign: "middle" });
    txt(s, b, { x: x + 0.2, y: 3.2, w: 2.45, h: 1.0, fontSize: 14 });
    if (i < 3) arrow(s, x + 2.82, 3.35, x + 3.08, 3.35, COL.grey); });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y: 4.6, w: 7.3, h: 1.85, rectRadius: 0.06, fill: { color: COL.ink }, line: { color: COL.ink }, objectName: nm("console") });
  txt(s, ["correctness holds for all 12 members", "(A) insider recovered all sigma_i: True", "    revoked member's own sigma gives kappa*? False",
          "(B) revoked member, using a stolen sigma, gets kappa*: True"].map((t, i, a) => ({ text: t, options: { breakLine: i < a.length - 1 } })),
      { x: 0.8, y: 4.72, w: 7.0, h: 1.65, fontSize: 13, fontFace: "Courier New", color: COL.white });
  card(s, 8.15, 4.6, 4.6, 1.85, COL.red, "Verified with our script", "n = 12, 160-bit moduli. Revocation is broken, and so is Theorem 5's \"removed UAVs are locked out\".", { hs: 16, bs: 14 });
  s.addNotes("Finding 4 is our strongest. The key polynomial is a constant C plus the product of x minus sigma i. Any member can compute C by putting its own sigma into the polynomial. Subtract, and you get the product exactly. Its roots are the keys of all other members. Now, when a UAV is revoked, the paper rebuilds the polynomial but keeps the same sigma for the UAVs that stay. The revoked UAV already knows those sigmas, so it computes the new key anyway. We verified this with a Python script: twelve members, 160-bit numbers. Output: True, True. Revocation does not revoke.");
}
{ const s = content("Part A - Findings", "Finding 4b: the key broadcast is megabytes, not bytes");
  s.addChart(pres.charts.LINE, [
    { name: "Base: CRT coefficients to all n UAVs", labels: kb.map(r => String(r.n)), values: kb.map(r => r.crt_total) },
    { name: "Base paper's Table V (104n)", labels: kb.map(r => String(r.n)), values: kb.map(r => r.paper_claim) },
    { name: "Ours: one ACK (68n + 4)", labels: kb.map(r => String(r.n)), values: kb.map(r => r.ours_total) }],
    { x: 0.6, y: 1.35, w: 7.8, h: 5.4, ...chartText, valAxisLogScaleBase: 10, chartColors: [HEX.red, HEX.grey, HEX.teal], lineSize: 3, lineDataSymbolSize: 7,
      showLegend: true, legendPos: "b", showValAxisTitle: true, valAxisTitle: "bytes (log scale)", showCatAxisTitle: true, catAxisTitle: "number of UAVs n",
      showTitle: true, title: "Group-key delivery traffic", titleColor: HEX.ink, titleFontSize: 15, valAxisLabelFormatCode: '[>=1000000]0,,"M";[>=1000]0,"K";0' });
  stat(s, 8.9, 1.5, 3.9, "16.7 MiB", "base scheme, n = 120 (measured)", COL.red);
  stat(s, 8.9, 3.25, 3.9, "12.2 KiB", "what the paper's Table V suggests", COL.grey);
  stat(s, 8.9, 5.0, 3.9, "8.0 KiB", "ours: about 2150× smaller", COL.teal);
  s.addNotes("The polynomial coefficients are integers that grow with n. We measured their real size. At 120 UAVs one acknowledgement is about 143 kilobytes, and the paper sends one to each UAV, so the total is about 16.7 megabytes. The paper's table suggests about 12 kilobytes. Our design, which we explain later, needs 8 kilobytes. Note the log scale: the red line grows as n cubed.");
}
{ const s = content("Part A - Findings", "Findings 3, 5, 6: three more claims that do not hold");
  card(s, 0.6, 1.45, 3.9, 3.3, COL.red, "3 · No forward secrecy", "σ_i = h_1(s_iξ_i)·P with ξ_i public. Steal s_i later and every past group key can be recomputed from recorded traffic. Claim F7 fails.", { bs: 15 });
  card(s, 4.72, 1.45, 3.9, 3.3, COL.red, "5 · Theorem 1 proves nothing", "Its CDH instance uses b = Σ υ_iξ_i, which is public. So abP = b·(s_{tu}P) is easy. The batch check also has no random weights: Γ_1+Δ and Γ_2−Δ still pass.", { bs: 15 });
  card(s, 8.85, 3.05 - 1.6, 3.9, 3.3, COL.red, "6 · Costs leave out the TA", "GA2 does 3 pairings per UAV on the TA (29.74 ms each UAV). Counted honestly: 3720 ms at n = 120, not 151 ms, plus the satellite round trip.", { bs: 15 });
  box(s, 0.6, 5.05, 12.15, 1.55, COL.deep, { tint: 92 });
  txt(s, [{ text: "One root cause behind all six findings: ", options: { bold: true, color: COL.deep } }, { text: "the TA is inside every operation. It holds every secret, does every check, and is reachable only over the link the disaster breaks." }],
      { x: 0.85, y: 5.15, w: 11.7, h: 1.35, fontSize: 18, valign: "middle" });
  s.addNotes("Three more findings, briefly. Finding 3: the decrypting key depends on the long-term secret and a public value, so if a UAV is captured later, all its past group keys can be recovered. No forward secrecy. Finding 5: the proof of Theorem 1 uses a CDH instance where b is public, so the instance is easy, and the proof proves nothing. Also the batch check has no random weights, so two errors can cancel. Finding 6: the reported 151 milliseconds leaves out the TA's three pairings per UAV. Counted honestly it is about 3720 milliseconds at 120 UAVs, plus the satellite delay. And here is the key insight: all six findings have one root cause. The TA is inside every operation.");
}
{ const s = content("Part A - Findings", "Honest accounting: the base scheme becomes the slowest");
  const names = ["Base (reported)", "Ali et al.", "Mei et al.", "Xu et al.", "Kumar et al.", "Base (honest)", "Ours"];
  const r = ga.find(x => x.n === 120);
  const vals = [r.orig, r.ali, r.mei, r.xu, r.kumar, r.orig_honest, r.ours_total];
  s.addChart(pres.charts.BAR, [{ name: "ms at n = 120", labels: names, values: vals }], { x: 0.6, y: 1.35, w: 8.2, h: 5.45, barDir: "bar", ...chartText,
    chartColors: [HEX.grey, HEX.grey, HEX.grey, HEX.grey, HEX.grey, HEX.red, HEX.teal], showValue: true, dataLabelPosition: "outEnd",
    dataLabelColor: HEX.ink, dataLabelFontSize: 12, dataLabelFormatCode: "#,##0", showLegend: false, valAxisHidden: true, valGridLine: { style: "none" },
    showTitle: true, title: "Group authentication of 120 UAVs (ms), base paper's own constants", titleColor: HEX.ink, titleFontSize: 15 });
  card(s, 9.1, 1.45, 3.65, 2.5, COL.red, "Where 151 ms came from", "Only the TUAV side was counted. The TA's 3 pairings per UAV and the satellite trip were left out.", { hs: 16, bs: 14 });
  card(s, 9.1, 4.2, 3.65, 2.5, COL.teal, "Ours: 228 ms", "Includes verification and key delivery, no pairings, no satellite link. We explain how next.", { hs: 16, bs: 14 });
  s.addNotes("Here is the same comparison as the paper's Figure 3, at 120 UAVs, using exactly the paper's own timing constants. The reported 151 milliseconds looks best. But once the TA's pairings are counted, the base scheme becomes 3720 milliseconds, the slowest of all, even before adding the satellite delay. Our scheme, which we present next, needs 228 milliseconds including key delivery.");
}

// =====================================================================
pres.addSection({ title: "Part B - Framework" });
section("Part B - Framework", "Part B · Cutting the Cord", "Keep the TUAV architecture. Move the trust root offline.");

{ const s = content("Part B - Framework", "Key idea: one offline trust root, three tiers");
  box(s, 0.6, 1.35, 12.15, 0.8, COL.deep, { tint: 85 });
  txt(s, [{ text: "TA: registration before deployment + tracing later.  ", options: { bold: true, color: COL.deep } }, { text: "Publishes P_{pub}. Never needed online.", options: { color: COL.deep } }], { x: 0.85, y: 1.45, w: 11.7, h: 0.6, fontSize: 17, valign: "middle" });
  box(s, 0.6, 2.35, 12.15, 1.25, COL.amber);
  txt(s, "C3 · TUAV tier", { x: 0.75, y: 2.4, w: 3, h: 0.35, fontSize: 13, bold: true, color: COL.amber });
  pill(s, 2.2, 2.75, 2.6, 0.6, COL.amber, "TUAV a + ECRV"); pill(s, 8.5, 2.75, 2.6, 0.6, COL.amber, "TUAV b + ECRV");
  arrow(s, 4.85, 3.05, 8.45, 3.05, COL.amber, { both: true, w: 2.5 }); txt(s, "link key K_{ab} · tickets · eviction lists", { x: 4.9, y: 2.68, w: 3.5, h: 0.35, fontSize: 13, align: "center" });
  box(s, 0.6, 3.8, 12.15, 1.25, COL.teal);
  txt(s, "C1 · UAV tier", { x: 0.75, y: 3.85, w: 3, h: 0.35, fontSize: 13, bold: true, color: COL.teal });
  [1.2, 2.6, 4.0, 7.6, 9.0, 10.4].forEach((x, i) => pill(s, x, 4.25, 1.1, 0.55, COL.teal, `UAV ${i + 1}`, { fs: 13 }));
  box(s, 0.6, 5.25, 12.15, 1.25, COL.violet);
  txt(s, "C2 · Vehicle tier", { x: 0.75, y: 5.3, w: 3, h: 0.35, fontSize: 13, bold: true, color: COL.violet });
  for (let i = 0; i < 8; i++) pill(s, 1.0 + i * 1.45, 5.72, 1.15, 0.5, COL.violet, `V${i + 1}`, { fs: 13 });
  [[3.5, 3.35, 1.75, 4.25], [3.5, 3.35, 4.55, 4.25], [9.8, 3.35, 8.15, 4.25], [9.8, 3.35, 10.95, 4.25]].forEach(([a, b, c2, d]) => arrow(s, a, b, c2, d, COL.teal, { noHead: true, w: 1.5 }));
  [[1.75, 4.8, 1.55, 5.72], [3.15, 4.8, 3.0, 5.72], [4.55, 4.8, 4.45, 5.72], [8.15, 4.8, 8.8, 5.72], [9.55, 4.8, 10.25, 5.72], [10.95, 4.8, 11.7, 5.72]].forEach(([a, b, c2, d]) => arrow(s, a, b, c2, d, COL.violet, { noHead: true, w: 1.5 }));
  txt(s, "Every UAV, vehicle and TUAV can verify every other one using only the TA's public key.", { x: 0.6, y: 6.55, w: 12.1, h: 0.4, fontSize: 15, italic: true, color: COL.deep });
  s.addNotes("Our key idea: keep the TUAV architecture, but make the trust root offline. The TA registers everyone before deployment and can trace a misbehaving entity later. During operation, nobody needs it. On top of that we build three tiers. C1, the UAV tier: the TUAV verifies UAVs itself. C2, the vehicle tier: vehicles, which the paper leaves out, are authenticated with the same kind of credential. C3, the TUAV tier: neighbouring TUAVs share a link key so members can move between cells. Everyone can verify everyone using only the TA's public key.");
}
{ const s = content("Part B - Framework", "Five phases: only Phase 0 needs the TA");
  const ph = [[COL.deep, "Phase 0", "Setup & registration", "ST, RG", "before deployment"], [COL.teal, "Phase 1 · C1", "UAV auth & group key", "UA, RK", "in the field"],
              [COL.violet, "Phase 2 · C2", "Vehicle auth & regional key", "VA", "in the field"], [COL.amber, "Phase 3 · C3", "TUAV link & handover", "HO", "in the field"],
              [COL.deep, "Phase 4", "Tracing & global revocation", "TR", "whenever reachable"]];
  ph.forEach(([c, h, b, l, when], i) => { const x = 0.6 + i * 2.5; box(s, x, 1.9, 2.2, 2.6, c, { tint: 86, dash: i === 4 ? "dash" : undefined });
    txt(s, when, { x, y: 1.45, w: 2.2, h: 0.4, fontSize: 12, bold: true, color: c, align: "center" });
    txt(s, h, { x: x + 0.1, y: 2.05, w: 2.0, h: 0.45, fontSize: 17, bold: true, color: c, align: "center" });
    txt(s, b, { x: x + 0.1, y: 2.6, w: 2.0, h: 1.0, fontSize: 15, align: "center" });
    pill(s, x + 0.55, 3.75, 1.1, 0.45, c, l, { fs: 13 });
    if (i < 4) arrow(s, x + 2.22, 3.2, x + 2.48, 3.2, COL.grey); });
  box(s, 3.1, 4.75, 7.2, 0.6, COL.teal, { tint: 80 });
  txt(s, "Phases 1–3 run with no TA, no satellite link", { x: 3.1, y: 4.78, w: 7.2, h: 0.55, fontSize: 16, bold: true, color: COL.teal, align: "center", valign: "middle" });
  txt(s, "The TA helps when present (tracing, permanent revocation) but is never on the critical path. That is what “infrastructure-less” should mean.", { x: 0.6, y: 5.75, w: 12.1, h: 0.8, fontSize: 17 });
  s.addNotes("The framework has five phases. Phase 0, setup and registration, happens before deployment and is the only phase that needs the TA. Phases 1, 2 and 3, the three tiers, run in the field without the TA and without the satellite link. Phase 4, tracing and permanent revocation, happens whenever the TA becomes reachable, and nothing waits for it. That is what infrastructure-less should mean: the infrastructure helps when present, but is not required.");
}
{ const s = content("Part B - Framework", "Phase 0: an escrow-free key, half from the TA, half secret");
  card(s, 0.6, 1.4, 3.7, 2.55, COL.teal, "UAV picks (RG1)", "secret value x, public X = x·P\nx never leaves the UAV", { bs: 16 });
  card(s, 4.8, 1.4, 3.7, 2.55, COL.deep, "TA certifies (RG2)", "pseudonym PID, nonce Y = y·P\nh = H_1(PID, ep, X, Y)\nd = y + s·h", { bs: 16 });
  card(s, 9.0, 1.4, 3.75, 2.55, COL.green, "Full key pair", "sk = x + d\npk = X + Y + h·P_{pub}\ncheck: sk·P = pk", { bs: 16 });
  arrow(s, 4.32, 2.65, 4.78, 2.65, COL.grey); arrow(s, 8.52, 2.65, 8.98, 2.65, COL.grey);
  const why = [["Escrow-free", "Signing needs x + d. The TA knows d, not x."], ["No certificates", "h binds d to this exact X. Replacing X needs the master key s."],
               ["Verify with P_{pub} only", "pk contains h·P_{pub}, so anyone can check it offline."], ["Traceable pseudonyms", "PID hides the real ID; only the TA's tracing key t opens it."]];
  why.forEach(([h, b], i) => { const x = 0.6 + (i % 2) * 6.1, y = 4.25 + Math.floor(i / 2) * 1.2;
    txt(s, h, { x, y, w: 5.9, h: 0.4, fontSize: 17, bold: true, color: COL.amber }); txt(s, b, { x, y: y + 0.42, w: 5.9, h: 0.6, fontSize: 15 }); });
  s.addNotes("Phase 0 is where we fix the escrow problem. The UAV picks its own secret x and only sends X equal to x times P. The TA creates a pseudonym and certifies it: d equals y plus s times h, where h binds the pseudonym and X. The full private key is x plus d. The TA knows d but never x, so it cannot sign for the UAV. Anyone can verify the public key using only the TA's public key P pub, because it is built into pk. And the pseudonym hides the real identity: only the TA's separate tracing key can open it. One pseudonym per epoch, for example per 15 minutes.");
}
{ const s = content("Part B - Framework", "C1: the TUAV authenticates the swarm itself");
  const xT = 1.5, xA = 6.65, xU = 11.6, y0 = 1.35;
  pill(s, xT - 1.0, y0, 2.0, 0.55, COL.amber, "TUAV a"); pill(s, xA - 1.0, y0, 2.0, 0.55, COL.grey, "TA (offline)"); pill(s, xU - 1.0, y0, 2.0, 0.55, COL.teal, "UAV i  (× n)");
  [xT, xU].forEach(x => lifeline(s, x, y0 + 0.55, 6.25));
  s.addShape(pres.shapes.LINE, { x: xA, y: y0 + 0.55, w: 0.001, h: 4.3, line: { color: "D0D5DA", width: 8 }, objectName: nm("ta-off") });
  txt(s, "never contacted", { x: xA - 1.0, y: 6.25 - 0.05, w: 2.0, h: 0.3, fontSize: 12, italic: true, color: COL.grey, align: "center" });
  msg(s, xT, xU, 2.4, COL.amber, "UA1  signed beacon ⟨ID_a, X_a, Y_a, E_a, ts_a, R_a, v_a⟩");
  msg(s, xU, xT, 3.3, COL.teal, "UA2  signed request ⟨PID_i, ep, X_i, Y_i, E_i, ts_i, R_i, v_i⟩");
  box(s, 0.45, 3.55, 3.4, 1.05, COL.amber, { tint: 85, solid: true });
  txt(s, "UA3  batch-verify all n with random weights λ_i, using only P_{pub}", { x: 0.55, y: 3.6, w: 3.2, h: 0.95, fontSize: 13 });
  msg(s, xT, xU, 5.15, COL.amber, "UA4  one ACK: {H(PID_i), C_i = Enc(K_i, GK_a)}");
  box(s, 9.9, 5.35, 3.0, 0.9, COL.teal, { tint: 85, solid: true });
  txt(s, "UA5  K_i from ECDH, decrypt GK_a ⇒ TUAV authentic", { x: 10.0, y: 5.4, w: 2.8, h: 0.8, fontSize: 13 });
  pill(s, 3.7, 6.5, 5.9, 0.42, COL.green, "mutual authentication + group key in one local round trip", { fs: 14 });
  s.addNotes("This is C1, the core. Compare it with the Phase 1 picture: the TA in the middle is greyed out, never contacted. Step UA1: the TUAV broadcasts a signed beacon containing a fresh Diffie-Hellman value E a. Step UA2: each UAV sends a signed request with its own fresh value E i. Step UA3: the TUAV verifies all n requests in one batch, using only the TA's public key. Step UA4: for each UAV it derives a pairwise key K i from Diffie-Hellman, and sends the group key encrypted under K i, all in one ACK. Step UA5: the UAV decrypts. If it works, the TUAV is authentic. Mutual authentication and the group key in one local round trip.");
}
{ const s = content("Part B - Framework", "C1: a sound batch check, and a bounded fallback");
  box(s, 0.6, 1.4, 12.15, 1.15, COL.deep, { tint: 93 });
  txt(s, "( Σ λ_iv_i )·P  =?  Σ λ_iR_i + Σ (λ_ic_i)·(X_i + Y_i) + ( Σ λ_ic_ih_i )·P_{pub}", { x: 0.9, y: 1.5, w: 11.6, h: 0.55, fontSize: 21, fontFace: "Cambria", align: "center" });
  txt(s, "Random 64-bit weights λ_i: a bad batch passes with probability ≤ 2^{−64}. Errors can no longer cancel.", { x: 0.9, y: 2.05, w: 11.6, h: 0.4, fontSize: 15, color: COL.grey, align: "center" });
  stat(s, 0.7, 2.9, 3.6, "119.9 ms", "clean batch, n = 120", COL.teal);
  stat(s, 4.75, 2.9, 3.6, "448.6 ms", "worst case: batch fails, then check each (3.7×)", COL.amber);
  stat(s, 8.8, 2.9, 3.9, "0 %", "base scheme goodput after one bad packet", COL.red);
  card(s, 0.6, 4.85, 6.0, 1.9, COL.amber, "Our fallback rule (UA3)", "If the batch fails: verify each request, accept the valid ones, put bad pseudonyms on the eviction list, and stay in individual mode until the windows are clean.", { hs: 17, bs: 14 });
  card(s, 6.75, 4.85, 6.0, 1.9, COL.teal, "A finding of our own", "Split-and-retest (the classical method) costs more here: batching is only 2.8× cheaper per signature, so checking each one is faster.", { hs: 17, bs: 14 });
  s.addNotes("Two improvements in the batch check. First, random 64-bit weights lambda i, so errors cannot cancel; a bad batch passes with probability at most 2 to the minus 64. Second, a failure branch, which the paper does not have. If the batch fails, we verify each request, accept the honest ones and evict the bad pseudonyms. Clean batch: about 120 milliseconds for 120 UAVs. Worst case: 449 milliseconds, bounded. In the base scheme one bad packet rejects everyone: goodput zero. We also found that the classical split-and-retest method costs more here, because batching gives only 2.8 times saving per signature.");
}
{ const s = content("Part B - Framework", "C1: group keys that really lock out leavers");
  card(s, 0.6, 1.4, 5.9, 2.6, COL.red, "Base: one CRT polynomial", "One public polynomial for everyone. A member can extract all keys, and a revoked UAV keeps decrypting. Size grows as n³.", { bs: 16 });
  card(s, 6.85, 1.4, 5.9, 2.6, COL.teal, "Ours: one small box per member", "C_i = Enc(K_i, GK_a ‖ ν), with K_i from a fresh ECDH. Knowing your own K_i says nothing about anyone else's. 68 bytes per member.", { bs: 16 });
  const rk = [["Leave or eviction (RK1)", "fresh GK′, version ν+1, encrypted only for those who stay", COL.teal], ["Revoked UAV", "has no K_j of others, so it cannot open any entry", COL.red],
              ["New member", "receives only the fresh key, so it cannot read the past", COL.violet], ["Large swarms (LKH tree)", "one leave costs 13 ciphertexts instead of 119 at n = 120", COL.amber]];
  rk.forEach(([h, b, c], i) => { const x = 0.6 + (i % 2) * 6.25, y = 4.3 + Math.floor(i / 2) * 1.2;
    pill(s, x, y + 0.08, 0.35, 0.35, c, ""); txt(s, h, { x: x + 0.5, y, w: 5.6, h: 0.45, fontSize: 17, bold: true, color: c }); txt(s, b, { x: x + 0.5, y: y + 0.45, w: 5.6, h: 0.6, fontSize: 15 }); });
  s.addNotes("Now the group key. The base scheme hides one key in one public polynomial, which leaks everyone's key. We replace it with one small encrypted box per member. Each box is encrypted with that member's own key K i, which comes from a fresh Diffie-Hellman exchange. Knowing your own key tells you nothing about anyone else's. When a UAV leaves or is evicted, the TUAV picks a fresh group key and encrypts it only for those who stay. The revoked UAV cannot open any box. A new member cannot read the past. For big swarms, a key tree reduces one leave to 13 ciphertexts.");
}
{ const s = content("Part B - Framework", "C2: vehicles join through the UAVs");
  const xT = 1.5, xU = 6.65, xV = 11.6, y0 = 1.35;
  pill(s, xT - 1.0, y0, 2.0, 0.55, COL.amber, "TUAV a"); pill(s, xU - 1.1, y0, 2.2, 0.55, COL.teal, "UAV i (relay)"); pill(s, xV - 1.0, y0, 2.0, 0.55, COL.violet, "vehicle j");
  [xT, xU, xV].forEach(x => lifeline(s, x, y0 + 0.55, 5.4));
  msg(s, xT, xU, 2.35, COL.amber, "VA1 beacon"); msg(s, xU, xV, 2.35, COL.teal, "re-broadcast (signed)");
  msg(s, xV, xU, 3.15, COL.violet, "VA2 signed request");
  msg(s, xU, xT, 3.95, COL.teal, "VA3 bundle + MAC(K_i)");
  msg(s, xT, xU, 4.75, COL.amber, "VA4 C_j = Enc(K_j, VK_a)"); msg(s, xU, xV, 4.75, COL.teal, "forward (cannot open)");
  const w = [["Same credential", "one registration, verifiable anywhere with P_{pub}"], ["UAVs relay, TUAV verifies", "batch pays off with hundreds of vehicles"],
             ["MAC filters floods", "only bundles from current members reach the TUAV"], ["Separate keys", "a captured car never gets the UAV key GK_a"]];
  w.forEach(([h, b], i) => { const x = 0.6 + i * 3.08; box(s, x, 5.6, 2.9, 1.25, COL.violet);
    txt(s, h, { x: x + 0.12, y: 5.66, w: 2.7, h: 0.4, fontSize: 15, bold: true, color: COL.violet }); txt(s, b, { x: x + 0.12, y: 6.05, w: 2.7, h: 0.75, fontSize: 13 }); });
  s.addNotes("C2 adds vehicles, which the paper leaves out even though vehicles are why the network exists. A vehicle holds the same kind of credential as a UAV. It hears the TUAV beacon through a UAV, sends a signed request to the UAV, and the UAV bundles requests and sends them to the TUAV with a MAC under its own key. So only bundles from real members reach the TUAV, which blocks floods. The TUAV batch-verifies and sends each vehicle the regional key, encrypted, through the UAV, which cannot read it. The vehicle key is separate from the UAV key. For V2V, routine beacons use a fast MAC; safety-critical events are signed for non-repudiation.");
}
{ const s = content("Part B - Framework", "C3: handover between TUAVs with a ticket");
  const xA = 1.5, xM = 6.65, xB = 11.6, y0 = 1.35;
  pill(s, xA - 1.0, y0, 2.0, 0.55, COL.amber, "old TUAV a"); pill(s, xM - 1.0, y0, 2.0, 0.55, COL.teal, "member M"); pill(s, xB - 1.0, y0, 2.0, 0.55, COL.amber, "new TUAV b");
  [xA, xM, xB].forEach(x => lifeline(s, x, y0 + 0.55, 5.3));
  arrow(s, xA, 2.3, xB, 2.3, COL.amber, { both: true, w: 2.5 }); txt(s, "HO0  signed ECDH → link key K_{ab} (per epoch) + eviction lists", { x: 2.5, y: 1.95, w: 8.2, h: 0.32, fontSize: 13, align: "center" });
  msg(s, xA, xM, 3.1, COL.amber, "HO1 ticket Tk = Enc(K_{ab}, PID, pk, hk, N, exp)");
  msg(s, xM, xB, 3.9, COL.teal, "HO2 ⟨Tk, E′_M, ts, MAC(hk, …)⟩");
  msg(s, xB, xM, 4.7, COL.amber, "HO3 ⟨E′_b, Enc(K′_M, GK_b)⟩");
  stat(s, 0.6, 5.35, 3.0, "0", "signature checks at the new TUAV", COL.amber);
  stat(s, 3.5, 5.35, 3.2, "1.81 ms", "new TUAV (full: 3.64 ms)", COL.teal);
  stat(s, 6.75, 5.35, 3.2, "1.81 ms", "member (full: 5.45 ms)", COL.teal);
  card(s, 10.05, 5.4, 2.7, 1.45, COL.amber, "Why hk, not K_M", "the new TUAV never learns the old key", { hs: 14, bs: 13 });
  s.addNotes("C3 is handover between TUAVs. Neighbouring TUAVs agree a link key with signed Diffie-Hellman, once per epoch, and share their eviction lists. Before a member moves, the old TUAV gives it a ticket, encrypted under the link key. The member shows the ticket to the new TUAV with a MAC. The new TUAV opens the ticket, checks the MAC, runs one fresh Diffie-Hellman for forward secrecy, and sends its group key. No signature verification, no TA. Cost about 1.8 milliseconds on each side, compared with 3.6 and 5.4 for a full re-admission. The handover key is derived from the old key, so the new TUAV never learns the old one.");
}
{ const s = content("Part B - Framework", "The TA's new role: two-speed revocation");
  card(s, 0.6, 1.45, 5.9, 3.0, COL.teal, "Fast and local (in the field)", "A TUAV evicts a bad pseudonym immediately (UA3, RK1) and shares the list with its neighbours (HO0). One pseudonym per epoch, so the attacker cannot simply come back.", { bs: 16 });
  card(s, 6.85, 1.45, 5.9, 3.0, COL.deep, "Permanent (whenever the TA is reachable)", "TR1: the tracing key opens the pseudonym to the real ID.\nTR2: the TA publishes the hashes of the entity's remaining pseudonyms. Past ones stay private.", { bs: 16 });
  box(s, 0.6, 4.75, 12.15, 1.6, COL.amber, { tint: 90 });
  txt(s, [{ text: "Infrastructure-less, made true: ", options: { bold: true, color: COL.amber } }, { text: "the infrastructure helps when it is there, but nothing waits for it." }], { x: 0.9, y: 4.9, w: 11.6, h: 1.3, fontSize: 22, valign: "middle" });
  s.addNotes("So what does the TA still do? Revocation now has two speeds. Fast and local: a TUAV evicts a bad pseudonym immediately and shares the list with its neighbours. Because there is one pseudonym per epoch, the attacker cannot just come back. Permanent: whenever the TA becomes reachable, by any channel, it can trace the real identity, and it publishes the remaining pseudonyms of that entity so they are blocked everywhere. Past pseudonyms stay private. The infrastructure helps when it is there, but nothing waits for it.");
}

// =====================================================================
pres.addSection({ title: "Part C - Analysis" });
section("Part C - Analysis", "Part C · Security and performance", "Same constants as the paper. Honest accounting. Limits stated.");

{ const s = content("Part C - Analysis", "Security: every claim backed by a theorem");
  const H = (t) => ({ text: t, options: { bold: true, color: COL.white, fill: { color: COL.deep }, fontSize: 14 } });
  const Y = { text: "✓", options: { color: COL.green, bold: true, align: "center" } }, X = { text: "✗", options: { color: COL.red, bold: true, align: "center" } };
  const P = (t) => ({ text: t, options: { color: COL.amber, align: "center" } }), T = (t) => ({ text: t, options: { color: COL.green, align: "center" } });
  const rows = [[H("Property"), H("Base claimed"), H("Base actual"), H("Ours")],
    ["F1 Unforgeability (valid proof)", Y, P("◐ proof empty"), T("✓ Thm 1")], ["F4 Key-escrow resilience", Y, X, T("✓ Thm 2")],
    ["F7 Forward secrecy", Y, X, T("✓ Thm 5")], ["F8 Sound batch validation", Y, P("◐ no weights"), T("✓ Thm 3")],
    ["F9 Unlinkability", Y, Y, P("◐ per epoch")], ["F10 Non-repudiation", Y, X, T("✓ Thm 2")],
    ["N1 Works without online TA", "–", X, T("✓ Prop. 2")], ["N2 Revoked UAV locked out", "–", X, T("✓ Thm 5")],
    ["N3 Bounded cost under poisoning", "–", X, T("✓ Prop. 1")], ["N4 Vehicles · N5 Handover", "–", X, T("✓ C2 · Thm 8")]];
  s.addTable(rows.map(r => r.map(c => typeof c === "string" ? { text: c, options: {} } : c)), { x: 0.6, y: 1.35, w: 8.3, colW: [3.9, 1.3, 1.65, 1.45], fontSize: 14, color: HEX.ink,
    border: { type: "solid", pt: 0.75, color: HEX.grid }, rowH: 0.42, valign: "middle", objectName: nm("sectable") });
  card(s, 9.2, 1.35, 3.55, 2.45, COL.teal, "Proof approach", "Reductions to ECDLP / CDH with a secret challenge, via the forking lemma. Small-exponent test for batches.", { hs: 16, bs: 14 });
  card(s, 9.2, 4.0, 3.55, 2.6, COL.amber, "Honest trade-off", "Unlinkable across epochs, linkable inside one, so that local eviction works. ProVerif check planned.", { hs: 16, bs: 14 });
  s.addNotes("Here is the security comparison. Four claims of the base paper do not hold: escrow, forward secrecy, non-repudiation, and a valid unforgeability proof. Our scheme backs each with a theorem. Our proofs reduce to ECDLP or CDH, and unlike the paper, the challenge is a secret value. We also add new properties: working without the TA, locking out revoked UAVs, bounded cost under poisoning, vehicles and handover. One honest trade-off: pseudonyms are unlinkable across epochs but linkable within one epoch, because that is what makes local eviction work. We will also check the protocol in ProVerif.");
}
{ const s = content("Part C - Analysis", "Performance: faster even though the TUAV now verifies");
  s.addChart(pres.charts.LINE, [
    { name: "Base, honest + GEO RTT (600 ms)", labels: e2e.map(r => String(r.n)), values: e2e.map(r => r.orig_geo) },
    { name: "Base, honest + LEO RTT (50 ms)", labels: e2e.map(r => String(r.n)), values: e2e.map(r => r.orig_leo) },
    { name: "Base, as reported", labels: e2e.map(r => String(r.n)), values: e2e.map(r => r.orig_reported) },
    { name: "Ours (verification + key, no link)", labels: e2e.map(r => String(r.n)), values: e2e.map(r => r.ours) }],
    { x: 0.6, y: 1.35, w: 8.0, h: 5.45, ...chartText, chartColors: [HEX.red, HEX.amber, HEX.grey, HEX.teal], lineSize: 3, lineDataSymbolSize: 7,
      showLegend: true, legendPos: "b", showValAxisTitle: true, valAxisTitle: "ms", showCatAxisTitle: true, catAxisTitle: "number of UAVs n",
      showTitle: true, title: "Time to authenticate and key n UAVs", titleColor: HEX.ink, titleFontSize: 15, valAxisLabelFormatCode: "#,##0" });
  stat(s, 9.0, 1.45, 3.8, "228 ms", "ours, n = 120, all included", COL.teal);
  stat(s, 9.0, 3.15, 3.8, "3720 ms", "base honest, n = 120, + RTT", COL.red);
  card(s, 9.0, 4.95, 3.75, 1.85, COL.amber, "Why", "No pairings at all: about 1 scalar multiplication per UAV instead of 3 pairings on the TA.", { hs: 16, bs: 14 });
  s.addNotes("Performance, using exactly the paper's own constants. You might expect our scheme to be slower, because the TUAV now does the verification. It is the opposite. The base scheme looked cheap only because the three pairings per UAV on the TA were not counted. Our verification needs no pairings, about one scalar multiplication per UAV. So at 120 UAVs we need 228 milliseconds including key delivery, while the base scheme needs 3720 milliseconds plus the satellite round trip.");
}
{ const s = content("Part C - Analysis", "What it costs, and what we do not solve");
  const t = [[COL.amber, "Bigger request", "248 B vs 104 B reported: it carries X, Y (no directory needed) and E (forward secrecy)."],
             [COL.amber, "Linkable inside an epoch", "the price of local eviction; epoch length is tunable"],
             [COL.red, "Captured TUAV", "learns its cell's keys; cannot forge members. Future: threshold trust"],
             [COL.grey, "Pseudonym pool", "about 184 B each; 288 for a 3-day mission ≈ 53 KB"],
             [COL.grey, "Analytical numbers", "operation counts × the paper's timings; real measurements next"],
             [COL.grey, "Proof sketches", "full proofs and ProVerif in the final report"]];
  t.forEach(([c, h, b], i) => { const x = 0.6 + (i % 2) * 6.25, y = 1.45 + Math.floor(i / 2) * 1.6;
    box(s, x, y, 5.9, 1.4, c); txt(s, h, { x: x + 0.2, y: y + 0.12, w: 5.5, h: 0.45, fontSize: 18, bold: true, color: c }); txt(s, b, { x: x + 0.2, y: y + 0.6, w: 5.5, h: 0.7, fontSize: 15 }); });
  s.addNotes("A proposal is only credible if it says what it does not solve. Our request is bigger: 248 bytes, because it carries public-key material and a Diffie-Hellman value. Pseudonyms are linkable within one epoch. A captured TUAV is the weakest point; it learns its cell's keys but cannot forge members, and threshold trust is future work. Each UAV must carry a pool of pseudonyms, about 53 kilobytes for three days. Our numbers are analytical, the same method as the paper, and our proofs are sketches. Both will be completed in the final phase.");
}
{ const s = content("Part C - Analysis", "Next: build it, measure it, prove it");
  const ex = [["E1", "Success vs TA-link availability"], ["E2", "Latency vs n and RTT (incl. RTT = 0 honesty check)"], ["E3", "Goodput under 0–20% bad requests"],
              ["E4", "Key and rekey bytes vs n"], ["E5", "Vehicle tier: 50–500 vehicles, flood filtering"], ["E6", "Handover vs full re-admission"], ["E7", "Attack demos on base vs ours"]];
  txt(s, "Experiments", { x: 0.6, y: 1.35, w: 6, h: 0.45, fontSize: 20, bold: true, color: COL.deep });
  ex.forEach(([id, d], i) => { pill(s, 0.6, 1.95 + i * 0.66, 0.7, 0.48, COL.teal, id, { fs: 14 }); txt(s, d, { x: 1.45, y: 1.95 + i * 0.66, w: 5.6, h: 0.48, fontSize: 15, valign: "middle" }); });
  txt(s, "Who does what", { x: 7.4, y: 1.35, w: 5, h: 0.45, fontSize: 20, bold: true, color: COL.deep });
  const who = [[COL.teal, "Swaraj Kumar", "C1 UAV tier, crypto module, attacks on the base scheme"], [COL.violet, "Hritik Ranjan", "C2 vehicle tier, batch + fallback, ProVerif"],
               [COL.amber, "Harsh Raj", "C3 handover, mobility simulation, figures"]];
  who.forEach(([c, n, d], i) => card(s, 7.4, 1.95 + i * 1.55, 5.35, 1.35, c, n, d, { hs: 17, bs: 14 }));
  box(s, 7.4, 6.6 - 0.05, 5.35, 0.4, COL.deep, { tint: 90 });
  txt(s, "Tools: Python cryptography (P-256, HKDF, AES-GCM), ProVerif", { x: 7.5, y: 6.57, w: 5.2, h: 0.36, fontSize: 13, color: COL.deep, valign: "middle" });
  s.addNotes("Our plan for the final phase. We will implement both schemes in Python, with a simulated satellite link, a mobility model and an attacker. Seven experiments, including an honesty check: if we set the satellite delay to zero and our advantage still appears, we must explain it differently. We will also verify the protocols in ProVerif. Work is split by tier: Swaraj on C1 and the attacks, Hritik on C2 and ProVerif, Harsh on C3 and the mobility simulation.");
}
{ const s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "Part C - Analysis" });
  s.addText("The drone must verify on its own", { placeholder: "title" });
  s.addText("and one bad packet, one revoked UAV, or one lost satellite link must not stop it.", { placeholder: "body" });
  const sum = [["6", "findings against the base paper"], ["3", "tiers, zero online TA"], ["228 ms", "vs 3720 ms + RTT at n = 120"], ["8 KiB", "vs 16.7 MiB of key traffic"]];
  sum.forEach(([b, l], i) => { const x = 0.8 + i * 3.05; txt(s, b, { x, y: 4.95, w: 2.9, h: 0.8, fontSize: 36, bold: true, color: COL.amber, fontFace: "Cambria", margin: 0 });
    txt(s, l, { x, y: 5.75, w: 2.9, h: 0.6, fontSize: 14, color: COL.white, margin: 0 }); });
  txt(s, "Thank you. Questions?", { x: 0.8, y: 6.6, w: 6, h: 0.45, fontSize: 18, bold: true, color: COL.white });
  s.addNotes("To conclude. The paper solves a real problem with a good architecture, but its protocol keeps the cloud inside every step. We found six problems, and we proposed Cutting the Cord: one offline trust root, three tiers, and no online TA. It is more secure, and with the paper's own constants it is also faster: 228 milliseconds against 3720 plus the satellite delay, and 8 kilobytes of key traffic instead of 16.7 megabytes. The drone must verify on its own. Thank you, we are happy to take questions.");
}

await pres.writeFile({ fileName: OUT });
await applyTheme(OUT, THEME);
console.log("wrote", OUT);
})().catch(e => { console.error(e); process.exit(1); });
