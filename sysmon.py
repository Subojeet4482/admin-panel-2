"""Live server monitor — RAM / CPU / disk / load / requests / Firestore latency.

Linux (Render) ke /proc aur cgroup se padhta hai, koi extra package nahi chahiye (psutil nahi).
Container ki asli limit (cgroup) dikhata hai, host ki nahi.
"""
import os, time, shutil, threading, platform
from collections import deque

BOOT = time.time()
_lock = threading.Lock()
_req = {"total": 0, "errors": 0, "times": deque(maxlen=2000), "lat": deque(maxlen=200)}
_cpu_prev = {"t": None, "u": None}
_fs = {"t": 0, "ms": None, "ok": None, "running": False}


def _read(path, default=None):
    try:
        with open(path, "r") as f:
            return f.read()
    except Exception:
        return default


# ---- request counters (Flask hooks) ----
def req_start():
    return time.time()


def req_end(t0, status):
    now = time.time()
    with _lock:
        _req["total"] += 1
        _req["times"].append(now)
        _req["lat"].append((now - t0) * 1000.0)
        if status >= 500:
            _req["errors"] += 1


# ---- memory ----
def _meminfo():
    out = {}
    for line in (_read("/proc/meminfo", "") or "").splitlines():
        k, _, v = line.partition(":")
        try:
            out[k] = int(v.strip().split()[0]) * 1024
        except Exception:
            pass
    return out


def memory():
    mi = _meminfo()
    host_total = mi.get("MemTotal", 0)
    host_used = host_total - mi.get("MemAvailable", 0) if host_total else 0
    limit = used = 0
    cur = _read("/sys/fs/cgroup/memory.current")          # cgroup v2
    mx = _read("/sys/fs/cgroup/memory.max")
    if cur is None:                                         # cgroup v1
        cur = _read("/sys/fs/cgroup/memory/memory.usage_in_bytes")
        mx = _read("/sys/fs/cgroup/memory/memory.limit_in_bytes")
    try:
        used = int(cur)
    except Exception:
        used = 0
    try:
        limit = int(mx) if mx and mx.strip() != "max" else 0
    except Exception:
        limit = 0
    if not limit or (host_total and limit > host_total * 2):
        limit = host_total
    if not used:
        used = host_used
    return {"used": used, "total": limit, "pct": round(used * 100.0 / limit, 1) if limit else 0}


def _proc_rss(pid):
    for line in (_read(f"/proc/{pid}/status", "") or "").splitlines():
        if line.startswith("VmRSS:"):
            try:
                return int(line.split()[1]) * 1024
            except Exception:
                return 0
    return 0


def processes():
    """Is container ke python/gunicorn processes ki count + RSS."""
    n = rss = 0
    try:
        for pid in os.listdir("/proc"):
            if not pid.isdigit():
                continue
            cmd = (_read(f"/proc/{pid}/cmdline", "") or "").replace("\0", " ")
            if "gunicorn" in cmd or "python" in cmd:
                n += 1
                rss += _proc_rss(pid)
    except Exception:
        pass
    return n, rss


# ---- cpu ----
def _ncpu_limit():
    cm = _read("/sys/fs/cgroup/cpu.max")
    if cm:
        q, _, p = cm.strip().partition(" ")
        try:
            if q != "max":
                return max(0.05, int(q) / int(p))
        except Exception:
            pass
    return float(os.cpu_count() or 1)


def cpu_percent():
    now = time.time()
    usage = None
    st = _read("/sys/fs/cgroup/cpu.stat")
    if st:
        for line in st.splitlines():
            if line.startswith("usage_usec"):
                usage = int(line.split()[1]) / 1e6
    if usage is None:
        u1 = _read("/sys/fs/cgroup/cpuacct/cpuacct.usage")
        if u1:
            try:
                usage = int(u1) / 1e9
            except Exception:
                usage = None
    if usage is None:                                       # fallback: process CPU time
        t = os.times()
        usage = t.user + t.system
    pct = 0.0
    with _lock:
        if _cpu_prev["t"] is not None and now > _cpu_prev["t"]:
            pct = (usage - _cpu_prev["u"]) / (now - _cpu_prev["t"]) / _ncpu_limit() * 100.0
        _cpu_prev["t"], _cpu_prev["u"] = now, usage
    return round(max(0.0, min(100.0, pct)), 1)


def _fs_probe(get_db):
    try:
        t0 = time.time()
        get_db().collection("bot_meta").document("settings").get(timeout=8)
        _fs["ms"], _fs["ok"] = round((time.time() - t0) * 1000), True
    except Exception:
        _fs["ms"], _fs["ok"] = None, False
    finally:
        _fs["running"] = False


def firestore_latency(get_db):
    """Firestore ping BACKGROUND thread mein (8s timeout) — request thread kabhi block nahi hota.
    Pehle yeh call request ke andar hota tha, Firestore atakne par panel ke saare threads phas jaate the."""
    now = time.time()
    if not _fs["running"] and now - _fs["t"] >= 15:
        _fs["t"], _fs["running"] = now, True
        threading.Thread(target=_fs_probe, args=(get_db,), daemon=True, name="fs-probe").start()
    elif _fs["running"] and now - _fs["t"] > 30:     # probe 30s se zyada atka -> DB issue maano
        _fs["ok"], _fs["ms"] = False, None
    return _fs["ms"], _fs["ok"]


def snapshot(get_db, bot_status=None, keepalive_state=None, backup_dir="/"):
    now = time.time()
    try:
        d_total, d_used, d_free = shutil.disk_usage(backup_dir if os.path.exists(backup_dir) else "/")
    except Exception:
        d_total = d_used = d_free = 0
    try:
        load = os.getloadavg()
    except Exception:
        load = (0, 0, 0)
    nproc, rss = processes()
    thr = 0
    for line in (_read("/proc/self/status", "") or "").splitlines():
        if line.startswith("Threads:"):
            thr = int(line.split()[1])
    try:
        fds = len(os.listdir("/proc/self/fd"))
    except Exception:
        fds = 0
    with _lock:
        last60 = sum(1 for t in _req["times"] if now - t <= 60)
        lat = list(_req["lat"])
        total, errs = _req["total"], _req["errors"]
    fs_ms, fs_ok = firestore_latency(get_db)
    return {
        "t": int(now * 1000),
        "uptime": int(now - BOOT),
        "python": platform.python_version(),
        "cpu": cpu_percent(), "cores": round(_ncpu_limit(), 2),
        "load": [round(x, 2) for x in load],
        "mem": memory(), "proc_rss": rss, "procs": nproc, "threads": thr, "fds": fds,
        "disk": {"used": d_used, "total": d_total, "pct": round(d_used * 100.0 / d_total, 1) if d_total else 0},
        "req": {"total": total, "per_min": last60, "errors": errs, "avg_ms": round(sum(lat) / len(lat)) if lat else 0},
        "firestore": {"ms": fs_ms, "ok": fs_ok},
        "bot": bot_status or {},
        "keepalive": keepalive_state or {},
        "pid": os.getpid(),
    }
