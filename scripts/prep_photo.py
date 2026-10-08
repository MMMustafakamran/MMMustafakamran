"""Prep a photo (or illustration) for ASCII conversion.

1. Isolate the subject:
   - photos: remove the background with rembg;
   - flat-color illustrations (--flat): key out the dominant background colors.
2. Boost local contrast with CLAHE so a flatly-lit face gets real highlights/shadows
   (skipped for --flat, where the line art already carries the contrast).
3. Composite onto pure white so the background maps to spaces in the ASCII ramp.

Usage: python scripts/prep_photo.py source-photo.png [out.png]
       python scripts/prep_photo.py --flat source-cartoon.png [out.png]
       KEY_TOL=20 python scripts/prep_photo.py --flat source-coding.jpg source-coding-prepped.png
         (lower KEY_TOL when dark hair is close to the background color)
"""
import os
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent


def rembg_alpha(img: Image.Image) -> np.ndarray:
    from rembg import new_session, remove

    # u2netp is a ~5 MB model; set REMBG_MODEL=isnet-general-use or birefnet-portrait for finer hair edges.
    session = new_session(os.environ.get("REMBG_MODEL", "u2netp"))
    cut = remove(img, session=session).convert("RGBA")
    return np.array(cut)[:, :, 3].astype(np.float32) / 255.0


def flat_alpha(rgb: np.ndarray, n_colors: int = 2, tol: float = 34.0) -> np.ndarray:
    """Key out the n most common colors wherever they connect to the image border."""
    q = (rgb // 8).reshape(-1, 3)
    keys, counts = np.unique(q, axis=0, return_counts=True)
    bg_colors = keys[np.argsort(counts)[::-1][:n_colors]].astype(np.float32) * 8 + 4

    px = rgb.astype(np.float32)
    near = np.zeros(rgb.shape[:2], bool)
    for c in bg_colors:
        near |= np.linalg.norm(px - c, axis=2) < tol

    # Background = bg-colored regions touching the border (so the same color inside the
    # subject, e.g. a cream highlight, survives). Iterate so a color region enclosed by
    # another bg color (a cream circle on navy) is reached too.
    n, labels = cv2.connectedComponents(near.astype(np.uint8), connectivity=4)
    border = set(np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]])))
    border.discard(0)
    bg = np.isin(labels, list(border))
    big = [i for i in range(1, n) if (labels == i).sum() > 0.05 * labels.size]
    bg |= np.isin(labels, big)

    subject = (~bg).astype(np.uint8)
    # Fill holes (glasses frames, highlights) by flood-filling the background from a corner.
    filled = subject.copy()
    ff = np.zeros((subject.shape[0] + 2, subject.shape[1] + 2), np.uint8)
    cv2.floodFill(filled, ff, (0, 0), 1)
    subject |= 1 - filled
    # Drop hairline leftovers, e.g. the anti-aliased rim between two background colors.
    subject = cv2.morphologyEx(subject, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    # Keep every substantial blob (a head can separate from the body) and soften edges.
    n, labels, stats, _ = cv2.connectedComponentsWithStats(subject, connectivity=8)
    keep = [i for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] >= 0.01 * subject.size]
    mask = np.isin(labels, keep).astype(np.float32)
    return cv2.GaussianBlur(mask, (3, 3), 0)


def flatten_skin(rgb: np.ndarray, gray: np.ndarray, tone: int) -> np.ndarray:
    """Paint skin one even tone so shading/stubble don't turn into blotchy ASCII.

    Skin = warm hue, saturated, reasonably bright. Dark outlines (eyes, nose, smile, jaw)
    and the low-saturation glasses fall outside the mask and keep their own values.
    """
    h, s, v = cv2.split(cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV))
    skin = ((h >= 3) & (h <= 22) & (s >= 90) & (v >= 120)).astype(np.uint8)
    skin = cv2.morphologyEx(skin, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    out = gray.copy()
    out[skin > 0] = tone
    return out


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flat = "--flat" in sys.argv
    src = Path(args[0]) if args else ROOT / "source-cartoon.png"
    out = Path(args[1]) if len(args) > 1 else ROOT / "source-prepped.png"

    img = Image.open(src).convert("RGB")
    rgb = np.array(img)
    alpha = flat_alpha(rgb, tol=float(os.environ.get("KEY_TOL", "34"))) if flat else rembg_alpha(img)

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    if flat:
        gray = flatten_skin(rgb, gray, int(os.environ.get("SKIN_TONE", "160")))
    else:
        gray = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(gray)
    gray = gray.astype(np.float32)

    # Composite onto white using the cutout alpha.
    composed = gray * alpha + 255.0 * (1.0 - alpha)
    Image.fromarray(np.clip(composed, 0, 255).astype(np.uint8), "L").save(out)
    print(f"wrote {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")


if __name__ == "__main__":
    main()
