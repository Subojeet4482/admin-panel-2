// Payment Bot panel: dashboard (aaj / kal / mahina), pending pool, history, bot control
const $ = (id) => document.getElementById(id);
const esc = A.esc;
let lastTop = null, sumTimer = null, botTimer = null, pend = [], sumBusy = false;
const kv = (k, v) => `<div class="kv"><span>${k}</span><span>${v}</span></div>`;
const dshort = (k) => { const d = new Date(k + 'T00:00:00'); return d.toLocaleDateString('en-IN', { weekday: 'short' }); };
const ref = (d) => `${d.utr ? 'UTR ' + esc(d.utr) : ''}${d.utr && d.txnId ? '<br>' : ''}${d.txnId ? 'Txn ' + esc(d.txnId) : ''}${(!d.utr && !d.txnId) ? esc(d.id) : ''}`;
const tm = (ms) => new Date(ms).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });

function paintSummary(s, first) {
  $('h-today').textContent = A.inr(s.today.total);
  $('h-today-sub').textContent = `${s.today.count} payment${s.today.count === 1 ? '' : 's'} · ${s.today.used} used · ${s.today.pending} pending`;
  $('m-yest').textContent = A.inr(s.yesterday.total); $('m-yest-c').textContent = s.yesterday.count + ' payments';
  $('m-month').textContent = A.inr(s.month.total); $('m-month-c').textContent = s.month.count + ' payments';
  $('m-pend').textContent = A.inr(s.pending_pool.total); $('m-pend-c').textContent = s.pending_pool.count + ' unclaimed';
  $('m-d30').textContent = A.inr(s.d30.total); $('m-d30-c').textContent = s.d30.count + ' payments';
  const mx = Math.max(1, ...s.chart.map(c => c.total));
  $('chart').innerHTML = s.chart.map((c, i) => `<div class="${i === s.chart.length - 1 ? 'today' : ''}"><span>${c.total ? '₹' + Math.round(c.total) : ''}</span><i style="height:${Math.max(3, c.total / mx * 78)}px"></i><small>${i === s.chart.length - 1 ? 'Aaj' : dshort(c.date)}</small></div>`).join('');
  $('best-day').textContent = s.best_day ? `Best din (30 din): ${s.best_day.date} — ${A.inr(s.best_day.total)} (${s.best_day.count} payments)` : '';
  $('feed').innerHTML = s.feed.length ? s.feed.map(f => `<div class="pay-row"><div class="pay-amt">${A.inr(f.amount)}</div><div class="pay-mid"><b>${ref(f)}</b><small>${tm(f.at)} · ${esc(f.source || '')}</small></div><span class="tag ${f.state === 'used' ? 'green' : 'gold'}">${f.state === 'used' ? 'USED' : 'PENDING'}</span></div>`).join('') : '<span class="muted">Aaj abhi koi payment nahi aaya</span>';
  const b = $('nav-pend-badge'); if (b) { b.style.display = s.pending_pool.count ? 'flex' : 'none'; b.textContent = s.pending_pool.count; }
  // naya payment aaya? -> toast + vibrate
  const top = s.feed[0] ? s.feed[0].id : null;
  if (!first && top && lastTop && top !== lastTop) { A.toast('💰 Naya payment: ' + A.inr(s.feed[0].amount)); if (navigator.vibrate) navigator.vibrate([60, 40, 60]); }
  lastTop = top || lastTop;
  paintBotMini(s.bot);
}

function paintBotMini(bt) {
  if (!bt) return;
  const on = bt.status === 'running' || bt.status === 'starting';
  const sw = $('bs-on'); if (sw && document.activeElement !== sw) sw.checked = on;
  const map = { running: '🟢 Chal raha hai', starting: '🟡 Start ho raha hai', stopped: '⚪ Band hai', error: '🔴 Error — Bot tab dekho', not_configured: '🔴 Gmail env missing' };
  $('bs-sub').textContent = (map[bt.status] || bt.status) + (bt.last_run ? ' · last poll ' + tm(Date.parse(bt.last_run)) : '');
}

A.refresh = async function (fresh) {
  if (sumBusy) return; sumBusy = true;
  try { const s = await A.api('/api/pay/summary' + (fresh ? '?fresh=1' : '')); paintSummary(s, !lastTop && !fresh); }
  catch (e) { if (fresh) A.fail(e); else $('feed').innerHTML = `<span class="muted">${esc(e.message)}</span>`; }
  finally { sumBusy = false; }
};

