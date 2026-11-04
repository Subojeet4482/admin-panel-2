// OPS: top strip (Render / UptimeRobot / Self-revive) + "Server & Revive" sheet — teeno panels mein ek hi code.
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s == null ? '' : s).replace(/[<>&"']/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&#39;' }[c]));
const fmtB = (n) => { n = Number(n) || 0; const u = ['B', 'KB', 'MB', 'GB', 'TB']; let i = 0; while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; } return n.toFixed(n >= 100 || i === 0 ? 0 : 1) + ' ' + u[i]; };
const dur = (s) => { s = Math.floor(s || 0); const d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60); return (d ? d + 'd ' : '') + (h ? h + 'h ' : '') + m + 'm'; };
const col = (p) => p >= 85 ? '#ef4444' : p >= 65 ? '#f59e0b' : '#10b981';
const ago = (ms) => { if (!ms) return '—'; const s = Math.max(0, Math.round((Date.now() - ms) / 1000)); return s < 60 ? s + 's pehle' : s < 3600 ? Math.floor(s / 60) + 'm pehle' : s < 86400 ? Math.floor(s / 3600) + 'h pehle' : Math.floor(s / 86400) + 'd pehle'; };
let timer = null, busy = false, sheetTimer = null, last = null;

function strip(s) {
  const root = $('ops-root'); if (!root) return;
  const db = s.firestore && s.firestore.ok === false;
  const ur = s.ur || {}, ka = s.keepalive || {};
  const urTxt = !ur.configured ? 'Setup karo' : !ur.found ? 'Monitor nahi mila' : (ur.status === 'up' ? (ur.d30 != null ? ur.d30 + '%' : 'UP') : (ur.status || '?').toUpperCase());
  const urDot = !ur.configured ? '' : (ur.status === 'up' ? 'on' : ur.found ? 'bad' : 'warn');
  const kaDot = !ka.enabled ? 'warn' : (ka.fails > 0 && ka.last_ok == null) ? 'bad' : 'on';
  const sib = (s.sib || []); const sibBad = sib.filter(x => x.ok === false).length;
  root.innerHTML = `<div class="ops-strip" onclick="A.opsOpen()">
    <div class="ops-chip"><small><span class="dot ${db ? 'bad' : 'on'}"></span>Render</small><b>${db ? 'DB issue' : 'Live'}</b><em>up ${dur(s.uptime)} · ${s.req ? s.req.per_min : 0}/min</em></div>
    <div class="ops-chip"><small><span class="dot ${urDot}"></span>UptimeRobot</small><b>${esc(urTxt)}</b><em>${ur.configured && ur.d1 != null ? '24h ' + ur.d1 + '%' : 'monitor status'}</em></div>
    <div class="ops-chip"><small><span class="dot ${kaDot}"></span>Self revive</small><b>${ka.enabled ? 'Active' : 'Off'}</b><em>${ka.last_ok ? 'ping ' + ago(ka.last_ok * 1000) : 'RAM ' + Math.round(s.mem.pct) + '% · CPU ' + Math.round(s.cpu) + '%'}${sibBad ? ' · ' + sibBad + ' sleeping' : ''}</em></div>
  </div><div class="ops-hint">Tap karo — Render, UptimeRobot aur self-revive ki poori detail</div>`;
}

async function tick() {
  if (busy || document.hidden) return;
  if (!$('panel') || $('panel').classList.contains('hidden')) return;
  busy = true;
  try { last = await A.api('/api/server/live'); strip(last); }
  catch (e) { const r = $('ops-root'); if (r) r.innerHTML = `<div class="ops-strip"><div class="ops-chip" style="grid-column:1/4"><small><span class="dot bad"></span>Server</small><b>Unreachable</b><em>${esc(String(e.message).slice(0, 60))}</em></div></div>`; }
  finally { busy = false; }
}

const plat = (p) => !p ? '<span class="muted">check ho raha hai…</span>' : (p.indicator === 'none' ? '✅ All systems operational' : '⚠️ ' + esc(p.description || p.indicator));

