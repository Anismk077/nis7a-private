import hashlib
import hmac
import json
import os
import re
import secrets
import threading
from datetime import datetime, timedelta, timezone
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
DATA_DIR = BASE_DIR / "data"
STATS_FILE = DATA_DIR / "stats.json"
VIDEOS_FILE = DATA_DIR / "videos.json"
EVENTS_FILE = DATA_DIR / "events.json"
ADMIN_USERS_FILE = DATA_DIR / "admin_users.json"
SESSIONS_FILE = DATA_DIR / "admin_sessions.json"

SESSION_COOKIE = "nis7a_session"
SESSION_HOURS = 12
PBKDF2_ITERATIONS = 130000
STORE_LOCK = threading.RLock()

UPLOAD_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)


def utc_now():
    return datetime.now(timezone.utc)


def utc_iso(dt=None):
    value = dt or utc_now()
    return value.isoformat().replace("+00:00", "Z")


def parse_iso(value: str):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


if not STATS_FILE.exists():
    STATS_FILE.write_text(json.dumps({"series": 0}, indent=2), encoding="utf-8")

if not VIDEOS_FILE.exists():
    VIDEOS_FILE.write_text("[]", encoding="utf-8")

if not EVENTS_FILE.exists():
    EVENTS_FILE.write_text(json.dumps({"visits": [], "downloads": [], "adminLoginAttempts": []}, indent=2), encoding="utf-8")

if not ADMIN_USERS_FILE.exists():
    seed_salt = secrets.token_hex(16)
    seed_hash = hashlib.pbkdf2_hmac(
        "sha256", "anis".encode("utf-8"), bytes.fromhex(seed_salt), PBKDF2_ITERATIONS
    ).hex()
    ADMIN_USERS_FILE.write_text(
        json.dumps(
            [
                {
                    "username": "anis",
                    "passwordSalt": seed_salt,
                    "passwordHash": seed_hash,
                    "iterations": PBKDF2_ITERATIONS,
                    "createdAt": utc_iso(),
                }
            ],
            indent=2,
        ),
        encoding="utf-8",
    )

if not SESSIONS_FILE.exists():
    SESSIONS_FILE.write_text("[]", encoding="utf-8")

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
    with STORE_LOCK:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []


def write_json(path: Path, data):
    with STORE_LOCK:
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp_path.replace(path)


def parse_content_type(value: str):
    parts = value.split(";")
    ctype = parts[0].strip().lower()
    params = {}
    for part in parts[1:]:
        if "=" in part:
            key, val = part.split("=", 1)
            params[key.strip().lower()] = val.strip().strip('"')
    return ctype, params


def normalize_username(value: str) -> str:
    return str(value or "").strip().lower()


def create_password_record(password: str):
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac(
        "sha256", str(password).encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS
    ).hex()
    return {"passwordSalt": salt, "passwordHash": pwd_hash, "iterations": PBKDF2_ITERATIONS}


def verify_password_record(user: dict, password: str) -> bool:
    pwd = str(password).encode("utf-8")
    salt = user.get("passwordSalt")
    pwd_hash = user.get("passwordHash")
    iterations = int(user.get("iterations", PBKDF2_ITERATIONS))

    if salt and pwd_hash:
        calculated = hashlib.pbkdf2_hmac("sha256", pwd, bytes.fromhex(salt), iterations).hex()
        return hmac.compare_digest(calculated, pwd_hash)

    # Legacy fallback for old sha256 only records
    if pwd_hash:
        legacy = hashlib.sha256(pwd).hexdigest()
        return hmac.compare_digest(legacy, pwd_hash)

    return False


def load_admin_users():
    users = read_json(ADMIN_USERS_FILE)
    if not isinstance(users, list):
        users = []

    changed = False
    normalized = []
    seen = set()
    for user in users:
        if not isinstance(user, dict):
            continue

        username = normalize_username(user.get("username", ""))
        if not username or username in seen:
            continue

        if not user.get("passwordHash") and user.get("password"):
            upgraded = create_password_record(user.get("password"))
            user.update(upgraded)
            changed = True

        if not user.get("passwordHash"):
            continue

        normalized.append(
            {
                "username": username,
                "passwordSalt": user.get("passwordSalt"),
                "passwordHash": user.get("passwordHash"),
                "iterations": int(user.get("iterations", PBKDF2_ITERATIONS)),
                "createdAt": user.get("createdAt") or utc_iso(),
            }
        )
        seen.add(username)

    if "anis" not in seen:
        seed = create_password_record("anis")
        normalized.append(
            {
                "username": "anis",
                "passwordSalt": seed["passwordSalt"],
                "passwordHash": seed["passwordHash"],
                "iterations": seed["iterations"],
                "createdAt": utc_iso(),
            }
        )
        changed = True

    if changed:
        write_json(ADMIN_USERS_FILE, normalized)

    return normalized


