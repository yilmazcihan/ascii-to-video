import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os
import subprocess
import shutil

CHARSET_PRESETS = {
    "minimal":   " .oO@",
    "standard":  " .:-=+*#@%",
    "dense":     " `.-':_,^=;><+!rc*/z?sLTv)J7(|Fi{C}fI31tlu[neoZ5Yxjya]2ESwqkP6h9d4VpOGbUAKXHm8RD#$Bg0MNWQ%&@",
    "numbers":   " 1234567890",
    "binary":    " 01",
    "braille":   " ⠁⠃⠇⠏⠟⠿",
    "blocks":    " ░▒▓█",
    "letters":   " .-+iIlLoO08@",
}

FONT_PATHS_WINDOWS = [
    "C:/Windows/Fonts/consola.ttf",
    "C:/Windows/Fonts/cour.ttf",
    "C:/Windows/Fonts/lucon.ttf",
]
FONT_PATHS_UNIX = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    "/System/Library/Fonts/Menlo.ttc",
]


def _hex_to_rgb(color: str) -> tuple:
    color = color.lstrip("#")
    return tuple(int(color[i:i+2], 16) for i in (0, 2, 4))


def _load_font(font_size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_PATHS_WINDOWS + FONT_PATHS_UNIX:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, font_size)
            except Exception:
                continue
    return ImageFont.load_default()


def _measure_char(font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    dummy = Image.new("RGB", (200, 200))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), "M", font=font)
    w = max(1, bbox[2] - bbox[0])
    h = max(1, bbox[3] - bbox[1])
    return w, h


