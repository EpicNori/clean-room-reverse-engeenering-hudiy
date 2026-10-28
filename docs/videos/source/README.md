# coscarOS intro video source

`coscaros-intro.html` is a deterministic 1920×1080 scene: `window.seek(t)` draws the
frame at `t` seconds (masked word reveals, tilted glass cards, gold particle swarm,
frame chrome with timecode and chapter progress). `render.cjs` opens it in headless
Edge/Chrome through Playwright, captures every frame at 30 fps and pipes the frames
to ffmpeg.

Every screen in the video is an actual application capture from `../../images/`
(referenced, not copied). Scene texts are in the `CHAPTERS` array of the HTML file;
show only features documented in the main README.

## Re-render

1. Install the render tools and fonts outside the repository:

   ```sh
   mkdir ~/coscaros-video-tools && cd ~/coscaros-video-tools
   npm init -y
   npm install playwright-core ffmpeg-static \
     @fontsource-variable/inter-tight @fontsource/instrument-serif @fontsource-variable/geist-mono
   ```

   The fonts (Inter Tight, Instrument Serif, Geist Mono) are SIL OFL licensed;
   `render.cjs` embeds them into the page at render time.

2. From this folder:

   ```sh
   COSCAROS_VIDEO_DEPS=~/coscaros-video-tools node render.cjs
   ```

   PowerShell: `$env:COSCAROS_VIDEO_DEPS="$HOME\coscaros-video-tools"; node render.cjs`

Outputs:

- `docs/videos/coscaros-intro.mp4`: H.264, yuv420p, faststart, no audio.
- `docs/images/coscaros-intro-poster.jpg`: title frame without a play symbol.
- `docs/images/coscaros-intro-poster-play.jpg`: title frame with a gold play button
  and the video length, for linking from the README.

Options: `--out <mp4>`, `--poster <jpg>`, `--poster-play <jpg>`, `--poster-time <s>`
(default 3.9), `--poster-only`, `--crf <n>` (default 27, about 7.6 MB), `--fps <n>` (default 30),
`--stills 5,12.5` (review PNGs next to `--out`), `--until <s>` (partial test render). Set `CHROME_PATH` for a browser
outside the default locations, or `FFMPEG_PATH` for your own ffmpeg.