def save_admin_users(users):
    write_json(ADMIN_USERS_FILE, users)


def load_sessions():
    sessions = read_json(SESSIONS_FILE)
    if not isinstance(sessions, list):
        sessions = []

    now = utc_now()
    active = []
    changed = False
    for s in sessions:
        if not isinstance(s, dict):
            changed = True
            continue
        expires = parse_iso(s.get("expiresAt", ""))
        if not expires or expires <= now:
            changed = True
            continue
        if not s.get("token") or not s.get("username"):
            changed = True
            continue
        active.append(s)

    if changed:
        write_json(SESSIONS_FILE, active)

    return active


def save_sessions(sessions):
    write_json(SESSIONS_FILE, sessions)


def create_session(username: str, ip: str):
    sessions = load_sessions()
    token = secrets.token_urlsafe(32)
    now = utc_now()
    sessions.append(
        {
            "token": token,
            "username": normalize_username(username),
            "ip": ip,
            "createdAt": utc_iso(now),
            "expiresAt": utc_iso(now + timedelta(hours=SESSION_HOURS)),
        }
    )
    save_sessions(sessions)
    return token


def revoke_session(token: str):
    sessions = load_sessions()
    filtered = [s for s in sessions if s.get("token") != token]
    if len(filtered) != len(sessions):
        save_sessions(filtered)


def parse_cookies(cookie_header: str):
    cookies = {}
    for part in (cookie_header or "").split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        cookies[key.strip()] = value.strip()
    return cookies


def get_client_ip(handler: BaseHTTPRequestHandler) -> str:
    xff = handler.headers.get("X-Forwarded-For", "").strip()
    if xff:
        return xff.split(",")[0].strip()
    if handler.client_address and len(handler.client_address) > 0:
        return str(handler.client_address[0])
    return "unknown"


def get_authenticated_user(handler: BaseHTTPRequestHandler):
    cookies = parse_cookies(handler.headers.get("Cookie", ""))
    token = cookies.get(SESSION_COOKIE)
    if not token:
        return None

    for session in load_sessions():
        if session.get("token") == token:
            return session.get("username")
    return None


