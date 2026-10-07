"""Prep a photo for ASCII conversion.

1. Remove the background with rembg so only the subject remains.
2. Boost local contrast with CLAHE so a flatly-lit face gets real highlights/shadows.
3. Composite onto pure white so the background maps to spaces in the ASCII ramp.

Usage: python scripts/prep_photo.py source-photo.png [out.png]
"""
import os
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from rembg import new_session, remove

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "source-photo.png"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "source-prepped.png"

    img = Image.open(src).convert("RGB")
    # u2netp is a ~5 MB model; set REMBG_MODEL=isnet-general-use or birefnet-portrait for finer hair edges.
    session = new_session(os.environ.get("REMBG_MODEL", "u2netp"))
    cut = remove(img, session=session).convert("RGBA")  # transparent background
    rgba = np.array(cut)
    alpha = rgba[:, :, 3].astype(np.float32) / 255.0

    gray = cv2.cvtColor(rgba[:, :, :3], cv2.COLOR_RGB2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    gray = clahe.apply(gray).astype(np.float32)

    # Composite onto white using the cutout alpha.
    composed = gray * alpha + 255.0 * (1.0 - alpha)
    Image.fromarray(np.clip(composed, 0, 255).astype(np.uint8), "L").save(out)
    print(f"wrote {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")


if __name__ == "__main__":
    main()
