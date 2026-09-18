import subprocess
import sys
from pathlib import Path


source = Path(sys.argv[1]).resolve()
desired = Path(sys.argv[2]).resolve()
template = Path(__file__).with_name("process_remaining.py").read_text(encoding="utf-8")
start = template.index("SOURCES = [")
end = template.index("\n]", start) + 2
replacement = f'SOURCES = [\\n    Path(r"{source}")\\n]'.replace("\\n", "\n")
generated = template[:start] + replacement + template[end:]
generated = generated.replace('note(f"Starting {position}/3:', 'note(f"Starting {position}/1:').replace('note(f"Completed {position}/3:', 'note(f"Completed {position}/1:')
generated_path = source.parent / "_web_pipeline.py"
generated_path.write_text(generated, encoding="utf-8")
try:
    completed = subprocess.run([sys.executable, str(generated_path)], cwd=source.parent, check=False)
    if completed.returncode:
        raise SystemExit(completed.returncode)
    produced = Path.home() / "Desktop" / source.name
    if not produced.exists():
        raise FileNotFoundError(produced)
    desired.parent.mkdir(exist_ok=True)
    produced.replace(desired)
finally:
    generated_path.unlink(missing_ok=True)
