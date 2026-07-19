"""Extract showcase writings and convert HEIC presentation photos to JPG."""
from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SHOWCASE = ROOT / "assets" / "showcase"
OUT = ROOT / "assets" / "img" / "seminar-showcase"
W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def docx_paragraphs(path: Path) -> tuple[list[str], list[str]]:
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
        paras: list[str] = []
        for p in root.iter(f"{W_NS}p"):
            texts = [t.text or "" for t in p.iter(f"{W_NS}t")]
            line = "".join(texts).strip()
            if line:
                paras.append(line)
        imgs = [n for n in z.namelist() if n.startswith("word/media/")]
    return paras, imgs


def extract_docx(src: Path, stem: str, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    paras, imgs = docx_paragraphs(src)
    (dest_dir / f"{stem}.txt").write_text("\n\n".join(paras), encoding="utf-8")
    print(f"{src.name}: {len(paras)} paras, {len(imgs)} images")
    with zipfile.ZipFile(src) as z:
        for i, img in enumerate(imgs, 1):
            ext = Path(img).suffix.lower() or ".bin"
            dest = dest_dir / f"{stem}-img-{i}{ext}"
            dest.write_bytes(z.read(img))
            print(f"  saved {dest.relative_to(ROOT)}")


def convert_heic_folder(src_dir: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    heics = sorted({*src_dir.glob("*.HEIC"), *src_dir.glob("*.heic")})
    if not heics:
        print(f"No HEIC in {src_dir}")
        return

    # Try magick / pillow-heif / sips-like fallbacks
    for i, heic in enumerate(heics, 1):
        dest = dest_dir / f"slide-{i:02d}.jpg"
        ok = False
        # ImageMagick
        try:
            subprocess.run(
                ["magick", str(heic), "-quality", "85", str(dest)],
                check=True,
                capture_output=True,
            )
            ok = True
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass
        if not ok:
            try:
                from PIL import Image  # type: ignore
                import pillow_heif  # type: ignore

                pillow_heif.register_heif_opener()
                with Image.open(heic) as im:
                    rgb = im.convert("RGB")
                    rgb.save(dest, "JPEG", quality=85)
                ok = True
            except Exception as exc:  # noqa: BLE001
                print(f"  failed {heic.name}: {exc}")
        if ok:
            print(f"  converted {heic.name} -> {dest.relative_to(ROOT)}")


def main() -> None:
    death = SHOWCASE / "Death and taxes"
    extract_docx(death / "Chin's writing.docx", "chin", OUT / "death-and-taxes")
    extract_docx(death / "Ryousuke's writing.docx", "ryousuke", OUT / "death-and-taxes")

    moon_src = SHOWCASE / "To the Moon" / "presentation pictures"
    convert_heic_folder(moon_src, OUT / "to-the-moon" / "slides")

    moon_writing = SHOWCASE / "To the Moon" / "To the Moon writing.txt"
    dest_txt = OUT / "to-the-moon" / "writing.txt"
    dest_txt.parent.mkdir(parents=True, exist_ok=True)
    dest_txt.write_text(moon_writing.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"copied writing -> {dest_txt.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
