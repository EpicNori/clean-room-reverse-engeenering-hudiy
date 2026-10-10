"""Merge addressed Bluetooth player metadata without retaining unrelated art."""
def with_bluetooth_media(data, bluetooth):
    native = data.get('media', {})
    if native.get('source') == 'android' or not bluetooth:
        return data
    same_track = native.get('source') == 'bluetooth' and all(
        native.get(key, '') == bluetooth.get(key, '') for key in ('title', 'artist', 'album'))
    media = {**(native if same_track else {}), **bluetooth}
    return {**data, 'media': media}
