// Coalesces rapid changes (for example equalizer slider drags) into at most one
// request in flight plus one merged pending value. The newest value is always
// sent last; intermediate values that were superseded while waiting are skipped.
export function createLatestQueue(merge = (a, b) => ({ ...a, ...b })) {
  let pending = null,
    sender = null,
    running = null;
  async function drain() {
    try {
      while (pending !== null) {
        const value = pending;
        pending = null;
        try {
          await sender(value);
        } catch {}
      }
    } finally {
      running = null;
    }
  }
  return {
    get busy() {
      return running !== null;
    },
    get pending() {
      return pending !== null;
    },
    push(value, send) {
      pending = pending === null ? value : merge(pending, value);
      sender = send;
      if (running === null) running = drain();
      return running;
    },
  };
}
