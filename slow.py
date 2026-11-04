"""Slow-mode helpers — Fampay bot sabse pehle, baaki sab heavy kaam dheere-dheere.

Render free plan mein CPU bahut kam hai (~0.1 core). Isliye har heavy kaam (backup, user list,
cleanup, data center, delete) chhote tukdon mein chalta hai aur beech beech mein aaram karta hai,
taaki bot aur panel ke requests ko hamesha CPU mile.

Env (sab optional):
  SLOW_FACTOR         1   -> 2 karo to sab aaram aur dheema, 0.5 karo to thoda tez
  BACKUP_PACE_EVERY   10  -> backup mein itne docs ke baad aaram
  BACKUP_PACE_REST    1.0 -> aaram ke seconds (auto-backup mein yeh 2x ho jata hai)
"""
import os, time, threading

FACTOR = max(0.1, float(os.environ.get("SLOW_FACTOR", "1") or 1))

def set_factor(x):
    """Panel se delay/speed badalna (0.25 = turbo ... 4 = ultra slow)."""
    global FACTOR
    FACTOR = max(0.1, min(10.0, float(x)))
    return FACTOR


# ---- bot priority: bot jab Gmail poll kar raha ho, heavy kaam ruk jaate hain ----
_busy_since = 0.0


def bot_busy_on():
    global _busy_since
    _busy_since = time.time()


def bot_busy_off():
    global _busy_since
    _busy_since = 0.0


def _wait_bot(max_s=20):
    t0 = time.time()
    # bot 60s se zyada "busy" dikhe (atka hua) to uska intezaar nahi karte
    while _busy_since and time.time() - _busy_since < 60 and time.time() - t0 < max_s:
        time.sleep(0.25)


def rest(sec):
    """Heavy kaam ke beech aaram (bot busy ho to pehle wo)."""
    _wait_bot()
    time.sleep(max(0.0, sec) * FACTOR)


class Pacer:
    """Har `every` items ke baad `rest_s` second ruko."""
    def __init__(self, every=20, rest_s=0.5):
        self.every, self.rest_s, self.n = max(1, int(every)), float(rest_s), 0

    def step(self):
        self.n += 1
        if self.n % self.every == 0:
            rest(self.rest_s)


def paced(iterable, every=25, rest_s=0.5):
    """for x in paced(query.stream(), 25, 0.5): ... — har 25 docs ke baad 0.5s aaram."""
    p = Pacer(every, rest_s)
    for x in iterable:
        yield x
        p.step()


def backup_pacer(auto=False):
    every = int(os.environ.get("BACKUP_PACE_EVERY", "200") or 200)
    rest_s = float(os.environ.get("BACKUP_PACE_REST", "0.5") or 0.5)
    return Pacer(every, rest_s * (2 if auto else 1))


# ---- slow delete (Firestore bulk writer ki speed limit ke saath; na chale to normal) ----
def _bulk_writer(db):
    try:
        from google.cloud.firestore_v1.bulk_writer import BulkWriterOptions, SendMode
        return db.bulk_writer(BulkWriterOptions(initial_ops_per_second=10, max_ops_per_second=30, mode=SendMode.serial))
    except Exception:
        return None


def delete_tree(db, ref):
    """db.recursive_delete ka dheema version (chhote chunks, ops/sec limit)."""
    bw = _bulk_writer(db)
    try:
        if bw is not None:
            return db.recursive_delete(ref, bulk_writer=bw, chunk_size=50)
        return db.recursive_delete(ref, chunk_size=50)
    except TypeError:
        return db.recursive_delete(ref)
