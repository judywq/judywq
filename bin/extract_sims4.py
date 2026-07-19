"""Extract Sims 4 household writing for showcase."""
from pathlib import Path
import zipfile
from xml.etree import ElementTree as ET
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "assets" / "showcase" / "sims4" / "household writing.docx"
OUT = ROOT / "assets" / "img" / "seminar-showcase" / "sims4"
W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(SRC) as z:
        root = ET.fromstring(z.read("word/document.xml"))
        paras = []
        for p in root.iter(f"{W_NS}p"):
            texts = [t.text or "" for t in p.iter(f"{W_NS}t")]
            line = "".join(texts).strip()
            if line:
                paras.append(line)
        (OUT / "household.txt").write_text("\n\n".join(paras), encoding="utf-8")
        print("=== TEXT ===")
        print("\n\n".join(paras))
        imgs = [n for n in z.namelist() if n.startswith("word/media/")]
        print("=== IMAGES", len(imgs), "===")
        for i, img in enumerate(imgs, 1):
            ext = Path(img).suffix.lower() or ".bin"
            raw = OUT / f"household-{i}{ext}"
            raw.write_bytes(z.read(img))
            with Image.open(raw) as im:
                im = im.convert("RGB")
                w = min(im.width, 1400)
                h = int(im.height * w / im.width)
                dest = OUT / f"household-{i}.jpg"
                im.resize((w, h), Image.Resampling.LANCZOS).save(dest, "JPEG", quality=82, optimize=True)
            if raw != dest and raw.exists():
                raw.unlink()
            print(dest.name, dest.stat().st_size)


if __name__ == "__main__":
    main()
