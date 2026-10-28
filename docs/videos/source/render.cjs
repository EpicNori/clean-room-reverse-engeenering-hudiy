#!/usr/bin/env node
// Renders docs/videos/coscaros-intro.mp4, docs/images/coscaros-intro-poster.jpg and
// docs/images/coscaros-intro-poster-play.jpg from coscaros-intro.html. See README.md.
"use strict";

const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");
const { createRequire } = require("module");
const { pathToFileURL } = require("url");

// Render tools and fonts are installed outside the repository; point COSCAROS_VIDEO_DEPS
// at that folder (it must contain node_modules), or install them where Node finds them.
const depsDir = process.env.COSCAROS_VIDEO_DEPS;
const req = depsDir ? createRequire(path.join(path.resolve(depsDir), "package.json")) : require;

const here = __dirname;
const args = process.argv.slice(2);
const opt = name => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : undefined; };
const flag = name => args.includes(name);

const htmlPath = path.join(here, "coscaros-intro.html");
const outMp4 = path.resolve(opt("--out") || path.join(here, "..", "coscaros-intro.mp4"));
const imagesDir = path.join(here, "..", "..", "images");
const outPoster = path.resolve(opt("--poster") || path.join(imagesDir, "coscaros-intro-poster.jpg"));
const outPosterPlay = path.resolve(opt("--poster-play") || path.join(imagesDir, "coscaros-intro-poster-play.jpg"));
const fps = Number(opt("--fps") || 30);
const crf = String(opt("--crf") || 27);
const posterTime = Number(opt("--poster-time") || 3.9);
const posterOnly = flag("--poster-only");
const stills = opt("--stills"); // comma-separated seconds; review PNGs next to the --out path

const FONTS = [
  ["InterTight", "normal", "100 900", "@fontsource-variable/inter-tight/files/inter-tight-latin-wght-normal.woff2"],
  ["InstrumentSerif", "italic", "400", "@fontsource/instrument-serif/files/instrument-serif-latin-400-italic.woff2"],
  ["InstrumentSerif", "normal", "400", "@fontsource/instrument-serif/files/instrument-serif-latin-400-normal.woff2"],
  ["GeistMono", "normal", "100 900", "@fontsource-variable/geist-mono/files/geist-mono-latin-wght-normal.woff2"],
];

function findBrowser() {
  const candidates = [
    process.env.CHROME_PATH,
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/microsoft-edge",
  ].filter(Boolean);
  const found = candidates.find(p => fs.existsSync(p));
  if (!found) throw new Error("No Chrome/Edge found; set CHROME_PATH.");
  return found;
}

function fontCss() {
  return FONTS.map(([family, style, weight, spec]) => {
    const file = req.resolve(spec);
    const b64 = fs.readFileSync(file).toString("base64");
    return `@font-face{font-family:"${family}";font-style:${style};font-weight:${weight};src:url(data:font/woff2;base64,${b64}) format("woff2");}`;
  }).join("\n");
}

const mss = s => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;

async function main() {
  const { chromium } = req("playwright-core");
  const ffmpeg = process.env.FFMPEG_PATH || req("ffmpeg-static");

  const browser = await chromium.launch({ executablePath: findBrowser(), headless: true });
  const open = async () => {
    const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
    page.on("pageerror", e => console.error("page error:", e.message));
    await page.goto(pathToFileURL(htmlPath).href);
    await page.addStyleTag({ content: fontCss() });
    const info = await page.evaluate(() => window.init());
    return { page, info };
  };
  const { page, info } = await open();
  console.log("scene:", info, "length", mss(info.duration));
  if (!info.fontsOk) throw new Error("Fonts did not load");

  fs.mkdirSync(path.dirname(outPoster), { recursive: true });
  await page.evaluate(t => window.seek(t), posterTime);
  await page.screenshot({ path: outPoster, type: "jpeg", quality: 90 });
  console.log("poster:", outPoster);
  {
    const { page: p2 } = await open();
    await p2.evaluate(label => window.posterPlay(label), `Watch the intro · ${mss(info.duration)}`);
    await p2.evaluate(t => window.seek(t), posterTime);
    await p2.screenshot({ path: outPosterPlay, type: "jpeg", quality: 90 });
    await p2.close();
    console.log("poster with play button:", outPosterPlay);
  }

  if (stills) {
    for (const s of stills.split(",").map(Number)) {
      await page.evaluate(t => window.seek(t), s);
      const p = path.join(path.dirname(outMp4), `still-${s.toFixed(2)}s.png`);
      await page.screenshot({ path: p, type: "png" });
      console.log("still:", p);
    }
  }
  if (posterOnly) { await browser.close(); return; }

  const frames = Math.round(Math.min(info.duration, Number(opt("--until") || Infinity)) * fps); // --until: partial test render
  fs.mkdirSync(path.dirname(outMp4), { recursive: true });
  const ff = spawn(ffmpeg, [
    "-y", "-loglevel", "error",
    "-f", "image2pipe", "-framerate", String(fps), "-c:v", "mjpeg", "-i", "-",
    "-c:v", "libx264", "-preset", "slow", "-crf", crf, "-pix_fmt", "yuv420p",
    "-r", String(fps), "-movflags", "+faststart", "-an", outMp4,
  ], { stdio: ["pipe", "inherit", "inherit"] });
  const ffDone = new Promise((res, rej) => ff.on("close", c => c === 0 ? res() : rej(new Error("ffmpeg exit " + c))));

  const t0 = Date.now();
  for (let f = 0; f < frames; f++) {
    await page.evaluate(t => window.seek(t), f / fps);
    const buf = await page.screenshot({ type: "jpeg", quality: 95 }); // JPEG frames: much faster than PNG at 1080p
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once("drain", r));
    if (f % 150 === 0) console.log(`frame ${f}/${frames} (${((Date.now() - t0) / 1000).toFixed(0)} s)`);
  }
  ff.stdin.end();
  await ffDone;
  await browser.close();
  console.log(`video: ${outMp4} (${frames} frames, ${mss(info.duration)}, ${(fs.statSync(outMp4).size / 1048576).toFixed(2)} MB)`);
}

main().catch(e => { console.error(e); process.exit(1); });
