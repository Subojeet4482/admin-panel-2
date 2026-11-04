"""Fampay deposit pool (Firestore) — sirf DB ke kaam, Gmail / bot thread nahi.
Payment-bot service (fampay_bot.py) aur main panel (wallet approve) dono yahi use karte hain."""
import time
import fb


class DepositStore:
    # ------------------------------------------------------------ deposits (pending pool + history)
    @staticmethod
    def _norm(v):
        v = (v or "").strip().upper()
        return v or None

    @staticmethod
    def _dep_doc_id(utr, txn_id):
        """payId = payment ka MAIN id (UTR ho to UTR, warna Transaction ID). Ek payment ke 2 copies ban sakte hain
        (UTR wala + Transaction ID wala) — dono mein `payId` same hota hai, isliye user dono mein se koi bhi
        daal de, payment sirf EK baar credit hoti hai (fampay_used marker)."""
        return utr or txn_id or None

    def _already_consumed(self, db, pay_id, utr, txn_id):
        """True agar yeh payment pehle hi use/credit ho chuki hai (marker, history, ya user ki success request)."""
        if db.collection("fampay_used").document(pay_id).get(timeout=20).exists:
            return True
        if db.collection("fampay_deposits_history").document(pay_id).get(timeout=20).exists:
            return True
        for ref in {r for r in (utr, txn_id) if r}:
            rq = db.collection("deposit_requests").document(ref).get(timeout=20)
            if rq.exists and (rq.to_dict() or {}).get("status") == "success":
                return True
        return False

    def save_deposit(self, amount, utr=None, txn_id=None, source="manual", added_by=None, extra=None):
        """Pending pool (fampay_deposits) mein payment daalta hai. UTR aur Transaction ID dono ho to dono ke naam se
        ek-ek copy banti hai (same payId) taaki user koi bhi ek daal ke verify kar sake. Duplicate / pehle se use ho
        chuki payment dobara save nahi hoti."""
        utr, txn_id = self._norm(utr), self._norm(txn_id)
        pay_id = self._dep_doc_id(utr, txn_id)
        if not pay_id:
            raise ValueError("UTR ya Transaction ID mein se kam se kam ek dena zaroori hai")
        db = fb.get_db()
        col = db.collection("fampay_deposits")
        ids = [i for i in dict.fromkeys([utr, txn_id]) if i]
        if any(col.document(i).get(timeout=20).exists for i in ids):
            return None
        if self._already_consumed(db, pay_id, utr, txn_id):
            return None
        doc = {"utr": utr, "txnId": txn_id, "amount": amount, "source": source, "payId": pay_id,
               "receivedAt": int(time.time() * 1000)}
        if added_by:
            doc["addedBy"] = added_by
        if extra:
            doc.update(extra)
        batch = db.batch()
        for i in ids:
            batch.set(col.document(i), doc)
        batch.commit(timeout=30)
        return pay_id

    def find_and_consume(self, ref_id, amount, used_by=None, note=None):
        """User ne jo bhi reference diya (UTR ya Transaction ID) + amount se match dhoondta hai; mil jaye to
        turant history mein move (mark_used). Nahi mila to None."""
        ref_id = self._norm(ref_id)
        if not ref_id or not amount:
            return None
        try:
            db = fb.get_db()
            snap = db.collection("fampay_deposits").document(ref_id).get()
        except Exception:
            return None
        if snap.exists:
            dd = snap.to_dict() or {}
            if abs(float(dd.get("amount") or 0) - float(amount)) < 0.01:
                return self.mark_used(ref_id, used_by=used_by, note=note)
        return None

    def mark_used(self, dep_id, used_by=None, note=None):
        """Payment ko 'successful' maan kar pending pool se history mein shift karta hai: dono copies (UTR + Transaction ID)
        delete, history mein ek entry, aur fampay_used marker (taaki dobara koi claim na kar sake)."""
        db = fb.get_db()
        col = db.collection("fampay_deposits")
        snap = col.document(dep_id).get()
        if not snap.exists:
            raise ValueError("Deposit nahi mila (shayad pehle hi use ho chuka hai)")
        d = snap.to_dict() or {}
        pay_id = d.get("payId") or dep_id
        d["id"] = pay_id
        d["usedAt"] = int(time.time() * 1000)
        if used_by:
            d["usedBy"] = used_by
        if note:
            d["note"] = str(note)[:200]
        batch = db.batch()
        batch.set(db.collection("fampay_deposits_history").document(pay_id), d)
        batch.set(db.collection("fampay_used").document(pay_id), {"ref": dep_id, "uid": used_by or "admin", "at": d["usedAt"]})
        for i in {dep_id, d.get("utr"), d.get("txnId"), pay_id}:
            if i:
                batch.delete(col.document(i))
        batch.commit()
        return d

    def delete_deposit(self, dep_id):
        """Admin delete: payment ki saari copies (UTR + Transaction ID) hata deta hai."""
        db = fb.get_db()
        col = db.collection("fampay_deposits")
        snap = col.document(dep_id).get()
        d = (snap.to_dict() or {}) if snap.exists else {}
        batch = db.batch()
        for i in {dep_id, d.get("utr"), d.get("txnId"), d.get("payId")}:
            if i:
                batch.delete(col.document(i))
        batch.commit()

    def history_list(self, days=None, limit=500):
        db = fb.get_db()
        q = db.collection("fampay_deposits_history").order_by("usedAt", direction="DESCENDING")
        if days is not None:
            cutoff = int((time.time() - days * 86400) * 1000)
            q = q.where("usedAt", ">=", cutoff)
        return [s.to_dict() or {} for s in q.limit(limit).stream()]

    def history_delete_before(self, days):
        """`days` se purani history permanently delete — admin PIN se protected (app.py mein)."""
        db = fb.get_db()
        cutoff = int((time.time() - days * 86400) * 1000)
        n = 0
        for s in db.collection("fampay_deposits_history").where("usedAt", "<", cutoff).stream():
            s.reference.delete()
            n += 1
        return n


store = DepositStore()
