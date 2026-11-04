"""FF Payment Bot panel (service 2) — Fampay Gmail bot 24/7 + payments dashboard.
Sirf yahi kaam: bot chalana, aaye payments dikhana, pending/history manage karna. Baaki sab alag services mein."""
import os, time, csv, io, threading
import datetime as dt
from flask import Flask, jsonify, request, send_from_directory, g, Response
from werkzeug.middleware.proxy_fix import ProxyFix

import fb, security, sysmon, keepalive, opsapi, paystats
from fampay_bot import bot

ROOT = os.path.dirname(os.path.abspath(__file__))
PUBLIC = os.path.join(ROOT, "public")

app = Flask(__name__, static_folder=None)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

ok = lambda **k: jsonify(ok=True, **k)
bad = lambda msg, code=400: (jsonify(ok=False, error=msg), code)


@app.after_request
def headers(r):
    r.headers["X-Content-Type-Options"] = "nosniff"
    r.headers["X-Frame-Options"] = "DENY"
    r.headers["Referrer-Policy"] = "same-origin"
    if request.path.startswith("/api/") or request.path.endswith((".html", ".js", ".css")) or request.path == "/":
        r.headers["Cache-Control"] = "no-store"
    return r


@app.before_request
def _t0():
    g._t0 = sysmon.req_start()


@app.after_request
def _t1(resp):
    try:
        if not request.path.startswith(("/api/server/live", "/health")):
            sysmon.req_end(getattr(g, "_t0", time.time()), resp.status_code)
    except Exception:
        pass
    return resp


@app.route("/")
def index():
    return send_from_directory(PUBLIC, "index.html")


@app.route("/<path:p>")
def static_files(p):
    if p.startswith("api/"):
        return bad("Not found", 404)
    return send_from_directory(PUBLIC, p)


opsapi.register_owner_auth(app)


def _slim():
    st = bot.status()
    return {k: st.get(k) for k in ("status", "last_run", "last_saved", "total_saved", "emails_found", "gmail_connected")}


opsapi.register_ops(app, bot_status_fn=_slim, extra_env_fn=bot.env_report)


# ------------------------------------------------------------------ payments dashboard
@app.get("/api/pay/summary")
@security.login_required
def pay_summary():
    try:
        return ok(**paystats.get(force=bool(request.args.get("fresh"))), bot=_slim())
    except Exception as e:
        return bad(f"Firestore error: {e}", 500)


# ------------------------------------------------------------------ bot control
@app.get("/api/bot/status")
@security.login_required
def bot_status():
    return ok(bot=bot.status(), logs=list(bot.logs)[-120:])


@app.post("/api/bot/<action>")
@security.login_required
def bot_action(action):
    if action == "start":
        good, msg = bot.start()
    elif action == "stop":
        good, msg = bot.stop()
    elif action == "poll":
        good, msg = bot.poll_now()
    else:
        return bad("Unknown action", 404)
    return ok(message=msg) if good else bad(msg, 400)


@app.post("/api/bot/settings")
@security.login_required
def bot_settings():
    d = request.get_json(silent=True) or {}
    try:
        bot.save_settings(poll_interval=int(d.get("poll_interval", bot.settings["poll_interval"])), query=d.get("query"))
    except (TypeError, ValueError):
        return bad("Poll interval number hona chahiye")
    return ok(settings=bot.settings)


@app.post("/api/bot/clear-processed")
@security.pin_required
def bot_clear():
    bot.clear_processed()
    return ok()


# ------------------------------------------------------------------ deposits
@app.get("/api/bot/deposits")
@security.login_required
def bot_deposits():
    try:
        snaps = fb.get_db().collection("fampay_deposits").order_by("receivedAt", direction="DESCENDING").limit(150).stream()
        rows = []
        for s in snaps:
            d = s.to_dict() or {}
            if d.get("payId") and d.get("payId") != s.id:
                continue          # UTR / Txn ID ki duplicate copy — ek payment ek hi baar
            rows.append({"id": s.id, **{k: v for k, v in d.items() if k in ("utr", "txnId", "amount", "receivedAt", "source", "addedBy")}})
        return ok(deposits=rows[:80])
    except Exception as e:
        return bad(f"Firestore error: {e}", 500)


