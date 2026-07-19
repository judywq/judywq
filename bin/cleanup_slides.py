from pathlib import Path

d = Path("assets/img/seminar-showcase/to-the-moon/slides")
for p in d.glob("slide-*.jpg"):
    n = int(p.stem.split("-")[1])
    if n > 9:
        p.unlink()
        print("removed", p.name)
print("remaining", sorted(x.name for x in d.glob("*.jpg")))
