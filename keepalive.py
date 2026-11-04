"""Self-revive: (1) khud ko ping (Render free idle-sleep se bachao), (2) watchdogs (bot thread etc.),
(3) supervised threads (crash par khud dobara), (4) sibling panels ki status + 'wake' (optional auto-ping)."""
import os, time, threading, urllib.request
import panel

INTERVAL = max(60, int(os.environ.get("KEEPALIVE_INTERVAL", "600") or 600))
ENABLED = os.environ.get("KEEPALIVE", "true").lower() not in ("0", "false", "no", "off")
BASE = (os.environ.get("KEEPALIVE_URL") or os.environ.get("RENDER_EXTERNAL_URL") or "").rstrip("/")
PING_SIBLINGS = os.environ.get("KEEPALIVE_SIBLINGS", "false").lower() in ("1", "true", "yes", "on")

state = {"enabled": ENABLED and bool(BASE), "url": BASE, "interval": INTERVAL, "last_ping": None, "last_ok": None, "last_error": None,
         "pings": 0, "fails": 0, "watchdog_restarts": 0, "thread_restarts": 0, "siblings_ping": PING_SIBLINGS}
_watchdogs = []
_sib = {}            # key -> {ok, ms, checked, status}
_sib_busy = set()


def _get(url, timeout=20):
    t0 = time.time()
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "ff-keepalive"}), timeout=timeout) as r:
        return r.status, int((time.time() - t0) * 1000)


def _ping():
    state["pings"] += 1; state["last_ping"] = int(time.time())
    try:
        code, _ = _get(BASE + "/health")
        if code != 200: raise RuntimeError(f"HTTP {code}")
        state["last_ok"] = int(time.time()); state["last_error"] = None
    except Exception as e:
        state["fails"] += 1; state["last_error"] = str(e)[:200]


def _ping_loop():
    time.sleep(30)
    while True:
        _ping()
        if PING_SIBLINGS:
            for s in panel.siblings():
                check_sibling(s["key"], wait=True)
        time.sleep(INTERVAL)


def add_watchdog(fn):
    _watchdogs.append(fn)


def _watchdog_loop():
    time.sleep(90)
    while True:
        for fn in list(_watchdogs):
            try:
                if fn(): state["watchdog_restarts"] += 1
            except Exception as e:
                print("[watchdog]", e, flush=True)
        time.sleep(45)


def supervised(name, fn, delay=10):
    """fn ko thread mein chalao; crash ho to `delay` s baad dobara (state['thread_restarts'] badhta hai)."""
    def run():
        while True:
            try:
                fn()
                return
            except Exception as e:
                state["thread_restarts"] += 1
                print(f"[supervised:{name}] crash: {e} — {delay}s baad restart", flush=True)
                time.sleep(delay)
    threading.Thread(target=run, daemon=True, name=name).start()


# ---------------------------------------------------------------- siblings
def _check(key, url, timeout):
    try:
        code, ms = _get(url.rstrip("/") + "/health", timeout)
        _sib[key] = {"ok": code == 200, "ms": ms, "checked": int(time.time()), "status": "up" if code == 200 else f"HTTP {code}"}
    except Exception as e:
        _sib[key] = {"ok": False, "ms": None, "checked": int(time.time()), "status": "sleeping / down"}
    finally:
        _sib_busy.discard(key)


def check_sibling(key, wait=False, timeout=8):
    s = next((x for x in panel.siblings() if x["key"] == key), None)
    if not s or key in _sib_busy: return
    _sib_busy.add(key)
    t = threading.Thread(target=_check, args=(key, s["url"], timeout), daemon=True, name="sib-" + key)
    t.start()
    if wait: t.join(timeout + 2)


def siblings_view(refresh=True):
    out = []
    for s in panel.siblings():
        c = _sib.get(s["key"])
        if refresh and (not c or time.time() - c["checked"] > 25):
            check_sibling(s["key"])
        out.append({**s, **(c or {"ok": None, "ms": None, "checked": None, "status": "checking…"})})
    return out


def wake(key):
    """Sibling ko jagao: /health par lamba (60s) intezaar background mein."""
    check_sibling(key, timeout=70)
    return True


def start():
    threading.Thread(target=_watchdog_loop, daemon=True, name="watchdog").start()
    if state["enabled"]:
        threading.Thread(target=_ping_loop, daemon=True, name="keepalive").start()
        print(f"[keepalive] har {INTERVAL}s par {BASE}/health ping hoga", flush=True)
    else:
        print("[keepalive] off — RENDER_EXTERNAL_URL / KEEPALIVE_URL nahi mila ya KEEPALIVE=false", flush=True)
