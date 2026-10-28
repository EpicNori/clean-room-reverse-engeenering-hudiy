import React from "react";
import { customizationAttributes } from "./layout";

export const ORIGINAL_WIDGET_TYPES = ["clock", "navigation", "music", "phone"];
function CardIcon({ name, size = 48 }) {
  return (
    <span
      className="material-symbols-rounded icon"
      aria-hidden="true"
      style={{ fontSize: `calc(${size} * var(--unit))` }}
    >
      {name}
    </span>
  );
}
function CardButton({
  icon,
  label,
  onClick,
  className = "",
  shortcutId,
  pinActions = false,
}) {
  return (
    <button
      className={`icon-button ${className}`}
      aria-label={label}
      title={label}
      onClick={onClick}
      {...(pinActions && shortcutId
        ? customizationAttributes("shortcut", shortcutId)
        : {})}
    >
      <CardIcon name={icon} />
    </button>
  );
}
const timeText = (n) =>
  `${String(Math.floor((Number.isFinite(n) ? n : 0) / 60)).padStart(2, "0")}:${String(Math.floor((Number.isFinite(n) ? n : 0) % 60)).padStart(2, "0")}`;
export function ClockCardContent({ time, now }) {
  return (
    <>
      <div>
        <CardIcon name="schedule" size={32} />
        <span>{time}</span>
      </div>
      <p>
        {now.toLocaleDateString("en-GB", { weekday: "long" })},<br />
        {now.getDate()}{" "}
        {now.toLocaleDateString("en-GB", { month: "long", year: "numeric" })}
      </p>
    </>
  );
}
export function NavigationCardContent({ navigation = {} }) {
  return (
    <>
      <CardIcon
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
    </>
  );
}
export function MusicCardContent({
  media = {},
  liveMedia,
  onOpen,
  onPrevious,
  onPlay,
  onNext,
  pinActions = false,
}) {
  return (
    <>
      <button
        className="album-tile"
        aria-label="Open music player"
        onClick={onOpen}
      >
        {liveMedia && media.coverart ? (
          <img
            alt="Album cover"
            src={`/api/projection/coverart?v=${media.coverartVersion}`}
          />
        ) : (
          <CardIcon name="music_note" size={84} />
        )}
      </button>
      <div className="dashboard-track">
        <span>{media.title || "-"}</span>
        <span>{media.artist || "-"}</span>
        <span>{media.album || "-"}</span>
      </div>
      <div className="dashboard-duration">
        {media.timeKnown === false ? "—" : timeText(media.time)}/
        {media.durationKnown === false ? "—" : timeText(media.duration)}
      </div>
      <div className="dashboard-playback">
        <CardButton
          icon="skip_previous"
          label="Previous track"
          shortcutId="media-previous"
          onClick={onPrevious}
          pinActions={pinActions}
        />
        <CardButton
          icon={media.playing ? "pause" : "play_arrow"}
          className="play-circle"
          label={media.playing ? "Pause" : "Play"}
          shortcutId="media-toggle"
          onClick={onPlay}
          pinActions={pinActions}
        />
        <CardButton
          icon="skip_next"
          label="Next track"
          shortcutId="media-next"
          onClick={onNext}
          pinActions={pinActions}
        />
      </div>
    </>
  );
}
export function PhoneCardContent({ name = "", onGo, pinActions = false }) {
  return (
    <>
      <div className="phone-title">
        <span>{name}</span>
        <CardIcon name="bluetooth" size={42} />
      </div>
      <div className="phone-shortcuts">
        {[
          ["contacts", "contacts"],
          ["star", "favorites"],
          ["dialpad", "dialpad"],
          ["history", "call-log"],
        ].map(([icon, id]) => (
          <CardButton
            key={id}
            icon={icon}
            label={id}
            shortcutId={id}
            onClick={() => onGo(id)}
            pinActions={pinActions}
          />
        ))}
      </div>
    </>
  );
}
