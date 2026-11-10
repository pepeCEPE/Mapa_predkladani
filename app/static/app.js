'use strict';
const $ = (s, r = document) => r.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const cz = d => { if (!d) return '—'; const [y, m, dd] = d.slice(0, 10).split('-'); return `${+dd}. ${+m}. ${y}`; };
let META = null, TODAY = null;
const view = $('#view');

async function api(path, opts = {}) {
  const sep = path.includes('?') ? '&' : '?';
  const url = opts.method && opts.method !== 'GET' ? path : `${path}${sep}today=${TODAY}`;
  const r = await fetch(url, opts);
  if (!r.ok) { let m = r.statusText; try { m = (await r.json()).detail || m; } catch {} throw new Error(m); }
  return r.json();
}
const post = (p, body, method = 'POST') => api(p, {method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify({today: TODAY, ...body})});
function toast(msg) { const t = $('#toast'); t.textContent = msg; t.hidden = false; clearTimeout(toast.t); toast.t = setTimeout(() => t.hidden = true, 3500); }
const badges = o => `${o.confirmed ? '<span class="badge ok">Potvrzeno</span>' : '<span class="badge warn">K ověření</span>'}${o.is_demo ? '<span class="badge">DEMO</span>' : ''}`;
const kindLbl = k => k === 'periodic' ? 'periodická' : 'vyvolaná událostí';

/* ---------- společné prvky ---------- */
function stepsHtml(steps, curId) {
  return `<ol class="steps">${steps.map(s => `<li class="${s.id === curId ? 'cur' : ''}"><span class="n">${s.step_no}</span>
   <div><b>${esc(s.organ_label)}</b> – ${esc(s.role || '')} (${esc(s.act_type)})
   ${s.deadline_text ? `<div class="mut">Lhůta: ${esc(s.deadline_text)}</div>` : ''}${s.date ? `<div class="k-rec">Plán: ${cz(s.date)}</div>` : ''}</div></li>`).join('')}</ol>`;
}
function ruleCard(r) {
  const cond = r.conditions ? `<div><b>Platí, když:</b> ${esc(r.conditions)}</div>` : '<div><b>Platí:</b> vždy</div>';
  const first = r.steps[0], last = r.steps[r.steps.length - 1];
  return `<div class="card"><div class="row"><h3>${esc(r.subject)}</h3><span class="spacer"></span>${badges(r)}<span class="badge">${kindLbl(r.kind)}</span></div>
   <div class="row" style="gap:20px"><div><b>Co řešit:</b> ${esc(r.agenda_title || r.subject)}</div></div>
   ${cond}<div><b>Do kdy:</b> ${esc(r.deadline_text || 'bez pevné lhůty')}</div>
   ${r.confirmed ? '' : `<div class="badge warn" style="margin-top:6px">K ověření: ${esc(r.steps.find(s => !s.confirmed)?.unconfirmed_reason || '')}</div>`}
   ${stepsHtml(r.steps)}
   <button class="btn sm" onclick="showDetail(${first.id})">Detail a zdroj</button> <button class="btn sm" onclick="showDetail(${last.id})">Doporučení termínu</button></div>`;
}

