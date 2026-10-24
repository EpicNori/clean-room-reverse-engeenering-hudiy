import React, { useEffect, useRef } from "react";
import Chart from "chart.js/auto";
const definitions = {
  coolant: ["Engine temperature", "°C", -40, 200],
  speed: ["Vehicle speed", "km/h", 0, 255],
  rpm: ["RPM", "1/min", 0, 8000],
  throttle: ["Throttle position", "%", 0, 100],
  load: ["Engine load", "%", 0, 100],
};
export function Gauge({ value, name, variant = 1, palette, definition }) {
  const canvas = useRef(null),
    chart = useRef(null);
  useEffect(() => {
    const [label, unit, min, max] = definition
        ? [definition.label, definition.unit, definition.min, definition.max]
        : definitions[name],
      text = palette["--text"],
      base = palette["--active"],
      primary = palette["--primary"];
    const fraction =
      value == null ? 0 : Math.max(0, Math.min(1, (value - min) / (max - min)));
    const plugin = {
      id: "gaugeLabels",
      afterDraw(c) {
        const ctx = c.ctx,
          arc = c.getDatasetMeta(0).data[0];
        if (!arc) return;
        const scale = Math.max(
          definition ? 0.1 : 0.45,
          Math.min(c.width / (variant === 2 ? 378 : 364), c.height / 350),
        );
        const x = 0,
          y = 0,
          r = arc.outerRadius / scale;
        ctx.save();
        ctx.translate(arc.x, arc.y);
        ctx.scale(scale, scale);
        ctx.fillStyle = text;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        if (variant === 2) {
          for (let i = 0; i <= 60; i++) {
            const a = ((135 + i * 4.5) * Math.PI) / 180;
            ctx.beginPath();
            ctx.strokeStyle = text;
            ctx.lineWidth = i % 10 === 0 ? 4 : 3;
            ctx.moveTo(x + Math.cos(a) * (r - 4), y + Math.sin(a) * (r - 4));
            ctx.lineTo(
              x + Math.cos(a) * (r - (i % 10 === 0 ? 25 : 17)),
              y + Math.sin(a) * (r - (i % 10 === 0 ? 25 : 17)),
            );
            ctx.stroke();
          }
          if (Number.isFinite(value)) {
            const angle = ((135 + fraction * 270) * Math.PI) / 180;
            ctx.beginPath();
            ctx.strokeStyle = primary;
            ctx.lineWidth = 5;
            ctx.moveTo(Math.cos(angle) * (r - 4), Math.sin(angle) * (r - 4));
            ctx.lineTo(Math.cos(angle) * (r - 31), Math.sin(angle) * (r - 31));
            ctx.stroke();
          }
          ctx.font = "bold 32px Roboto";
          const heading = definition
            ? label.toUpperCase().slice(0, 24)
            : name === "coolant"
              ? "COOLANT"
              : name.toUpperCase();
          if (definition)
            ctx.font = `bold ${Math.min(32, 480 / Math.max(heading.length, 1))}px Roboto`;
          const tracking = 3.5;
          const headingWidth =
            [...heading].reduce(
              (width, letter) => width + ctx.measureText(letter).width,
              0,
            ) +
            tracking * (heading.length - 1);
          let headingX = x - headingWidth / 2;
          ctx.textAlign = "left";
          for (const letter of heading) {
            ctx.fillText(letter, headingX, y - 78);
            headingX += ctx.measureText(letter).width + tracking;
          }
          ctx.textAlign = "center";
          ctx.font = definition
            ? `bold ${Math.max(86, 28 / scale)}px Roboto`
            : "bold 86px Roboto";
          ctx.fillText(
            value == null
              ? "—"
              : definition
                ? value.toFixed(definition.decimals || 0)
                : Math.round(value),
            x,
            y + 15,
          );
          ctx.font = definition
            ? `${Math.max(38, 12 / scale)}px Roboto`
            : "38px Roboto";
          ctx.fillText(unit, x, y + 110);
        } else {
          ctx.font = definition
            ? `bold ${Math.max(50, 28 / scale)}px Roboto`
            : "bold 50px Roboto";
          ctx.fillText(
            value == null
              ? "—"
              : definition
                ? value.toFixed(definition.decimals || 0)
                : Math.round(value),
            x,
            y - 39,
          );
          ctx.font = definition
            ? `${Math.max(34, 12 / scale)}px Roboto`
            : "34px Roboto";
          ctx.fillText(
            definition
              ? unit
              : name === "coolant"
                ? "Engine [°C]"
                : name === "speed"
                  ? "km/h"
                  : "RPM",
            x,
            y + 37,
          );
          ctx.font = definition
            ? `bold ${Math.max(34, 10 / scale)}px Roboto`
            : "bold 34px Roboto";
          ctx.fillText(min, x - 95, y + 87);
          ctx.fillText(max, x + 90, y + 87);
          if (Number.isFinite(value)) {
            const angle = ((135 + fraction * 270) * Math.PI) / 180;
            ctx.beginPath();
            ctx.fillStyle = primary;
            ctx.arc(
              Math.cos(angle) * r * 0.955,
              Math.sin(angle) * r * 0.955,
              10,
              0,
              Math.PI * 2,
            );
            ctx.fill();
          }
        }
        ctx.restore();
      },
    };
    chart.current = new Chart(canvas.current, {
      type: "doughnut",
      data: {
        datasets: [
          {
            data: [fraction, 1 - fraction],
            backgroundColor:
              variant === 2 ? ["transparent", "transparent"] : [primary, base],
            borderWidth: 0,
            borderRadius: 10,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        cutout: "91%",
        rotation: 225,
        circumference: 270,
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
      },
      plugins: [plugin],
    });
    let disposed = false;
    document.fonts.ready.then(() => {
      if (!disposed) chart.current?.update("none");
    });
    return () => {
      disposed = true;
      chart.current?.destroy();
    };
  }, [
    value,
    name,
    variant,
    palette,
    definition?.label,
    definition?.unit,
    definition?.min,
    definition?.max,
    definition?.decimals,
  ]);
  return (
    <canvas
      ref={canvas}
      role="img"
      aria-label={`${definition?.label ?? definitions[name]?.[0]}: ${value ?? "unavailable"} ${definition?.unit ?? definitions[name]?.[1]}`}
    />
  );
}
function LinePlot({ history, name, value, palette }) {
  const canvas = useRef(null);
  useEffect(() => {
    const data = history.slice(-60).map((s) => s[name] ?? null);
    const chart = new Chart(canvas.current, {
      type: "line",
      data: {
        labels: data.map((_, i) => i),
        datasets: [
          {
            data,
            borderColor: palette["--primary"],
            borderWidth: 3,
            pointRadius: 0,
            tension: 0.2,
          },
        ],
      },
      options: {
        animation: false,
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
        scales: { x: { display: false }, y: { display: false } },
      },
    });
    return () => chart.destroy();
  }, [history, name, palette]);
  return (
    <canvas
      ref={canvas}
      role="img"
      aria-label={`${definitions[name][0]} history, latest ${value ?? "unavailable"}`}
    />
  );
}
export function Telemetry({
  screen,
  telemetry,
  demo,
  now,
  onSettings,
  onLogs,
  palette,
}) {
  const values = demo
    ? {
        coolant: 89,
        speed: Math.round(48 + Math.sin(now.getTime() / 5000) * 18),
        rpm: Math.round(1800 + Math.sin(now.getTime() / 3000) * 600),
        throttle: 22,
        load: 32,
      }
    : telemetry.values || {};
  const isGauge = screen.startsWith("gauges");
  const keys = isGauge
    ? ["coolant", "speed", "rpm"]
    : screen === "combined"
      ? ["coolant", "speed", "speed", "rpm"]
      : ["coolant", "rpm", "throttle", "speed", "load"];
  return (
    <div
      className={`telemetry ${isGauge ? "gauge-layout" : "wide-layout"} ${screen}`}
    >
      <button className="telemetry-status" onClick={onSettings}>
        {demo
          ? "DEMO"
          : telemetry.connected
            ? "ELM327 connected"
            : "OBD disconnected"}
      </button>
      <button className="telemetry-log-link" onClick={onLogs}>
        Logs
      </button>
      {keys.map((name, i) => {
        const [label, unit, min, max] = definitions[name],
          value = values[name];
        return (
          <div className={`card sensor sensor-${i}`} key={`${name}-${i}`}>
            {isGauge ? (
              <div className="gauge-canvas">
                <Gauge
                  value={value}
                  name={name}
                  variant={screen === "gauges-2" ? 2 : 1}
                  palette={palette}
                />
              </div>
            ) : (
              <>
                <div className="sensor-label">{label}</div>
                {screen === "obd-charts" ||
                (screen === "combined" && i % 2 === 0) ? (
                  <div className="line-sensor">
                    <div>
                      {value ?? "--"}
                      <br />
                      <small>{unit}</small>
                    </div>
                    <LinePlot
                      history={telemetry.history || []}
                      name={name}
                      value={value}
                      palette={palette}
                    />
                  </div>
                ) : (
                  <>
                    <div className="sensor-value">
                      {value ?? "--"} {unit}
                    </div>
                    <div className="sensor-blocks">
                      {Array.from({ length: 24 }, (_, j) => (
                        <span
                          key={j}
                          className={
                            value != null &&
                            j / 24 < (value - min) / (max - min)
                              ? "filled"
                              : ""
                          }
                        />
                      ))}
                    </div>
                  </>
                )}
              </>
            )}
          </div>
        );
      })}
    </div>
  );
}
