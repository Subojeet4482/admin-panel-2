// Shell (services 2 & 3): login, API helper, toast, PIN modal, job tracker, tab switch. Main panel apni auth.js/core.js use karta hai (same look).
window.A = window.A || {};
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s == null ? '' : s).replace(/[<>&"']/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&#39;' }[c]));
A.esc = esc; A._esc = esc;
A.fmtBytes = (n) => n > 1073741824 ? (n / 1073741824).toFixed(2) + ' GB' : n > 1048576 ? (n / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round((n || 0) / 1024)) + ' KB';
A.fmtAgo = (ms) => { if (!ms) return '—'; const s = Math.max(0, Math.round((Date.now() - ms) / 1000)); if (s < 60) return s + 's pehle'; if (s < 3600) return Math.floor(s / 60) + 'm pehle'; if (s < 86400) return Math.floor(s / 3600) + 'h pehle'; return Math.floor(s / 86400) + 'd pehle'; };
A.fmtDur = (s) => { s = Math.floor(s); const d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60); return (d ? d + 'd ' : '') + (h ? h + 'h ' : '') + m + 'm'; };
A.inr = (n) => '₹' + (Number(n) || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 });
A.fail = (e) => A.toast(e.message || 'Error', 'err');
A.closeModal = (id) => $(id).classList.remove('show');

A.toast = function (msg, type = 'ok') {
  const w = $('toast-wrap'), d = document.createElement('div');
  d.className = 'toast ' + type;
  d.innerHTML = `<i class="fa-solid ${type === 'ok' ? 'fa-check-circle' : 'fa-circle-exclamation'}"></i> ${esc(msg)}`;
  w.appendChild(d);
  setTimeout(() => { d.style.animation = 'tout .3s forwards'; setTimeout(() => d.remove(), 350); }, 2800);
};

A.api = async function (path, opt = {}) {
  const init = { method: opt.method || ((opt.body || opt.form) ? 'POST' : 'GET'), credentials: 'same-origin', headers: { 'X-Requested-With': 'ffadmin' } };
  if (opt.form) init.body = opt.form; else if (opt.body) { init.headers['Content-Type'] = 'application/json'; init.body = JSON.stringify(opt.body); }
  const ctl = new AbortController(); init.signal = ctl.signal;
  const tm = setTimeout(() => ctl.abort(), (opt.form || /export|download/.test(path)) ? 300000 : 30000);
  let r; try { r = await fetch(path, init); } catch (e) { clearTimeout(tm); throw new Error(e && e.name === 'AbortError' ? 'Server jawab nahi de raha (timeout) — free plan so raha ho sakta hai, 1 min baad try karo' : 'Server se connect nahi ho paya'); }
  clearTimeout(tm);
  let j = {}; try { j = await r.json(); } catch (e) { }
  if (r.status === 401 && j.code === 'auth') { location.reload(); throw new Error('Session expire ho gaya — dobara login karo'); }
  if (!r.ok || j.ok === false) { const e = new Error(j.error || ('HTTP ' + r.status)); e.code = j.code; throw e; }
  return j;
};

function showLogin(msg) { $('panel').classList.add('hidden'); $('auth').style.display = 'flex'; $('a-loading').classList.add('hidden'); $('login-form').classList.remove('hidden'); $('a-err2').innerText = msg || ''; }
function openPanel() { $('auth').style.display = 'none'; $('panel').classList.remove('hidden'); A.opsStart(); if (A.onOpen) A.onOpen(); }

Object.assign(A, {
  togglePass(el) { const i = $('a-pass'), s = i.type === 'password'; i.type = s ? 'text' : 'password'; el.className = 'fa-solid ' + (s ? 'fa-eye-slash' : 'fa-eye'); },
  async login() {
    const err = $('a-err'), btn = $('a-btn'); err.innerText = '';
    btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Checking...';
    try {
      await A.api('/api/login', { body: { email: $('a-email').value, password: $('a-pass').value, pin: $('a-pin').value } });
      $('a-pass').value = ''; $('a-pin').value = ''; openPanel();
    } catch (e) { err.innerText = '❌ ' + e.message; $('a-pin').value = ''; }
    finally { btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-lock-open"></i> Login'; }
  },
  async logout() { if (!confirm('Logout?')) return; try { await A.api('/api/logout', { method: 'POST' }); } catch (e) { } location.reload(); },
  goTab(id) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('show'));
    document.querySelectorAll('.nav-btn').forEach(n => n.classList.remove('active'));
    const t = $('tab-' + id); if (!t) return; t.classList.add('show', 'fresh'); setTimeout(() => t.classList.remove('fresh'), 1400);
    const n = $('nav-' + id); if (n) n.classList.add('active');
    window.scrollTo({ top: 0 });
    if (A.onTab) A.onTab(id);
  }
});