function copyBox(txt) { return `<div class="os-copy"><span>${esc(txt)}</span><button onclick="A.opsCopy(this.dataset.t)" data-t="${esc(txt)}">COPY</button></div>`; }

function sheetHTML(o, live) {
  const r = o.render || {}, ur = o.uptimerobot || {}, rv = o.revive || {}, m = ur.monitor;
  const mem = live ? live.mem.pct : 0, cpu = live ? live.cpu : 0, disk = live ? live.disk.pct : 0;
  const g = (v, l, sub) => `<div class="os-g"><b style="color:${col(v)}">${Math.round(v)}%</b><small>${l}</small><div class="os-bar"><i style="width:${Math.min(100, v)}%;background:${col(v)}"></i></div><small style="font-weight:600">${sub}</small></div>`;
  const dep = r.api && r.api.deploy ? r.api.deploy : null;
  const envs = Object.entries(o.env || {}).map(([k, v]) => `<div><span>${esc(k)}</span><span>${v ? '✅' : (k.endsWith('(optional)') ? '➖' : '❌')}</span></div>`).join('');
  const sib = (o.siblings || []).map(s => `<div class="os-sib"><span class="dot ${s.ok === true ? 'on' : s.ok === false ? 'bad' : 'warn'}"></span><div><b>${esc(s.name)}</b><small>${s.ok === true ? 'Online · ' + s.ms + ' ms' : s.ok === false ? 'Sleeping / down — Wake dabao' : 'checking…'}</small></div>
      <button class="btn btn-outline mini" onclick="A.opsWake('${s.key}')"><i class="fa-solid fa-bolt"></i> Wake</button><a class="btn btn-primary mini" href="${esc(s.url)}" target="_blank" rel="noopener"><i class="fa-solid fa-arrow-up-right-from-square"></i></a></div>`).join('')
    || '<div class="os-note">Doosre panels ke links nahi hain. Env mein <b>PANEL_MAIN_URL / PANEL_PAYMENT_URL / PANEL_BACKUP_URL</b> daalo.</div>';
  const urBlock = !ur.configured ? `
      <div class="os-note">UptimeRobot abhi connect nahi hai. Neeche 3 step karo (2 minute):</div>
      <ol class="os-steps"><li><b>uptimerobot.com</b> → <b>Add New Monitor</b> → type <b>HTTP(s)</b>, interval <b>5 min</b>.</li><li>URL mein yeh daalo:${ur.health_url ? copyBox(ur.health_url) : '<span class="muted"> (Render URL env nahi mila)</span>'}</li><li>Status yahan dekhne ke liye: UptimeRobot → My Settings → <b>API</b> → <b>Read-only API key</b> → Render env <b>UPTIMEROBOT_API_KEY</b>.</li></ol>`
    : (ur.error ? `<div class="os-note">UptimeRobot error: ${esc(ur.error)}</div>`
      : !ur.found ? `<div class="os-note">API chal rahi hai (${ur.count || 0} monitors) par is service ka monitor nahi mila. Monitor URL mein <b>${esc(ur.health_url || '')}</b> hona chahiye, ya env <b>UPTIMEROBOT_MONITOR</b> mein monitor ka naam do.</div>`
      : `<div class="os-big"><div class="os-ico" style="background:${m.status === 'up' ? '#10b981' : '#ef4444'}"><i class="fa-solid fa-heart-pulse"></i></div><div><b>${esc(m.name)} — ${m.status === 'up' ? 'UP ✅' : esc(m.status.toUpperCase())}</b><small>Avg response ${m.avg_ms != null ? Math.round(m.avg_ms) + ' ms' : '—'}</small></div></div>
         <div class="os-up"><div><b>${m.uptime.d1 ?? '—'}%</b><small>24 ghante</small></div><div><b>${m.uptime.d7 ?? '—'}%</b><small>7 din</small></div><div><b>${m.uptime.d30 ?? '—'}%</b><small>30 din</small></div></div>`);
  return `
  <div class="os-sec"><div class="os-h"><span><i class="fa-solid fa-gauge-high"></i>Server (live)</span><span class="tag">${esc(o.panel.name)}</span></div>
    <div class="os-gauges">${g(mem, 'RAM', live ? fmtB(live.mem.used) + ' / ' + fmtB(live.mem.total) : '—')}${g(cpu, 'CPU', live ? live.cores + ' core' : '—')}${g(disk, 'DISK', live ? fmtB(live.disk.used) : '—')}</div>
    <div class="os-card">
      <div class="os-kv"><span>Uptime</span><span>${dur(o.uptime)}</span></div>
      <div class="os-kv"><span>Requests / min</span><span>${live ? live.req.per_min : '—'} (avg ${live ? live.req.avg_ms : '—'} ms)</span></div>
      <div class="os-kv"><span>Firebase</span><span>${o.firebase.ok ? '✅ ' + esc(o.firebase.project_id) : '❌ ' + esc(o.firebase.error || 'not connected')}</span></div>
      <div class="os-kv"><span>Firestore latency</span><span>${live && live.firestore.ms != null ? live.firestore.ms + ' ms' : '…'}</span></div>
      <div class="os-kv"><span>Logged in</span><span>${esc(o.user)}</span></div></div></div>

  <div class="os-sec"><div class="os-h"><span><i class="fa-solid fa-cloud"></i>Render status</span></div>
    <div class="os-card"><div class="os-kv"><span>Platform</span><span>${plat(r.platform)}</span></div>
      ${(r.platform && r.platform.incidents || []).map(i => `<div class="os-kv"><span>Incident</span><span>${esc(i.name)}</span></div>`).join('')}
      <div class="os-kv"><span>Service</span><span>${esc(r.service)}${r.on_render ? '' : ' (local)'}</span></div>
      <div class="os-kv"><span>Deploy</span><span>${r.commit ? esc(r.commit) + (r.branch ? ' · ' + esc(r.branch) : '') : '—'}</span></div>
      ${dep ? `<div class="os-kv"><span>Last deploy</span><span>${esc(dep.status || '—')}${r.api.suspended && r.api.suspended !== 'not_suspended' ? ' · ⚠️ ' + esc(r.api.suspended) : ''}</span></div>` : ''}
      ${r.api_error ? `<div class="os-kv"><span>Render API</span><span>⚠️ ${esc(r.api_error)}</span></div>` : ''}
      ${!r.api_configured ? '<div class="os-note">Optional: Render env mein <b>RENDER_API_KEY</b> + <b>RENDER_SERVICE_ID</b> do — deploy status aur ek-tap Restart yahan aa jayega.</div>' : ''}
    </div></div>

  <div class="os-sec"><div class="os-h"><span><i class="fa-solid fa-heart-pulse"></i>UptimeRobot</span></div><div class="os-card">${urBlock}</div></div>

  <div class="os-sec"><div class="os-h"><span><i class="fa-solid fa-life-ring"></i>Self revive</span><span class="tag ${rv.enabled ? 'green' : 'red'}">${rv.enabled ? 'ON' : 'OFF'}</span></div>
    <div class="os-card">
      <div class="os-kv"><span>Self-ping (har ${Math.round((rv.interval || 600) / 60)} min)</span><span>${rv.enabled ? (rv.last_error ? '⚠️ ' + esc(rv.last_error) : rv.last_ok ? '✅ ' + ago(rv.last_ok * 1000) : '⏳ pehla ping baaki') : '❌ off (URL nahi mila)'}</span></div>
      <div class="os-kv"><span>Pings ok / fail</span><span>${(rv.pings || 0) - (rv.fails || 0)} / ${rv.fails || 0}</span></div>
      <div class="os-kv"><span>Watchdog restarts</span><span>${rv.watchdog_restarts || 0}</span></div>
      <div class="os-kv"><span>Crashed threads revived</span><span>${rv.thread_restarts || 0}</span></div>
      <div class="os-kv"><span>Sibling auto-ping</span><span>${rv.siblings_ping ? 'ON' : 'OFF (KEEPALIVE_SIBLINGS)'}</span></div>
      ${!rv.enabled ? '<div class="os-note">Self-ping band hai: Render pe <b>RENDER_EXTERNAL_URL</b> khud milta hai; local/Docker mein <b>KEEPALIVE_URL</b> do.</div>' : ''}
      ${o.can_restart ? '<button class="btn btn-danger btn-full big-btn" onclick="A.opsRestart()"><i class="fa-solid fa-power-off"></i> Restart this service (Render)</button>' : ''}
    </div>
    <div class="os-h" style="margin-top:12px"><span><i class="fa-solid fa-link"></i>Doosre panels</span></div>${sib}
    <div class="os-note ok" style="margin-top:6px">Free plan: service 15 min idle rehne par so jati hai. UptimeRobot (bahar se) + self-ping (andar se) dono lagao — ek chhoot jaye to doosra jagaye.</div></div>

  <div class="os-sec"><div class="os-h"><span><i class="fa-solid fa-key"></i>Env check</span></div><div class="os-env">${envs}</div>
    <p class="muted" style="margin-top:8px;font-size:.68rem">Values kabhi nahi dikhti — sirf set hai ya nahi. Session ${o.session_hours}h.</p></div>
  <button class="btn btn-outline btn-full" onclick="A.logout()"><i class="fa-solid fa-right-from-bracket"></i> Logout</button>`;
}

