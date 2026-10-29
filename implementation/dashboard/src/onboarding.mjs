import { appCategories, menus, settingCategories } from "./catalog.js";
import { categoryLabel } from "./branding.mjs";
import { SHORTCUTS } from "./layout.js";
export const GUIDE_VERSION = 1;
export const GUIDE_KEY = "coscaros.onboarding.v1";
// `target` lists CSS selectors in order of preference; all visible matches of one
// selector are highlighted together. The guide uses the first selector the card fits
// beside and centers the card when nothing is found, so list small, specific
// elements only — a whole screen would always be covered by the card.
const FIRST_SETTING = "[data-tour=settings] > :first-child";
// `interactive` lists areas the viewer may use during the step (the first selector
// that matches wins; a selector may name several parts, e.g. a list and its scroll
// arrows), so settings can be set up right away. Everything else stays blocked, and
// the guide itself never presses anything there. `follow` names other screens the
// viewer may open from the step themselves.
const SETTINGS_AREA = ["[data-tour=settings], .scroll-buttons"];
// `path` lists the real taps that lead to a step from any screen, so the guide can
// show the way instead of jumping there. Each tap names the visible label, the
// button to highlight and the screen state it leads to. The guide only highlights
// and navigates; it never presses the buttons, so no device action runs.
const taskbar = (id, to) => ({
  label: SHORTCUTS[id].label,
  target: [`[data-tour=taskbar] [data-layout-id=${id}]`],
  to,
});
const category = (route, list, name) => ({
  label: categoryLabel(name),
  target: [
    `.sidebar > button:nth-child(${list.findIndex(([n]) => n === name) + 1})`,
  ],
  to: { route, category: name },
});
const tile = (group, id, to = { route: id }) => ({
  label: menus[group].find(([, , tileId]) => tileId === id)[0],
  target: [`[data-tour=menu] > [data-layout-id=${id}]`],
  to,
});
const APPS = (name) => [
  taskbar("apps", { route: "apps" }),
  category("apps", appCategories, name),
];
const SETTINGS = (name) => [
  ...APPS("Hudiy"),
  tile("Hudiy", "settings", { route: "settings", category: "System" }),
  category("settings", settingCategories, name),
];
export const GUIDE_STEPS = [
  {
    id: "welcome",
    title: "Welcome to coscarOS",
    route: "dashboard",
    body: "This short tour shows where everything lives. It does not pair, play, record or install anything.",
  },
  {
    id: "dashboard",
    title: "Your dashboard",
    route: "dashboard",
    target: [
      ".dashboard-left",
      ".dash-widget-grid > :first-child",
    ],
    body: "Clock and navigation live here, with music and phone shortcuts beside them.",
  },
  {
    id: "taskbar",
    title: "Taskbar",
    route: "dashboard",
    target: ["[data-tour=taskbar]"],
    body: "Home, apps and volume are always one tap away. Long-press a shortcut to move it.",
  },
  {
    id: "apps",
    path: APPS("Hudiy"),
    title: "Applications",
    route: "apps",
    category: "Hudiy",
    target: ["[data-tour=menu] > .tile"],
    body: "Pick a category on the left to see its apps. Vehicle holds all OBD views.",
  },
  {
    id: "studio",
    path: [
      taskbar("dashboard", { route: "dashboard" }),
      {
        label: "Customize dashboard",
        target: [".dashboard-customize-entry"],
        to: { route: "dashboard-editor" },
      },
    ],
    title: "Dashboard Studio",
    route: "dashboard-editor",
    target: [".dash-inspector", ".dash-studio-header"],
    body: "Add, rename and resize widgets, drag a grip to move one, then Save.",
  },
  {
    id: "extensions",
    path: [...APPS("Hudiy"), tile("Hudiy", "marketplace")],
    title: "Layouts",
    route: "marketplace",
    target: [".dash-pack-actions", ".dash-pack:first-child"],
    body: "Import or export a layout as a JSON file, or start from a ready-made one.",
  },
  {
    id: "settings",
    path: SETTINGS("System"),
    title: "Settings",
    route: "settings",
    category: "System",
    target: [".sidebar"],
    body: "Settings are grouped into System, Projections, Audio and Bluetooth.",
  },
  {
    id: "theme",
    interactive: SETTINGS_AREA,
    path: [...SETTINGS("System"), tile("System", "theme")],
    title: "Theme",
    route: "theme",
    target: [
      "[data-tour=settings] > .setting-row:nth-child(-n+2)",
      FIRST_SETTING,
    ],
    body: "Switch between light and dark mode and pick an accent color.",
  },
  {
    id: "pair",
    interactive: [
      ".bluetooth-view, .bluetooth-scroll-buttons",
      "[data-tour=menu] > [data-layout-id=bluetooth-connections]",
    ],
    follow: ["bluetooth-connections"],
    path: SETTINGS("Bluetooth"),
    title: "Pair your phone",
    route: "settings",
    category: "Bluetooth",
    target: [
      ".bluetooth-view > header",
      "[data-tour=menu] > [data-layout-id=bluetooth-connections]",
      "[data-tour=menu] > .tile:first-child",
    ],
    body: "Tap Bluetooth to pair your phone now: turn it on, pick your phone and confirm the code.",
  },
  {
    id: "android",
    interactive: SETTINGS_AREA,
    path: [...SETTINGS("Projections"), tile("Projections", "android-settings")],
    title: "Android Auto",
    route: "android-settings",
    target: [".wireless-setting", ".wireless-setting > label"],
    body: "Set up the car hotspot and automatic connection here, or use a USB data cable.",
  },
  {
    id: "contacts",
    interactive: SETTINGS_AREA,
    path: [...SETTINGS("Bluetooth"), tile("Bluetooth", "contacts-settings")],
    title: "Contacts and calls",
    route: "contacts-settings",
    target: [FIRST_SETTING],
    body: "Choose how often contacts refresh, then Save. Allow contact sharing on your phone.",
  },
  {
    id: "music",
    interactive: SETTINGS_AREA,
    path: [...SETTINGS("Audio"), tile("Audio", "music-settings")],
    title: "Music",
    route: "music-settings",
    target: [FIRST_SETTING],
    body: "Choose how often song details refresh, then Save. Pick a source in Applications → Music.",
  },
  {
    id: "audio",
    interactive: SETTINGS_AREA,
    path: [...SETTINGS("Audio"), tile("Audio", "sound")],
    title: "Sound output",
    route: "sound",
    target: ["[data-tour=settings] > .toggle-row + .slider-row", FIRST_SETTING],
    body: "Set volume and balance here. A Bluetooth receiver for the car radio is optional.",
  },
  {
    id: "microphone",
    interactive: SETTINGS_AREA,
    path: [...SETTINGS("Audio"), tile("Audio", "audio-input")],
    title: "Microphone",
    route: "audio-input",
    target: [".audio-input-device", FIRST_SETTING],
    body: "Choose your microphone, adjust gain or mute, then Save.",
  },
  {
    id: "obd",
    interactive: SETTINGS_AREA,
    path: [...APPS("Vehicle"), tile("Vehicle", "obd-settings")],
    title: "Vehicle diagnostics",
    route: "obd-settings",
    target: [".obd-actions", FIRST_SETTING],
    body: "Pair a powered Bluetooth ELM327 adapter, select it, then tap Save and connect.",
  },
  {
    id: "my-obd",
    path: [...APPS("Vehicle"), tile("Vehicle", "custom-obd")],
    title: "My OBD",
    route: "custom-obd",
    target: [".obd-page-header"],
    body: "Your own grid of gauges, charts and values. Tap Edit dashboard to change it.",
  },
  {
    id: "logs",
    interactive: [".obd-logs"],
    path: [...APPS("Vehicle"), tile("Vehicle", "obd-logs")],
    title: "OBD Logs",
    route: "obd-logs",
    target: [".obd-log-recorder-head", ".obd-log-header"],
    body: "Record a session manually or automatically, then export it as CSV or JSONL.",
  },
  {
    id: "updates",
    interactive: [".software-updates"],
    path: [...SETTINGS("System"), tile("System", "software-update")],
    title: "Software updates",
    route: "software-update",
    target: [".software-actions", ".software-status"],
    body: "Check for updates now and choose manual or automatic installation.",
  },
  {
    id: "finish",
    interactive: SETTINGS_AREA,
    path: [...SETTINGS("System"), tile("System", "notification-settings")],
    title: "You're all set",
    route: "notification-settings",
    target: [FIRST_SETTING],
    body: "This switch silences all popups. Replay the tour in Settings → System → Application.",
  },
];
export function guideState(raw) {
  if (
    !raw ||
    raw.version !== GUIDE_VERSION ||
    !["pending", "completed", "skipped"].includes(raw.outcome) ||
    !Number.isInteger(raw.step) ||
    raw.step < 0 ||
    raw.step >= GUIDE_STEPS.length
  )
    return { version: GUIDE_VERSION, outcome: "pending", step: 0 };
  return { version: GUIDE_VERSION, outcome: raw.outcome, step: raw.step };
}
export function readGuide(storage) {
  try {
    return guideState(JSON.parse(storage.getItem(GUIDE_KEY)));
  } catch {
    return guideState(null);
  }
}
// Smallest box around all given client rects; empty rects are ignored.
export function unionRect(rects) {
  const visible = rects.filter((r) => r && r.width >= 1 && r.height >= 1);
  if (!visible.length) return null;
  const left = Math.min(...visible.map((r) => r.left)),
    top = Math.min(...visible.map((r) => r.top)),
    right = Math.max(...visible.map((r) => r.right)),
    bottom = Math.max(...visible.map((r) => r.bottom));
  return { left, top, right, bottom, width: right - left, height: bottom - top };
}
export function guideRect(rect, width, height) {
  if (!rect || rect.width < 1 || rect.height < 1) return null;
  const left = Math.max(8, rect.left - 6),
    top = Math.max(8, rect.top - 6);
  const right = Math.min(width - 8, rect.right + 6),
    bottom = Math.min(height - 8, rect.bottom + 6);
  return right > left && bottom > top
    ? { left, top, width: right - left, height: bottom - top }
    : null;
}
// Places the card beside the spotlight on the side with the most room, never
// covering it when any side fits, and always keeps the card inside the viewport.
export function guidePlacement(spot, card, width, height, gap = 14, margin = 12) {
  const clamp = (value, max) => Math.max(margin, Math.min(value, max - margin));
  const maxLeft = width - card.width,
    maxTop = height - card.height;
  if (!spot)
    return {
      side: "center",
      left: clamp((width - card.width) / 2, maxLeft),
      top: clamp((height - card.height) / 2, maxTop),
    };
  const centerX = spot.left + spot.width / 2 - card.width / 2,
    centerY = spot.top + spot.height / 2 - card.height / 2;
  const sides = [
    {
      side: "bottom",
      room: height - (spot.top + spot.height) - gap - margin,
      need: card.height,
      left: clamp(centerX, maxLeft),
      top: spot.top + spot.height + gap,
    },
    {
      side: "top",
      room: spot.top - gap - margin,
      need: card.height,
      left: clamp(centerX, maxLeft),
      top: spot.top - gap - card.height,
    },
    {
      side: "right",
      room: width - (spot.left + spot.width) - gap - margin,
      need: card.width,
      left: spot.left + spot.width + gap,
      top: clamp(centerY, maxTop),
    },
    {
      side: "left",
      room: spot.left - gap - margin,
      need: card.width,
      left: spot.left - gap - card.width,
      top: clamp(centerY, maxTop),
    },
  ];
  const fitting = sides.filter((s) => s.room >= s.need);
  // Fall back to the roomiest side; the card then overlaps as little as possible.
  const best = (fitting.length ? fitting : sides).reduce((a, b) =>
    b.room - b.need > a.room - a.need ? b : a,
  );
  return {
    side: fitting.length ? best.side : `${best.side} overlap`,
    left: clamp(best.left, maxLeft),
    top: clamp(best.top, maxTop),
  };
}