/* ---------- detail ---------- */
window.showDetail = async function (id) {
  const d = await api(`/api/obligations/${id}`);
  const o = d.obligation, p = d.plan;
  const planHtml = p ? `<h2>Doporučení zasedání</h2>${planBlock(p)}` : '';
  $('#detail-body').innerHTML = `<h1>${esc(o.subject)}</h1><div>${badges(o)} <span class="badge">${esc(o.organ_label)}</span> <span class="badge">${esc(o.act_type)}</span> <span class="badge">${kindLbl(o.kind)}</span></div>
  ${o.confirmed ? '' : `<div class="card" style="background:var(--warnbg)"><b>K ověření.</b> ${esc(o.unconfirmed_reason)} Pravidlo se nezobrazuje jako potvrzená povinnost ECRU.</div>`}
  <h2>Pořadí kroků</h2>${stepsHtml(d.chain.map(c => ({...c, date: null})), o.id)}
  <table><tr><th>Platí, když</th><td>${esc(o.conditions || 'vždy')}</td></tr>
  <tr><th>Odpovědný subjekt</th><td>${esc(o.responsible || '—')}</td></tr>
  <tr><th>Předkládá</th><td>${esc(o.submitter || '—')}</td></tr>
  <tr><th>Schvalovatelé</th><td>${esc(o.approvers || '—')}</td></tr>
  <tr><th>Povaha povinnosti</th><td>${esc(o.nature || '—')}</td></tr>
  <tr><th>Výjimky a poznámky</th><td style="white-space:pre-line">${esc(o.exceptions || '—')}</td></tr>
  <tr><th>Lhůta</th><td>${esc(o.deadline_text || 'bez pevné lhůty')}</td></tr>
  <tr><th>Potřebné podklady</th><td>${esc(o.documents || '—')}</td></tr>
  <tr><th>Doporučený bod programu</th><td>${esc(o.agenda_title || '—')}</td></tr>
  <tr><th>Návrh usnesení</th><td>${esc(o.resolution_text || '—')}</td></tr>
  <tr><th>Návaznosti</th><td>${esc(o.follow_up || '—')}</td></tr>
  <tr><th>Zdroj</th><td>${esc(o.source_name || '—')}; ${esc(o.source_ref || 'článek chybí')}</td></tr>
  <tr><th>Verze / účinnost / ověřeno</th><td>${esc(o.source_version || '—')} / ${cz(o.effective_from)} / ${cz(o.verified_on)}</td></tr></table>${planHtml}`;
  $('#detail').showModal();
};
function planBlock(p) {
  const st = {ok: 'ok', conflict: 'bad', incomplete: 'warn'}[p.status] || '';
  let h = '';
  if (p.status === 'ok') h += `<div class="badge ok">Zasedání nalezena</div>`;
  if (p.status === 'conflict') h += `<div class="badge bad">Konflikt – žádné zasedání nevyhovuje</div>`;
  if (p.status === 'incomplete') h += `<div class="badge warn">Kalendář není úplný</div>`;
  h += (p.reasons || []).map(r => `<div class="${st ? 'k-' + (p.status === 'ok' ? 'rec' : 'dead') : ''}">${esc(r)}</div>`).join('');
  h += (p.warnings || []).map(r => `<div class="k-prep">${esc(r)}</div>`).join('');
  if (p.steps) h += `<table><tr><th>Krok</th><th>Orgán</th><th>Závazná lhůta</th><th>Podklady do</th><th>Doporučené zasedání</th><th>Předchozí vhodné</th></tr>${p.steps.map(s =>
    `<tr><td>${s.step_no}. ${esc(s.role || s.act_type)}</td><td>${esc(s.organ_label)}</td><td class="k-dead">${cz(s.deadline)}</td><td class="k-prep">${cz(s.prep_date)}</td><td class="k-rec"><b>${cz(s.date)}</b></td><td>${cz(s.previous_date)}</td></tr>`).join('')}</table>`;
  if (p.notice_on) h += `<div class="mut">Upozornění: bod lze projednat už na předchozím vhodném zasedání – podklady připravte do ${cz(p.notice_on)}.</div>`;
  return h;
}

