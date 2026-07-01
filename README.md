# ASCII Video Converter

Convert any video into an ASCII art video — rendered as actual characters, fully customizable.

![Python](https://img.shields.io/badge/Python-3.10+-blue) ![Flask](https://img.shields.io/badge/Flask-2.3+-lightgrey) ![FFmpeg](https://img.shields.io/badge/FFmpeg-required-orange)

## Features

- **Custom character sets** — use presets (minimal, standard, dense, blocks…) or type your own
- **Custom colors** — pick any foreground and background color
- **Adjustable character size** — controls how many characters fit per frame
- **Original color mode** — each character takes the color of the corresponding video region
- **Audio preserved** — original audio is muxed back via FFmpeg
- **Browser preview** — watch the result directly in the app before downloading
- **H.264 output** — plays in any browser or media player

## Requirements

- Python 3.10+
- [FFmpeg](https://ffmpeg.org/download.html) (must be in your PATH)

## Installation

```bash
# Clone the repo
git clone https://github.com/yilmazcihan/ascii-to-video.git
cd ascii-to-video

# Create a virtual environment and install dependencies
python -m venv venv

# Windows
venv\Scripts\pip install -r requirements.txt

# macOS / Linux
source venv/bin/activate && pip install -r requirements.txt
```

On **Windows** you can also double-click `install.bat`.

## Usage

```bash
# Windows
venv\Scripts\python app.py

# macOS / Linux
venv/bin/python app.py
```

Then open **http://localhost:5000** in your browser.

On **Windows** you can also double-click `start.bat`.

## How it works

1. Drop an MP4 (or any video format) into the app
2. Choose your character set, colors, and font size
3. Click **Convert** — frames are processed server-side using NumPy vectorized operations
4. Watch the preview, then download the final H.264 MP4

### Conversion pipeline

```
Input video
   └─ OpenCV reads frames
       └─ Grayscale per-cell brightness (vectorized reshape)
           └─ Brightness → character lookup table
               └─ Pre-rendered character images assembled via NumPy transpose
                   └─ FFmpeg re-encodes to H.264 + muxes original audio
                       └─ Output MP4
```

## Parameters

| Parameter | Description |
|-----------|-------------|
| Character set | Characters used, ordered from lightest to densest visually |
| Foreground color | Color of the characters |
| Background color | Color of the background |
| Font size (px) | Smaller = more characters per frame = more detail |
| Original colors | Each character uses the average color of the source video region |
| Brightness mapping | Auto, normal, or inverted — controls light/dark mapping |

## License

MIT