@app.post("/api/bot/deposits")
@security.login_required
def bot_deposit_add():
    d = request.get_json(silent=True) or {}
    try:
        amount = float(d.get("amount")); assert amount > 0
    except Exception:
        return bad("Amount sahi number hona chahiye")
    utr = (d.get("utr") or "").strip() or None
    txn_id = (d.get("txnId") or "").strip() or None
    if not (utr or txn_id):
        return bad("UTR ya Transaction ID mein se kam se kam ek do")
    try:
        did = bot.save_deposit(amount, utr, txn_id, source="manual", added_by=g.user.get("u"))
    except ValueError as e:
        return bad(str(e))
    except Exception as e:
        return bad(f"Firestore error: {e}", 500)
    if not did:
        return bad("Yeh UTR/Transaction ID pehle se maujood hai (duplicate)")
    paystats.bust()
    return ok(id=did)


@app.post("/api/bot/deposits/<dep_id>/delete")
@security.pin_required
def bot_deposit_delete(dep_id):
    try:
        bot.delete_deposit(dep_id)
    except Exception as e:
        return bad(f"Firestore error: {e}", 500)
    paystats.bust()
    return ok()


@app.post("/api/bot/deposits/<dep_id>/use")
@security.login_required
def bot_deposit_use(dep_id):
    d = request.get_json(silent=True) or {}
    try:
        row = bot.mark_used(dep_id, used_by=g.user.get("u"), note=d.get("note"))
    except ValueError as e:
        return bad(str(e), 404)
    except Exception as e:
        return bad(f"Firestore error: {e}", 500)
    paystats.bust()
    return ok(row=row)


def _days(rng):
    return {"today": 1, "7d": 7, "30d": 30, "all": None}.get(rng, None)


@app.get("/api/bot/deposits/history")
@security.login_required
def bot_deposit_history():
    rng = (request.args.get("range") or "7d").strip().lower()
    try:
        return ok(history=bot.history_list(days=_days(rng), limit=300))
    except Exception as e:
        return bad(f"Firestore error: {e}", 500)


@app.get("/api/bot/deposits/history/export")
@security.login_required
def bot_deposit_history_export():
    rng = (request.args.get("range") or "all").strip().lower()
    try:
        rows = bot.history_list(days=_days(rng), limit=5000)
    except Exception as e:
        return bad(f"Firestore error: {e}", 500)
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["id", "utr", "txnId", "amount", "source", "receivedAt", "usedBy", "usedAt", "note"])
    fmt = lambda ms: dt.datetime.fromtimestamp(ms / 1000, paystats.IST).strftime("%Y-%m-%d %H:%M:%S") if ms else ""
    for r in rows:
        w.writerow([r.get("id", ""), r.get("utr") or "", r.get("txnId") or "", r.get("amount", ""), r.get("source", ""),
                    fmt(r.get("receivedAt")), r.get("usedBy") or "", fmt(r.get("usedAt")), r.get("note") or ""])
    resp = Response(buf.getvalue().encode("utf-8-sig"), mimetype="text/csv")
    resp.headers["Content-Disposition"] = f'attachment; filename="fampay_history_{rng}.csv"'
    return resp


@app.post("/api/bot/deposits/history/delete-old")
@security.pin_required
def bot_deposit_history_delete_old():
    d = request.get_json(silent=True) or {}
    try:
        days = float(d.get("days")); assert days >= 0
    except Exception:
        return bad("Days number hona chahiye")
    try:
        n = bot.history_delete_before(days)
    except Exception as e:
        return bad(f"Firestore error: {e}", 500)
    paystats.bust()
    return ok(deleted=n)


@app.errorhandler(500)
def _json_500(e):
    if request.path.startswith("/api/"):
        return jsonify(ok=False, error="Server error"), 500
    return e


# ------------------------------------------------------------------ boot + watchdog
def bot_watchdog():
    """Bot 24/7: thread mar gaya to dobara start; zinda par atka (heartbeat purana) to naya thread."""
    if not (bot.settings.get("enabled") and bot.configured() and not bot.stop_flag.is_set()):
        return False
    alive = bot.thread and bot.thread.is_alive()
    stale = time.time() - bot.beat
    limit = max(300, int(bot.settings.get("poll_interval", 15)) * 3 + 240)
    if not alive:
        good, _ = bot.start(persist=False)
        if good: bot.log("watchdog: bot band mila, dobara start kiya", "warn")
        return bool(good)
    if stale > limit:
        return bool(bot.restart(f"{int(stale)}s se heartbeat nahi — atka hua tha"))
    return False


_booted, _lock = False, threading.Lock()


def boot():
    global _booted
    with _lock:
        if _booted: return
        _booted = True
    if not security.creds_ready():
        print("[warn] OWNER_EMAIL/PASSWORD/PIN set nahi — login disabled", flush=True)
    threading.Thread(target=bot.autostart, daemon=True, name="bot-boot").start()
    keepalive.add_watchdog(bot_watchdog)
    keepalive.start()


boot()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