/* ---------- Přehled ---------- */
async function home() {
  const dash = await api('/api/dashboard');
  view.innerHTML = `<h1>Co potřebujete schválit nebo projednat?</h1>
  <form class="search" id="sf"><input id="q" placeholder="Např. bonus, změna auditora, outsourcing, střet zájmů…" autofocus><button class="btn pri">Hledat</button></form>
  <div id="results"></div>
  <h2>Příští zasedání</h2><div class="grid">${dash.next_meetings.map(m => `<div class="card"><div class="mut">${esc(m.organ_label)}</div>
   ${m.date ? `<div class="big">${cz(m.date)}</div><div><b>${m.must}</b> povinných bodů · ${m.check} k prověření · ${m.suggest} vhodných</div>
   <button class="btn sm" onclick="goCheck('${m.organ}','${m.date}')">Prověřit program</button>` : '<div class="mut">Termín zasedání není zadán.</div><button class="btn sm" onclick="location.hash=\'#program\'">Zadat datum a prověřit</button>'}</div>`).join('')}</div>
  <p><button class="btn pri" onclick="location.hash='#program'">Prověřit program zasedání</button></p>
  <h2>Blížící se povinnosti (90 dní)</h2>
  ${upcomingTable(dash.upcoming)}
  ${dash.upcoming_unverified.length ? `<h2>Blížící se – K ověření</h2><p class="mut">Neověřená pravidla; nejde o potvrzené povinnosti ECRU.</p>${upcomingTable(dash.upcoming_unverified)}` : ''}`;
  $('#sf').onsubmit = async e => {
    e.preventDefault();
    const q = $('#q').value.trim(); if (!q) return;
    const r = await api(`/api/search?q=${encodeURIComponent(q)}`);
    $('#results').innerHTML = `<h2>${r.count ? `Nalezeno pravidel: ${r.count}` : 'Nic nenalezeno'}</h2>` +
      (r.count > 1 ? '<p class="mut">Odpovídá více pravidel – u každého je uvedeno, kdy platí.</p>' : '') +
      (r.count ? r.results.map(ruleCard).join('') : '<p class="mut">Zkuste jiné slovo nebo běžný popis situace.</p>');
  };
}
function upcomingTable(items) {
  if (!items.length) return '<p class="mut">Žádné povinnosti ve sledovaném období.</p>';
  return `<div class="card"><table><tr><th>Povinnost</th><th>Orgán</th><th>Závazná lhůta</th><th>Podklady do</th><th>Doporučené zasedání</th><th></th></tr>${items.map(i => `<tr class="click" onclick="showDetail(${i.obligation_id})">
   <td>${esc(i.subject)}</td><td>${esc(i.organ_label)}</td><td class="k-dead">${cz(i.deadline)}</td><td class="k-prep">${cz(i.prep_date)}</td>
   <td class="k-rec">${i.plan_status === 'ok' ? cz(i.recommended) : i.plan_status === 'no_calendar' ? '<span class="mut">bez zasedání</span>' : `<span class="badge ${i.plan_status === 'conflict' ? 'bad' : 'warn'}">${i.plan_status === 'conflict' ? 'Konflikt' : i.plan_status === 'incomplete' ? 'Kalendář neúplný' : '—'}</span>`}</td>
   <td>${i.notice_on ? '<span class="badge">dřívější termín možný</span>' : ''}</td></tr>`).join('')}</table></div>`;
}
window.goCheck = (organ, date) => { sessionStorage.setItem('pre', JSON.stringify({organ, date})); location.hash = '#program'; if (location.hash === '#program') route(); };

/* ---------- Katalog ---------- */
async function catalog() {
  const f = JSON.parse(sessionStorage.getItem('cf') || '{}');
  const opt = (arr, v, lbl = x => x) => `<option value="">vše</option>` + arr.map(x => `<option value="${esc(Array.isArray(x) ? x[0] : x)}" ${v === (Array.isArray(x) ? x[0] : x) ? 'selected' : ''}>${esc(lbl(Array.isArray(x) ? x[1] : x))}</option>`).join('');
  view.innerHTML = `<h1>Katalog povinností <small class="mut" id="cnt"></small></h1><div class="filters">
   <input id="cq" placeholder="Hledat…" value="${esc(f.q || '')}">
   <select id="co">${opt(Object.entries(META.organs), f.organ)}</select><select id="ca">${opt(META.acts, f.act_type)}</select>
   <select id="cr">${opt(META.areas, f.area)}</select><select id="ck">${opt([['periodic', 'periodická'], ['event', 'vyvolaná událostí']], f.kind)}</select>
   <select id="cs">${opt([['potvrzeno', 'potvrzeno'], ['k_overeni', 'K ověření']], f.status)}</select></div>
   <div class="card"><table id="ct"></table></div><div class="row"><button class="btn" id="prev">‹</button><button class="btn" id="next">›</button></div>`;
  let off = f.off || 0; const lim = 50;
  const load = async () => {
    const cur = {q: $('#cq').value, organ: $('#co').value, act_type: $('#ca').value, area: $('#cr').value, kind: $('#ck').value, status: $('#cs').value, off};
    sessionStorage.setItem('cf', JSON.stringify(cur));
    const qs = new URLSearchParams({...cur, offset: off, limit: lim}); qs.delete('off');
    const r = await api(`/api/obligations?${qs}`);
    $('#cnt').textContent = `(${r.total})`;
    $('#ct').innerHTML = `<tr><th>Kód</th><th>Předmět</th><th>Orgán</th><th>Úkon</th><th>Typ</th><th>Lhůta</th><th>Stav</th></tr>` + r.items.map(o => `<tr class="click" onclick="showDetail(${o.id})">
     <td>${esc(o.code)}</td><td>${esc(o.subject)}<div class="mut">${esc(o.area || '')}</div></td><td>${esc(o.organ_label)}</td><td>${esc(o.act_type)}</td><td>${kindLbl(o.kind)}</td><td>${esc(o.deadline_text || '—')}</td><td>${badges(o)}</td></tr>`).join('');
    $('#prev').disabled = off === 0; $('#next').disabled = off + lim >= r.total;
  };
  ['cq', 'co', 'ca', 'cr', 'ck', 'cs'].forEach(i => $('#' + i).oninput = () => { off = 0; load(); });
  $('#prev').onclick = () => { off = Math.max(0, off - lim); load(); }; $('#next').onclick = () => { off += lim; load(); };
  load();
}

