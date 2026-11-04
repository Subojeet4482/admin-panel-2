"""UptimeRobot status (API v2). Env: UPTIMEROBOT_API_KEY (read-only key chalegi), optional UPTIMEROBOT_MONITOR (naam ya id).
Is service ka monitor URL (RENDER_EXTERNAL_URL / KEEPALIVE_URL) se ya naam se dhoondha jaata hai. 2 min cache."""
import os, json, time, threading, urllib.request, urllib.parse
from urllib.parse import urlparse

API = "https://api.uptimerobot.com/v2/getMonitors"
STATUS = {0: "paused", 1: "pending", 2: "up", 8: "seems_down", 9: "down"}
_c = {"t": 0, "v": None, "e": None}
_run = {"on": False}
_lk = threading.Lock()


def own_url():
    return (os.environ.get("KEEPALIVE_URL") or os.environ.get("RENDER_EXTERNAL_URL") or "").rstrip("/")


def health_url():
    u = own_url()
    return (u + "/health") if u else ""


def _fetch():
    body = urllib.parse.urlencode({"api_key": os.environ["UPTIMEROBOT_API_KEY"].strip(), "format": "json", "logs": 0,
                                   "custom_uptime_ratios": "1-7-30", "response_times": 1, "response_times_average": 1440}).encode()
    req = urllib.request.Request(API, data=body, headers={"Content-Type": "application/x-www-form-urlencoded", "Cache-Control": "no-cache", "User-Agent": "ff-admin"})
    with urllib.request.urlopen(req, timeout=10) as r:
        d = json.loads(r.read().decode())
    if d.get("stat") != "ok":
        raise RuntimeError((d.get("error") or {}).get("message") or "UptimeRobot API error")
    return d.get("monitors") or []


def _pick(mons):
    want = (os.environ.get("UPTIMEROBOT_MONITOR") or "").strip().lower()
    host = urlparse(own_url()).netloc.lower()
    for m in mons:
        if want and want in (str(m.get("id")), (m.get("friendly_name") or "").lower()):
            return m
    for m in mons:
        if host and host in (m.get("url") or "").lower():
            return m
    return None


def _shape(m):
    r = (m.get("custom_uptime_ratio") or "").split("-")
    f = lambda i: (float(r[i]) if len(r) > i and r[i] not in ("", None) else None)
    return {"name": m.get("friendly_name"), "url": m.get("url"), "status": STATUS.get(m.get("status"), "unknown"),
            "uptime": {"d1": f(0), "d7": f(1), "d30": f(2)}, "avg_ms": m.get("average_response_time")}


def _refresh():
    try:
        mons = _fetch(); m = _pick(mons)
        v = {"found": bool(m), "monitor": _shape(m) if m else None, "count": len(mons)}
        e = None
    except Exception as ex:
        v, e = None, str(ex)[:160]
    with _lk:
        _c.update(t=time.time(), v=v, e=e); _run["on"] = False


def status():
    """Hamesha turant cache deta hai; purana ho to background mein refresh."""
    out = {"configured": bool(os.environ.get("UPTIMEROBOT_API_KEY")), "health_url": health_url(), "found": False, "monitor": None, "error": None}
    if not out["configured"]:
        return out
    with _lk:
        if time.time() - _c["t"] > 120 and not _run["on"]:
            _run["on"] = True
            threading.Thread(target=_refresh, daemon=True, name="ur-refresh").start()
        v, e = _c["v"], _c["e"]
    if v: out.update(v)
    out["error"] = e
    return out
