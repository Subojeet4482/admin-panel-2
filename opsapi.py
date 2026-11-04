"""Teeno panels ka common backend: login (owner), session, health, live server numbers, ops status
(Render + UptimeRobot + self-revive + sibling panels), wake, restart."""
import os, time, platform, shutil
from flask import jsonify, request, g
import security, keepalive, sysmon, renderinfo, uptimerobot, panel, fb

BOOT = time.time()
_bad = lambda msg, code=400: (jsonify(ok=False, error=msg), code)


def register_ops(app, bot_status_fn=None, extra_env_fn=None, disk_dir="/"):
    """Login-required ops routes. bot_status_fn() -> dict (slim) panel ke live strip ke liye."""

    @app.get("/api/server/live")
    @security.login_required
    def server_live():
        try:
            slim = bot_status_fn() if bot_status_fn else {}
            snap = sysmon.snapshot(fb.get_db, slim, {k: keepalive.state.get(k) for k in ("enabled", "pings", "fails", "watchdog_restarts", "last_ok")}, disk_dir)
            ur = uptimerobot.status()
            snap["ur"] = {"configured": ur["configured"], "found": ur["found"], "status": (ur.get("monitor") or {}).get("status"),
                          "d30": ((ur.get("monitor") or {}).get("uptime") or {}).get("d30"), "d1": ((ur.get("monitor") or {}).get("uptime") or {}).get("d1")}
            sib = keepalive.siblings_view(refresh=False)
            snap["sib"] = [{"key": s["key"], "ok": s["ok"]} for s in sib]
            snap["panel"] = {"key": panel.KEY, "name": panel.NAME}
            return jsonify(ok=True, **snap)
        except Exception as e:
            return _bad(f"Monitor error: {e}", 500)

    @app.get("/api/panels")
    @security.login_required
    def panels():
        return jsonify(ok=True, panels=panel.siblings(), me=panel.KEY)

    @app.get("/api/ops/status")
    @security.login_required
    def ops_status():
        st = fb.firebase_status()
        if not st["ok"]:
            try: fb.get_db()
            except Exception: pass
            st = fb.firebase_status()
        env = {k: bool(os.environ.get(k)) for k in panel.ENV_KEYS}
        env.update({k + " (optional)": bool(os.environ.get(k)) for k in panel.OPTIONAL})
        if extra_env_fn: env.update(extra_env_fn())
        try: free = shutil.disk_usage(disk_dir)[2]
        except Exception: free = 0
        return jsonify(ok=True, panel={"key": panel.KEY, "name": panel.NAME}, uptime=int(time.time() - BOOT), python=platform.python_version(),
                       render=renderinfo.info(), uptimerobot=uptimerobot.status(), revive=dict(keepalive.state),
                       siblings=keepalive.siblings_view(), firebase=st, env=env, disk_free=free,
                       can_restart=renderinfo.can_restart(), user=g.user.get("u"), session_hours=security.SESSION_HOURS)

    @app.post("/api/ops/wake")
    @security.login_required
    def ops_wake():
        key = (request.get_json(silent=True) or {}).get("key")
        if not any(s["key"] == key for s in panel.siblings()):
            return _bad("Unknown panel")
        keepalive.wake(key)
        return jsonify(ok=True, message="Wake signal bhej diya — free plan par 30-60s lag sakte hain")

    @app.post("/api/ops/restart")
    @security.pin_required
    def ops_restart():
        try:
            renderinfo.restart()
        except Exception as e:
            return _bad(f"Restart nahi hua: {e}", 500)
        return jsonify(ok=True, message="Render ko restart bol diya — 1 min mein wapas aayega")


def register_owner_auth(app):
    """Services 2 & 3: sirf OWNER login (admin/lite creds in panels mein nahi chalte)."""

    @app.get("/health")
    def health():
        return jsonify(ok=True, panel=panel.KEY, uptime=int(time.time() - BOOT))

    @app.post("/api/login")
    def login():
        if not security.creds_ready():
            return _bad("Server par OWNER_EMAIL / OWNER_PASSWORD / OWNER_PIN env set nahi hain (Render → Environment).", 503)
        ip = security.client_ip()
        wait = security.locked_for(ip)
        if wait:
            return _bad(f"Bahut zyada galat attempts. {wait // 60 + 1} minute baad try karo.", 429)
        d = request.get_json(silent=True) or {}
        role = security.check_login_combined(d.get("email"), d.get("password"), d.get("pin"))
        if not role:
            security.register_fail(ip); time.sleep(0.8)
            return _bad("Email, password ya PIN galat hai", 401)
        if role != "owner":
            return _bad("Is panel ke liye OWNER login chahiye (sub-admin sirf Main panel khol sakta hai).", 403)
        security.register_ok(ip)
        resp = jsonify(ok=True, role="owner")
        resp.set_cookie(security.SESSION_COOKIE, security.make_session(security.creds()[0]), max_age=int(security.SESSION_HOURS * 3600),
                        httponly=True, samesite="Strict", secure=request.is_secure)
        return resp

    @app.get("/api/session")
    def session():
        u = security.current_user()
        return jsonify(ok=bool(u), ready=security.creds_ready(), role="owner" if u else None, email=(u or {}).get("u"), panel=panel.NAME)

    @app.post("/api/logout")
    def logout():
        resp = jsonify(ok=True); resp.delete_cookie(security.SESSION_COOKIE); return resp