/* PIN (+ optional type-to-confirm + optional backup checkbox) */
let pending = null;
const settle = (v) => { if (pending) { const r = pending; pending = null; r(v); } };
new MutationObserver(() => { const m = $('m-danger'); if (m && !m.classList.contains('show')) settle(null); }).observe($('m-danger'), { attributes: true, attributeFilter: ['class'] });
A.askDanger = function ({ title, text, typed, backup = true, backupLabel, okLabel = 'Confirm', danger = true }) {
  settle(null);
  $('dg-title').innerText = title; $('dg-text').innerText = text || '';
  $('dg-typed-wrap').style.display = typed ? 'block' : 'none'; $('dg-typed-want').innerText = typed || ''; $('dg-typed').value = '';
  $('dg-bk-wrap').style.display = backup === null ? 'none' : 'flex'; $('dg-bk').checked = backup !== false;
  if (backupLabel) $('dg-bk-lbl').innerText = backupLabel;
  $('dg-pin').value = '';
  const ok = $('dg-ok'); ok.innerText = okLabel; ok.className = 'btn ' + (danger ? 'btn-danger' : 'btn-primary'); ok.style.flex = '1';
  $('m-danger').classList.add('show'); setTimeout(() => $(typed ? 'dg-typed' : 'dg-pin').focus(), 150);
  return new Promise((resolve) => {
    pending = resolve;
    $('dg-cancel').onclick = () => $('m-danger').classList.remove('show');
    ok.onclick = () => {
      if (typed && $('dg-typed').value.trim() !== typed) { A.toast('Confirm text match nahi hua', 'err'); return; }
      const pin = $('dg-pin').value.trim(); if (!pin) { A.toast('PIN daalo', 'err'); return; }
      const v = { pin, backup: $('dg-bk').checked, typed: $('dg-typed').value.trim() };
      pending = null; $('m-danger').classList.remove('show'); resolve(v);
    };
  });
};

/* Background job poll + progress bar */
A.trackJob = function (jobId, label) {
  const bar = $('job-bar'), txt = $('job-txt'), ic = $('job-ic');
  bar.className = 'job-bar'; ic.className = 'fa-solid fa-spinner fa-spin'; txt.innerText = label + '…';
  return new Promise((resolve) => {
    const tick = async () => {
      let j; try { j = (await A.api('/api/jobs/' + jobId)).job; } catch (e) { txt.innerText = e.message; setTimeout(tick, 3000); return; }
      if (j.status === 'running') { txt.innerText = label + ': ' + j.progress; setTimeout(tick, 1500); return; }
      const good = j.status === 'done';
      bar.className = 'job-bar ' + (good ? 'ok' : 'err'); ic.className = 'fa-solid ' + (good ? 'fa-circle-check' : 'fa-circle-exclamation');
      txt.innerText = good ? label + ' complete ✓' : (label + ' fail: ' + j.error);
      setTimeout(() => bar.classList.add('hidden'), good ? 3500 : 7000); resolve(j);
    };
    tick();
  });
};

// modal behaviour + offline banner
document.addEventListener('click', e => { if (e.target.classList && e.target.classList.contains('overlay')) e.target.classList.remove('show'); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') { const o = [...document.querySelectorAll('.overlay.show')].pop(); if (o) o.classList.remove('show'); } });
new MutationObserver(() => { document.body.style.overflow = document.querySelector('.overlay.show') ? 'hidden' : ''; }).observe(document.body, { subtree: true, attributes: true, attributeFilter: ['class'] });
const nb = document.createElement('div'); nb.id = 'net-banner'; nb.innerText = '📡 Internet nahi hai'; document.body.appendChild(nb);
window.addEventListener('offline', () => nb.classList.add('show')); window.addEventListener('online', () => { nb.classList.remove('show'); A.toast('Back online'); });
window.addEventListener('unhandledrejection', e => { console.error(e.reason); });

(async function boot() {
  let s; try { s = await A.api('/api/session'); } catch (e) { showLogin(e.message); return; }
  if (!s.ok) { showLogin(s.ready ? '' : 'Server par login env (OWNER_*) set nahi hain'); return; }
  openPanel();
})();