A.botSwitch = async function (el) {
  const want = el.checked;
  try { await A.api('/api/bot/' + (want ? 'start' : 'stop'), { body: {} }); A.toast('Fampay bot ' + (want ? 'ON' : 'OFF')); }
  catch (e) { el.checked = !want; A.fail(e); }
  setTimeout(() => A.refresh(true), 700);
};

/* ---------------- pending ---------------- */
function paintPend() {
  const q = ($('pend-q').value || '').trim().toLowerCase();
  const rows = pend.filter(d => !q || [d.utr, d.txnId, d.id, String(d.amount)].some(x => String(x || '').toLowerCase().includes(q)));
  $('bot-deps').innerHTML = rows.length ? rows.map(d => `
    <div class="pay-row"><div class="pay-amt">${A.inr(d.amount)}</div><div class="pay-mid"><b>${ref(d)}</b><small>${esc(d.source || '')} · ${A.fmtAgo(d.receivedAt)}</small></div>
    <div class="btn-row" style="gap:6px"><button class="btn btn-success mini" title="Successful maan kar history mein bhejo" data-i="${esc(d.id)}" onclick="A.botUseDep(this.dataset.i)"><i class="fa-solid fa-check"></i></button>
    <button class="btn btn-danger mini" data-i="${esc(d.id)}" onclick="A.botDelDep(this.dataset.i)"><i class="fa-solid fa-trash"></i></button></div></div>`).join('')
    : `<span class="muted">${pend.length ? 'Match nahi mila' : 'Koi unclaimed payment nahi ✓'}</span>`;
}
A.pendFilter = paintPend;
A.botDeposits = async function () {
  try { const r = await A.api('/api/bot/deposits'); pend = r.deposits; paintPend(); }
  catch (e) { $('bot-deps').innerHTML = `<span class="muted">${esc(e.message)}</span>`; }
};
A.openAddTxn = () => { $('at-amount').value = ''; $('at-utr').value = ''; $('at-txn').value = ''; $('m-addtxn').classList.add('show'); setTimeout(() => $('at-amount').focus(), 150); };
A.addTxnSubmit = async function () {
  const amount = parseFloat($('at-amount').value), utr = $('at-utr').value.trim(), txnId = $('at-txn').value.trim();
  if (!amount || amount <= 0) return A.toast('Sahi amount daalo', 'err');
  if (!utr && !txnId) return A.toast('UTR ya Transaction ID mein se ek do', 'err');
  try { await A.api('/api/bot/deposits', { body: { amount, utr, txnId } }); A.toast('Transaction add ho gaya ✓'); A.closeModal('m-addtxn'); A.botDeposits(); A.refresh(true); }
  catch (e) { A.fail(e); }
};
A.botUseDep = async function (id) {
  try { await A.api('/api/bot/deposits/' + encodeURIComponent(id) + '/use', { body: {} }); A.toast('History mein move ho gaya ✓'); A.botDeposits(); A.refresh(true); } catch (e) { A.fail(e); }
};
A.botDelDep = async function (id) {
  const v = await A.askDanger({ title: 'Payment delete?', text: 'UTR aur Transaction ID dono copies hat jayengi: ' + id, backup: null, okLabel: 'Delete' }); if (!v) return;
  try { await A.api('/api/bot/deposits/' + encodeURIComponent(id) + '/delete', { body: { pin: v.pin } }); A.toast('Deleted'); A.botDeposits(); A.refresh(true); } catch (e) { A.fail(e); }
};

/* ---------------- history ---------------- */
A.botHistLoad = async function () {
  try {
    const r = await A.api('/api/bot/deposits/history?range=' + $('bot-hist-range').value);
    $('hs-n').textContent = r.history.length; $('hs-t').textContent = A.inr(r.history.reduce((a, h) => a + (Number(h.amount) || 0), 0));
    $('bot-hist').innerHTML = r.history.length ? r.history.map(h => `<div class="pay-row"><div class="pay-amt">${A.inr(h.amount)}</div><div class="pay-mid"><b>${ref(h)}</b><small>${A.fmtAgo(h.usedAt)}${h.usedBy ? ' · ' + esc(String(h.usedBy).slice(0, 14)) : ''}${h.note ? ' · ' + esc(h.note) : ''}</small></div></div>`).join('')
      : '<span class="muted">Is period mein koi successful payment nahi</span>';
  } catch (e) { $('bot-hist').innerHTML = `<span class="muted">${esc(e.message)}</span>`; }
};
A.botHistDownload = () => window.open('/api/bot/deposits/history/export?range=' + $('bot-hist-range').value, '_blank');
A.botHistDeleteOld = async function () {
  const v = await A.askDanger({ title: 'Purani history delete?', text: 'Chuni hui range se purani saari history hamesha ke liye delete (pehle CSV download kar lo).', backup: null, okLabel: 'Delete' }); if (!v) return;
  const days = { today: 1, '7d': 7, '30d': 30, all: 0 }[$('bot-hist-range').value] ?? 7;
  try { const r = await A.api('/api/bot/deposits/history/delete-old', { body: { days, pin: v.pin } }); A.toast(r.deleted + ' entries delete ✓'); A.botHistLoad(); } catch (e) { A.fail(e); }
};