def compute_stats(stats_base, videos, events):
    visits = events.get("visits", []) if isinstance(events, dict) else []
    downloads = events.get("downloads", []) if isinstance(events, dict) else []
    admin_attempts = events.get("adminLoginAttempts", []) if isinstance(events, dict) else []

    uploader_set = set(v.get("uploader", "unknown") for v in videos if isinstance(v, dict))
    uploader_set.discard("")
    uploader_set.discard("unknown")

    visitor_ips = set(v.get("ip", "unknown") for v in visits if isinstance(v, dict))
    visitor_ips.discard("")

    downloader_ips = set(d.get("ip", "unknown") for d in downloads if isinstance(d, dict))
    downloader_ips.discard("")

    attempt_ips = set(a.get("ip", "unknown") for a in admin_attempts if isinstance(a, dict))
    attempt_ips.discard("")

    return {
        "downloads": len(downloads),
        "users": len(uploader_set),
        "episodes": len(videos),
        "series": int(stats_base.get("series", 0)) if isinstance(stats_base, dict) else 0,
        "visitorsTotal": len(visits),
        "uniqueVisitors": len(visitor_ips),
        "uniqueDownloaders": len(downloader_ips),
        "adminLoginAttempts": len(admin_attempts),
        "adminLoginAttemptIps": len(attempt_ips),
        "recentAdminAttempts": admin_attempts[-10:],
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def _send_json(self, data, status=200, extra_headers=None):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location: str):
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.end_headers()

    def _serve_file(self, relative_path: str, no_cache=False):
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
        if no_cache:
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        ip = get_client_ip(self)
        current_user = get_authenticated_user(self)

        if path.startswith("/admin/") and path != "/admin/login.html" and not current_user:
            self._redirect("/admin/login.html")
            return

        if path == "/api/stats":
            stats_base = read_json(STATS_FILE)
            videos = read_json(VIDEOS_FILE)
            events = read_json(EVENTS_FILE)
            self._send_json(compute_stats(stats_base, videos, events))
            return

        if path == "/api/videos":
            self._send_json(read_json(VIDEOS_FILE))
            return

        if path == "/api/me":
            if not current_user:
                self._send_json({"ok": False, "error": "non authentifie"}, 401)
                return
            self._send_json({"ok": True, "username": current_user})
            return

        if path == "/api/admin-users":
            if not current_user:
                self._send_json({"ok": False, "error": "non authentifie"}, 401)
                return
            users = load_admin_users()
            public_users = [{"username": u.get("username"), "createdAt": u.get("createdAt")} for u in users]
            self._send_json({"users": public_users, "count": len(public_users)})
            return

        if path.startswith("/uploads/"):
            events = read_json(EVENTS_FILE)
            if not isinstance(events, dict):
                events = {"visits": [], "downloads": [], "adminLoginAttempts": []}
            events.setdefault("downloads", []).append(
                {
                    "ip": ip,
                    "path": path,
                    "at": utc_iso(),
                }
            )
            write_json(EVENTS_FILE, events)
            self._serve_file(path)
            return

        if path in [
            "/",
            "/index.html",
            "/admin/login.html",
            "/admin/dashboard.html",
            "/admin/series.html",
            "/admin/films.html",
            "/admin/upload.html",
            "/admin/users.html",
            "/admin/statistics.html",
            "/admin/settings.html",
        ]:
            if path in ["/", "/index.html"]:
                events = read_json(EVENTS_FILE)
                if not isinstance(events, dict):
                    events = {"visits": [], "downloads": [], "adminLoginAttempts": []}
                events.setdefault("visits", []).append(
                    {
                        "ip": ip,
                        "path": path,
                        "at": utc_iso(),
                    }
                )
                write_json(EVENTS_FILE, events)

            if path == "/":
                self._serve_file("index.html")
            else:
                self._serve_file(path.lstrip("/"), no_cache=path.startswith("/admin/"))
            return

        self._serve_file(path.lstrip("/"))

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        current_user = get_authenticated_user(self)

        if path == "/api/upload":
            if not current_user:
                self._send_json({"ok": False, "error": "non authentifie"}, 401)
                return

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
                cd = part.get("Content-Disposition", "") or ""
                match = re.search(r'name="([^"]+)"', cd)
                name = match.group(1) if match else None
                if not name:
                    continue
                if part.get_filename():
                    file_part = part
                else:
                    try:
                        form_fields[name] = part.get_content()
                    except Exception:
                        form_fields[name] = part.get_payload(decode=True).decode("utf-8", "ignore")

            if file_part is None:
                self._send_json({"ok": False, "error": "aucun fichier recu"}, 400)
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
            if not isinstance(videos, list):
                videos = []
            qs = parse_qs(parsed.query)
            uploader = (qs.get("uploader") or [None])[0] or form_fields.get("uploader") or current_user
            videos.insert(
                0,
                {
                    "id": len(videos) + 1,
                    "name": safe_name,
                    "path": f"/uploads/{safe_name}",
                    "size": save_path.stat().st_size,
                    "uploadedAt": utc_iso(),
                    "uploader": normalize_username(uploader),
                },
            )
            write_json(VIDEOS_FILE, videos)
            self._send_json({"ok": True, "file": f"/uploads/{safe_name}"})
            return

        if path == "/api/admin-login":
            content_length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(content_length)
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception:
                self._send_json({"ok": False, "error": "payload invalide"}, 400)
                return

            username = normalize_username(payload.get("username", ""))
            password = str(payload.get("password", "")).strip()
            ip = get_client_ip(self)

            users = load_admin_users()
            ok = False
            for user in users:
                if user.get("username") == username and verify_password_record(user, password):
                    ok = True
                    if not user.get("passwordSalt"):
                        upgraded = create_password_record(password)
                        user["passwordSalt"] = upgraded["passwordSalt"]
                        user["passwordHash"] = upgraded["passwordHash"]
                        user["iterations"] = upgraded["iterations"]
                        save_admin_users(users)
                    break

            events = read_json(EVENTS_FILE)
            if not isinstance(events, dict):
                events = {"visits": [], "downloads": [], "adminLoginAttempts": []}
            events.setdefault("adminLoginAttempts", []).append(
                {"ip": ip, "username": username, "ok": ok, "at": utc_iso()}
            )
            write_json(EVENTS_FILE, events)

            if not ok:
                self._send_json({"ok": False})
                return

            token = create_session(username, ip)
            cookie = f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={SESSION_HOURS * 3600}"
            self._send_json({"ok": True, "username": username}, extra_headers={"Set-Cookie": cookie})
            return

        if path == "/api/admin-logout":
            cookie_token = parse_cookies(self.headers.get("Cookie", "")).get(SESSION_COOKIE)
            if cookie_token:
                revoke_session(cookie_token)
            clear_cookie = f"{SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"
            self._send_json({"ok": True}, extra_headers={"Set-Cookie": clear_cookie})
            return

        if path == "/api/admin-users":
            if not current_user:
                self._send_json({"ok": False, "error": "non authentifie"}, 401)
                return

            content_length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(content_length)
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception:
                self._send_json({"ok": False, "error": "payload invalide"}, 400)
                return

            username = normalize_username(payload.get("username", ""))
            password = str(payload.get("password", "")).strip()
            if len(username) < 3:
                self._send_json({"ok": False, "error": "username trop court"}, 400)
                return
            if len(password) < 6:
                self._send_json({"ok": False, "error": "mot de passe trop court"}, 400)
                return

            users = load_admin_users()
            if any(u.get("username") == username for u in users):
                self._send_json({"ok": False, "error": "compte deja existant"}, 400)
                return

            new_record = create_password_record(password)
            users.append(
                {
                    "username": username,
                    "passwordSalt": new_record["passwordSalt"],
                    "passwordHash": new_record["passwordHash"],
                    "iterations": new_record["iterations"],
                    "createdAt": utc_iso(),
                }
            )
            save_admin_users(users)
            self._send_json({"ok": True, "username": username})
            return

        if path == "/api/admin-password":
            if not current_user:
                self._send_json({"ok": False, "error": "non authentifie"}, 401)
                return

            content_length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(content_length)
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception:
                self._send_json({"ok": False, "error": "payload invalide"}, 400)
                return

            current_password = str(payload.get("currentPassword", "")).strip()
            new_password = str(payload.get("newPassword", "")).strip()
            if len(new_password) < 6:
                self._send_json({"ok": False, "error": "nouveau mot de passe trop court"}, 400)
                return

            users = load_admin_users()
            updated = False
            for user in users:
                if user.get("username") == current_user:
                    if not verify_password_record(user, current_password):
                        self._send_json({"ok": False, "error": "mot de passe actuel invalide"}, 400)
                        return
                    new_record = create_password_record(new_password)
                    user["passwordSalt"] = new_record["passwordSalt"]
                    user["passwordHash"] = new_record["passwordHash"]
                    user["iterations"] = new_record["iterations"]
                    updated = True
                    break

            if not updated:
                self._send_json({"ok": False, "error": "compte introuvable"}, 404)
                return

            save_admin_users(users)
            self._send_json({"ok": True})
            return

        if path == "/api/admin-users/delete":
            if not current_user:
                self._send_json({"ok": False, "error": "non authentifie"}, 401)
                return

            content_length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(content_length)
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception:
                self._send_json({"ok": False, "error": "payload invalide"}, 400)
                return

            username = normalize_username(payload.get("username", ""))
            if not username:
                self._send_json({"ok": False, "error": "username requis"}, 400)
                return
            if username == current_user:
                self._send_json({"ok": False, "error": "suppression de votre compte interdite"}, 400)
                return
            if username == "anis":
                self._send_json({"ok": False, "error": "compte principal protege"}, 400)
                return

            users = load_admin_users()
            kept = [u for u in users if u.get("username") != username]
            if len(kept) == len(users):
                self._send_json({"ok": False, "error": "compte introuvable"}, 404)
                return

            save_admin_users(kept)
            self._send_json({"ok": True, "deleted": username})
            return

        self.send_error(404)


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    requested_port = int(os.environ.get("PORT", "8000"))

    # Try a short range of ports to avoid startup failure when 8000/8001 are occupied.
    candidate_ports = [requested_port]
    candidate_ports.extend(p for p in range(8000, 8011) if p not in candidate_ports)

    server = None
    port = requested_port
    last_exc = None
    for candidate in candidate_ports:
        try:
            server = ThreadingHTTPServer((host, candidate), Handler)
            port = candidate
            break
        except OSError as exc:
            last_exc = exc
            continue

    if server is None:
        raise last_exc

    print(f"Serveur lance sur http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
