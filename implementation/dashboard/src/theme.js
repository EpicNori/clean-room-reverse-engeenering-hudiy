import { colors } from "./catalog.js";

function mix(first, second, amount) {
  const channel = (hex, index) => parseInt(hex.slice(index, index + 2), 16);
  return (
    "#" +
    [1, 3, 5]
      .map((index) =>
        Math.round(
          channel(first, index) * (1 - amount) +
            channel(second, index) * amount,
        )
          .toString(16)
          .padStart(2, "0"),
      )
      .join("")
  );
}

export function themePalette(dark, accent) {
  const index =
    Number.isInteger(accent) && accent >= 0 && accent < colors.length
      ? accent
      : dark
        ? 0
        : 1;
  const seed = colors[index];
  const palette = dark
    ? {
        bg: "#000000",
        surface: mix(seed, "#121418", 0.92),
        selected: mix(seed, "#ffffff", 0.64),
        active: mix(seed, "#ffffff", 0.64),
        primary: mix(seed, "#ffffff", 0.72),
        "primary-text": mix(seed, "#000000", 0.88),
        text: "#ffffff",
        muted: mix(seed, "#ffffff", 0.83),
        track: mix(seed, "#303238", 0.68),
        outline: mix(seed, "#ffffff", 0.75),
        "switch-track": mix(seed, "#303238", 0.9),
        "switch-thumb": mix(seed, "#ffffff", 0.75),
      }
    : {
        bg: mix(seed, "#ffffff", 0.97),
        surface: mix(seed, "#ffffff", 0.9),
        selected: mix(seed, "#ffffff", 0.8),
        active: mix(seed, "#ffffff", 0.76),
        primary: mix(seed, "#000000", 0.55),
        "primary-text": mix(seed, "#000000", 0.65),
        text: mix(seed, "#000000", 0.88),
        muted: mix(seed, "#000000", 0.7),
        track: mix(seed, "#ffffff", 0.7),
        outline: mix(seed, "#000000", 0.75),
        "switch-track": mix(seed, "#ffffff", 0.83),
        "switch-thumb": mix(seed, "#000000", 0.65),
      };
  if (!dark && index === 1)
    Object.assign(palette, {
      bg: "#fff8f9",
      surface: "#f8eaf0",
      selected: "#fadaec",
      active: "#ffd7ee",
      primary: "#844c73",
      "primary-text": "#69345a",
      text: "#201a1e",
      muted: "#574b53",
      track: "#d4c3cd",
      outline: "#342b31",
      "switch-track": "#eadfe4",
      "switch-thumb": "#574b53",
    });
  if (dark && index === 0)
    Object.assign(palette, {
      surface: "#111318",
      selected: "#a6c3fc",
      active: "#a6c3fc",
      primary: "#eaf0ff",
      "primary-text": "#00152e",
      muted: "#ffffff",
      track: "#51545b",
      outline: "#f2f2f2",
      "switch-track": "#33363d",
    });
  return Object.fromEntries(
    Object.entries(palette).map(([key, value]) => ["--" + key, value]),
  );
}
