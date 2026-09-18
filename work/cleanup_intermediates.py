from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
work = ROOT / "work"
extensions = {".wav", ".png", ".log"}
removed = []

for path in work.rglob("*"):
    if path.is_file() and (path.suffix.lower() in extensions or "stdout" in path.name.lower() or "stderr" in path.name.lower()):
        size = path.stat().st_size
        path.unlink()
        removed.append((path, size))

# These are superseded local render outputs. The delivered videos are on Desktop;
# subtitle files in outputs remain intact.
outputs = ROOT / "outputs"
for path in outputs.glob("*.mp4"):
    size = path.stat().st_size
    path.unlink()
    removed.append((path, size))

print(f"Removed {len(removed)} intermediate files, freeing {sum(size for _, size in removed)} bytes.")
for path, size in removed:
    print(f"{size}\t{path}")
