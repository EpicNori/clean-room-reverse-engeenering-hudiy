import React, { useState, useEffect, useRef, useMemo } from "react";
import "@material-symbols/font-600/rounded.css";
import "@fontsource/roboto/400.css";
import {
  appCategories,
  settingCategories,
  menus,
  frequencies,
  colors,
  readPreferences,
} from "./catalog";
import { Telemetry } from "./Telemetry";
import { createMediaProcessor } from "./audio";
import { audioPresets } from './audioPresets.mjs';
import { themePalette } from "./theme";
import { useDragScroll } from "./useDragScroll";
import { PhonebookView } from "./PhonebookView";
import { UpdateInterval } from "./UpdateInterval";
import { BluetoothView } from "./BluetoothView";
import { OBDSettings } from "./OBDSettings";
import { DisplayBrightness } from "./DisplayBrightness";
import { CallButton } from "./CallButton";
import { WirelessSettings } from "./WirelessSettings";
import { PhoneReconnect } from "./PhoneReconnect";
import { RadioOutput } from "./RadioOutput";
import { resolveMedia, isRemotePlayer } from "./media.mjs";
import { NoticeCenter, TrackObserver } from "./notifications.mjs";
import { LAYOUT_KEY, SHORTCUTS, SCREEN_IDS, REQUIRED_SHORTCUTS, readLayout, normalizeLayout, moveItem, pinShortcut, customizationAttributes } from './layout';
import { useLongPress } from './useLongPress';
import { CustomizeMenu } from './CustomizeMenu';

const HOST_MODE = new URLSearchParams(location.search).get("host");
const TASKBAR = HOST_MODE === "taskbar";
const CONTENT = HOST_MODE === "content";

export function Icon({ name, size = 48 }) {
  return (
    <span
      className="material-symbols-rounded icon"
      style={{ fontSize: `calc(${size} * var(--unit))` }}
      aria-hidden="true"
    >
      {name}
    </span>
  );
}
export function IconButton({
  icon,
  label,
  onClick,
  className = "",
  size = 48,
  shortcutId,
  disabled=false,
  layoutKind = 'shortcut',
}) {
  return (
    <button
      className={`icon-button ${className}`}
      aria-label={label}
      title={label}
      onClick={onClick}
      disabled={disabled}
      {...(shortcutId ? customizationAttributes(layoutKind, shortcutId) : {})}
    >
      <Icon name={icon} size={size} />
    </button>
  );
}
function Tile({ label, icon, onClick, id, group }) {
  return (
    <button className="tile" onClick={onClick} {...customizationAttributes('tile', id, group)}>
      <Icon name={icon} />
      <span>{label}</span>
    </button>
  );
}
function Toggle({ label, value, onChange }) {
  return (
    <div className="setting-row toggle-row">
      <span>{label}</span>
      <button
        className={`switch ${value ? "on" : ""}`}
        role="switch"
        aria-label={label}
        aria-checked={value}
        onClick={() => onChange(!value)}
      >
        <span />
      </button>
    </div>
  );
}
function Radio({ label, options, value, onChange }) {
  return (
    <fieldset className="setting-row radio-row">
      <legend>{label}</legend>
      <div>
        {options.map((opt) => (
          <label key={opt}>
            <input
              type="radio"
              name={label}
              checked={value === opt}
              onChange={() => onChange(opt)}
            />
            {opt}
          </label>
        ))}
      </div>
    </fieldset>
  );
}
function Slider({
  label,
  value,
  onChange,
  min = 0,
  max = 100,
  step = 1,
  format = (v) => v,
}) {
  return (
    <div className="setting-row slider-row">
      <span>{label}</span>
      <div className="slider-controls">
        <IconButton
          icon="arrow_left"
          label={`Decrease ${label}`}
          onClick={() => onChange(Math.max(min, value - step))}
        />
        <input
          aria-label={label}
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          style={{ "--fill": `${((value - min) / (max - min)) * 100}%` }}
        />
        <output>{format(value)}</output>
        <IconButton
          icon="arrow_right"
          label={`Increase ${label}`}
          onClick={() => onChange(Math.min(max, value + step))}
        />
      </div>
    </div>
  );
}
const fmt = (n) =>
  `${String(Math.floor((Number.isFinite(n) ? n : 0) / 60)).padStart(2, "0")}:${String(Math.floor((Number.isFinite(n) ? n : 0) % 60)).padStart(2, "0")}`;