// States the app passes through while following a path; categories carry over.
function pathStates(path) {
  const states = [];
  let state = {};
  for (const tap of path) {
    state =
      tap.to.route === state.route ? { ...state, ...tap.to } : { ...tap.to };
    states.push(state);
  }
  return states;
}
// Where a path continues from `state`: right after the same screen and category,
// or right after entering the same screen, so the category tap still follows.
function resumeAt(states, state) {
  const exact = states.findLastIndex(
    (s) => s.route === state.route && s.category === state.category,
  );
  return exact >= 0 ? exact : states.findIndex((s) => s.route === state.route);
}
// Screens without the standard Back button.
const NO_BACK = ["apps", "settings", "dashboard", "dashboard-editor", "marketplace"];
// Taps that lead from the screen of step `from` to step `to`. Steps on the same
// screen need none. Otherwise continue the path from the current screen when it lies
// on the way, go Back one screen when that is shorter, or start again from the
// always-visible taskbar.
export function guideRoute(from, to) {
  const path = to.path || [];
  const here = { route: from.route, category: from.category };
  if (!path.length || (here.route === to.route && here.category === to.category))
    return [];
  const states = pathStates(path);
  const continueAt = resumeAt(states, here);
  const options = [path];
  if (continueAt >= 0) options.push(path.slice(continueAt + 1));
  const parent = pathStates(from.path || []).findLast(
    (state) => state.route !== here.route,
  );
  if (parent && !NO_BACK.includes(here.route)) {
    const backAt = resumeAt(states, parent);
    if (backAt >= 0)
      options.push([
        { label: "Back", target: [".back-button"], to: parent, back: true },
        ...path.slice(backAt + 1),
      ]);
  }
  return options.reduce((best, option) =>
    option.length < best.length ? option : best,
  );
}
// "Applications › coscarOS › Settings" — the way to a step in words.
export function guidePathLabel(step) {
  return (step.path || []).map((tap) => tap.label).join(" › ");
}