class AsciiVideoConverter:
    def __init__(
        self,
        charset: str,
        fg_color: str,
        bg_color: str,
        font_size: int,
        colored: bool = False,
        invert: bool | None = None,
    ):
        self.charset = charset or " .:-=+*#@%"
        self.fg_rgb = _hex_to_rgb(fg_color)
        self.bg_rgb = _hex_to_rgb(bg_color)
        self.font_size = max(4, min(int(font_size), 48))
        self.colored = colored

        # Auto-invert: on dark backgrounds, dense chars should map to bright pixels
        if invert is None:
            lum = 0.299 * self.bg_rgb[0] + 0.587 * self.bg_rgb[1] + 0.114 * self.bg_rgb[2]
            self.invert = lum < 128
        else:
            self.invert = invert

        self.font = _load_font(self.font_size)
        self.char_w, self.char_h = _measure_char(self.font)
        self._build_lut()

    def _build_lut(self):
        charset = self.charset if not self.invert else self.charset[::-1]
        n = len(charset)

        # brightness_to_idx: maps 0-255 → index in charset
        self.brightness_idx = np.array(
            [int(i * (n - 1) / 255) for i in range(256)], dtype=np.int32
        )

        # Pre-render each unique character in BGR (for flat-color mode)
        unique_chars = sorted(set(charset))
        char_to_id = {c: i for i, c in enumerate(unique_chars)}

        char_imgs = np.zeros((len(unique_chars), self.char_h, self.char_w, 3), dtype=np.uint8)
        bg_bgr = self.bg_rgb[::-1]
        fg_bgr = self.fg_rgb[::-1]

        for char, idx in char_to_id.items():
            img = Image.new("RGB", (self.char_w, self.char_h), self.bg_rgb)
            draw = ImageDraw.Draw(img)
            draw.text((0, 0), char, font=self.font, fill=self.fg_rgb)
            arr = np.array(img)
            char_imgs[idx] = arr[:, :, ::-1]  # RGB → BGR

        # brightness_lut[b] = BGR image of the char for brightness b
        self.brightness_lut = char_imgs[
            [char_to_id[charset[i]] for i in self.brightness_idx]
        ]  # (256, char_h, char_w, 3)

        # For colored mode: build a grayscale alpha mask (white-on-black)
        if self.colored:
            mask_imgs = np.zeros((len(unique_chars), self.char_h, self.char_w), dtype=np.uint8)
            for char, idx in char_to_id.items():
                img = Image.new("L", (self.char_w, self.char_h), 0)
                draw = ImageDraw.Draw(img)
                draw.text((0, 0), char, font=self.font, fill=255)
                mask_imgs[idx] = np.array(img)
            self.mask_lut = mask_imgs[
                [char_to_id[charset[i]] for i in self.brightness_idx]
            ]  # (256, char_h, char_w)

        self.bg_bgr_arr = np.array(self.bg_rgb[::-1], dtype=np.float32)

    def convert_frame(self, frame_bgr: np.ndarray) -> np.ndarray:
        h, w = frame_bgr.shape[:2]
        cols = max(1, w // self.char_w)
        rows = max(1, h // self.char_h)
        target_w, target_h = cols * self.char_w, rows * self.char_h

        frame = cv2.resize(frame_bgr, (target_w, target_h), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Average brightness per character cell — vectorized
        gray_r = gray.reshape(rows, self.char_h, cols, self.char_w)
        cell_bright = gray_r.mean(axis=(1, 3)).astype(np.uint8)  # (rows, cols)

        if self.colored:
            # Get average cell color from original frame — vectorized
            frame_r = frame.reshape(rows, self.char_h, cols, self.char_w, 3)
            cell_color = frame_r.mean(axis=(1, 3))  # (rows, cols, 3) float64

            # Look up alpha masks: (rows, cols, char_h, char_w)
            masks = self.mask_lut[cell_bright].astype(np.float32) / 255.0
            masks = masks[:, :, :, :, np.newaxis]  # (rows, cols, char_h, char_w, 1)

            # Broadcast cell color over char cell
            cc = cell_color[:, :, np.newaxis, np.newaxis, :]  # (rows, cols, 1, 1, 3)
            bg = self.bg_bgr_arr  # (3,)

            # Blend: bg * (1 - mask) + cell_color * mask
            output = (bg * (1 - masks) + cc * masks).astype(np.uint8)
        else:
            # Flat color: direct LUT lookup
            output = self.brightness_lut[cell_bright]  # (rows, cols, char_h, char_w, 3)

        # Assemble: (rows, char_h, cols, char_w, 3) → (rows*char_h, cols*char_w, 3)
        return output.transpose(0, 2, 1, 3, 4).reshape(
            rows * self.char_h, cols * self.char_w, 3
        )

    def convert_video(
        self,
        input_path: str,
        output_path: str,
        progress_callback=None,
    ) -> str:
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video file: {input_path}")

        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
        orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        cols = max(1, orig_w // self.char_w)
        rows = max(1, orig_h // self.char_h)
        out_w = cols * self.char_w
        out_h = rows * self.char_h

        # Always write a raw intermediate with mp4v; FFmpeg will re-encode to H.264 after
        tmp_path = output_path.replace(".mp4", "_raw.avi")
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        writer = cv2.VideoWriter(tmp_path, fourcc, fps, (out_w, out_h))
        if not writer.isOpened():
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            tmp_path = output_path.replace(".mp4", "_raw.mp4")
            writer = cv2.VideoWriter(tmp_path, fourcc, fps, (out_w, out_h))
        if not writer.isOpened():
            raise RuntimeError("No compatible video codec found.")

        frame_n = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            writer.write(self.convert_frame(frame))
            frame_n += 1
            if progress_callback and total > 0:
                progress_callback(min(99, int(frame_n / total * 100)))

        cap.release()
        writer.release()

        # Try to mux original audio with FFmpeg
        final_path = _mux_audio(tmp_path, input_path, output_path)
        if final_path != tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

        if progress_callback:
            progress_callback(100)

        return final_path


def _mux_audio(video_path: str, audio_source: str, output_path: str) -> str:
    """Re-encode to H.264 (browser-compatible) and mux original audio if available."""
    if not shutil.which("ffmpeg"):
        os.rename(video_path, output_path)
        return output_path

    # Re-encode video to H.264 + mux audio from original source
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_source,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-c:a", "aac",
        "-map", "0:v:0",
        "-map", "1:a:0?",   # audio is optional — won't fail if absent
        "-shortest",
        "-movflags", "+faststart",  # metadata at start → enables browser streaming/seeking
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode == 0 and os.path.exists(output_path):
        return output_path

    # Fallback: H.264 without audio
    cmd2 = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-movflags", "+faststart",
        output_path,
    ]
    result2 = subprocess.run(cmd2, capture_output=True)
    if result2.returncode == 0 and os.path.exists(output_path):
        return output_path

    # Last resort: keep raw intermediate as-is
    os.rename(video_path, output_path)
    return output_path
