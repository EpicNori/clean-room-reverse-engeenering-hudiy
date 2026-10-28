export const GUIDE_VERSION = 1;
export const GUIDE_KEY = "coscaros.onboarding.v1";
// `target` lists CSS selectors in order of preference; all visible matches of one
// selector are highlighted together. The guide uses the first selector the card fits
// beside and centers the card when nothing is found, so list small, specific
// elements only — a whole screen would always be covered by the card.
const FIRST_SETTING = "[data-tour=settings] > :first-child";
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
    title: "Applications",
    route: "apps",
    category: "Hudiy",
    target: ["[data-tour=menu] > .tile"],
    body: "Pick a category on the left to see its apps. Vehicle holds all OBD views.",
  },
  {
    id: "studio",
    title: "Dashboard Studio",
    route: "dashboard-editor",
    target: [".dash-inspector", ".dash-studio-header"],
    body: "Add, rename and resize widgets, drag a grip to move one, then Save.",
  },
  {
    id: "extensions",
    title: "Layouts",
    route: "marketplace",
    target: [".dash-pack-actions", ".dash-pack:first-child"],
    body: "Import or export a layout as a JSON file, or start from a ready-made one.",
  },
  {
    id: "settings",
    title: "Settings",
    route: "settings",
    category: "System",
    target: [".sidebar"],
    body: "Settings are grouped into System, Projections, Audio and Bluetooth.",
  },
  {
    id: "theme",
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
    title: "Pair your phone",
    route: "settings",
    category: "Bluetooth",
    target: [
      "[data-tour=menu] > [data-layout-id=pair]",
      "[data-tour=menu] > [data-layout-id=bluetooth-connections]",
      "[data-tour=menu] > .tile:first-child",
    ],
    body: "After the tour, pair your phone from this menu. Confirm the same code on both devices.",
  },
  {
    id: "android",
    title: "Android Auto",
    route: "android-settings",
    target: [".wireless-setting", ".wireless-setting > label"],
    body: "Connect with a USB data cable, or wirelessly through Bluetooth and the car hotspot.",
  },
  {
    id: "contacts",
    title: "Contacts and calls",
    route: "contacts-settings",
    target: [FIRST_SETTING],
    body: "Allow contact sharing on your phone, then choose how often contacts refresh.",
  },
  {
    id: "music",
    title: "Music",
    route: "music-settings",
    target: [FIRST_SETTING],
    body: "Choose how often song details refresh. Pick a source in Applications → Music.",
  },
  {
    id: "audio",
    title: "Sound output",
    route: "sound",
    target: ["[data-tour=settings] > .toggle-row + .slider-row", FIRST_SETTING],
    body: "Set the output volume here. A Bluetooth receiver for the car radio is optional.",
  },
  {
    id: "microphone",
    title: "Microphone",
    route: "audio-input",
    target: [".audio-input-device", FIRST_SETTING],
    body: "Choose your microphone, adjust gain or mute, then Save.",
  },
  {
    id: "obd",
    title: "Vehicle diagnostics",
    route: "obd-settings",
    target: [".obd-actions", FIRST_SETTING],
    body: "Pair a powered Bluetooth ELM327 adapter, select it, then tap Save and connect.",
  },
  {
    id: "my-obd",
    title: "My OBD",
    route: "custom-obd",
    target: [".obd-page-header"],
    body: "Your own grid of gauges, charts and values. Tap Edit dashboard to change it.",
  },
  {
    id: "logs",
    title: "OBD Logs",
    route: "obd-logs",
    target: [".obd-log-recorder-head", ".obd-log-header"],
    body: "Record a session manually or automatically, then export it as CSV or JSONL.",
  },
  {
    id: "updates",
    title: "Software updates",
    route: "software-update",
    target: [".software-actions", ".software-status"],
    body: "Check for updates here and choose manual or automatic installation.",
  },
  {
    id: "finish",
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
