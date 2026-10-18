---
name: media-utilities
description: "Small media utility tools: GIF search via Tenor API (curl/jq"
version: 1.0.1
author: agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [GIF, Media, Tenor, Audio, Spectrogram, MFCC, Songsee, Visualization]
    related_skills: [spotify, youtube-content, ascii-video]
---

# Media Utilities

> **Umbrella for small media tools:**
>
> | Task | Section |
> |------|---------|
> | Find/download GIFs from Tenor | [Section A — GIF Search](#section-a--gif-search-tenor-api) |
> | Audio spectrograms, mel, chroma, MFCC visualization | [Section B — Songsee](#section-b--songsee-audio-visualization) |

---

## Section A — GIF Search (Tenor API)

Search and download GIFs directly via the Tenor API using curl + jq.

**Prerequisites:** `TENOR_API_KEY` env var (free key at https://developers.google.com/tenor/guides/quickstart), `curl`, `jq`

### Quick Commands

```bash
# Search and get GIF URLs
curl -s "https://tenor.googleapis.com/v2/search?q=thumbs+up&limit=5&key=${TENOR_API_KEY}" | jq -r '.results[].media_formats.gif.url'

# Get preview (smaller) versions
curl -s "https://tenor.googleapis.com/v2/search?q=nice+work&limit=3&key=${TENOR_API_KEY}" | jq -r '.results[].media_formats.tinygif.url'

# Download top result
URL=$(curl -s "https://tenor.googleapis.com/v2/search?q=celebration&limit=1&key=${TENOR_API_KEY}" | jq -r '.results[0].media_formats.gif.url')
curl -sL "$URL" -o celebration.gif

# Full metadata
curl -s "https://tenor.googleapis.com/v2/search?q=cat&limit=3&key=${TENOR_API_KEY}" | jq '.results[] | {title: .title, url: .media_formats.gif.url, preview: .media_formats.tinygif.url, dimensions: .media_formats.gif.dims}'
```

### API Parameters

| Parameter | Description |
|-----------|-------------|
| `q` | Search query (spaces as `+`) |
| `limit` | Max results (1-50) |
| `key` | API key from `$TENOR_API_KEY` |
| `media_filter` | `gif`, `tinygif`, `mp4`, `tinymp4`, `webm` |
| `contentfilter` | `off`, `low`, `medium`, `high` |

### Media Formats

| Format | Use case |
|--------|----------|
| `gif` | Full quality GIF |
| `tinygif` | Small preview (use for chat) |
| `mp4` | Smaller video version |
| `nanogif` | Tiny thumbnail |

**Tip:** GIF URLs work directly in markdown: `![alt](url)`

---

## Section B — Songsee (Audio Visualization)

Generate spectrograms and multi-panel audio feature visualizations.

**Install:**
```bash
go install github.com/steipete/songsee/cmd/songsee@latest
# Optional: ffmpeg for formats beyond WAV/MP3
```

### Quick Commands

```bash
# Basic spectrogram
songsee track.mp3

# Save to file
songsee track.mp3 -o spectrogram.png

# Multi-panel visualization grid
songsee track.mp3 --viz spectrogram,mel,chroma,hpss,selfsim,loudness,tempogram,mfcc,flux

# Time slice (start at 12.5s, 8s duration)
songsee track.mp3 --start 12.5 --duration 8 -o slice.jpg
```

### Visualization Types

| Type | Description |
|------|-------------|
| `spectrogram` | Standard frequency spectrogram |
| `mel` | Mel-scaled spectrogram |
| `chroma` | Pitch class distribution |
| `hpss` | Harmonic/percussive separation |
| `selfsim` | Self-similarity matrix |
| `loudness` | Loudness over time |
| `tempogram` | Tempo estimation |
| `mfcc` | Mel-frequency cepstral coefficients |
| `flux` | Spectral flux (onset detection) |

### Common Flags

| Flag | Description |
|------|-------------|
| `--viz` | Visualization types (comma-separated) |
| `--style` | Color palette: `classic`, `magma`, `inferno`, `viridis`, `gray` |
| `--width`/`--height` | Output image dimensions |
| `--format` | `jpg` or `png` |
| `-o` | Output file path |

**Tip:** Output images can be analyzed with `vision_analyze` for automated audio analysis pipelines.
