export const bandFrequencies = [
  25, 40, 63, 100, 160, 250, 400, 630, 1000, 1600, 2500, 4000, 6300, 10000,
  16000,
];

const bounded = (value, min, max, fallback = 0) =>
  Number.isFinite(value) ? Math.max(min, Math.min(max, value)) : fallback;

// The same graph is used by local media playback and offline signal verification.
export function createEqualizerGraph(context) {
  const filters = bandFrequencies.map((frequency) => {
    const node = context.createBiquadFilter();
    node.type = "peaking";
    node.frequency.value = Math.min(frequency, context.sampleRate * 0.49);
    node.Q.value = 1.4;
    node.gain.value = 0;
    return node;
  });
  const panner = context.createStereoPanner();
  const gain = context.createGain();
  const limiter = context.createDynamicsCompressor();
  limiter.threshold.value = 0;
  limiter.knee.value = 0;
  limiter.ratio.value = 20;
  limiter.attack.value = 0.001;
  limiter.release.value = 0.05;
  filters
    .reduce((previous, node) => {
      previous.connect(node);
      return node;
    })
    .connect(panner);
  panner.connect(gain);
  gain.connect(limiter);
  limiter.connect(context.destination);
  const set = (parameter, value) => {
    parameter.cancelScheduledValues(context.currentTime);
    parameter.setTargetAtTime(value, context.currentTime, 0.015);
  };
  return {
    input: filters[0],
    update(preferences) {
      filters.forEach((node, index) =>
        set(node.gain, bounded(preferences.equalizer?.[index], -12, 12)),
      );
      set(panner.pan, bounded(preferences.balance, -100, 100) / 100);
      set(
        gain.gain,
        preferences.mute ? 0 : bounded(preferences.volume, 0, 100, 80) / 100,
      );
    },
    disconnect() {
      [...filters, panner, gain, limiter].forEach((node) => node.disconnect());
    },
  };
}

export function createMediaProcessor(element) {
  const Constructor = window.AudioContext || window.webkitAudioContext;
  if (!Constructor) return null;
  const context = new Constructor();
  const graph = createEqualizerGraph(context);
  const source = context.createMediaElementSource(element);
  source.connect(graph.input);
  element.volume = 1;
  return {
    update: graph.update,
    resume: () => context.resume(),
    close: () => {
      source.disconnect();
      graph.disconnect();
      return context.close();
    },
  };
}