const mediaTitles = {
  storage: "Storage",
  radio: "FM Radio",
  a2dp: "Bluetooth",
  "autobox-music": "Autobox",
  "android-music": "Android Auto",
};
const mediaIcons = {
  storage: "audio_file",
  radio: "cell_tower",
  a2dp: "bluetooth_audio",
  "autobox-music": "smartphone",
  "android-music": "navigation",
};
export function App() {
  const [layout, setLayout] = useState(readLayout);
  const [customize, setCustomize] = useState(null);
  const [prefs, setPrefs] = useState(readPreferences),
    [screen, setScreen] = useState("dashboard"),
    [category, setCategory] = useState("Phone"),
    [settingCategory, setSettingCategory] = useState("System"),
    [history, setHistory] = useState([]),
    [now, setNow] = useState(new Date()),
    [viewport, setViewport] = useState({
      width: innerWidth,
      height: innerHeight,
    }),
    [notice, setNotice] = useState(""),
    [digits, setDigits] = useState(""),
    [frequency, setFrequency] = useState(87.5),
    [files, setFiles] = useState([]),
    [shuffle, setShuffle] = useState(false),
    [repeat, setRepeat] = useState(false),
    [media, setMedia] = useState({
      title: "",
      duration: 0,
      time: 0,
      playing: false,
      source: "storage",
    }),
    [status, setStatus] = useState({
      obd: { connected: false, values: {}, history: [] },
      phone: { name: "" },
    }),
    [service, setService] = useState(false),
    [projectionData, setProjectionData] = useState({
      media: {},
      navigation: {},
    }),
    [phonebookData, setPhonebookData] = useState({ views: {}, error: '', syncing: false }),
    [obdPath, setObdPath] = useState("/dev/rfcomm0");
  const audio = useRef(null),
    viewportRef = useRef(null),
    processor = useRef(null),
    fileInput = useRef(null),
    scroll = useRef(null),
    urls = useRef([]),
    routeRevision = useRef(0);
  const layoutState = useRef(layout), layoutPending = useRef(0), layoutQueue = useRef(Promise.resolve()), layoutEnabled = useRef(false), layoutReady = useRef(false), layoutGeneration = useRef(0), updatesPending = useRef(0);
  const latestNotice = useRef({prefs, native: false});
  latestNotice.current = {prefs, native: Boolean(HOST_MODE && status.projection?.enabled)};
  const noticeCenter = useRef(null), trackObserver = useRef(new TrackObserver());
  const outputControl = useRef({busy: false, pending: null, confirmed: null});
  const nativeNotice = payload => {
    const p = latestNotice.current.prefs;
    const palette = themePalette(p.dark, p.dark ? p.darkAccent : p.accent);
    return fetch('/api/action', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({action: 'notification', ...payload,
        background: palette['--active'], foreground: palette['--primary-text']})});
  };
  if (!noticeCenter.current) noticeCenter.current = new NoticeCenter(
    () => latestNotice.current.prefs, payload => {
      if (latestNotice.current.native) {
        setNotice("");
        if (payload.expired) return; // Native timer owns expiry across both web views.
        nativeNotice(payload).then(r => { if (!r.ok) throw Error(); })
          .catch(() => { if (noticeCenter.current.current === payload) setNotice(payload.message ? payload : ''); });
      } else setNotice(payload.message ? payload : '');
    });
  useEffect(() => {
    noticeCenter.current.sync();
    if (latestNotice.current.native) {
      for (const [kind, key] of [['output','outputNotice'],['input','inputNotice'],['track','nowPlayingNotice']]) {
        if (!prefs[key]) nativeNotice({kind, message: '', duration: 1}).catch(() => {});
      }
    }
  }, [prefs.outputNotice, prefs.inputNotice, prefs.nowPlayingNotice, status.projection?.enabled]);
  useEffect(() => {
    if (latestNotice.current.native) nativeNotice({kind: 'theme'}).catch(() => {});
  }, [prefs.dark, prefs.accent, prefs.darkAccent, status.projection?.enabled]);
  useEffect(() => {
    if (TASKBAR) return;
    const message = trackObserver.current.observe(media, projectionData.media);
    if (message) noticeCenter.current.show('track', message);
  }, [media, projectionData.media]);
  const audioPending=useRef(0), audioQueue=useRef(Promise.resolve()), audioConfirmed=useRef(null);
  layoutState.current = layout;
  layoutEnabled.current = Boolean(status.projection?.enabled);
  useDragScroll(viewportRef);
  useLongPress(viewportRef, setCustomize);
  useEffect(() => {
    const sync = event => { if (event.key === LAYOUT_KEY && !layoutEnabled.current) setLayout(readLayout()); };
    addEventListener('storage', sync);
    return () => removeEventListener('storage', sync);
  }, []);
  const updateLayout = change => {
    if (HOST_MODE && (!layoutReady.current || !layoutEnabled.current)) {
      tell('Waiting for the Pi service; layout has not been saved');
      return;
    }
    const next = normalizeLayout(change(layoutEnabled.current ? layoutState.current : readLayout()));
    try { localStorage.setItem(LAYOUT_KEY, JSON.stringify(next)); }
    catch { if (!layoutEnabled.current) { tell('Could not save the layout'); return; } }
    layoutState.current = next;
    layoutGeneration.current++;
    setLayout(next);
    if (layoutEnabled.current) {
      layoutPending.current++;
      layoutQueue.current = layoutQueue.current.then(async () => {
        try {
          const result = await action('layout-settings', { layout: next });
          if (result && layoutPending.current === 1) {
            const confirmed = normalizeLayout(result.layout);
            setLayout(confirmed);
            try { localStorage.setItem(LAYOUT_KEY, JSON.stringify(confirmed)); } catch {}
            tell('Layout saved');
          }
        } finally { layoutPending.current--; }
      });
    } else tell('Layout saved');
  };
  const saveRefresh = async (key, value) => {
    if (HOST_MODE || status.projection?.enabled) {
      updatesPending.current++;
      try {
        const result = await action('refresh-settings', { updates: { [key]: value } });
        if (result) setPrefs(p => ({ ...p, ...result.updates }));
      } finally { updatesPending.current--; }
    } else { setPrefs(p => ({ ...p, [key]: value })); tell('Refresh interval saved'); }
  };
  const moveCustomized = (delta, part) => {
    updateLayout(current => {
      if (customize.kind === 'taskbar') return { ...current, taskbar: moveItem(current.taskbar, customize.id, delta) };
      if (customize.kind === 'tile') return { ...current, menus: { ...current.menus, [customize.group]: moveItem(current.menus[customize.group], customize.id, delta) } };
      if (part === 'leftCards') return { ...current, leftCards: [...current.leftCards].reverse() };
      const column = ['clock', 'navigation'].includes(customize.id) ? 'clock-navigation' : customize.id;
      return { ...current, columns: moveItem(current.columns, column, delta) };
    });
  };
  const saveAudio = patch => {
    setPrefs(p=>({...p,...patch}));
    if (status.projection?.renderer!=='standalone') return;
    audioPending.current++;
    audioQueue.current=audioQueue.current.then(async()=>{
      try {
        const result=await action('audio-settings',{settings:patch});
        if (result) audioConfirmed.current=result.settings;
        if (audioPending.current===1 && audioConfirmed.current) setPrefs(p=>({...p,...audioConfirmed.current}));
      } finally {audioPending.current--;}
    });
  };
  const pref = (key, value) => {
    if (key === 'volume') { outputVolume(value); return; }
    if (key === 'mute') { outputMute(value); return; }
    if (key === 'inputVolume' || key === 'muteInput') {
      setPrefs(p => ({...p, [key]: value}));
      noticeCenter.current.show('input', key === 'muteInput' ? value ? 'Input mute setting: on' : 'Input mute setting: off' : `Input level setting ${value}`);
      return;
    }
    if (['equalizer','balance','preset'].includes(key)) {
      saveAudio({[key]:value,...(key==='equalizer' ? {preset:'Custom'} : {})}); return;
    }
    if (key === 'androidDayNight' && status.projection?.enabled) {
      action('projection-settings', {
        dayNight: value,
        ...(HOST_MODE && value === 'Common' ? {darkMode: prefs.dark} : {}),
      }).then(result => { if (result) setPrefs(p => ({...p, androidDayNight: result.options.dayNight})); });
      return;
    }
    if (key === 'dark' && HOST_MODE && status.projection?.enabled) {
      action('projection-settings', {darkMode: value}).then(result => {
        if (result) setPrefs(p => ({...p, dark: result.options.darkMode}));
      });
      return;
    }
    if (
      ["androidAutostart", "androidTaskbar"].includes(key) &&
      status.projection?.enabled
    ) {
      action("projection-settings", {
        [key === "androidAutostart" ? "autostart" : "taskbarVisible"]: value,
      }).then((result) => {
        if (result) setPrefs((p) => ({ ...p, [key]: value }));
      });
    } else setPrefs((p) => ({ ...p, [key]: value }));
  };
  const tell = message => noticeCenter.current.show('toast', message);
  const go = (next) => {
    if (TASKBAR) {
      action("projection", { operation: next });
      return;
    }
    setHistory((h) => [...h, { screen, category, settingCategory }]);
    setScreen(next);
  };
  const back = () => {
    if (history.length) {
      const old = history[history.length - 1];
      setScreen(old.screen);
      setCategory(old.category);
      setSettingCategory(old.settingCategory);
      setHistory((h) => h.slice(0, -1));
    } else setScreen("dashboard");
  };
  const home = () => {
      if (TASKBAR) {
        action("projection", { operation: "dashboard" });
        return;
      }
      setScreen("dashboard");
      setHistory([]);
    },
    menu = () => {
      if (TASKBAR) {
        action("projection", { operation: "apps" });
        return;
      }
      setScreen("apps");
      setHistory([]);
    };
  const time = now.toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: prefs.timeFormat === "12h",
  });
  useEffect(() => {
    const resize = () =>
      setViewport({ width: innerWidth, height: innerHeight });
    resize();
    addEventListener("resize", resize);
    return () => removeEventListener("resize", resize);
  }, []);
  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      const controller = new AbortController();
      const deadline = setTimeout(() => controller.abort(), 2000);
      try {
        const response = await fetch("/api/projection", {
          signal: controller.signal,
        });
        if (!response.ok) throw Error();
        const data = await response.json();
        if (!cancelled) {
          setProjectionData(data);
          if (data.enabled && ['Common', 'Day', 'Night'].includes(data.options?.dayNight)) {
            setPrefs(p => p.androidDayNight === data.options.dayNight ? p : {...p, androidDayNight: data.options.dayNight});
          }
          if (HOST_MODE && data.enabled)
            setPrefs((p) => ({
              ...p,
              androidAutostart: data.options.autostart,
              androidTaskbar: data.options.taskbarVisible,
              ...(typeof data.options.darkMode === 'boolean' ? {dark: data.options.darkMode} : {}),
            }));
        }
      } catch {
        if (!cancelled) setProjectionData({ media: {}, navigation: {} });
      } finally {
        clearTimeout(deadline);
      }
    };
    poll();
    const interval = setInterval(poll, prefs.musicRefreshSeconds * 1000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [prefs.musicRefreshSeconds]);
  useEffect(() => {
    if (TASKBAR) return;
    let cancelled = false;
    const poll = async () => {
      const controller = new AbortController();
      const deadline = setTimeout(() => controller.abort(), 2000);
      try {
        const response = await fetch('/api/phonebook', { signal: controller.signal });
        if (!response.ok) throw Error();
        const data = await response.json();
        if (!cancelled) setPhonebookData(data);
      } catch {
        if (!cancelled) setPhonebookData({ views: {}, error: 'Phonebook service unavailable', syncing: false });
      } finally { clearTimeout(deadline); }
    };
    poll();
    const interval = setInterval(poll, 5000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [prefs.contactsRefreshSeconds]);
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  useEffect(()=>{
    if(status.projection?.renderer!=='standalone') return;
    let cancelled=false;
    const poll=async()=>{
      const controller=new AbortController(); const deadline=setTimeout(()=>controller.abort(),2000);
      try {
        const response=await fetch('/api/audio-settings',{signal:controller.signal});
        if(!response.ok) return;
        const data=await response.json();
        if(!cancelled && data.enabled && !audioPending.current) {
          audioConfirmed.current=data.settings;
          setPrefs(p=>JSON.stringify({equalizer:p.equalizer,balance:p.balance,preset:p.preset})===JSON.stringify(data.settings) ? p : {...p,...data.settings});
        }
      } catch {} finally {clearTimeout(deadline);}
    };
    poll(); const interval=setInterval(poll,1000);
    return()=>{cancelled=true;clearInterval(interval);};
  },[status.projection?.renderer]);
  useEffect(() => {
    try {
      localStorage.setItem("hudiy.preferences", JSON.stringify(prefs));
    } catch {}
  }, [prefs]);
  useEffect(() => {
    const sync = (e) => {
      if (e.key === "hudiy.preferences") setPrefs(readPreferences());
    };
    addEventListener("storage", sync);
    return () => removeEventListener("storage", sync);
  }, []);
  useEffect(() => {
    if (processor.current) processor.current.update(prefs);
    else audio.current.volume = prefs.mute ? 0 : prefs.volume / 100;
  }, [prefs.volume, prefs.mute, prefs.equalizer, prefs.balance]);
  useEffect(() => {
    if (scroll.current) scroll.current.scrollTop = 0;
  }, [screen]);
  useEffect(() => {
    viewportRef.current
      ?.querySelector(".sidebar .selected")
      ?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [screen, category, settingCategory, viewport.width, viewport.height]);
  useEffect(
    () => () => {
      urls.current.forEach(URL.revokeObjectURL);
      noticeCenter.current.dispose();
      if (processor.current) processor.current.close().catch(() => {});
    },
    [],
  );
  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      const controller = new AbortController();
      const deadline = setTimeout(() => controller.abort(), 2000);
      try {
        const generation = layoutGeneration.current;
        const r = await fetch("/api/status", {
          signal: controller.signal,
        });
        if (!r.ok) throw Error();
        const data = await r.json();
        if (!cancelled) {
          setService(true);
          setStatus(data);
          if (data.layout && !layoutPending.current && generation === layoutGeneration.current) {
            const loaded = normalizeLayout(data.layout);
            layoutReady.current = true;
            layoutState.current = loaded;
            setLayout(loaded);
            try { localStorage.setItem(LAYOUT_KEY, JSON.stringify(loaded)); } catch {}
          }
          if (data.updates && !updatesPending.current) setPrefs(p => ({ ...p, ...data.updates }));
          if (CONTENT && data.projection?.revision > routeRevision.current) {
            routeRevision.current = data.projection.revision;
            const next = SCREEN_IDS.has(data.projection.route) ? data.projection.route : 'dashboard';
            setScreen(next);
            if (next in mediaTitles) setMedia(current => ({ ...current, source: next }));
            setHistory([]);
          }
        }
      } catch {
        if (!cancelled) setService(false);
      } finally {
        clearTimeout(deadline);
      }
    };
    poll();
    const t = setInterval(poll, 1000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, []);
  async function action(name, params = {}, {quiet = false} = {}) {
    try {
      const r = await fetch("/api/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: name, ...params }),
      });
      const d = await r.json();
      if (!r.ok) throw Error(d.error || "Action unavailable");
      if (d.message && !quiet) tell(d.message);
      return d;
    } catch (e) {
      tell(service ? e.message : "Local hardware service is not running");
      return null;
    }
  }
  async function setOutput(patch, message) {
    const next = {...latestNotice.current.prefs, ...patch};
    const control = outputControl.current;
    if (!control.busy) control.confirmed = {volume: prefs.volume, mute: prefs.mute};
    latestNotice.current.prefs = next;
    setPrefs(p => ({...p, ...patch}));
    if (!HOST_MODE) { noticeCenter.current.show('output', message); return; }
    // At most one request and one latest pending value, even while dragging.
    control.pending = {volume: next.volume, mute: next.mute, message};
    if (control.busy) return;
    control.busy = true;
    try {
      while (control.pending) {
        const change = control.pending; control.pending = null;
        const result = await action('audio-volume', {volume: change.mute ? 0 : change.volume}, {quiet: true});
        if (result) {
          control.confirmed = {volume: change.volume, mute: change.mute};
          if (!control.pending) noticeCenter.current.show('output', change.message);
        } else if (!control.pending) setPrefs(p => ({...p, ...control.confirmed}));
      }
    } finally { control.busy = false; }
  }
  function outputVolume(value) { return setOutput({volume: value}, `Volume ${value}`); }
  function outputMute(value = !latestNotice.current.prefs.mute) {
    return setOutput({mute: value}, value ? 'Output muted' : 'Output unmuted');
  }
  function play() {
    if (screen === 'a2dp' || (liveMedia && shownMedia.source === 'a2dp')) {
      action('bluetooth-media', {operation:'toggle'}); return;
    }
    if (liveMedia) {
      action("projection", { operation: "media-toggle" });
      return;
    }
    if (isRemotePlayer(screen)) { tell(`${mediaTitles[screen]} media is unavailable`); return; }
    if (media.source === "storage" && audio.current.src) {
      if (audio.current.paused) {
        try {
          if (!processor.current)
            processor.current = createMediaProcessor(audio.current);
          if (processor.current) {
            processor.current.update(prefs);
            processor.current
              .resume()
              .catch(() => tell("Audio processing could not resume"));
          }
          audio.current
            .play()
            .catch(() => tell("This audio file could not be played"));
        } catch {
          tell("Audio processing could not start");
        }
      } else audio.current.pause();
    } else
      tell(`${mediaTitles[media.source] || "Media source"} is not connected`);
  }
  function selectFile(i, autoplay = false) {
    const f = files[i];
    if (!f) return;
    audio.current.src = f.url;
    setMedia({
      title: f.name,
      duration: 0,
      time: 0,
      playing: false,
      source: "storage",
    });
    audio.current.load();
    if (autoplay)
      audio.current
        .play()
        .catch(() => tell("This audio file could not be played"));
  }
  function stepTrack(delta, autoplay = media.playing) {
    if (screen === 'a2dp' || (liveMedia && shownMedia.source === 'a2dp')) {
      action('bluetooth-media', {operation:delta > 0 ? 'next' : 'previous'}); return;
    }
    if (liveMedia) {
      action("projection", {
        operation: delta > 0 ? "media-next" : "media-previous",
      });
      return;
    }
    if (isRemotePlayer(screen)) { tell(`${mediaTitles[screen]} media is unavailable`); return; }
    if (!files.length) {
      tell("No audio files loaded");
      return;
    }
    const i = files.findIndex((f) => f.name === media.title);
    selectFile(
      shuffle
        ? Math.floor(Math.random() * files.length)
        : (i + delta + files.length) % files.length,
      autoplay,
    );
  }
  function loadFiles(e) {
    urls.current.forEach(URL.revokeObjectURL);
    const next = Array.from(e.target.files || [])
      .filter(
        (f) =>
          f.type.startsWith("audio/") ||
          /\.(mp3|wav|ogg|flac|m4a)$/i.test(f.name),
      )
      .map((f) => ({
        name: f.name.replace(/\.[^.]+$/, ""),
        url: URL.createObjectURL(f),
      }));
    urls.current = next.map((f) => f.url);
    setFiles(next);
    if (next.length) {
      audio.current.src = next[0].url;
      setMedia({
        title: next[0].name,
        duration: 0,
        time: 0,
        playing: false,
        source: "storage",
      });
      audio.current.load();
      go("storage");
    } else tell("Select an audio file");
    e.target.value = "";
  }
  function open(id) {
    if (id === "quit") {
      action('application-quit');
      return;
    }
    if (
      (id.startsWith("android-") &&
        !["android-settings", "android-music"].includes(id)) ||
      (id.startsWith("autobox-") &&
        !["autobox-settings", "autobox-music", "autobox-device"].includes(id))
    ) {
      action("projection", {
        projection: id.startsWith("android") ? "android" : "autobox",
        operation: id.split("-").slice(-1)[0],
      });
      return;
    }
    if (id in mediaTitles) setMedia((m) => ({ ...m, source: id }));
    go(id);
  }
  useEffect(() => {
    if (projectionData.exitError) tell(projectionData.exitError);
  }, [projectionData.exitError]);
  function activateShortcut(id) {
    if (id === 'dashboard') return home();
    if (id === 'apps') return menu();
    if (id === 'mute') return outputMute();
    if (id === 'volume-down') return outputVolume(Math.max(0, prefs.volume - 5));
    if (id === 'volume-up') return outputVolume(Math.min(100, prefs.volume + 5));
    if (id === 'connection-status') return go('obd-settings');
    if (id === 'clock') return home();
    if (id === 'media-toggle') return TASKBAR ? action('projection', { operation: 'media-toggle' }) : play();
    if (id === 'media-next' || id === 'media-previous') return TASKBAR ? action('projection', { operation: id }) : stepTrack(id === 'media-next' ? 1 : -1);
    open(id);
  }
  useEffect(() => {
    const key = (e) => {
      if (/INPUT|TEXTAREA/.test(e.target.tagName)) return;
      if (customize || document.querySelector('[role="dialog"]')) return;
      if (e.key === "Escape") {
        e.preventDefault();
        back();
      } else if (e.key === "h") home();
      else if (e.key === "g") {
        menu();
        setCategory("Phone");
      } else if (e.key === "j") open("storage");
      else if (e.key === "b") play();
      else if (e.key === "x" && !shownMedia.playing) play();
      else if (e.key === "c") {
        if (liveMedia && shownMedia.playing)
          action("projection", { operation: "media-toggle" });
        else audio.current.pause();
      } else if (e.key === "n") stepTrack(1);
      else if (e.key === "v") stepTrack(-1);
      else if (e.key.startsWith("Arrow")) {
        const controls = [
          ...document.querySelectorAll(
            ".app-canvas button,.app-canvas input:not([type=file])",
          ),
        ];
        const i = controls.indexOf(document.activeElement);
        controls[
          (i +
            (e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 1) +
            controls.length) %
            controls.length
        ]?.focus();
        e.preventDefault();
      }
    };
    addEventListener("keydown", key);
    return () => removeEventListener("keydown", key);
  });
  const toggle = (key, label) => (
    <Toggle
      key={key}
      label={label}
      value={prefs[key]}
      onChange={(v) => pref(key, v)}
    />
  );
  const slider = (key, label, options = {}) => (
    <Slider
      key={key}
      label={label}
      value={prefs[key]}
      onChange={(v) => pref(key, v)}
      {...options}
    />
  );
  const radio = (key, label, options) => (
    <Radio
      key={key}
      label={label}
      options={options}
      value={prefs[key]}
      onChange={(v) => pref(key, v)}
    />
  );
  const settings = {
    'music-settings': <>
      <UpdateInterval label="Music refresh interval" value={prefs.musicRefreshSeconds} min={1} max={60}
        save={value => saveRefresh('musicRefreshSeconds', value)} />
      <p className="setting-note">Refresh music details, cover art and navigation from Android Auto. Phone data updates while automatic opening is off.</p>
    </>,
    'contacts-settings': <>
      <UpdateInterval label="Contacts refresh interval" value={prefs.contactsRefreshSeconds} min={5} max={3600}
        save={value => saveRefresh('contactsRefreshSeconds', value)} />
      <p className="setting-note">Download contacts, favorites and call history from the connected Bluetooth phone at this interval. Refresh on a contact screen still runs immediately; the screen checks for new results every 5 seconds.</p>
    </>,
    theme: (
      <>
        {toggle("dark", "Dark mode")}
        <div className="setting-row color-row">
          <span>Color</span>
          <div>
            {colors.map((c, i) => (
              <button
                key={c}
                aria-label={`Accent color ${i + 1}`}
                aria-pressed={
                  (prefs.dark ? prefs.darkAccent : prefs.accent) === i
                }
                style={{ background: c }}
                className={
                  (prefs.dark ? prefs.darkAccent : prefs.accent) === i
                    ? "chosen"
                    : ""
                }
                onClick={() => pref(prefs.dark ? "darkAccent" : "accent", i)}
              />
            ))}
          </div>
        </div>
        {slider(prefs.dark ? "darkContrast" : "contrast", "Contrast", {
          min: -1,
          max: 1,
          step: 0.05,
          format: (v) => v.toFixed(2),
        })}
        {slider("opacity", "Opacity", { min: 30, max: 100 })}
      </>
    ),
    appearance: (
      <>
        <DisplayBrightness action={action}/>
        {radio("timeFormat", "Time format", ["24h", "12h"])}
        {toggle("showClock", "Show clock")}
        {slider("barHeight", "Bottom bar height", { min: 65, max: 100 })}
        <button className="layout-reset" onClick={() => updateLayout(() => ({}))}>Restore default layout</button>
      </>
    ),
    application: (
      <>
        {toggle("hotspot", "Enable hotspot")}
        {toggle("showCursor", "Show cursor")}
      </>
    ),
    "notification-settings": (
      <>
        {toggle("outputNotice", "Output volume level")}
        {toggle("inputNotice", "Input volume level")}
        {toggle("nowPlayingNotice", "Now playing")}
        {slider("notificationDuration", "Notification duration", {
          min: 1,
          max: 15,
        })}
        {slider("toastDuration", "Toast duration", { min: 1, max: 15 })}
      </>
    ),
    overlays: (
      <>
        {radio("navigationOverlay", "Navigation", [
          "None",
          "Always",
          "Projection",
          "UI",
        ])}
        {radio("volumeOverlay", "Volume", [
          "None",
          "Always",
          "Projection",
          "UI",
        ])}
        {slider("xStep", "X step", { min: 1, max: 20 })}
        {slider("yStep", "Y step", { min: 1, max: 20 })}
        <button
          className="setting-row link-row"
          onClick={() => go("custom-overlays")}
        >
          Custom overlays visibility
          <Icon name="chevron_right" />
        </button>
      </>
    ),
    "android-settings": (
      <>
        <DisplayBrightness action={action}/>
        <WirelessSettings action={action} standalone={status.projection?.renderer === 'standalone'}/>
        <PhoneReconnect action={action}/>
        {toggle("androidAutostart", "Open Android Auto automatically")}
        {toggle("androidTaskbar", "Keep taskbar visible")}
        <p className="setting-note">
          Music and navigation update every {prefs.musicRefreshSeconds} seconds, even when automatic
          opening is off.
          {status.projection?.enabled
            ? " Layout changes reconnect Android Auto. The dashboard stays running."
            : " Live projection settings are available on the Pi."}
        </p>
        {status.projection?.layoutPending && (
          <button
            className="setting-row link-row"
            onClick={() => action("projection-layout-apply")}
          >
            Apply projection layout
            <Icon name="restart_alt" />
          </button>
        )}
        {radio("androidDayNight", "Day/Night", ["Common", "Day", "Night"])}
      </>
    ),
    "autobox-settings": (
      <>
        {toggle("autoboxWireless", "Wireless autoconnect")}
        {radio("autoboxDayNight", "Day/Night", ["Common", "Day", "Night"])}
        <button
          className="setting-row link-row"
          onClick={() => go("autobox-device")}
        >
          About device
          <Icon name="chevron_right" />
        </button>
      </>
    ),
    sound: (
      <>
        <RadioOutput action={action} connections={()=>go('bluetooth-connections')}/>
        {toggle("mute", "Mute output")}
        {slider("volume", "Output volume")}
        {toggle("muteInput", "Mute input")}
        {slider("inputVolume", "Input volume")}
        {slider("balance", "Balance", { min: -100, max: 100 })}
        {slider("fade", "Fade", { min: -100, max: 100 })}
        {slider("subwoofer", "Subwoofer", { min: -100, max: 100 })}
      </>
    ),
    "obd-settings": <OBDSettings action={action} status={status} demo={prefs.demo} demoControl={toggle("demo", "Demo telemetry")}/>,
  };
  const selectedAccent = prefs.dark ? prefs.darkAccent : prefs.accent;
  const {liveMedia, shownMedia, playerMedia} = resolveMedia(media, projectionData.media, screen);
  const navigation = projectionData.navigation || {};
  const palette = useMemo(
    () => themePalette(prefs.dark, selectedAccent),
    [prefs.dark, selectedAccent],
  );
  const unit = Math.max(
    0.55,
    Math.min(
      viewport.width / 1280,
      viewport.height / (TASKBAR ? 81 : CONTENT ? 639 : 720),
    ),
  );
  const barHeight = CONTENT
    ? 0
    : TASKBAR
      ? viewport.height
      : Math.max(56, prefs.barHeight * unit);
  return (
    <div className="viewport" ref={viewportRef}>
      <main
        className={`app-canvas ${prefs.dark ? "dark" : ""} ${TASKBAR ? "host-taskbar" : CONTENT ? "host-content" : ""}`}
        style={{
          "--unit": `${unit}px`,
          "--x": `${viewport.width / 1280}px`,
          "--y": `${Math.max(1, viewport.height - barHeight) / 639}px`,
          "--bar-height": `${barHeight}px`,
          "--ui-opacity": prefs.opacity / 100,
          "--ui-contrast":
            1 + (prefs.dark ? prefs.darkContrast - 1 : prefs.contrast) * 0.25,
          ...palette,
        }}
        aria-label="Car dashboard"
      >
        <audio
          ref={audio}
          onLoadedMetadata={() =>
            setMedia((m) => ({ ...m, duration: audio.current.duration || 0 }))
          }
          onTimeUpdate={() =>
            setMedia((m) => ({ ...m, time: audio.current.currentTime }))
          }
          onPlay={() => setMedia((m) => ({ ...m, playing: true }))}
          onPause={() => setMedia((m) => ({ ...m, playing: false }))}
          onEnded={() => {
            if (repeat) {
              audio.current.currentTime = 0;
              audio.current.play();
            } else stepTrack(1, true);
          }}
        />
        <input
          className="file-input"
          ref={fileInput}
          type="file"
          accept="audio/*"
          multiple
          onChange={loadFiles}
        />
        <section className={`screen screen-${screen}`}>
          {screen === "dashboard" && (
            <div className="dashboard-grid">
              <div className="dashboard-left" style={{ order: layout.columns.indexOf('clock-navigation') }}>
                <div className="card clock-card" role="group" aria-label="Clock card" tabIndex={0} style={{ order: layout.leftCards.indexOf('clock') }} {...customizationAttributes('card', 'clock', undefined, 'dashboard')}>
                  <div>
                    <Icon name="schedule" size={32} />
                    <span>{time}</span>
                  </div>
                  <p>
                    {now.toLocaleDateString("en-GB", { weekday: "long" })},
                    <br />
                    {now.getDate()}{" "}
                    {now.toLocaleDateString("en-GB", {
                      month: "long",
                      year: "numeric",
                    })}
                  </p>
                </div>
                <button
                  className="card navigation-card"
                  aria-label="Navigation card"
                  style={{ order: layout.leftCards.indexOf('navigation') }}
                  {...customizationAttributes('card', 'navigation', undefined, 'android-resume')}
                  onClick={() =>
                    navigation.active
                      ? action("projection", { operation: "resume" })
                      : tell(
                          "Waiting for navigation data from a connected phone",
                        )
                  }
                >
                  <Icon
                    name={
                      navigation.side === 1
                        ? "turn_left"
                        : navigation.side === 2
                          ? "turn_right"
                          : "navigation"
                    }
                  />
                  {navigation.active ? (
                    <span>
                      {navigation.description || "Navigation active"}
                      <br />
                      {navigation.distance || ""}
                    </span>
                  ) : (
                    <span>
                      Waiting for
                      <br />
                      destination
                    </span>
                  )}
                </button>
              </div>
              <div className="card media-card" role="group" aria-label="Music card" tabIndex={0} style={{ order: layout.columns.indexOf('music') }} {...customizationAttributes('card', 'music', undefined, shownMedia.source)}>
                <button
                  className="album-tile"
                  aria-label="Open music player"
                  onClick={() => open(shownMedia.source)}
                >
                  {liveMedia && shownMedia.coverart ? (
                    <img
                      alt="Album cover"
                      src={`/api/projection/coverart?v=${shownMedia.coverartVersion}`}
                    />
                  ) : (
                    <Icon name="music_note" size={84} />
                  )}
                </button>
                <div className="dashboard-track">
                  <span>{shownMedia.title || "-"}</span>
                  <span>{shownMedia.artist || "-"}</span>
                  <span>{shownMedia.album || "-"}</span>
                </div>
                <div className="dashboard-duration">
                  {shownMedia.timeKnown === false ? "—" : fmt(shownMedia.time)}/{shownMedia.durationKnown === false ? "—" : fmt(shownMedia.duration)}
                </div>
                <div className="dashboard-playback">
                  <IconButton
                    icon="skip_previous"
                    label="Previous track"
                    shortcutId="media-previous"
                    onClick={() => stepTrack(-1)}
                  />
                  <IconButton
                    icon={shownMedia.playing ? "pause" : "play_arrow"}
                    className="play-circle"
                    label={shownMedia.playing ? "Pause" : "Play"}
                    shortcutId="media-toggle"
                    onClick={play}
                  />
                  <IconButton
                    icon="skip_next"
                    label="Next track"
                    shortcutId="media-next"
                    onClick={() => stepTrack(1)}
                  />
                </div>
              </div>
              <div className="card phone-card" role="group" aria-label="Phone card" tabIndex={0} style={{ order: layout.columns.indexOf('phone') }} {...customizationAttributes('card', 'phone', undefined, 'contacts')}>
                <div className="phone-title">
                  <span>{status.phone?.name || phonebookData.name || ""}</span>
                  <Icon name="bluetooth" size={42} />
                </div>
                <div className="phone-shortcuts">
                  {[
                    ["contacts", "contacts"],
                    ["star", "favorites"],
                    ["dialpad", "dialpad"],
                    ["history", "call-log"],
                  ].map(([i, id]) => (
                    <IconButton
                      key={id}
                      icon={i}
                      label={id}
                      shortcutId={id}
                      onClick={() => go(id)}
                    />
                  ))}
                </div>
              </div>
            </div>
          )}
          {["apps", "settings"].includes(screen) && (
            <>
              <IconButton
                className="back-button"
                icon="arrow_back"
                label="Back"
                onClick={back}
                size={42}
              />
              <div className="sidebar">
                {(screen === "apps" ? appCategories : settingCategories).map(
                  ([label, icon]) => (
                    <button
                      key={label}
                      className={
                        (screen === "apps" ? category : settingCategory) ===
                        label
                          ? "selected"
                          : ""
                      }
                      onClick={() =>
                        screen === "apps"
                          ? setCategory(label)
                          : setSettingCategory(label)
                      }
                    >
                      <Icon name={icon} />
                      <span>{label}</span>
                    </button>
                  ),
                )}
              </div>
              <div className="menu-grid">
                {[...menus[screen === "apps" ? category : settingCategory]].sort((a, b) => layout.menus[screen === 'apps' ? category : settingCategory].indexOf(a[2]) - layout.menus[screen === 'apps' ? category : settingCategory].indexOf(b[2])).map(
                  ([label, icon, id]) => (
                    <Tile
                      key={id}
                      label={label}
                      icon={icon}
                      id={id}
                      group={screen === 'apps' ? category : settingCategory}
                      onClick={() => open(id)}
                    />
                  ),
                )}
              </div>
            </>
          )}
          {screen !== "dashboard" &&
            !["apps", "settings"].includes(screen) &&
            ![
              "obd-charts",
              "obd-blocks",
              "combined",
              "gauges",
              "gauges-2",
            ].includes(screen) && (
              <IconButton
                className="back-button"
                icon={screen in mediaTitles ? "close" : "arrow_back"}
                label="Back"
                onClick={back}
                size={42}
              />
            )}
          {settings[screen] && (
            <>
              <div
                className={`settings-scroll settings-${screen}`}
                ref={scroll}
              >
                {settings[screen]}
              </div>
              <div className="scroll-buttons">
                <IconButton
                  icon="expand_less"
                  label="Scroll up"
                  onClick={() =>
                    scroll.current?.scrollBy({ top: -350, behavior: "smooth" })
                  }
                />
                <IconButton
                  icon="expand_more"
                  label="Scroll down"
                  onClick={() =>
                    scroll.current?.scrollBy({ top: 350, behavior: "smooth" })
                  }
                />
              </div>
            </>
          )}
          {["contacts", "favorites", "call-log"].includes(screen) && (
            <PhonebookView view={screen} data={phonebookData}
              settings={() => go('contacts-settings')}
              refresh={() => action('phone-refresh', { view: screen })}
              select={number => { setDigits(number); go('dialpad'); }} />
          )}
          {["dialpad", "active-call"].includes(screen) && (
            <>
              <div className="dialpad">
                {"123456789*0#".split("").map((d) => (
                  <button
                    key={d}
                    aria-label={`Dial ${d}`}
                    onClick={() =>
                      setDigits((v) => (v.length < 32 ? v + d : v))
                    }
                  >
                    {d}
                  </button>
                ))}
              </div>
              <div className="dial-number">{screen === 'active-call'
                ? (status.phone?.call?.name || status.phone?.call?.number || 'No active call') : digits}</div>
              {screen === "dialpad" ? (
                <>
                  <IconButton
                    icon="backspace"
                    className="dial-delete"
                    label="Delete digit"
                    size={64}
                    onClick={() => setDigits((v) => v.slice(0, -1))}
                  />
                  <CallButton number={digits} available={status.capabilities?.phone} action={action} onAccepted={()=>go('active-call')}/>
                </>
              ) : (
                <>
                  {status.phone?.call?.status==='incoming' && <IconButton icon="call" className="dial-call" label="Answer call" size={80}
                    disabled={!status.capabilities?.phone} onClick={()=>action('phone-answer')}/>}
                  <IconButton
                    className="call-microphone"
                    icon={status.phone?.microphoneMuted ? "mic_off" : "mic"}
                    label="Toggle microphone"
                    size={72}
                    disabled={!status.capabilities?.phone || status.phone?.call?.status!=='active' || typeof status.phone?.microphoneMuted!=='boolean'}
                    onClick={() => action('phone-microphone',{muted:!status.phone.microphoneMuted})}
                  />
                  <IconButton
                    className="call-hangup"
                    icon="call_end"
                    label="End call"
                    size={80}
                    disabled={!status.capabilities?.phone || status.phone?.call?.count!==1}
                    onClick={() => action("phone-end")}
                  />
                </>
              )}
            </>
          )}
          {screen in mediaTitles && (
            <>
              <div className="player-title">
                <Icon name={mediaIcons[screen]} />
                {mediaTitles[screen]}
                <IconButton icon="settings" label="Music settings" onClick={() => go('music-settings')} size={32} />
              </div>
              <div className="player-art">
                {isRemotePlayer(screen) &&
                liveMedia &&
                shownMedia.coverart ? (
                  <img
                    alt="Album cover"
                    src={`/api/projection/coverart?v=${shownMedia.coverartVersion}`}
                  />
                ) : (
                  <Icon name={mediaIcons[screen]} size={120} />
                )}
              </div>
              <div className="player-info">
                <div>
                  {screen === "radio"
                    ? `${frequency.toFixed(2)} MHz`
                    : screen === "storage"
                      ? media.title || "notification_sound"
                      : screen === "android-music"
                        ? shownMedia.title ||
                          "Android Auto is not providing track data"
                        : screen === "a2dp"
                          ? shownMedia.title || "Not Provided"
                          : ""}
                </div>
                {isRemotePlayer(screen) && (
                  <p className="projection-track-detail">
                    {shownMedia.artist || ""}
                    {shownMedia.album ? ` · ${shownMedia.album}` : ""}
                  </p>
                )}
                {screen === "radio" ? (
                  <>
                    <p>FM Radio</p>
                    <IconButton
                      icon="heart_plus"
                      label="Save station"
                      onClick={() => {
                        let saved = [];
                        try {
                          saved = JSON.parse(
                            localStorage.getItem("hudiy.stations") || "[]",
                          );
                          localStorage.setItem(
                            "hudiy.stations",
                            JSON.stringify([...new Set([...saved, frequency])]),
                          );
                        } catch {}
                        tell("Station saved");
                      }}
                    />
                  </>
                ) : (
                  <div className="player-progress">
                    <input
                      aria-label="Track position"
                      type="range"
                      min="0"
                      max={playerMedia.duration || 1}
                      step=".1"
                      value={playerMedia.time}
                      disabled={isRemotePlayer(screen)}
                      onChange={(e) => {
                        if (audio.current.duration)
                          audio.current.currentTime = Number(e.target.value);
                      }}
                    />
                    <div>
                      <span>{fmt(playerMedia.time)}</span>
                      <span>{playerMedia.durationKnown === false ? "—" : fmt(playerMedia.duration)}</span>
                    </div>
                  </div>
                )}
              </div>
              <div
                className={`player-controls ${screen === "storage" ? "storage-controls" : screen === "radio" ? "radio-controls" : "simple-controls"}`}
              >
                {screen === "storage" && (
                  <>
                    <IconButton
                      icon="folder_open"
                      label="Open audio files"
                      onClick={() => fileInput.current.click()}
                      size={64}
                    />
                    <IconButton
                      icon="queue_music"
                      label="Playlist"
                      onClick={() => go("playlist")}
                      size={64}
                    />
                  </>
                )}
                {screen === "radio" && (
                  <>
                    <IconButton
                      icon="playlist_add_check"
                      label="Saved stations"
                      onClick={() => go("stations")}
                      size={64}
                    />
                    <IconButton
                      icon="fast_rewind"
                      label="Seek down"
                      onClick={() =>
                        setFrequency((v) => Math.max(87.5, v - 0.5))
                      }
                      size={64}
                    />
                    <IconButton
                      icon="chevron_left"
                      label="Tune down"
                      onClick={() =>
                        setFrequency((v) => Math.max(87.5, v - 0.05))
                      }
                      size={64}
                    />
                  </>
                )}
                <IconButton
                  icon="skip_previous"
                  label="Previous"
                  onClick={() => stepTrack(-1)}
                  size={64}
                />
                <IconButton
                  className="play-circle"
                  icon={playerMedia.playing ? "pause" : "play_arrow"}
                  label={playerMedia.playing ? "Pause" : "Play"}
                  onClick={play}
                  size={64}
                />
                <IconButton
                  icon="skip_next"
                  label="Next"
                  onClick={() => stepTrack(1)}
                  size={64}
                />
                {screen === "storage" && (
                  <>
                    <IconButton
                      className={shuffle ? "active-icon" : ""}
                      icon="shuffle"
                      label="Shuffle"
                      onClick={() => setShuffle((v) => !v)}
                      size={64}
                    />
                    <IconButton
                      className={repeat ? "active-icon" : ""}
                      icon="repeat"
                      label="Repeat"
                      onClick={() => setRepeat((v) => !v)}
                      size={64}
                    />
                  </>
                )}
                {screen === "radio" && (
                  <>
                    <IconButton
                      icon="chevron_right"
                      label="Tune up"
                      onClick={() =>
                        setFrequency((v) => Math.min(108, v + 0.05))
                      }
                      size={64}
                    />
                    <IconButton
                      icon="fast_forward"
                      label="Seek up"
                      onClick={() =>
                        setFrequency((v) => Math.min(108, v + 0.5))
                      }
                      size={64}
                    />
                  </>
                )}
              </div>
            </>
          )}
          {screen === "playlist" && (
            <div className="list-page">
              {files.length ? (
                files.map((f, i) => (
                  <button
                    key={f.url}
                    onClick={() => {
                      selectFile(i);
                      back();
                    }}
                  >
                    <Icon name="audio_file" />
                    {f.name}
                  </button>
                ))
              ) : (
                <Tile
                  label="Open audio files"
                  icon="folder_open"
                  onClick={() => fileInput.current.click()}
                />
              )}
            </div>
          )}
          {screen === "stations" && (
            <StationList
              onSelect={(v) => {
                setFrequency(v);
                back();
              }}
            />
          )}
          {screen === "equalizer" && (
            <div className="equalizer">
              {frequencies.map((hz, i) => (
                <div className="eq-band" key={hz}>
                  <IconButton
                    icon="arrow_drop_up"
                    label={`Increase ${hz}`}
                    onClick={() =>
                      pref(
                        "equalizer",
                        prefs.equalizer.map((v, j) =>
                          j === i ? Math.min(12, v + 1) : v,
                        ),
                      )
                    }
                  />
                  <input
                    type="range"
                    aria-label={`${hz} ${i < 8 ? "Hz" : "KHz"}`}
                    min="-12"
                    max="12"
                    step=".25"
                    value={prefs.equalizer[i]}
                    onChange={(e) =>
                      pref(
                        "equalizer",
                        prefs.equalizer.map((v, j) =>
                          j === i ? Number(e.target.value) : v,
                        ),
                      )
                    }
                  />
                  <output>{prefs.equalizer[i].toFixed(2)}</output>
                  <span>
                    {hz}
                    <br />
                    {i < 8 ? "Hz" : "KHz"}
                  </span>
                  <IconButton
                    icon="arrow_drop_down"
                    label={`Decrease ${hz}`}
                    onClick={() =>
                      pref(
                        "equalizer",
                        prefs.equalizer.map((v, j) =>
                          j === i ? Math.max(-12, v - 1) : v,
                        ),
                      )
                    }
                  />
                </div>
              ))}
            </div>
          )}
          {screen === "presets" && (
            <div className="preset-screen">
              <div className="preset-list">
                {[
                  "Flat",
                  "Pop",
                  "Rock",
                  "Jazz",
                  "Classical",
                  "Bass boost",
                  "Voice",
                ].map((p) => (
                  <button
                    key={p}
                    onClick={() => {
                      saveAudio({preset:p,equalizer:[...audioPresets[p]]});
                      tell(`${p} preset selected`);
                    }}
                  >
                    <Icon name="graphic_eq" size={60} />
                    {p}
                  </button>
                ))}
              </div>
              <div className="preset-preview">
                <div className="eq-preview">
                  {prefs.equalizer.map((v, i) => (
                    <span
                      key={i}
                      style={{ height: `calc(${118 + v * 8} * var(--unit))` }}
                    />
                  ))}
                </div>
                <Tile
                  label="Restore"
                  icon="restart_alt"
                  onClick={() => {
                    saveAudio({equalizer:Array(15).fill(0),preset:'Flat'});
                  }}
                />
              </div>
            </div>
          )}
          {screen === "about" && (
            <div className="about">
              <h1>Hudiy recreation</h1>
              <p>Independent dashboard based on observed Hudiy 1.24 screens.</p>
              <p>
                Original project:{" "}
                <a href="https://hudiy.eu" target="_blank" rel="noreferrer">
                  www.hudiy.eu
                </a>
              </p>
              <p>Version 0.1 · Raspberry Pi touchscreen</p>
            </div>
          )}
          {["pair", "remove", "bluetooth-connections"].includes(screen) && <BluetoothView mode={screen} action={action} />}
          {screen === "autobox-device" && (
            <div className="about">
              <h1>Autobox</h1>
              <p>No CarlinKit adapter connected.</p>
            </div>
          )}
          {screen === "active-apps" && (
            <div className="empty-message">
              No background applications active.
            </div>
          )}
          {[
            "obd-charts",
            "obd-blocks",
            "combined",
            "gauges",
            "gauges-2",
          ].includes(screen) && (
            <Telemetry
              screen={screen}
              telemetry={status.obd}
              demo={prefs.demo}
              now={now}
              palette={palette}
              onSettings={() => go("obd-settings")}
            />
          )}
          {screen === "marketplace" && <Marketplace tell={tell} />}
        </section>
        <footer className="bottom-bar">
          <div className="taskbar-items" aria-label="Taskbar shortcuts">
            {layout.taskbar.filter(id => id !== 'clock' || prefs.showClock).map((id, index, items) => {
              const meta = SHORTCUTS[id];
              const attrs = customizationAttributes('taskbar', id);
              const spacer = id === 'android-resume' && index === items.length - (prefs.showClock && items.includes('clock') ? 3 : 2);
              if (id === 'clock') return <button key={id} className="bar-clock" aria-label="Clock" onClick={home} {...attrs}>{time}</button>;
              if (id === 'connection-status') return <button key={id} className="status-container" aria-label={meta.label} onClick={() => activateShortcut(id)} {...attrs}>
                <Icon name={status.phone?.connected ? 'bluetooth_connected' : 'bluetooth_disabled'} size={24} />
                <Icon name={status.phone?.levels?.signal !== undefined ? `signal_cellular_${Math.round(status.phone.levels.signal / 25)}_bar` : 'signal_cellular_off'} size={24} />
                <Icon name={status.phone?.levels?.battery !== undefined ? `battery_${Math.round(status.phone.levels.battery * 6 / 5)}_bar` : 'battery_unknown'} size={24} />
              </button>;
              return <div className={`taskbar-item ${spacer ? 'taskbar-spacer' : ''}`} key={id}>
                <IconButton icon={id === 'mute' ? (prefs.mute ? 'volume_off' : 'volume_mute') : meta.icon}
                  label={id === 'android-resume' && status.projection?.visible ? 'Android Auto active' : meta.label}
                  className={id === 'android-resume' && status.projection?.visible ? 'projection-active' : ''}
                  shortcutId={id} layoutKind="taskbar" size={id === 'android-resume' ? 32 : 38} onClick={() => activateShortcut(id)} />
              </div>;
            })}
          </div>
          {TASKBAR && customize && <CustomizeMenu item={customize} layout={layout} close={() => setCustomize(null)}
            inline move={moveCustomized} remove={id => { if (!REQUIRED_SHORTCUTS.includes(id)) updateLayout(current => ({ ...current, taskbar: current.taskbar.filter(item => item !== id) })); setCustomize(null); }} />}
        </footer>
        {!TASKBAR && customize && <CustomizeMenu item={customize} layout={layout} close={() => setCustomize(null)}
          pin={id => { updateLayout(current => pinShortcut(current, id)); setCustomize(null); }}
          move={moveCustomized} remove={id => { if (!REQUIRED_SHORTCUTS.includes(id)) updateLayout(current => ({ ...current, taskbar: current.taskbar.filter(item => item !== id) })); setCustomize(null); }} />}
        {notice && (
          <div className="toast" role="status">
            {notice.message}
          </div>
        )}
      </main>
    </div>
  );
}
function Marketplace({ tell }) {
  const [category, setCategory] = useState("All");
  const [query, setQuery] = useState("");
  return (
    <div className="marketplace">
      <header>
        <small>✦ HUDIY SETTINGS</small>
        <h1>Hudiy Marketplace</h1>
        <p>Community extensions for your Hudiy dashboard.</p>
        <div className="market-actions">
          <span>No catalog connected</span>
          <button onClick={() => tell("No community catalog is configured.")}>
            Refresh marketplace
          </button>
          <button
            onClick={() =>
              tell("Plugin submission requires a connected catalog.")
            }
          >
            Submit plugin
          </button>
        </div>
      </header>
      <div className="market-banner">
        <Icon name="apps" />
        <div>
          <strong>Opened in Hudiy</strong>
          <p>Marketplace view within the normal settings</p>
        </div>
        <span>Community-made · unverified</span>
      </div>
      <div className="market-filters">
        <input
          aria-label="Search extensions"
          placeholder="Search by name, type, author or description"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <div>
          {["All", "Apps", "Widgets", "Overlays", "Dashboards"].map((value) => (
            <button
              key={value}
              className={category === value ? "selected" : ""}
              onClick={() => setCategory(value)}
            >
              {value}
            </button>
          ))}
          <label>
            Sort{" "}
            <select aria-label="Sort extensions">
              <option>Popularity</option>
              <option>Name</option>
              <option>Newest</option>
            </select>
          </label>
        </div>
      </div>
      <div className="market-warning">
        <strong>Community content is unverified.</strong>
        <p>
          No security, virus or functionality guarantee. Review permissions and
          source before installing.
        </p>
      </div>
      <h2>Community catalog</h2>
      <p>Available extensions will be listed here.</p>
      <div className="market-empty">No catalog connected.</div>
    </div>
  );
}
function StationList({ onSelect }) {
  let saved = [];
  try {
    saved = JSON.parse(localStorage.getItem("hudiy.stations") || "[]");
  } catch {}
  return (
    <div className="list-page">
      {saved.length ? (
        saved.map((v) => (
          <button key={v} onClick={() => onSelect(v)}>
            <Icon name="cell_tower" />
            {Number(v).toFixed(2)} MHz
          </button>
        ))
      ) : (
        <p>No saved stations</p>
      )}
    </div>
  );
}
