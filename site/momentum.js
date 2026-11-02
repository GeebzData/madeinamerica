// Four sections shared by the Alabama and Southeast pages: which industries are best positioned,
// why they're expanding, public vs private money, and small business. Loads its own data files.
// renderMomentum(el, { focus: '01', picker: false })
const MO_STATES = { '01': 'Alabama', '13': 'Georgia', '47': 'Tennessee', '45': 'South Carolina', '28': 'Mississippi', '37': 'North Carolina', '21': 'Kentucky' };
const MO_ABBR = { '01': 'AL', '13': 'GA', '47': 'TN', '45': 'SC', '28': 'MS', '37': 'NC', '21': 'KY' };
// Codes like '13' are integer-like object keys, which JavaScript sorts first, so order explicitly.
const MO_ORDER = ['01', '13', '47', '45', '28', '37', '21'];
// Alabama's best-known clusters, for the "why" section. Other states get data-driven lines only.
const MO_CLUSTERS = {
  '01': [
    ['Vehicles', 'Mercedes-Benz chose Vance in 1993, then came Honda (Lincoln, 2001), Hyundai (Montgomery, 2005) and Mazda Toyota (Huntsville, 2021). Each assembly plant draws parts suppliers within a day\'s drive.'],
    ['Aerospace & defense', 'Huntsville grew around NASA\'s Marshall Space Flight Center and the Army\'s Redstone Arsenal; Blue Origin builds rocket engines there and ULA assembles rockets in nearby Decatur. Airbus assembles jets in Mobile.'],
    ['Steel & metals', 'Birmingham\'s iron and steel roots continue at AM/NS Calvert near Mobile and Nucor in Decatur and Tuscaloosa; Novelis is building an aluminum plant at Bay Minette.'],
    ['Ports & power', 'The Port of Mobile handles imported parts and exported vehicles, and industrial power is cheaper than the U.S. average (see the scorecard).']
  ]
};
const MO_BDS = { '31': '31-33', '44': '44-45', '48': '48-49' };

