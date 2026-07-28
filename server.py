import json
import os
from datetime import datetime
from email import policy
from email.parser import BytesParser
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
DATA_DIR = BASE_DIR / "data"
STATS_FILE = DATA_DIR / "stats.json"
VIDEOS_FILE = DATA_DIR / "videos.json"

UPLOAD_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

if not STATS_FILE.exists():
    STATS_FILE.write_text(json.dumps({"downloads": 1240, "users": 86, "episodes": 124, "series": 28}, indent=2), encoding="utf-8")

if not VIDEOS_FILE.exists():
    VIDEOS_FILE.write_text("[]", encoding="utf-8")

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".mp4": "video/mp4",
    ".mkv": "video/x-matroska",
    ".avi": "video/x-msvideo",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def write_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def parse_content_type(value: str):
    parts = value.split(";")
    ctype = parts[0].strip().lower()
    params = {}
    for part in parts[1:]:
        if "=" in part:
            key, val = part.split("=", 1)
            params[key.strip().lower()] = val.strip().strip('"')
    return ctype, params


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, relative_path: str):
        path = (BASE_DIR / relative_path.lstrip("/")).resolve()
        if not str(path).startswith(str(BASE_DIR)):
            self.send_error(403)
            return
        if not path.exists() or not path.is_file():
            self.send_error(404)
            return
        ext = path.suffix.lower()
        mime = MIME_TYPES.get(ext, "application/octet-stream")
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/stats":
            self._send_json(read_json(STATS_FILE))
            return

        if path == "/api/videos":
            self._send_json(read_json(VIDEOS_FILE))
            return

        if path.startswith("/uploads/"):
            self._serve_file(path)
            return

        if path in ["/", "/index.html", "/admin/login.html", "/admin/dashboard.html", "/admin/series.html", "/admin/films.html", "/admin/upload.html", "/admin/users.html", "/admin/statistics.html", "/admin/settings.html"]:
            if path == "/":
                self._serve_file("index.html")
            else:
                self._serve_file(path.lstrip("/"))
            return

        self._serve_file(path.lstrip("/"))

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/upload":
            ctype, pdict = parse_content_type(self.headers.get("Content-Type", ""))
            if ctype != "multipart/form-data":
                self._send_json({"ok": False, "error": "format invalide"}, 400)
                return

            boundary = pdict.get("boundary")
            if not boundary:
                self._send_json({"ok": False, "error": "boundary manquant"}, 400)
                return

            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length)
            raw = f"Content-Type: multipart/form-data; boundary={boundary}\r\n\r\n".encode("utf-8") + body
            message = BytesParser(policy=policy.default).parsebytes(raw)

            file_part = None
            form_fields = {}
            for part in message.iter_parts():
                # Robustly extract the form field name from Content-Disposition
                cd = part.get('Content-Disposition', '') or ''
                m = re.search(r'name="([^"]+)"', cd)
                name = m.group(1) if m else None
                if not name:
                    continue
                if part.get_filename():
                    file_part = part
                else:
                    try:
                        form_fields[name] = part.get_content()
                    except Exception:
                        form_fields[name] = part.get_payload(decode=True).decode('utf-8', 'ignore')

            if file_part is None:
                self._send_json({"ok": False, "error": "aucun fichier reçu"}, 400)
                return

            filename = os.path.basename(file_part.get_filename())
            stem, suffix = os.path.splitext(filename)
            if not suffix:
                suffix = ".mp4"
            safe_name = f"{stem}_{len(os.listdir(UPLOAD_DIR))}{suffix}"
            save_path = UPLOAD_DIR / safe_name
            payload = file_part.get_payload(decode=True)
            if payload is None:
                payload = b""
            with save_path.open("wb") as handle:
                handle.write(payload)

            videos = read_json(VIDEOS_FILE)
            # allow uploader to be passed via query string for robustness
            qs = parse_qs(parsed.query)
            uploader = (qs.get('uploader') or [None])[0] or form_fields.get('uploader') or form_fields.get('author') or 'unknown'
            # Debug: log form fields to help diagnose missing uploader
            try:
                with open(BASE_DIR / 'upload_debug.log', 'a', encoding='utf-8') as dbg:
                    dbg.write(f"FORM_FIELDS:{form_fields}\n")
                    dbg.write(f"UPLOADER:{uploader}\n")
            except Exception:
                pass
            videos.insert(0, {
                "id": len(videos) + 1,
                "name": safe_name,
                "path": f"/uploads/{safe_name}",
                "size": save_path.stat().st_size,
                "uploadedAt": datetime.utcnow().isoformat() + "Z",
                "uploader": uploader,
            })
            write_json(VIDEOS_FILE, videos)

            # Recompute users based on unique uploader names and increment episodes
            stats = read_json(STATS_FILE)
            stats["episodes"] = int(stats.get("episodes", 0)) + 1
            try:
                users_set = set(v.get('uploader') for v in videos if v.get('uploader'))
                stats["users"] = len(users_set)
            except Exception:
                stats["users"] = int(stats.get("users", 0))
            write_json(STATS_FILE, stats)

            self._send_json({"ok": True, "file": f"/uploads/{safe_name}"})
            return

        self.send_error(404)


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    try:
        server = ThreadingHTTPServer((host, port), Handler)
    except OSError as exc:
        if "Address already in use" in str(exc) or "Operation not permitted" in str(exc):
            alt_port = 8001
            server = ThreadingHTTPServer((host, alt_port), Handler)
            port = alt_port
        else:
            raise
    print(f"Serveur lancé sur http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