/* ---------- Kontrola programu ---------- */
let DRAFT = [], LAST = null;
async function program() {
  const pre = JSON.parse(sessionStorage.getItem('pre') || 'null'); sessionStorage.removeItem('pre');
  const ms = await api('/api/meetings');
  view.innerHTML = `<h1>Kontrola programu zasedání</h1><div class="card"><div class="row">
   <label>Orgán <select id="po">${META.program_organs.map(o => `<option value="${o}">${esc(META.organs[o])}</option>`).join('')}</select></label>
   <label>Datum zasedání <input type="date" id="pd"></label><label>Pokrýt období do <input type="date" id="pc"></label>
   <span class="mut" id="pm"></span></div>
   <h3 style="margin-top:12px">Situační checklist</h3><table class="checklist">${META.checklist.map(c => `<tr><td>${esc(c.label)}</td><td>${['ano', 'ne', 'nevim'].map(v => `<label><input type="radio" name="${c.key}" value="${v}" ${v === 'ne' ? 'checked' : ''}> ${{ano: 'Ano', ne: 'Ne', nevim: 'Nevím'}[v]}</label>`).join('')}</td></tr>`).join('')}</table>
   <p><button class="btn pri" id="run">Zkontrolovat program</button></p></div><div id="out"></div>`;
  const fillMeet = () => { const o = $('#po').value; const l = ms.filter(m => m.organ === o && m.date >= TODAY);
    $('#pm').innerHTML = l.length ? 'Známá zasedání: ' + l.map(m => `<a href="#" data-d="${m.date}">${cz(m.date)}</a>`).join(', ') : 'Žádná zasedání v kalendáři.';
    view.querySelectorAll('#pm a').forEach(a => a.onclick = e => { e.preventDefault(); $('#pd').value = a.dataset.d; }); if (!$('#pd').value && l[0]) $('#pd').value = l[0].date; };
  $('#po').onchange = () => { $('#pd').value = ''; fillMeet(); };
  if (pre) { $('#po').value = pre.organ; } fillMeet(); if (pre) $('#pd').value = pre.date;
  $('#run').onclick = async () => {
    const answers = {}; META.checklist.forEach(c => answers[c.key] = view.querySelector(`input[name=${c.key}]:checked`).value);
    if (!$('#pd').value) return toast('Zadejte datum zasedání.');
    try {
      LAST = await post('/api/program/check', {organ: $('#po').value, date: $('#pd').value, covers_until: $('#pc').value || null, answers});
    } catch (e) { return toast(e.message); }
    const sv = await api(`/api/programs?organ=${LAST.organ}&date=${LAST.meeting_date}`);
    DRAFT = sv.saved ? sv.items.map(i => ({...i})) : LAST.must.map(i => ({obligation_id: i.obligation_id, title: i.title, act_type: i.act_type, category: 'must'}));
    LAST.answers = answers; renderOut();
  };
}
function itemHtml(cat, i) {
  const inP = DRAFT.some(d => d.obligation_id === i.obligation_id);
  return `<div class="card item ${cat}"><div class="row"><b>${esc(i.title)}</b><span class="spacer"></span>
   ${i.confirmed ? '' : '<span class="badge warn">K ověření</span>'}<span class="badge ${i.in_program === 'ano' ? 'ok' : i.in_program === 'ne' ? 'bad' : ''}">${i.in_program === 'ano' ? 'Zařazeno' : i.in_program === 'ne' ? 'Není zařazeno' : 'Stav neznámý (program neuložen)'}</span>
   <label><input type="checkbox" ${inP ? 'checked' : ''} onchange="toggleItem(${i.obligation_id},this.checked)"> do programu</label></div>
   ${i.reasons.map(r => `<div>${esc(r)}</div>`).join('')}${i.warnings.map(r => `<div class="k-prep">${esc(r)}</div>`).join('')}
   ${i.deadline ? `<div class="mut">Lhůta ${cz(i.deadline)}${i.latest_safe ? ' · poslední bezpečné zasedání ' + cz(i.latest_safe) : ''}</div>` : ''}
   ${i.confirmed ? '' : `<div class="k-prep">${esc(i.unconfirmed_reason)}</div>`}
   ${i.chain.length ? `<div class="mut">Řetězec: ${i.chain.map(c => `${c.current ? '<b>' : ''}${esc(c.organ_label)} ${esc(c.role || '')} ${c.date ? cz(c.date) : ''}${c.current ? '</b>' : ''}`).join(' → ')}</div>` : ''}
   <button class="btn sm" onclick="showDetail(${i.obligation_id})">Detail</button></div>`;
}
window.toggleItem = (id, on) => {
  const all = [...LAST.must, ...LAST.check, ...LAST.suggest]; const it = all.find(x => x.obligation_id === id);
  const dup = DRAFT.some(d => d.obligation_id === id || d.title.toLowerCase() === it.title.toLowerCase());
  if (on && !dup) DRAFT.push({obligation_id: id, title: it.title, act_type: it.act_type, category: it.category});
  if (!on) DRAFT = DRAFT.filter(d => d.obligation_id !== id);
  renderDraft();
};
function renderOut() {
  const r = LAST, sec = (cat, title, hint) => `<h2>${title} <span class="badge">${r[cat].length}</span></h2><p class="mut">${hint}</p>${r[cat].map(i => itemHtml(cat, i)).join('') || '<p class="mut">Nic.</p>'}`;
  $('#out').innerHTML = `<div class="card">Zasedání: <b>${esc(r.organ_label)} ${cz(r.meeting_date)}</b> · pokrývané období do ${cz(r.covers_until)} · další známé zasedání: ${r.next_meeting ? cz(r.next_meeting) : '<span class="badge warn">není v kalendáři</span>'}</div>
   ${r.warnings.map(w => `<div class="card" style="background:var(--warnbg)">${esc(w)}</div>`).join('')}
   ${sec('must', 'Musí být zařazeno', 'Ověřené povinné body, které nelze bezpečně odložit na další zasedání. Zařazení do programu samo o sobě neznamená splnění povinnosti.')}
   ${sec('check', 'Prověřte, zda se vás týká', 'Použitelnost není potvrzena (odpověď „Nevím“, podmíněné nebo neověřené pravidlo).')}
   ${sec('suggest', 'Mohlo by být vhodné zařadit', 'Body vhodné k přípravě nebo projednání s předstihem.')}
   ${r.follow_ups.length ? `<h2>Navazující kroky jiných orgánů</h2><div class="card">${r.follow_ups.map(f => `<div>${esc(f.subject)} – ${esc(f.organ_label)} (${esc(f.role || f.act_type)}) ${f.planned ? cz(f.planned) : '<span class="mut">termín zasedání není zadán</span>'}</div>`).join('')}</div>` : ''}
   <h2>Návrh programu</h2><div class="card" id="draft"></div>`;
  renderDraft();
}
function draftText() { return `Návrh programu – ${LAST.organ_label}, ${cz(LAST.meeting_date)}\n\n` + DRAFT.map((d, n) => `${n + 1}. ${d.title}${d.act_type ? ` (${d.act_type})` : ''}`).join('\n'); }
function renderDraft() {
  $('#draft').innerHTML = `${DRAFT.length ? `<ol>${DRAFT.map((d, n) => `<li>${esc(d.title)} <button class="btn sm" onclick="rmDraft(${n})">×</button></li>`).join('')}</ol>` : '<p class="mut">Program je prázdný.</p>'}
   <div class="row"><input id="manual" placeholder="Vlastní bod programu"><button class="btn sm" id="addm">Přidat</button><span class="spacer"></span>
   <button class="btn" id="save">Uložit program</button><button class="btn" id="copy">Zkopírovat</button></div>`;
  $('#addm').onclick = () => { const t = $('#manual').value.trim(); if (t && !DRAFT.some(d => d.title.toLowerCase() === t.toLowerCase())) { DRAFT.push({obligation_id: null, title: t}); renderDraft(); } };
  $('#save').onclick = async () => { const r = await post('/api/programs', {organ: LAST.organ, date: LAST.meeting_date, covers_until: LAST.covers_until, answers: LAST.answers, items: DRAFT}); toast(`Program uložen (${r.count} bodů).`); $('#run').click(); };
  $('#copy').onclick = async () => { try { await navigator.clipboard.writeText(draftText()); toast('Program zkopírován do schránky.'); } catch { toast('Kopírování se nepodařilo – označte text ručně.'); } };
}
window.rmDraft = n => { DRAFT.splice(n, 1); renderDraft(); };

