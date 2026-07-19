"""Resize showcase slides for web delivery."""
from pathlib import Path
from PIL import Image

ROOT = Path("assets/img/seminar-showcase")
MAX_W = 1400

for path in ROOT.rglob("*"):
    if path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
        continue
    with Image.open(path) as im:
        im = im.convert("RGB") if path.suffix.lower() in {".jpg", ".jpeg"} or im.mode not in ("RGB", "RGBA") else im
        if im.width <= MAX_W:
            print(f"ok {path} {im.size}")
            continue
        h = int(im.height * MAX_W / im.width)
        out = im.resize((MAX_W, h), Image.Resampling.LANCZOS)
        if path.suffix.lower() == ".png" and im.mode == "RGBA":
            out.save(path, optimize=True)
        else:
            dest = path.with_suffix(".jpg")
            out.convert("RGB").save(dest, "JPEG", quality=82, optimize=True)
            if dest != path:
                path.unlink()
            print(f"resized {path.name} -> {dest.name if dest != path else path.name} {out.size}")
            continue
        print(f"resized {path} {out.size}")
