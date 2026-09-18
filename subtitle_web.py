import json
import mimetypes
import os
import shutil
import subprocess
import threading
import uuid
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).parent.resolve()
UPLOADS = ROOT / "web_uploads"
UPLOADS.mkdir(exist_ok=True)
PYTHON = ROOT / "work" / ".venv" / "Scripts" / "python.exe"
jobs = {}


def worker(job_id, source):
    job = jobs[job_id]
    job["status"] = "processing"
    job["message"] = "正在识别和翻译音频..."
    try:
        # The production pipeline is reused so the web UI keeps the same subtitle rules.
        original = Path(job["filename"])
        output_dir = Path(job.get("output_dir") or (Path.home() / "Desktop"))
        output_dir.mkdir(parents=True, exist_ok=True)
        desired = output_dir / f"{original.stem}_中文字幕{original.suffix}"
        command = [str(PYTHON), str(ROOT / "work" / "web_worker.py"), str(source), str(desired)]
        process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        for line in process.stdout:
            job["message"] = line.strip()[-160:]
        code = process.wait()
        if code:
            raise RuntimeError(f"处理失败，退出码 {code}")
        job["status"] = "done"
        job["message"] = "已完成"
        job["output"] = str(desired)
    except Exception as error:
        job["status"] = "error"
        job["message"] = str(error)


class Handler(BaseHTTPRequestHandler):
    def send_json(self, data, status=200):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        request_path = self.path.split("?", 1)[0]
        if request_path == "/":
            body = (ROOT / "subtitle_web.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if request_path in ("/logo.webp", "/favicon.ico"):
            asset = "favicon.ico" if request_path == "/favicon.ico" else "logo.webp"
            body = (ROOT / asset).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/x-icon" if asset.endswith(".ico") else "image/webp")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if request_path.startswith("/api/jobs/"):
            job_id = request_path.rsplit("/", 1)[-1]
            self.send_json(jobs.get(job_id, {"status": "missing"}))
            return
        self.send_error(404)

    def do_POST(self):
        if self.path == "/api/select-folder":
            result = subprocess.run([str(PYTHON), str(ROOT / "choose_folder.py")], capture_output=True, text=True, encoding="utf-8", errors="replace")
            # Some Python environments print cache warnings; the chooser path is the final line.
            selected = result.stdout.strip().splitlines()[-1].strip() if result.stdout.strip() else ""
            if selected and not Path(selected).is_dir():
                selected = ""
            self.send_json({"path": selected})
            return
        if self.path == "/api/cleanup":
            removed = 0
            for path in UPLOADS.iterdir():
                if path.is_file():
                    path.unlink()
                    removed += 1
                elif path.is_dir():
                    shutil.rmtree(path)
                    removed += 1
            UPLOADS.mkdir(exist_ok=True)
            jobs.clear()
            self.send_json({"removed": removed})
            return
        if self.path != "/api/upload":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        envelope = (f"Content-Type: {self.headers.get('Content-Type', '')}\r\nMIME-Version: 1.0\r\n\r\n").encode() + body
        message = BytesParser(policy=policy.default).parsebytes(envelope)
        fields = {}
        for part in message.iter_parts():
            disposition = part.get("Content-Disposition", "")
            name = part.get_param("name", header="content-disposition")
            if not name:
                continue
            fields[name] = {"filename": part.get_filename(), "data": part.get_payload(decode=True) or b""}
        item = fields.get("video")
        if not item or not item.get("filename"):
            self.send_json({"error": "没有收到视频文件"}, 400)
            return
        filename = Path(item["filename"]).name
        source = UPLOADS / f"{uuid.uuid4().hex}_{filename}"
        with source.open("wb") as stream:
            stream.write(item["data"])
        job_id = uuid.uuid4().hex
        output_dir = fields.get("output_dir", {}).get("data", b"").decode("utf-8", "replace").strip()
        jobs[job_id] = {"status": "queued", "message": "已加入队列", "filename": filename, "output_dir": output_dir}
        threading.Thread(target=worker, args=(job_id, source), daemon=True).start()
        self.send_json({"id": job_id})


if __name__ == "__main__":
    print("字幕工具运行于 http://127.0.0.1:8766")
    ThreadingHTTPServer(("127.0.0.1", 8766), Handler).serve_forever()