/* ---------------- bot tab ---------------- */
let formFilled = false;
function paintBot(b, logs) {
  const map = { running: ['Running', 'ok'], starting: ['Starting', 'warn'], stopped: ['Stopped', ''], error: ['Error', 'err'], not_configured: ['Env missing', 'err'] };
  const [t, c] = map[b.status] || [b.status, '']; $('bot-pill').innerText = t; $('bot-pill').className = 'pill ' + c;
  $('bot-kv').innerHTML = kv('Gmail', b.gmail_connected ? '✅ ' + esc(b.gmail_account || 'connected') : '❌ not connected') + kv('Mails mile (last poll)', b.emails_found) +
    kv('Last poll', b.last_run ? new Date(b.last_run).toLocaleTimeString() : '—') + kv('Last poll mein save', b.last_saved) + kv('Total save (is run mein)', b.total_saved) +
    kv('Interval', b.settings.poll_interval + 's') + kv('Heartbeat', b.beat_age + 's pehle') + kv('Processed cache', b.processed_cached);
  $('bot-env').innerHTML = Object.entries(b.env).map(([k, v]) => `<div class="kv"><span>${esc(k)}</span><span>${v ? '✅ set' : '❌ missing'}</span></div>`).join('');
  if (!formFilled) { $('bot-int').value = b.settings.poll_interval; $('bot-q').value = b.settings.query; formFilled = true; }
  const lb = $('bot-log'), atEnd = lb.scrollHeight - lb.scrollTop - lb.clientHeight < 30;
  lb.innerHTML = logs.length ? logs.map(l => `<div class="${l.l === 'error' ? 'e' : l.l === 'warn' ? 'w' : l.l === 'ok' ? 'k' : ''}">${esc(l.t.slice(11, 19))} ${esc(l.m)}</div>`).join('') : '<div>Abhi koi log nahi</div>';
  if (atEnd) lb.scrollTop = lb.scrollHeight;
  paintBotMini({ status: b.status, last_run: b.last_run });
}
A.botLoad = async function () { try { const r = await A.api('/api/bot/status'); paintBot(r.bot, r.logs); } catch (e) { if (!botTimer) A.fail(e); } };
A.botAct = async function (a) { try { const r = await A.api('/api/bot/' + a, { method: 'POST' }); A.toast(r.message); setTimeout(A.botLoad, 600); if (a === 'poll') setTimeout(() => A.refresh(true), 3500); } catch (e) { A.fail(e); } };
A.botSave = async function () { try { await A.api('/api/bot/settings', { body: { poll_interval: parseInt($('bot-int').value, 10), query: $('bot-q').value } }); A.toast('Bot settings save'); formFilled = false; A.botLoad(); } catch (e) { A.fail(e); } };
A.botClear = async function () {
  const v = await A.askDanger({ title: 'Saare mails dobara scan?', text: 'Processed list saaf hogi. Duplicate payments phir bhi save nahi hongi.', backup: null, okLabel: 'Rescan', danger: false }); if (!v) return;
  try { await A.api('/api/bot/clear-processed', { body: { pin: v.pin } }); A.toast('Done — next poll mein rescan'); A.botLoad(); } catch (e) { A.fail(e); }
};

/* ---------------- shell hooks ---------------- */
A.onOpen = function () {
  A.renderSwitcher(); A.refresh(false); A.botDeposits();
  clearInterval(sumTimer); sumTimer = setInterval(() => { if (!document.hidden && $('tab-home').classList.contains('show')) A.refresh(false); }, 30000);
};
A.onTab = function (id) {
  clearInterval(botTimer); botTimer = null;
  if (id === 'home') A.refresh(false);
  if (id === 'pending') A.botDeposits();
  if (id === 'history') A.botHistLoad();
  if (id === 'bot') { formFilled = false; A.botLoad(); botTimer = setInterval(() => { if (!document.hidden) A.botLoad(); }, 8000); }
};