/* ---------- Kalendář ---------- */
let CY = null;
async function calendar() {
  CY = CY || +TODAY.slice(0, 4);
  const [c, ms] = await Promise.all([api(`/api/calendar?year=${CY}`), api('/api/meetings')]);
  const months = ['leden', 'únor', 'březen', 'duben', 'květen', 'červen', 'červenec', 'srpen', 'září', 'říjen', 'listopad', 'prosinec'];
  view.innerHTML = `<h1>Kalendář</h1><div class="row"><button class="btn" onclick="CY--;route()">‹</button><b>${CY}</b><button class="btn" onclick="CY++;route()">›</button>
   <span class="mut">Legenda: <span class="k-dead">závazná lhůta</span> · <span class="k-prep">podklady do</span> · <span class="k-rec">doporučené projednání</span></span></div>
   ${c.no_calendar ? `<div class="card" style="background:var(--blue)">Termíny zasedání nejsou zadány, počítá se jen s lhůtami. Zasedání můžete kdykoli doplnit níže – doporučení se pak dopočtou.</div>` : c.incomplete.length ? `<div class="card" style="background:var(--warnbg)">Kalendář není úplný: v roce ${CY} nejsou zadána zasedání orgánů: ${c.incomplete.map(o => META.organs[o]).join(', ')}.</div>` : ''}
   <div class="cal">${months.map((m, i) => { const mm = String(i + 1).padStart(2, '0');
     const dl = c.items.filter(x => x.deadline.slice(5, 7) === mm), mt = c.meetings.filter(x => x.date.slice(5, 7) === mm);
     return `<div class="m"><h4>${m}</h4>${mt.map(x => `<div class="ev">🗓 <b>${esc(x.organ_label)}</b> ${cz(x.date)}</div>`).join('')}
     ${dl.map(x => `<div class="ev" onclick="showDetail(${x.obligation_id})" style="cursor:pointer"><span class="k-dead">${cz(x.deadline)}</span> ${esc(x.subject)} <span class="mut">(${esc(x.organ_label)})</span>${x.confirmed ? '' : ' <span class="badge warn">K ověření</span>'}</div>`).join('')}</div>`; }).join('')}</div>
   <h2>Doporučení termínů</h2><div class="card"><table><tr><th>Povinnost</th><th>Orgán</th><th class="k-dead">Závazná lhůta</th><th class="k-prep">Podklady do</th><th class="k-rec">Doporučené zasedání</th><th>Předchozí vhodné</th><th>Stav</th></tr>
   ${c.items.map(x => `<tr class="click" onclick="showDetail(${x.obligation_id})"><td>${esc(x.subject)}</td><td>${esc(x.organ_label)}</td><td>${cz(x.deadline)}</td><td>${cz(x.prep_date)}</td><td><b>${cz(x.recommended)}</b></td><td>${cz(x.previous)}</td>
   <td>${x.plan_status === 'ok' ? '<span class="badge ok">OK</span>' : x.plan_status === 'conflict' ? `<span class="badge bad">Konflikt</span><div class="mut">${esc(x.reasons[0] || '')}</div>` : x.plan_status === 'incomplete' ? `<span class="badge warn">Kalendář neúplný</span><div class="mut">${esc(x.reasons[0] || '')}</div>` : x.plan_status === 'no_calendar' ? '<span class="mut">jen lhůta</span>' : '<span class="mut">uplynulo</span>'}${x.confirmed ? '' : ' <span class="badge warn">K ověření</span>'}</td></tr>`).join('')}</table></div>
   <h2>Zasedání</h2><div class="card"><div class="row"><select id="mo">${Object.entries(META.organs).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join('')}</select><input type="date" id="md"><input id="mn" placeholder="Poznámka"><button class="btn pri" id="ma">Přidat zasedání</button></div>
   <table>${ms.map(m => `<tr><td>${esc(m.organ_label)}</td><td>${cz(m.date)}</td><td>${esc(m.note || '')}</td><td><button class="btn sm" onclick="delMeet(${m.id})">Smazat</button></td></tr>`).join('')}</table></div>`;
  $('#ma').onclick = async () => { try { const r = await post('/api/meetings', {organ: $('#mo').value, date: $('#md').value, note: $('#mn').value}); changed(r); } catch (e) { toast(e.message); } };
}
function changed(r) { toast(r.changed.length ? `Doporučení přepočítána, změnilo se: ${r.changed.length} povinností.` : 'Doporučení přepočítána, beze změny.'); route(); }
window.delMeet = async id => { changed(await api(`/api/meetings/${id}`, {method: 'DELETE'})); };