async function loadSheet() {
  try {
    const [o, l] = await Promise.all([A.api('/api/ops/status'), A.api('/api/server/live').catch(() => last)]);
    $('ops-body').innerHTML = sheetHTML(o, l);
  } catch (e) { $('ops-body').innerHTML = `<div class="os-note">${esc(e.message)}</div>`; }
}

Object.assign(window.A, {
  opsStart() { clearInterval(timer); tick(); timer = setInterval(tick, 12000); },
  opsStop() { clearInterval(timer); timer = null; },
  opsOpen() { $('m-ops').classList.add('show'); $('ops-body').innerHTML = '<p class="muted" style="text-align:center;padding:30px"><i class="fa-solid fa-spinner fa-spin"></i> Loading…</p>'; loadSheet(); clearInterval(sheetTimer); sheetTimer = setInterval(() => { if ($('m-ops').classList.contains('show')) loadSheet(); else clearInterval(sheetTimer); }, 20000); },
  opsCopy(t) { (navigator.clipboard ? navigator.clipboard.writeText(t) : Promise.reject()).then(() => A.toast('Copied ✓')).catch(() => A.toast(t)); },
  async opsWake(key) { try { const r = await A.api('/api/ops/wake', { body: { key } }); A.toast(r.message); setTimeout(loadSheet, 4000); } catch (e) { A.toast(e.message, 'err'); } },
  async opsRestart() {
    const v = await A.askDanger({ title: 'Service restart?', text: 'Render service dobara start karega (~1 min). Bot / jobs rukkar wapas chalenge.', backup: null, okLabel: 'Restart' }); if (!v) return;
    try { const r = await A.api('/api/ops/restart', { body: { pin: v.pin } }); A.toast(r.message); } catch (e) { A.toast(e.message, 'err'); }
  }
});
document.addEventListener('visibilitychange', () => { if (!document.hidden) { busy = false; tick(); } });

// panel switcher (header mein 3 chhote icons: Main / Payment / Backup)
const ICON = { main: 'fa-gauge-high', payment: 'fa-indian-rupee-sign', backup: 'fa-cloud-arrow-down' };
const LABEL = { main: 'Main Panel', payment: 'Payment Bot', backup: 'Backup Center' };
A.renderSwitcher = async function () {
  const el = $('switcher'); if (!el) return;
  try {
    const r = await A.api('/api/panels');
    el.innerHTML = `<span class="switcher">` + [{ key: r.me, url: '' }, ...r.panels].sort((a, b) => ['main', 'payment', 'backup'].indexOf(a.key) - ['main', 'payment', 'backup'].indexOf(b.key))
      .map(p => `<a class="${p.key === r.me ? 'me' : ''}" title="${LABEL[p.key]}" ${p.key === r.me ? '' : `href="${esc(p.url)}" target="_blank" rel="noopener"`}><i class="fa-solid ${ICON[p.key]}"></i></a>`).join('') + `</span>`;
  } catch (e) { }
};
