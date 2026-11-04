"""Render ki jaankari: is service ki info (env se), Render platform status (public), aur optional Render API
(RENDER_API_KEY + RENDER_SERVICE_ID) se deploy status + restart. Sab cache hota hai, request thread kabhi atakta nahi."""
import os, json, time, threading, urllib.request

STATUS_URL = "https://status.render.com/api/v2/summary.json"
API = "https://api.render.com/v1"
_cache, _lock = {}, threading.Lock()
_running = set()


def _http(url, method="GET", headers=None, data=None, timeout=8):
    req = urllib.request.Request(url, data=data, method=method, headers={"User-Agent": "ff-admin", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        return json.loads(raw.decode() or "null") if raw else None


def _bg(key, ttl, fn):
    """Cache return karo; purana ho to background thread mein refresh (request block nahi hoti)."""
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        stale = (not hit) or now - hit["t"] > ttl
        if stale and key not in _running:
            _running.add(key)
            def run():
                try: val, err = fn(), None
                except Exception as e: val, err = None, str(e)[:160]
                with _lock:
                    _cache[key] = {"t": time.time(), "v": val, "e": err}
                    _running.discard(key)
            threading.Thread(target=run, daemon=True, name="ri-" + key).start()
        return dict(hit) if hit else {"t": 0, "v": None, "e": None}


def _platform():
    d = _http(STATUS_URL, timeout=6) or {}
    st = d.get("status") or {}
    inc = [{"name": i.get("name"), "status": i.get("status"), "impact": i.get("impact")} for i in (d.get("incidents") or [])][:3]
    bad = [c.get("name") for c in (d.get("components") or []) if c.get("status") not in ("operational", None) and not c.get("group")][:4]
    return {"indicator": st.get("indicator", "none"), "description": st.get("description", ""), "incidents": inc, "degraded": bad}


def _api_key():
    return (os.environ.get("RENDER_API_KEY") or "").strip(), (os.environ.get("RENDER_SERVICE_ID") or "").strip()


def can_restart():
    k, s = _api_key()
    return bool(k and s)


def _service():
    k, sid = _api_key()
    h = {"Authorization": "Bearer " + k, "Accept": "application/json"}
    svc = _http(f"{API}/services/{sid}", headers=h) or {}
    dep = _http(f"{API}/services/{sid}/deploys?limit=1", headers=h) or []
    d = (dep[0].get("deploy") if dep and isinstance(dep[0], dict) and "deploy" in dep[0] else (dep[0] if dep else {})) or {}
    return {"suspended": svc.get("suspended"), "type": svc.get("type"), "region": (svc.get("serviceDetails") or {}).get("region"),
            "deploy": {"status": d.get("status"), "finishedAt": d.get("finishedAt"), "commit": ((d.get("commit") or {}).get("message") or "")[:80]}}


def restart():
    k, sid = _api_key()
    if not (k and sid):
        raise RuntimeError("RENDER_API_KEY / RENDER_SERVICE_ID env set nahi hain")
    _http(f"{API}/services/{sid}/restart", method="POST", headers={"Authorization": "Bearer " + k, "Accept": "application/json"}, data=b"")
    return True


def info():
    e = os.environ.get
    on_render = bool(e("RENDER") or e("RENDER_SERVICE_ID") or e("RENDER_EXTERNAL_URL"))
    out = {"on_render": on_render, "service": e("RENDER_SERVICE_NAME") or "local", "url": e("RENDER_EXTERNAL_URL") or "",
           "commit": (e("RENDER_GIT_COMMIT") or "")[:7], "branch": e("RENDER_GIT_BRANCH") or "", "instance": (e("RENDER_INSTANCE_ID") or "")[-8:],
           "api_configured": can_restart()}
    p = _bg("platform", 300, _platform)
    out["platform"] = p["v"]; out["platform_error"] = p["e"]
    if can_restart():
        s = _bg("service", 120, _service)
        out["api"] = s["v"]; out["api_error"] = s["e"]
    return out
