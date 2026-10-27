// Audio output is distinct from a phone audio source and a serial OBD adapter.
export function canUseBluetoothAudio(device) {
  return device?.paired === true && device?.audioReceiver === true;
}
export async function useBluetoothAudio(device, action) {
  if (!canUseBluetoothAudio(device))
    throw Error("Choose a paired audio output device.");
  const saved = await action(
    "audio-radio-output",
    { address: device.address },
    { quiet: true },
  );
  if (!saved?.saved)
    return {
      saved: false,
      message:
        "Audio device could not be selected. Check the connection and try again after any call ends.",
    };
  if (!device.connected) {
    const connection = await action(
      "bluetooth-connect",
      { address: device.address },
      { quiet: true },
    );
    if (!connection?.accepted)
      return {
        saved: true,
        message:
          "Audio device selected, but connection failed. Use Connect to retry.",
      };
  }
  return {
    saved: true,
    message:
      "Audio device selected.",
  };
}
