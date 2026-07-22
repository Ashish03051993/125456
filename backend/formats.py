"""Video output format registry.

Adding a new aspect ratio (1:1, 4:5, etc.) = adding an entry here. Nothing
else in the pipeline needs to change.

Each format specifies:
  - width / height: output resolution
  - fit: "cover" (crop overflow) or "pad_blur" (blurred background pad)
  - subtitle_y: `y` value passed to ffmpeg drawtext (pixels from top-left)
  - subtitle_font: font size for burned-in subtitle
  - subtitle_box_height: black overlay strip height
  - zoom_dur_frames_per_second: ken-burns pan frame count per second
  - default: True marks the primary format (kept as video_url for backwards compat)
"""
from typing import Dict, List

FORMATS: Dict[str, dict] = {
    "landscape": {
        "label": "YouTube / Web",
        "platforms": ["YouTube", "Twitter", "Web"],
        "aspect": "16:9",
        "width": 1920,
        "height": 1080,
        "fit": "cover",
        "subtitle_font": 44,
        "subtitle_box_height": 160,
        "subtitle_box_from_bottom": True,
        "subtitle_y_offset": 130,          # from bottom
        "subtitle_wrap_chars": 34,
        "zoom_end_scale": 1.12,
        "default": True,
    },
    "vertical": {
        "label": "LinkedIn / Reels / Shorts",
        "platforms": ["LinkedIn", "Instagram Reels", "YouTube Shorts", "TikTok"],
        "aspect": "9:16",
        "width": 1080,
        "height": 1920,
        "fit": "pad_blur",                 # source images are 16:9 — pad with blurred background
        "subtitle_font": 56,
        "subtitle_box_height": 260,
        "subtitle_box_from_bottom": True,
        "subtitle_y_offset": 230,
        "subtitle_wrap_chars": 22,
        "zoom_end_scale": 1.15,
        "default": False,
    },
    # Future formats — keep the entry commented until a caller needs it.
    # "square": {"label": "Instagram Feed", "aspect": "1:1", "width": 1080,
    #            "height": 1080, "fit": "pad_blur", ...},
    # "portrait_45": {"label": "Instagram Portrait", "aspect": "4:5",
    #                 "width": 1080, "height": 1350, "fit": "pad_blur", ...},
}


def list_formats() -> List[dict]:
    """Return format specs decorated with their `id`."""
    return [{"id": k, **v} for k, v in FORMATS.items()]


def get_format(fid: str) -> dict:
    if fid not in FORMATS:
        raise KeyError(f"Unknown video format: {fid}")
    return {"id": fid, **FORMATS[fid]}


def default_format() -> str:
    for k, v in FORMATS.items():
        if v.get("default"):
            return k
    return next(iter(FORMATS))


def build_scene_vf(spec: dict, per_scene_seconds: float, sub_text_esc: str) -> str:
    """Build the ffmpeg -vf filtergraph for a single scene image → clip.

    Handles cover-crop and blurred-pad fits for arbitrary aspect ratios.
    """
    w, h = spec["width"], spec["height"]
    frames = max(int(per_scene_seconds * 30), 1)
    end_scale = spec["zoom_end_scale"]
    zoom_step = (end_scale - 1.0) / frames  # linear pan

    if spec["fit"] == "cover":
        base = (
            f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
            f"zoompan=z='min(zoom+{zoom_step:.6f},{end_scale})'"
            f":d={frames}:s={w}x{h}:fps=30"
        )
    elif spec["fit"] == "pad_blur":
        # Split input → blurred+cover-filled background + centered fitted foreground
        base = (
            f"split=2[bg][fg];"
            f"[bg]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
            f"gblur=sigma=40,eq=brightness=-0.1[bgb];"
            f"[fg]scale={w}:{h}:force_original_aspect_ratio=decrease[fgs];"
            f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2,"
            f"zoompan=z='min(zoom+{zoom_step:.6f},{end_scale})'"
            f":d={frames}:s={w}x{h}:fps=30"
        )
    else:
        raise ValueError(f"Unknown fit: {spec['fit']}")

    box_h = spec["subtitle_box_height"]
    y_off = spec["subtitle_y_offset"]
    font_sz = spec["subtitle_font"]
    return (
        f"{base},"
        f"drawbox=y=ih-{box_h}:color=black@0.55:width=iw:height={box_h}:t=fill,"
        f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
        f"text='{sub_text_esc}':fontcolor=white:fontsize={font_sz}:"
        f"x=(w-text_w)/2:y=h-{y_off}"
    )