function renderMomentum(el, opts) {
  const fmt = d3.format(',');
  const sign = v => (v > 0 ? '+' : v < 0 ? '−' : '');
  const pctFmt = (v, d = 0) => (v == null || !isFinite(v) ? 'n/a' : sign(v) + Math.abs(v).toFixed(d) + '%');
  const money = m => (m == null ? 'n/a' : Math.abs(m) >= 1000 ? `$${(m / 1000).toFixed(m >= 10000 ? 0 : 1)}B` : `$${Math.round(m)}M`);
  const tone = v => (v == null ? '' : v < 0 ? 'is-loss' : v > 0 ? 'is-gain' : '');
  const pct = (a, b) => (a && b != null ? (b - a) / a * 100 : null);
  const sum = (arr, from, to, years) => d3.sum(years.map((y, i) => (y >= from && y <= to ? arr[i] || 0 : 0)));
  const short = s => s.replace(/ manufacturing$/i, '').replace(/ mfg\.?$/i, '').replace(/^./, c => c.toUpperCase());
  const state = { focus: opts.focus, level: '4', sort: 'edge', all: false };
  let D;

  el.innerHTML = `
    ${opts.picker ? `<section class="wrap block mo-pick"><div class="card"><div class="block-head">
      <div><p class="eyebrow">Dig into one state</p><h2 id="mo-pick-h">Who's growing, and why</h2></div>
      <div class="mo-states" id="mo-state" role="group" aria-label="State">
        ${MO_ORDER.map(f => `<button type="button" class="pill" data-v="${f}" aria-pressed="${f === state.focus}">${MO_STATES[f]}</button>`).join('')}
      </div></div>
      <p class="lede">The four sections below follow the state you pick: its best-positioned industries, why plants are coming, where the money comes from, and which small businesses are starting and lasting.</p></div></section>` : ''}
    <section class="wrap block" aria-labelledby="mo-best-h"><div class="card">
      <div class="block-head"><h2 id="mo-best-h"></h2>
        <div class="mo-tools">
          <div class="segmented small" id="mo-level" role="group" aria-label="Detail">
            <button type="button" data-v="4" aria-pressed="true">Industries</button>
            <button type="button" data-v="6" aria-pressed="false">Exact products</button>
          </div>
          <label class="mo-sort">Sort by <select class="select" id="mo-sort">
            <option value="edge">Local edge</option><option value="lq">Concentration</option>
            <option value="growth">10-year growth</option><option value="jobs">Jobs</option><option value="pay">Pay</option>
          </select></label>
          <button type="button" class="dl-button" id="mo-dl">Download CSV</button>
        </div></div>
      <p class="lede" id="mo-best-lede"></p>
      <div class="mo-cards" id="mo-callouts"></div>
      <div class="table-scroll"><table class="data-table" id="mo-best"></table></div>
      <button type="button" class="link-button" id="mo-more" hidden></button>
      <p class="panel-note" id="mo-best-note"></p>
    </div></section>
    <section class="wrap block" aria-labelledby="mo-why-h"><div class="card">
      <h2 id="mo-why-h"></h2>
      <p class="lede" id="mo-why-lede"></p>
      <div class="table-scroll"><table class="data-table" id="mo-score"></table></div>
      <p class="panel-note" id="mo-score-note"></p>
      <div class="mo-two">
        <div><h3 class="mo-h3">Most concentrated industries</h3><ol class="mo-list" id="mo-clusters"></ol></div>
        <div id="mo-notes-wrap"><h3 class="mo-h3" id="mo-notes-h"></h3><dl class="mo-notes" id="mo-notes"></dl></div>
      </div>
      <div id="mo-ann-wrap"><h3 class="mo-h3" id="mo-ann-h"></h3><p class="mo-sub" id="mo-ann-lede"></p>
        <div class="table-scroll"><table class="data-table" id="mo-ann"></table></div></div>
    </div></section>
    <section class="wrap block" aria-labelledby="mo-money-h"><div class="card">
      <h2 id="mo-money-h"></h2>
      <p class="lede" id="mo-money-lede"></p>
      <div class="table-scroll"><table class="data-table" id="mo-money"></table></div>
      <p class="panel-note" id="mo-money-note"></p>
      <h3 class="mo-h3">Major incentive packages since 2015</h3>
      <p class="mo-sub" id="mo-deals-lede"></p>
      <div class="table-scroll"><table class="data-table mo-deals" id="mo-deals"></table></div>
      <p class="panel-note" id="mo-deals-note"></p>
    </div></section>
    <section class="wrap block" aria-labelledby="mo-small-h"><div class="card wide-chart">
      <h2 id="mo-small-h"></h2>
      <p class="lede" id="mo-small-lede"></p>
      <div class="mo-cards" id="mo-kpis"></div>
      <h3 class="mo-h3">New business applications, indexed to 2019</h3>
      <div class="mo-key" id="mo-apps-key"></div>
      <svg id="mo-apps" role="img" aria-label="Business applications over time, 2019 = 100"></svg>
      <h3 class="mo-h3">Startups and how they fared, by sector</h3>
      <div class="table-scroll"><table class="data-table" id="mo-sectors"></table></div>
      <p class="panel-note" id="mo-sectors-note"></p>
      <h3 class="mo-h3" id="mo-sba-h"></h3>
      <div class="table-scroll"><table class="data-table" id="mo-sba"></table></div>
      <p class="panel-note" id="mo-sba-note"></p>
    </div></section>`;

  const $ = id => document.getElementById(id);
  const name = () => MO_STATES[state.focus];

  // ---------- 1. Best-positioned industries ----------
  function industryRows() {
    const I = D.ind;
    const area = I.areas[state.focus];
    const us = I.areas.US;
    const n = I.years.length - 1;
    const i5 = I.years.indexOf(I.years[n] - 5);
    const rows = [];
    for (const [code, r] of Object.entries(area)) {
      if (code.length !== Number(state.level) || !/^3[123]/.test(code)) continue;
      const e1 = r.e[n];
      if (!e1 || e1 < 250) continue;
      const e0 = r.e[0];
      const u = us[code] || { e: [], p: [] };
      const g = e0 ? e1 / e0 - 1 : null;
      const gu = u.e[0] && u.e[n] ? u.e[n] / u.e[0] - 1 : null;
      const edge = e0 && gu != null ? Math.round(e0 * (g - gu)) : null;
      const lq = r.lq == null ? null : r.lq;
      const gap = g != null && gu != null ? (g - gu) * 100 : null;
      let label = '';
      if (lq >= 1.5 && gap >= 5 && g > 0) label = 'Leader';
      else if (lq < 1.5 && gap >= 10 && g >= 0.2) label = 'Rising';
      else if (lq >= 1.5 && gap <= -5) label = 'Concentrated, lagging';
      rows.push({
        code, name: short(I.names[code] || code), jobs: e1, e0, chg: e0 ? e1 - e0 : null, g: g == null ? null : g * 100,
        g5: r.e[i5] ? pct(r.e[i5], e1) : null, gu: gu == null ? null : gu * 100, edge, lq,
        pay: r.p[n], usPay: u.p[n], label
      });
    }
    const key = { edge: r => r.edge, lq: r => r.lq, growth: r => r.g, jobs: r => r.jobs, pay: r => r.pay }[state.sort];
    return rows.sort((a, b) => (key(b) ?? -Infinity) - (key(a) ?? -Infinity));
  }

  function drawBest() {
    const I = D.ind;
    const y1 = I.years[I.years.length - 1];
    const y0 = I.years[0];
    const rows = industryRows();
    const show = state.all ? rows : rows.slice(0, 15);
    const unit = state.level === '4' ? 'industries' : 'products';
    $('mo-best-h').textContent = `${name()}'s best-positioned ${state.level === '4' ? 'industries' : 'products'}`;
    $('mo-best').innerHTML =
      `<thead><tr><th>${state.level === '4' ? 'Industry' : 'Product'}</th><th>Jobs, ${y1}</th><th>10 years<br>${y0}–${y1}</th><th>5 years</th>` +
      `<th>Same industry,<br>U.S., 10 years</th><th>Concentration<br>vs U.S.</th><th>Local edge<br>(jobs)</th><th>Avg pay<br>vs U.S.</th></tr></thead><tbody>` +
      show.map(r => `<tr><td>${r.name}${r.label ? `<span class="tag${r.label === 'Concentrated, lagging' ? ' tag-warn' : ''}">${r.label}</span>` : ''}<small>NAICS ${r.code}</small></td>` +
        `<td>${fmt(r.jobs)}</td>` +
        `<td class="${tone(r.chg)}">${r.chg == null ? 'n/a' : sign(r.chg) + fmt(Math.abs(r.chg))}<small>${pctFmt(r.g)}</small></td>` +
        `<td class="${tone(r.g5)}">${pctFmt(r.g5)}</td>` +
        `<td class="${tone(r.gu)}">${pctFmt(r.gu)}</td>` +
        `<td>${r.lq == null ? 'n/a' : r.lq.toFixed(1) + '×'}</td>` +
        `<td class="${tone(r.edge)}">${r.edge == null ? 'n/a' : sign(r.edge) + fmt(Math.abs(r.edge))}</td>` +
        `<td>${r.pay == null ? 'n/a' : '$' + fmt(r.pay)}<small class="${tone(r.pay - r.usPay)}">${r.usPay ? pctFmt(pct(r.usPay, r.pay)) : ''}</small></td></tr>`).join('') +
      '</tbody>';
    const more = $('mo-more');
    more.hidden = rows.length <= 15;
    more.textContent = state.all ? 'Show the top 15' : `Show all ${rows.length} ${unit}`;
    const leaders = rows.filter(r => r.label === 'Leader');
    const rising = rows.filter(r => r.label === 'Rising');
    const byEdge = [...rows].filter(r => r.edge != null).sort((a, b) => b.edge - a.edge);
    $('mo-best-lede').textContent =
      `Of ${rows.length} ${name()} ${unit} with at least 250 jobs, ${leaders.length} are leaders: at least 1.5 times as concentrated here as nationally, adding jobs, and growing at least 5 points faster than the same ${state.level === '4' ? 'industry' : 'product'} across the U.S. since ${y0}. ` +
      `${rising.length} more are rising: not yet concentrated here, but up 20% or more and outgrowing the nation by 10 points or more.`;
    const top = byEdge.slice(0, 3);
    const payLead = leaders.filter(r => r.pay).sort((a, b) => b.pay - a.pay)[0];
    const lqTop = [...rows].filter(r => r.lq != null && r.jobs >= 1000).sort((a, b) => b.lq - a.lq)[0];
    $('mo-callouts').innerHTML = [
      top[0] && ['Biggest local edge', top[0].name, `${sign(top[0].edge)}${fmt(Math.abs(top[0].edge))} jobs beyond the national trend for this ${state.level === '4' ? 'industry' : 'product'}`],
      lqTop && ['Most concentrated', lqTop.name, `${lqTop.lq.toFixed(1)}× its share of U.S. jobs · ${fmt(lqTop.jobs)} jobs`],
      payLead && ['Best-paying leader', payLead.name, `$${fmt(payLead.pay)} average pay · ${pctFmt(pct(payLead.usPay, payLead.pay))} vs U.S.`],
      rising[0] && ['Fastest rising', [...rising].sort((a, b) => b.g - a.g)[0].name, `${pctFmt([...rising].sort((a, b) => b.g - a.g)[0].g)} since ${y0}`]
    ].filter(Boolean).map(([k, v, s]) => `<div class="insight"><span>${k}</span><strong>${v}</strong><p>${s}</p></div>`).join('');
    $('mo-best-note').textContent =
      `Concentration (location quotient) is the ${state.level === '4' ? 'industry' : 'product'}'s share of ${name()}'s private jobs divided by its share nationally, from BLS; 2.0× means twice the national share. ` +
      `Local edge is the job change since ${y0} beyond what the state would have had if the ${state.level === '4' ? 'industry' : 'product'} had grown at its national rate: a sign of something local, such as new plants, site advantages or suppliers. ` +
      `Leader: concentration 1.5× or more, adding jobs, and growing at least 5 points faster than the national rate. Rising: below 1.5×, up 20% or more and at least 10 points faster than the nation. Concentrated, lagging: 1.5× or more but 5 points or more behind the nation. ` +
      `For scale, manufacturing as a whole is ${D.ind.areas[state.focus]['31-33'].lq.toFixed(2)}× as concentrated in ${name()} as nationally. ` +
      `Pay is the ${y1} average in ${y1} dollars. BLS withholds some figures to protect individual employers; those show as n/a or are left out.`;
  }

  function bestCsv() {
    const I = D.ind;
    const y1 = I.years[I.years.length - 1];
    const rows = [['NAICS', 'Industry', `jobs ${I.years[0]}`, `jobs ${y1}`, '10-yr % change', '5-yr % change', 'U.S. 10-yr % change',
      'location quotient', 'local edge (jobs)', `avg pay ${y1}`, `U.S. avg pay ${y1}`, 'label']];
    for (const r of industryRows()) {
      rows.push([r.code, r.name, r.e0, r.jobs, r.g?.toFixed(1), r.g5?.toFixed(1), r.gu?.toFixed(1), r.lq, r.edge, r.pay, r.usPay, r.label]);
    }
    const csv = rows.map(r => r.map(v => (v == null ? '' : /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : v)).join(',')).join('\n');
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
    a.download = `${name().toLowerCase().replace(' ', '-')}-industries-${state.level}-digit-${y1}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  // ---------- 2. Why they're expanding ----------
  function rank(map, fips, asc) {
    const vals = Object.entries(map).filter(([k, v]) => k !== 'US' && k !== '72' && v != null);
    const sorted = vals.sort((a, b) => (asc ? a[1] - b[1] : b[1] - a[1]));
    const i = sorted.findIndex(([k]) => k === fips);
    return i < 0 ? '' : `${i + 1} of ${sorted.length}`;
  }

  function drawWhy() {
    const C = D.cond;
    const I = D.ind;
    const n = I.years.length - 1;
    const cols = [...MO_ORDER, 'US'];
    const power = Object.fromEntries(Object.entries(C.power.states).map(([k, v]) => [k, v[0]]));
    const union = Object.fromEntries(Object.entries(C.union.states).map(([k, v]) => [k, v[1]]));
    const popg = Object.fromEntries(Object.entries(C.pop.states).map(([k, v]) => [k, pct(v[0], v[1])]));
    const mfg = f => I.areas[f]['31-33'];
    const rows = [
      ['Industrial power price', `¢ per kWh, ${C.power.year}`, f => power[f]?.toFixed(2), f => rank(power, f, true), 'cheapest'],
      ['Factory pay', `average, ${I.years[n]}`, f => (mfg(f)?.p[n] ? '$' + fmt(mfg(f).p[n]) : 'n/a'), () => '', ''],
      ['Union membership', `% of workers, ${C.union.years[1]}`, f => union[f]?.toFixed(1), f => rank(union, f, true), 'lowest'],
      ['Population growth', `${C.pop.years[0]}–${C.pop.years[1]}`, f => pctFmt(popg[f], 1), f => rank(popg, f, false), 'fastest'],
      ['Manufacturing concentration', `share of jobs vs U.S., ${I.years[n]}`, f => (f === 'US' ? '1.0×' : mfg(f)?.lq ? mfg(f).lq.toFixed(2) + '×' : 'n/a'), () => '', '']
    ];
    $('mo-why-h').textContent = `Why plants are choosing ${name()}`;
    $('mo-score').innerHTML =
      `<thead><tr><th></th>${cols.map(f => `<th>${f === 'US' ? 'U.S.' : MO_ABBR[f]}</th>`).join('')}<th>${name()}'s rank<br>among states</th></tr></thead><tbody>` +
      rows.map(([label, unit, val, rk, dir]) => `<tr><td>${label}<small>${unit}</small></td>` +
        cols.map(f => `<td class="${f === state.focus ? 'mo-focus' : ''}">${val(f) ?? 'n/a'}</td>`).join('') +
        `<td>${rk(state.focus) ? `${rk(state.focus)}<small>1 = ${dir}</small>` : ''}</td></tr>`).join('') + '</tbody>';
    const p = power[state.focus];
    const pay = mfg(state.focus)?.p[n];
    const usPay = mfg('US')?.p[n];
    $('mo-why-lede').textContent =
      `Site-selection teams weigh costs, workers and room to grow. ${name()}'s industrial power costs ${p.toFixed(1)}¢ per kWh against ${power.US.toFixed(1)}¢ nationally, ` +
      `factory pay averages ${pctFmt(pct(usPay, pay))} vs the U.S. (cheaper for employers, less for workers), ` +
      `and ${union[state.focus].toFixed(1)}% of workers belong to a union against ${union.US.toFixed(1)}% nationally. Incentive packages (below) often seal the choice.`;
    $('mo-score-note').textContent =
      `Power: EIA average price to industrial customers. Pay: BLS, all private manufacturing, in ${I.years[n]} dollars. Union: BLS Current Population Survey, all wage and salary workers` +
      `${C.union.years[1] === 2025 ? ' (2025 excludes October, when the federal shutdown stopped the survey)' : ''}. Population: Census estimates. Ranks cover the 50 states and D.C.`;

    const area = I.areas[state.focus];
    const conc = Object.entries(area).filter(([c, r]) => c.length === 4 && /^3[123]/.test(c) && r.lq != null && r.e[n] >= 1000)
      .sort((a, b) => b[1].lq - a[1].lq).slice(0, 6);
    $('mo-clusters').innerHTML = conc.map(([c, r]) =>
      `<li><span>${short(I.names[c])}</span><span><b>${r.lq.toFixed(1)}×</b> · ${fmt(r.e[n])} jobs</span></li>`).join('');
    const notes = MO_CLUSTERS[state.focus];
    $('mo-notes-wrap').hidden = !notes;
    if (notes) {
      $('mo-notes-h').textContent = `How ${name()}'s clusters formed`;
      $('mo-notes').innerHTML = notes.map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join('');
    }
    drawAnnouncements();
  }

  function drawAnnouncements() {
    const wrap = $('mo-ann-wrap');
    wrap.hidden = false;
    if (state.focus !== '01') {
      $('mo-ann-h').textContent = 'Announced projects by industry';
      $('mo-ann-lede').textContent = `This industry breakdown uses Alabama's Commerce reports, so it is shown for Alabama only. The incentive deals below cover ${name()}'s largest projects, and the Commerce Dept tab compares every state's recruiting totals.`;
      $('mo-ann').innerHTML = '';
      return;
    }
    const A = D.ann;
    const years = A.years.map(Number);
    const from = years[years.length - 1] - 4;
    const sectorOf = naics => {
      const two = naics.slice(0, 2);
      if (['31', '32', '33'].includes(two)) return naics.slice(0, 3);
      return { 44: '44-45', 45: '44-45', 48: '48-49', 49: '48-49' }[two] || two;
    };
    const groups = d3.rollups(A.projects.filter(p => p.year >= from), v => ({
      n: v.length, fresh: v.filter(p => p.type === 'new').length, jobs: d3.sum(v, p => p.jobs || 0), inv: d3.sum(v, p => p.invest || 0) / 1e6
    }), p => sectorOf(p.naics || '')).sort((a, b) => b[1].inv - a[1].inv);
    const total = d3.sum(groups, g => g[1].inv);
    const jobs = d3.sum(groups, g => g[1].jobs);
    const fresh = d3.sum(groups, g => g[1].fresh);
    const count = d3.sum(groups, g => g[1].n);
    $('mo-ann-h').textContent = `Announced projects by industry, ${from}–${years[years.length - 1]}`;
    $('mo-ann-lede').textContent =
      `${fmt(count)} projects promised ${fmt(jobs)} jobs and ${money(total)} of investment. ${Math.round(fresh / count * 100)}% were new locations; the rest were expansions of plants already here, ` +
      `a sign that companies that came keep adding.`;
    $('mo-ann').innerHTML =
      '<thead><tr><th>Industry</th><th>Projects</th><th>New locations</th><th>Jobs promised</th><th>Investment</th><th>Share of investment</th></tr></thead><tbody>' +
      groups.slice(0, 12).map(([code, g]) => `<tr><td>${short(D.ind.names[code] || D.sba.sectors[code] || 'Other')}</td><td>${fmt(g.n)}</td><td>${fmt(g.fresh)}</td>` +
        `<td>${fmt(g.jobs)}</td><td>${money(g.inv)}</td><td>${Math.round(g.inv / total * 100)}%</td></tr>`).join('') + '</tbody>';
  }

  // ---------- 3. Public vs private money ----------
  function drawMoney() {
    const F = D.fed;
    const S = D.sba;
    const K = D.con;
    const f = state.focus;
    const last = F.fys[F.fys.length - 1];
    const win = [[last - 9, last - 5], [last - 4, last]];
    const grants = Object.entries(F.groups).map(([id, g]) => [g.name, win.map(([a, b]) => sum(F.states[f][id], a, b, F.fys))]);
    const grantTotal = win.map((_, i) => d3.sum(grants, g => g[1][i]));
    const contracts = win.map(([a, b]) => sum(K.states[f], a, b, K.fys));
    const deals = D.inc.deals.filter(d => d.st === f);
    const incent = win.map(([a, b]) => d3.sum(deals.filter(d => d.year >= a && d.year <= b), d => d.inc));
    const sba = win.map(([a, b]) => sum(S.areas[f].fy.amt, a, b, S.fys));
    const announced = test => win.map(([a, b]) => d3.sum(D.ann.projects.filter(p => p.year >= a && p.year <= b && test(p)), p => p.invest || 0) / 1e6);
    const ann = f === '01' ? announced(() => true) : null;
    const annMfg = f === '01' ? announced(p => /^3[123]/.test(p.naics || '')) : null;
    const row = (label, vals, cls = '', note = '', change = true) => `<tr class="${cls}"><td>${label}${note ? `<small>${note}</small>` : ''}</td>` +
      vals.map(v => `<td>${v == null ? 'n/a' : money(v)}</td>`).join('') +
      `<td class="${change ? tone(vals[1] - vals[0]) : ''}">${!change ? '' : vals[0] ? pctFmt(pct(vals[0], vals[1])) : vals[1] ? 'new' : ''}</td></tr>`;
    $('mo-money-h').textContent = `Public money and private money in ${name()}`;
    $('mo-money').innerHTML =
      `<thead><tr><th></th><th>${win[0][0]}–${win[0][1]}</th><th>${win[1][0]}–${win[1][1]}</th><th>Change</th></tr></thead><tbody>` +
      `<tr class="mo-group"><td colspan="4">Public</td></tr>` +
      row('Federal economic-development grants', grantTotal, 'is-focus', 'federal fiscal years') +
      grants.map(([n, v]) => row(`<span class="mo-indent">${n}</span>`, v)).join('') +
      row('Federal contracts with manufacturers', contracts, '', 'purchases, mostly defense; federal fiscal years') +
      row('Major state and local incentive packages', incent, '', 'deals in the list below; promised when announced, paid over many years', false) +
      `<tr class="mo-group"><td colspan="4">Private</td></tr>` +
      (ann ? row('Investment companies announced', ann, 'is-focus', 'recruited projects, calendar years') +
        row('<span class="mo-indent">Factories</span>', annMfg) + row('<span class="mo-indent">Data centers, power, warehouses and other</span>', ann.map((v, i) => v - annMfg[i])) : '') +
      row('SBA-backed small-business loans', sba, '', 'bank loans with a federal guarantee; federal fiscal years') + '</tbody>';
    const g1 = grantTotal[1];
    $('mo-money-lede').textContent =
      `Over the last five years, ${name()} drew ${money(g1)} in federal grants aimed at factories, workers and regional development, ${pctFmt(pct(grantTotal[0], g1))} from the five years before, ` +
      `and manufacturers there booked ${money(contracts[1])} in federal contracts. ` +
      (ann ? `Companies announced ${money(ann[1])} of investment in the same years, ${money(annMfg[1])} of it in factories. Even counting factories alone, that's about ${Math.round(annMfg[1] / (g1 + incent[1]))} dollars of private money promised for every dollar of federal development grants and major state packages counted here.`
        : `${name()} doesn't publish a full list of announced private investment; the incentive deals below show its largest projects.`);
    $('mo-money-note').textContent =
      `Grants are obligations from USAspending.gov for a fixed list of business, factory, workforce and regional programs (listed in the sources); broadband, research and safety-net money is left out. ` +
      `Contracts are federal purchases from manufacturers by where the work is done. Incentive packages count deals in the list below by the year they were announced. ` +
      `Announced investment is what companies promised, not what they spent. Federal tax credits (such as the IRA's manufacturing credits) aren't published by state, so they aren't included. ` +
      `Fiscal year ${last + 1} grants are left out until reporting catches up; early figures show net cancellations of some DOE manufacturing grants.`;

    const all = [...D.inc.deals].sort((a, b) => (b.st === f) - (a.st === f) || b.inc - a.inc);
    $('mo-deals-lede').textContent = opts.picker
      ? `The largest Southeast packages, ${name()} first. Packages are promises, mostly paid out over 10 to 25 years if the company meets its targets.`
      : 'The largest Southeast packages, Alabama first. Packages are promises, mostly paid out over 10 to 25 years if the company meets its targets.';
    $('mo-deals').innerHTML =
      '<thead><tr><th>Project</th><th>State</th><th>Announced</th><th>Investment</th><th>Jobs</th><th>Incentives</th><th>Per job</th></tr></thead><tbody>' +
      all.map(d => `<tr class="${d.st === f ? 'is-focus' : ''}"><td><a href="${d.src}" target="_blank" rel="noopener">${d.company}</a>, ${d.place}<small>${d.kind}. ${d.note}</small></td>` +
        `<td>${MO_ABBR[d.st]}</td><td>${d.year}</td><td>${d.invest ? money(d.invest) : 'n/a'}</td><td>${d.jobs ? fmt(d.jobs) : 'n/a'}</td>` +
        `<td>${money(d.inc)}</td><td>${d.jobs ? '$' + fmt(Math.round(d.inc * 1e6 / d.jobs / 1000)) + 'K' : 'n/a'}</td></tr>`).join('') + '</tbody>';
    $('mo-deals-note').textContent = `${D.inc.note} Compiled ${D.inc.updated}; each project links to its source.`;
  }

  // ---------- 4. Small business ----------
  function drawSmall() {
    const B = D.form.bfs;
    const T = D.form.bds;
    const S = D.sba;
    const f = state.focus;
    const a = B.areas[f];
    const us = B.areas.US;
    const C = D.cond;
    const yl = B.years[B.years.length - 1];
    const i19 = B.years.indexOf(2019);
    const per = (area, fips) => area.apps[area.apps.length - 1] / C.pop.states[fips][1] * 1000;
    const surv = (area, sec = 'all') => {
      const c = T.areas[area][sec].c;
      return c[0] && c[1] != null ? c[1] / c[0] * 100 : null;
    };
    const ytd = (x, k = 'ytd') => pct(x[k][1], x[k][0]);
    const month = new Date(2000, B.ytd.months - 1).toLocaleString('en-US', { month: 'long' });
    $('mo-small-h').textContent = `Small business in ${name()}: who's starting, and who lasts`;
    $('mo-kpis').innerHTML = [
      ['New business applications, ' + yl, fmt(a.apps[a.apps.length - 1]), `${per(a, f).toFixed(1)} per 1,000 residents · U.S. ${per(us, 'US').toFixed(1)}`],
      ['Likely employers since 2019', pctFmt(pct(a.likely[i19], a.likely[a.likely.length - 1])), `applications Census expects to hire · U.S. ${pctFmt(pct(us.likely[i19], us.likely[us.likely.length - 1]))}`],
      [`${B.ytd.year} so far`, pctFmt(ytd(a)), `January–${month} vs the same months of ${B.ytd.year - 1} · U.S. ${pctFmt(ytd(us))}`],
      [`${T.cohort[0]} startups still open in ${T.cohort[1]}`, pctFmt(surv(f)).replace('+', ''), `U.S. ${pctFmt(surv('US')).replace('+', '')} · jobs at survivors ${pctFmt(pct(T.areas[f].all.c[2], T.areas[f].all.c[3]))} vs at the start`]
    ].map(([k, v, s]) => `<div class="insight"><span>${k}</span><strong>${v}</strong><p>${s}</p></div>`).join('');
    $('mo-small-lede').textContent =
      `New business filings jumped across the Southeast after 2020 and have stayed high. Most are one-person firms; "likely employers" are the applications Census expects to hire, a better guide to future jobs. ` +
      `Startups data runs through ${T.years[T.years.length - 1]}; SBA loans run through fiscal ${S.fys[S.fys.length - 1]}.`;
    drawApps();

    const secs = Object.entries(S.sectors).filter(([c]) => T.areas[f][MO_BDS[c] || c]);
    const t = T.areas[f];
    const ty = T.years;
    const sb = S.areas[f];
    const base = arr => d3.mean(arr.slice(ty.indexOf(2015), ty.indexOf(2019) + 1).filter(v => v != null));
    const rows = secs.map(([c, n]) => {
      const b = t[MO_BDS[c] || c];
      const s = b.s[b.s.length - 1];
      const loss = sb.loss[c];
      const loans = sb.sec[c];
      return {
        c, n, s, vs: pct(base(b.s), s), j: b.j[b.j.length - 1],
        surv: b.c[0] && b.c[1] != null ? b.c[1] / b.c[0] * 100 : null,
        kept: b.c[2] && b.c[3] != null ? b.c[3] / b.c[2] * 100 : null,
        loans: loans ? loans[0] : 0, amt: loans ? loans[1] : 0, young: loans && loans[0] ? loans[3] / loans[0] * 100 : null,
        loss: loss && loss[0] >= 20 ? loss[1] / loss[0] * 100 : null
      };
    }).filter(r => r.s).sort((x, y) => y.s - x.s);
    const usS = surv('US');
    $('mo-sectors').innerHTML =
      `<thead><tr><th>Sector</th><th>Startups,<br>${ty[ty.length - 1]}</th><th>vs 2015–19<br>average</th><th>Jobs at<br>startups</th>` +
      `<th>Still open<br>after 5 years</th><th>Jobs kept<br>after 5 years</th><th>SBA loans,<br>FY${S.recent[0]}–${S.recent[1]}</th><th>Share to new<br>businesses</th><th>Loans written off<br>(FY2010–19)</th></tr></thead><tbody>` +
      rows.map(r => `<tr class="${r.c === '31' ? 'is-focus' : ''}"><td>${r.n}</td><td>${fmt(r.s)}</td><td class="${tone(r.vs)}">${pctFmt(r.vs)}</td><td>${r.j == null ? 'n/a' : fmt(r.j)}</td>` +
        `<td class="${r.surv == null ? '' : tone(r.surv - usS)}">${r.surv == null ? 'n/a' : Math.round(r.surv) + '%'}</td>` +
        `<td class="${tone(r.kept - 100)}">${r.kept == null ? 'n/a' : Math.round(r.kept) + '%'}</td>` +
        `<td>${fmt(r.loans)}<small>${money(r.amt)}</small></td><td>${r.young == null ? '' : Math.round(r.young) + '%'}</td>` +
        `<td>${r.loss == null ? '' : r.loss.toFixed(1) + '%'}</td></tr>`).join('') + '</tbody>';
    $('mo-sectors-note').textContent =
      `Startups are firms in their first year with at least one employee (Census Business Dynamics Statistics). "Still open after 5 years" compares ${T.cohort[0]} startups with five-year-old firms in ${T.cohort[1]}, ` +
      `colored against the U.S. rate of ${Math.round(usS)}% for all sectors; "jobs kept" compares their employment at the same two points, so over 100% means the survivors grew enough to replace the jobs lost at firms that closed. ` +
      `SBA loans are 7(a) and 504 approvals for businesses located in ${name()}, net of canceled loans; "new businesses" are startups and firms two years old or less. ` +
      `Write-offs are charged-off loans among those approved in fiscal 2010–2019, shown where at least 20 loans were made. Manufacturing is highlighted.`;

    const prior = S.prior;
    const top = sb.top.slice(0, 12);
    $('mo-sba-h').textContent = `Industries borrowing most through SBA, FY${S.recent[0]}–${S.recent[1]}`;
    $('mo-sba').innerHTML =
      `<thead><tr><th>Industry</th><th>Loans</th><th>vs FY${prior[0]}–${prior[1]}</th><th>Amount</th></tr></thead><tbody>` +
      top.map(([c, n, before, amt]) => `<tr class="${/^3[123]/.test(c) ? 'is-focus' : ''}"><td>${short(S.names[c] || c)}<small>NAICS ${c}</small></td><td>${fmt(n)}</td>` +
        `<td class="${tone(n - before)}">${before ? pctFmt(pct(before, n)) : 'new'}</td><td>${money(amt)}</td></tr>`).join('') + '</tbody>';
    const mfgN = sb.sec['31'] ? sb.sec['31'][0] : 0;
    $('mo-sba-note').textContent =
      `SBA loans are a window on small businesses that are borrowing to start, buy or grow, not on all small businesses. Manufacturers took ${fmt(mfgN)} of ${name()}'s ` +
      `${fmt(d3.sum(Object.values(sb.sec), v => v[0]))} SBA loans in these years. The two windows are both six fiscal years.`;
  }

  function drawApps() {
    const B = D.form.bfs;
    const svg = d3.select('#mo-apps');
    const W = 760, H = 240, m = { t: 12, r: 120, b: 24, l: 40 };
    svg.attr('viewBox', `0 0 ${W} ${H}`).selectAll('*').remove();
    const years = B.years;
    const i19 = years.indexOf(2019);
    const keys = opts.picker ? [...MO_ORDER, 'US'] : [state.focus, 'US'];
    const lines = keys.map(k => ({ k, v: B.areas[k].likely.map(x => x / B.areas[k].likely[i19] * 100) }));
    const x = d3.scaleLinear().domain(d3.extent(years)).range([m.l, W - m.r]);
    const y = d3.scaleLinear().domain([0, d3.max(lines, l => d3.max(l.v)) * 1.05]).nice().range([H - m.b, m.t]);
    svg.append('g').attr('transform', `translate(0,${H - m.b})`).call(d3.axisBottom(x).ticks(8).tickFormat(d3.format('d')).tickSizeOuter(0));
    svg.append('g').attr('transform', `translate(${m.l},0)`).call(d3.axisLeft(y).ticks(5).tickSize(-(W - m.l - m.r))).call(g => g.select('.domain').remove())
      .call(g => g.selectAll('.tick line').attr('stroke', '#E6E6E1'));
    svg.append('line').attr('x1', x(2019)).attr('x2', x(2019)).attr('y1', m.t).attr('y2', H - m.b).attr('stroke', '#A8A8A2').attr('stroke-dasharray', '3 3');
    const line = d3.line().x((_, i) => x(years[i])).y(v => y(v));
    // End labels for the highlighted lines, nudged apart so they don't overlap.
    const labeled = lines.filter(l => l.k === state.focus || l.k === 'US').map(l => ({ l, y: y(l.v[l.v.length - 1]) + 4 }))
      .sort((a, b) => a.y - b.y);
    for (let i = 1; i < labeled.length; i++) labeled[i].y = Math.max(labeled[i].y, labeled[i - 1].y + 15);
    for (const l of lines) {
      const focus = l.k === state.focus;
      const color = l.k === 'US' ? '#141414' : focus ? '#355E3B' : '#B4B4AE';
      svg.append('path').attr('d', line(l.v)).attr('fill', 'none').attr('stroke', color)
        .attr('stroke-width', focus || l.k === 'US' ? 2.2 : 1.2).attr('stroke-dasharray', l.k === 'US' ? '5 4' : null);
      if (focus || l.k === 'US') {
        svg.append('text').attr('class', 'end-label').attr('x', W - m.r + 6).attr('y', labeled.find(o => o.l === l).y)
          .style('fill', color).text(`${l.k === 'US' ? 'U.S.' : MO_STATES[l.k]} ${Math.round(l.v[l.v.length - 1])}`);
      }
    }
    $('mo-apps-key').innerHTML = `<span><i style="border-color:#355E3B"></i>${name()}</span><span><i class="dash" style="border-color:#141414"></i>U.S.</span>` +
      (opts.picker ? '<span><i style="border-color:#B4B4AE"></i>Other Southeast states</span>' : '') +
      '<span>Likely-employer applications, 2019 = 100</span>';
  }

  function render() {
    for (const b of el.querySelectorAll('#mo-state button')) b.setAttribute('aria-pressed', String(b.dataset.v === state.focus));
    drawBest();
    drawWhy();
    drawMoney();
    drawSmall();
  }

  Promise.all(['industries', 'conditions', 'federal', 'contracts', 'sba', 'formation', 'incentives', 'announcements']
    .map(f => d3.json(`data/${f}.json`))).then(([ind, cond, fed, con, sba, form, inc, ann]) => {
    D = { ind, cond, fed, con, sba, form, inc, ann };
    if (opts.picker) {
      $('mo-state').addEventListener('click', e => {
        const b = e.target.closest('button');
        if (!b) return;
        state.focus = b.dataset.v;
        state.all = false;
        render();
      });
    }
    $('mo-level').addEventListener('click', e => {
      const b = e.target.closest('button');
      if (!b) return;
      state.level = b.dataset.v;
      state.all = false;
      for (const x of el.querySelectorAll('#mo-level button')) x.setAttribute('aria-pressed', String(x === b));
      drawBest();
    });
    $('mo-sort').addEventListener('change', e => { state.sort = e.target.value; drawBest(); });
    $('mo-more').onclick = () => { state.all = !state.all; drawBest(); };
    $('mo-dl').onclick = bestCsv;
    render();
  }).catch(err => {
    el.insertAdjacentHTML('afterbegin', '<p class="wrap panel-note">Could not load this section. Please refresh to try again.</p>');
    console.error(err);
  });
}