/* ---------- Import ---------- */
async function importView() {
  const hist = await api('/api/import/history');
  view.innerHTML = `<h1>Import mapy předkládání</h1><div class="card"><p>Nahrajte schválenou mapu (XLSX nebo CSV). Před uložením uvidíte náhled, chyby po řádcích a možné duplicity. Opakovaný import stejného souboru záznamy nezdvojí.
   <a href="/api/import/template.csv">Stáhnout šablonu CSV</a></p><input type="file" id="f" accept=".xlsx,.csv"> <button class="btn pri" id="pv">Zobrazit náhled</button>
   <details style="margin-top:10px"><summary>Doplnit verzi, účinnost a ověření (jen pokud jste mapu skutečně ověřili)</summary>
   <p class="mut">Platí pro řádky s čitelným a dohledaným zdrojem; ostatní zůstanou K ověření. Vyplňte všechna tři pole.</p>
   <div class="row"><input id="o_zdroj" placeholder="Název zdroje (volitelné)"><input id="o_verze" placeholder="Verze, např. NZ 1021/2026"><label>Účinnost od <input type="date" id="o_uc"></label><label>Ověřeno dne <input type="date" id="o_ov"></label></div>
   <label style="display:block;margin-top:8px"><input type="checkbox" id="o_vp"> Compliance / právník potvrdil, že vnitřní předpisy (VP_…) jsou použitelné i po změně názvu na ECRU</label></details></div><div id="pvout"></div>
   <h2>Historie importů</h2><div class="card"><table><tr><th>Soubor</th><th>Kdy</th><th>Nových</th><th>Změněných</th><th>Beze změny</th><th>Přeskočeno</th></tr>${hist.map(h => `<tr><td>${esc(h.filename)}</td><td>${esc(h.imported_at)}</td><td>${h.created}</td><td>${h.updated}</td><td>${h.unchanged}</td><td>${h.skipped}</td></tr>`).join('')}</table></div>`;
  $('#pv').onclick = async () => {
    const f = $('#f').files[0]; if (!f) return toast('Vyberte soubor.');
    const fd = new FormData(); fd.append('file', f);
    const qs = new URLSearchParams({zdroj: $('#o_zdroj').value, verze: $('#o_verze').value, ucinnost_od: $('#o_uc').value, overeno_dne: $('#o_ov').value, vp_potvrzeno: $('#o_vp').checked});
    let r; try { r = await api('/api/import/preview?' + qs, {method: 'POST', body: fd}); } catch (e) { return toast(e.message); }
    const s = r.summary, lbl = {new: 'nový', update: 'změna', unchanged: 'beze změny', error: 'chyba', duplicate: 'duplicita'};
    $('#pvout').innerHTML = `<div class="card"><b>${esc(r.filename)}</b> (rozpoznaný formát: ${r.layout === 'ecru' ? 'mapa předkládání' : 'šablona'})
     ${r.already_imported ? '<div class="badge warn">Tento soubor už byl importován – uložení nic nezdvojí.</div>' : ''}
     <div>Nových: <b>${s.new}</b> · změn: <b>${s.update}</b> · beze změny: <b>${s.unchanged}</b> · chyb: <b>${s.error}</b> · duplicit: <b>${s.duplicate}</b> · z toho K ověření: <b>${s.k_overeni}</b></div>
     <p><button class="btn pri" id="cm">Uložit import (${s.new + s.update} záznamů)</button></p></div>
     <div class="card"><table><tr><th>Řádek</th><th>Kód</th><th>Předmět</th><th>Akce</th><th>Stav</th><th>Chyby / upozornění</th></tr>${r.rows.map(x => `<tr><td>${x.line}</td><td>${esc(x.code)}</td><td>${esc(x.subject)}</td>
     <td><span class="badge ${x.action === 'error' ? 'bad' : x.action === 'duplicate' ? 'warn' : x.action === 'unchanged' ? '' : 'ok'}">${lbl[x.action]}</span></td><td>${x.status === 'k_overeni' ? '<span class="badge warn">K ověření</span>' : x.status ? 'potvrzeno' : ''}</td>
     <td>${x.errors.map(e => `<div class="k-dead">${esc(e)}</div>`).join('')}${x.warnings.map(e => `<div class="k-prep">${esc(e)}</div>`).join('')}</td></tr>`).join('')}</table></div>`;
    $('#cm').onclick = async () => { const c = await post('/api/import/commit', {token: r.token}); toast(`Uloženo: ${c.created} nových, ${c.updated} změněných, ${c.unchanged} beze změny.`); META = await api('/api/meta'); banner(); importView(); };
  };
}

/* ---------- router ---------- */
function banner() {
  const b = $('#demo-banner');
  const t = [];
  if (META.demo_count) t.push(`Zobrazena DEMONSTRAČNÍ data (${META.demo_count} syntetických pravidel) – nejde o schválenou mapu ECRU.`);
  if (!META.has_meetings) t.push('Termíny zasedání nejsou zadány – aplikace počítá jen s lhůtami.');
  b.hidden = !t.length; b.textContent = t.join(' ');
}
const routes = {home, catalog, program, calendar, import: importView};
async function route() {
  const v = (location.hash || '#home').slice(1);
  document.querySelectorAll('#nav a').forEach(a => a.classList.toggle('on', a.dataset.v === v));
  try { await (routes[v] || home)(); } catch (e) { view.innerHTML = `<div class="card">Chyba: ${esc(e.message)}</div>`; }
}
window.route = route;
(async () => {
  META = await fetch('/api/meta').then(r => r.json());
  TODAY = localStorage.getItem('today') || META.today;
  $('#today').value = TODAY;
  $('#today').onchange = e => { TODAY = e.target.value || META.today; try { localStorage.setItem('today', TODAY); } catch {} route(); };
  banner(); window.addEventListener('hashchange', route); route();
})();
