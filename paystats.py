"""Payments dashboard ke numbers (aaj / kal / 7 din / mahina) — pending pool + successful history dono se.
Sirf zaroori fields (select) padhta hai, 40s cache, ek time par ek hi compute."""
import time, threading, datetime as dt
import fb, slow

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
TTL = 40
_c = {"t": 0, "v": None}
_lk = threading.Lock()
FIELDS = ["amount", "receivedAt", "usedAt", "payId", "utr", "txnId", "source"]
LIMIT = 20000


def bust():
    _c["t"] = 0


def _ms(d):
    return int(d.timestamp() * 1000)


def _stream(db, col, field, cutoff):
    q = db.collection(col).where(field, ">=", cutoff).select(FIELDS)
    n = 0
    for s in slow.paced(q.stream(), 300, 0.2):
        yield s
        n += 1
        if n >= LIMIT: break


def compute():
    db = fb.get_db()
    now = dt.datetime.now(IST)
    today0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    cut30 = _ms(today0 - dt.timedelta(days=29))
    month0 = _ms(today0.replace(day=1))
    seen, rows = set(), []
    for col, state in (("fampay_deposits", "pending"), ("fampay_deposits_history", "used")):
        for s in _stream(db, col, "receivedAt", cut30):
            d = s.to_dict() or {}
            pid = d.get("payId") or s.id
            if (state, pid) in seen: continue          # UTR + TxnID ki do copies ek hi payment
            seen.add((state, pid))
            try: amt = float(d.get("amount") or 0)
            except Exception: amt = 0.0
            rows.append({"id": pid, "amount": amt, "at": int(d.get("receivedAt") or 0), "usedAt": d.get("usedAt"), "utr": d.get("utr"),
                         "txnId": d.get("txnId"), "source": d.get("source"), "state": state})
    # pending pool (poora, sirf 30 din nahi — jo abhi tak claim nahi hua)
    pend, pseen = 0.0, set()
    pc = 0
    for s in db.collection("fampay_deposits").select(["amount", "payId"]).limit(3000).stream():
        d = s.to_dict() or {}; pid = d.get("payId") or s.id
        if pid in pseen: continue
        pseen.add(pid); pc += 1
        try: pend += float(d.get("amount") or 0)
        except Exception: pass
    days = {}
    for i in range(30):
        k = (today0 - dt.timedelta(days=i)).strftime("%Y-%m-%d")
        days[k] = {"date": k, "total": 0.0, "count": 0}
    t0 = _ms(today0); y0 = _ms(today0 - dt.timedelta(days=1))
    today = {"total": 0.0, "count": 0, "used": 0, "pending": 0}
    yest = {"total": 0.0, "count": 0}
    mtd = {"total": 0.0, "count": 0}
    d30 = {"total": 0.0, "count": 0}
    feed = []
    for r in rows:
        if not r["at"]: continue
        k = dt.datetime.fromtimestamp(r["at"] / 1000, IST).strftime("%Y-%m-%d")
        if k in days:
            days[k]["total"] += r["amount"]; days[k]["count"] += 1
        d30["total"] += r["amount"]; d30["count"] += 1
        if r["at"] >= month0: mtd["total"] += r["amount"]; mtd["count"] += 1
        if r["at"] >= t0:
            today["total"] += r["amount"]; today["count"] += 1
            today["used" if r["state"] == "used" else "pending"] += 1
            feed.append(r)
        elif r["at"] >= y0:
            yest["total"] += r["amount"]; yest["count"] += 1
    feed.sort(key=lambda x: -x["at"])
    chart = [days[k] for k in sorted(days)][-7:]
    best = max(days.values(), key=lambda x: x["total"]) if days else None
    r2 = lambda x: round(x, 2)
    return {"t": int(time.time() * 1000), "today": {**today, "total": r2(today["total"])}, "yesterday": {**yest, "total": r2(yest["total"])},
            "month": {**mtd, "total": r2(mtd["total"])}, "d30": {**d30, "total": r2(d30["total"])},
            "pending_pool": {"count": pc, "total": r2(pend)}, "chart": [{**c, "total": r2(c["total"])} for c in chart],
            "best_day": ({**best, "total": r2(best["total"])} if best and best["total"] else None), "feed": feed[:60]}


def get(force=False):
    if not force and _c["v"] and time.time() - _c["t"] < TTL:
        return _c["v"]
    with _lk:
        if not force and _c["v"] and time.time() - _c["t"] < TTL:
            return _c["v"]
        v = compute()
        _c.update(t=time.time(), v=v)
        return v
