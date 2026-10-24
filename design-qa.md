# Notifications visual QA — 10 October 2026

Scope: the existing Notifications settings and local web popups. Source: original Hudiy capture 012 (1280×720, light purple/pink, three switches on, notification duration 8), supplemented by captures 089/090 for the lower duration setting. Rendered target: localhost4173, fresh captures in the private notification-audit archive. Raw captures remain excluded from publication.

## Findings and iterations

1. P1 behavior: Output volume level off still produced a Volume popup (fresh capture 02). Fixed with independently gated notice kinds; capture 03 shows the off state without the popup. Timer/gating tests pass.
2. P2 theme: popup colors were fixed peach/brown. They now use active/primary-text tokens. Fresh captures 04/05 show red and amber accents. All native colors are validated hex RGB; native visual acceptance is separate.
3. P2 fidelity: the light reference comparison (source 012 and fresh capture 06 in the same comparison input) showed a shortened slider and undersized arrows. Scoped landscape spacing/arrow corrections align the track, value and toggle content. Source 012 and post-fix capture 07 were compared together again at the same viewport/state/theme.
4. P2 compact targets: switches were shorter than 48px. Capture 09 and DOM measurements establish 64×48px switches at 320×568; page scrollWidth equals 320. Pointer drag moved settings scrollTop to 48 with no selected text. Physical touchscreen input remains pending.

## Fidelity surfaces

- Typography: existing locally bundled Roboto 400, original 40 scaled-pixel row labels and 34 scaled-pixel values preserved; Material Symbols arrows follow measured sizing.
- Spacing: original 128px toggle rows and 187px slider rows retained. Landscape toggle baseline/right inset and slider widths now follow the reference more closely; compact styles stay independent.
- Colors: light purple/pink compared in the matching source state; dark red and amber popups inspected separately. All changed surfaces use existing tokens.
- Imagery: this screen has no raster assets. Actual controls and library icons are rendered from code; no reference screenshot is embedded into the app.
- Copy: original labels/order/duration remain. Input popups explicitly describe a saved setting, avoiding a claim that microphone gain works. Toast duration is reachable by scrolling.

## Limits and P3 notes

The reference taskbar has fewer shortcuts and a different clock; our persisted owner layout intentionally keeps its extra shortcuts. Font rasterization, divider length and small glyph/baseline differences remain P3 follow-up polish. No physical touch, assistive-technology, native popup rendering or complete screen-by-screen 1:1 acceptance is claimed. The native overlay is implemented but upload/compile/CTest is pending following Pi shutdown.

Local Notifications visual check: passed.

final result: blocked — native overlay compilation/device verification is pending because the Pi powered off before upload.

Implementation checklist: local switches/durations/theme, screenshot comparison, compact target/drag check, frontend regressions, production build and backend schema/security tests completed. Native compilation, CTest and real Android Auto overlay acceptance remain open. Full recreation goal remains open.
