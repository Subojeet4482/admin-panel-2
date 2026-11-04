# 2️⃣ FF Payment Bot — Fampay Gmail bot 24/7 + payments dashboard

Gmail se Fampay payment mails padhta hai, UTR / Transaction ID Firestore pool mein save karta hai. Is panel se bot control + kitna paisa aaya sab dikhta hai.
Sirf yahi kaam karta hai — koi backup, chat ya heavy job nahi, isliye bot ko kabhi disturb nahi hota.

## Panel mein
- **Home**: Aaj aaya ₹ (IST), kal, is mahine, pichle 30 din, pending (unclaimed) total, 7-din chart, **Bot ON/OFF switch**, aaj ke payments ki live feed (naya payment aate hi toast + vibrate)
- **Pending**: unclaimed payments — search, manual add, ✓ (successful → history), delete (PIN)
- **History**: Aaj / 7 / 30 din / sab, total ₹, CSV export, purani delete (PIN)
- **Bot**: status, Start / Stop / Abhi poll, settings, Gmail env check, live log, rescan
- Top strip: Render · UptimeRobot · Self revive (header ka server icon = poori detail)

## 24/7 + self revive
- Bot thread ka **watchdog** (har 45s): thread mara to dobara start, heartbeat atka to restart
- **Self-ping** har 10 min + UptimeRobot dono lagao → Render free idle-sleep nahi karta
- Optional `RENDER_API_KEY` + `RENDER_SERVICE_ID` → panel se ek-tap Render restart
- Is service ko **hamesha jaaga** rakhna sabse zaroori hai (bot 24/7) — hours ka hisaab root README mein hai

## Login
Sirf **OWNER** (email + password + PIN). Sub-admin yahan nahi khulta.

## Render par deploy (Docker)
1. Is folder ko apni **alag GitHub repo** mein daalo (ya ek repo mein 3 folder rakho aur Render mein *Root Directory* set karo).
2. Render → **New → Blueprint** (ya New → Web Service → Runtime **Docker**) → repo choose karo. `render.yaml` sab bhar deta hai.
3. **Environment** mein `.env.example` ke hisaab se values bharo. Firebase key ke liye: `python tools/make_b64.py serviceAccount.json` ka output `FIREBASE_CREDENTIALS_B64` mein paste.
4. Deploy ke baad `https://<service>.onrender.com/health` kholo — `{"ok":true}` aana chahiye.
5. UptimeRobot: **Add New Monitor → HTTP(s)** → URL `https://<service>.onrender.com/health` → interval **5 min**.
   Phir UptimeRobot → My Settings → API → **Read-only API key** → env `UPTIMEROBOT_API_KEY`. Ab panel ke top strip mein uptime % dikhega.
6. Panel ke header mein **server icon** dabao — Render status, UptimeRobot, Self-revive aur env check ek jagah.

## Gmail env
`GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN` (gmail.readonly) — pehle jaisa. `GMAIL_QUERY` default: `from:no-reply@famapp.in newer_than:30d`.
> Purani Main service se bot hata diya gaya hai — pehle naya Service 1 deploy karo, tab yeh start karo, warna do bot ek saath chalenge (duplicate payment save nahi hoti, par Gmail API dugni use hogi).
