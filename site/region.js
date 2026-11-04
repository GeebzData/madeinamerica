// Alabama-versus-peers figures for the Southeast page. Every employment number is
// computed from the QCEW files; EV ranks come from site/data/context.json.
function drawRegionBrief(deps) {
  const { states, national, years, gdp, contracts, ann, ctx, peers } = deps;
  const end = years[years.length - 1];
  const i19 = years.indexOf(2019);
  const i15 = years.indexOf(2015);
  const fmtK = v => (Math.abs(v) >= 1000 ? (v / 1000).toFixed(1) + 'k' : d3.format(',')(Math.round(v)));
  const fmtPct = v => `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(1)}%`;
  const at = (id, key, i) => states[id].sel[key].e[i];
  const ordinal = n => n + (['th', 'st', 'nd', 'rd'][n % 100 > 10 && n % 100 < 14 ? 0 : n % 10] || 'th');

  const rows = peers.map(p => {
    const jobs = at(p.id, 'all|all', years.length - 1);
    const base = at(p.id, 'all|all', i19);
    const elec = at(p.id, 'all|electrical', years.length - 1);
    return {
      id: p.id,
      name: p.name,
      jobs,
      pct: (jobs - base) / base * 100,
      elec,
      elecShare: elec / jobs * 100,
      veh: at(p.id, 'all|vehicles', years.length - 1),
      aero: at(p.id, 'all|aero', years.length - 1),
      est: states[p.id].sel['all|all'].n[years.length - 1] - states[p.id].sel['all|all'].n[i19]
    };
  }).sort((a, b) => b.jobs - a.jobs);
  const al = rows.find(r => r.id === '01');
  const veh15 = at('01', 'all|vehicles', years.length - 1) - at('01', 'all|vehicles', i15);
  const all15 = at('01', 'all|all', years.length - 1) - at('01', 'all|all', i15);
  const vehShare15 = veh15 / all15 * 100;

  const lede = document.getElementById('score-lede');
  if (lede) {
    const growth = rows.slice().sort((a, b) => b.pct - a.pct);
    const elec = rows.slice().sort((a, b) => b.elec - a.elec);
    lede.innerHTML = [
      `Alabama factory jobs are ${fmtPct(al.pct)} since 2019, to ${d3.format(',')(al.jobs)} in ${end}: ${growth[0] === al ? 'the fastest growth' : `${ordinal(growth.indexOf(al) + 1)} fastest`} of these ${rows.length} states.`,
      `Vehicles (${fmtK(al.veh)} jobs) made up about ${vehShare15.toFixed(0)}% of Alabama's net new factory jobs since 2015; aerospace adds ${fmtK(al.aero)}.`,
      `Electrical equipment and batteries are only ${fmtK(al.elec)} jobs, ${al.elecShare.toFixed(1)}% of Alabama manufacturing, ${elec[elec.length - 1] === al ? 'the fewest' : `${ordinal(elec.indexOf(al) + 1)} most`} of these states.`
    ].map(t => `<li>${t}</li>`).join('');
  }

  const head = `<thead><tr><th>State</th><th>Factory jobs, ${end}</th><th>Change since 2019</th><th>Electrical, ${end}</th><th>Vehicles, ${end}</th><th>Aerospace, ${end}</th><th>Establishments since 2019</th></tr></thead>`;
  const body = rows.map(r => `<tr class="${r.id === '01' ? 'is-focus' : ''}"><td>${r.name}</td><td>${d3.format(',')(r.jobs)}</td><td class="${r.pct < 0 ? 'is-loss' : 'is-gain'}">${fmtPct(r.pct)}</td><td>${d3.format(',')(r.elec)}</td><td>${d3.format(',')(r.veh)}</td><td>${d3.format(',')(r.aero)}</td><td class="${r.est < 0 ? 'is-loss' : 'is-gain'}">${r.est > 0 ? '+' : ''}${d3.format(',')(r.est)}</td></tr>`).join('');
  const table = document.getElementById('score-table');
  if (table) table.innerHTML = head + '<tbody>' + body + '</tbody>';

  const bars = (id, list, fmt, caption) => {
    const el = document.getElementById(id);
    if (!el) return;
    const max = d3.max(list, d => Math.abs(d.v)) || 1;
    el.innerHTML = `<div class="hbar">` + list.map(d => {
      const neg = d.v < 0;
      const color = d.id === '01' ? '#9E1B32' : (neg ? '#9A4410' : '#6FA077');
      return `<div class="row${d.id === '01' ? ' is-focus' : ''}"><div class="name">${d.name}</div><div class="track"><div style="width:${Math.abs(d.v) / max * 100}%;background:${color}"></div></div><div class="val">${fmt(d.v)}</div></div>`;
    }).join('') + `</div><p class="panel-note">${caption}</p>`;
  };
  const by = (key) => rows;
  bars('chart-growth', by('pct').map(r => ({ id: r.id, name: r.name, v: r.pct })), fmtPct,
    `Percent change in the annual average, 2019 to ${end}. BLS QCEW, private sector, not seasonally adjusted. Not December 2019, and not the seasonally adjusted CES series.`);
  bars('chart-elec', by('elec').map(r => ({ id: r.id, name: r.name, v: r.elec })), v => d3.format(',')(v),
    `Batteries, grid equipment and other electrical manufacturing in ${end}. This is Alabama's scale gap. Source: BLS QCEW.`);
  bars('chart-veh', by('veh').map(r => ({ id: r.id, name: r.name, v: r.veh })), v => d3.format(',')(v),
    `Vehicles and parts employment in ${end}. Alabama, Tennessee and Kentucky are the cluster. Source: BLS QCEW.`);

  const note = document.getElementById('score-note');
  if (note && gdp && contracts && ann && ctx) {
    const gi = gdp.years.length - 1;
    const gy = gdp.years[gi];
    const alGdp = gdp.states['01'];
    const usGdp = gdp.states['00'];
    const share = alGdp.mfg[gi] / alGdp.total[gi] * 100;
    const usShare = usGdp.mfg[gi] / usGdp.total[gi] * 100;
    const fy = contracts.fys;
    const fed = contracts.states['01'];
    const fedNow = fed[fy.length - 1];
    const fedThen = fed[fy.indexOf(2021)];
    const announced = ann.state[end] || ann.state[String(end)];
    const lf = ctx.lfpr.states;
    const ev = ctx.ev;
    const jobsLine = Object.entries(ev.june2025.jobsByState).map(([id, n]) => `${({ '01': 'Alabama', '12': 'Florida', '13': 'Georgia', '37': 'North Carolina', '45': 'South Carolina', '47': 'Tennessee' })[id]} ${d3.format(',')(n)}`).join('; ');
    const bits = [
      `Manufacturing was ${share.toFixed(1)}% of Alabama GDP in ${gy}, against ${usShare.toFixed(1)}% of U.S. GDP (BEA).`,
      `Federal manufacturing-contract obligations in Alabama were $${(fedNow / 1000).toFixed(1)} billion in FY${fy[fy.length - 1]}, ${fmtPct((fedNow - fedThen) / fedThen * 100)} since FY2021 (USAspending; NAICS 31–33, place of performance, not only defense).`,
      `Alabama Commerce counted $${(announced[5] / 1e9).toFixed(1)} billion of announced factory investment in ${end}, and ${d3.format(',')(announced[4])} jobs attached to those projects.`,
      `Labor force participation in ${ctx.lfpr.asOf} was ${lf['01'].latest}% in Alabama and ${lf.US.latest}% in the United States (BLS LAUS via FRED, seasonally adjusted).`,
      `Announced EV-supply-chain jobs through June 30, 2025, in the six-state Atlas/SACE region: ${jobsLine}. Alabama's end-of-2025 one-pager still shows ${d3.format(',')(ev.alabamaEoy2025.jobs)} anticipated jobs and $${ev.alabamaEoy2025.investBillion.toFixed(1)} billion, rank ${ev.alabamaEoy2025.rank} of those six states, with no growth in that tracker during 2025.`
    ];
    note.innerHTML = bits.join('<br>');
  }

  const work = document.getElementById('work-chart');
  if (work && ctx) {
    const order = [...peers.map(p => p.id), 'US'];
    const list = order.filter(id => ctx.lfpr.states[id]).map(id => ({ id, name: ctx.lfpr.states[id].name, v: ctx.lfpr.states[id].latest }));
    bars('work-chart', list.sort((a, b) => b.v - a.v), v => v.toFixed(1) + '%',
      `Labor force participation, seasonally adjusted, ${ctx.lfpr.asOf}. Alabama was ${ctx.lfpr.states['01'].avg2019}% on a 2019 average and ${ctx.lfpr.states['01'].latest}% in the latest month; the U.S. was ${ctx.lfpr.states.US.avg2019}% and ${ctx.lfpr.states.US.latest}%. Source: BLS LAUS (state series LBSSA) and CIVPART, via FRED. This is the headline rate, not prime-age participation.`);
  }

  const chips = document.getElementById('chips-lede');
  if (chips && ctx) {
    const ev = ctx.ev.june2025;
    const al = ctx.ev.alabamaEoy2025;
    chips.textContent =
      `Through June 30, 2025, Atlas and the Southern Alliance for Clean Energy counted $${ev.regionInvestBillion} billion of announced EV-manufacturing investment and ${d3.format(',')(ev.regionJobs)} anticipated jobs in Alabama, Florida, Georgia, North Carolina, South Carolina and Tennessee. ` +
      `About ${Math.round(ev.batteryShareOfInvestment * 100)}% of that investment was batteries and battery recycling. Georgia, North Carolina and Tennessee are three of the top five states nationally on that investment tally. ` +
      `In the year ending June 30, 2025, new announcements were $${ev.newInvestBillionPrior12Months} billion, down from $${ev.newInvestBillionYearBefore} billion the year before, and cancellations removed about $${ev.canceledInvestBillion} billion and ${d3.format(',')(ev.canceledJobs)} jobs. Georgia, South Carolina and Tennessee had job retractions in that window. ` +
      `Alabama's separate end-of-2025 snapshot was still ${d3.format(',')(al.jobs)} anticipated jobs and $${al.investBillion.toFixed(1)} billion, with no growth during 2025. ${al.trainingCenter} Kentucky and Mississippi are outside that six-state tracker.`;
  }

  const win = document.getElementById('vs-win');
  const lag = document.getElementById('vs-lag');
  if (win && lag) {
    win.innerHTML = [
      `<b>Auto assembly.</b> Mercedes near Vance, Hyundai in Montgomery, Honda in Lincoln, and Mazda Toyota in Huntsville. Vehicles employment is ${fmtK(al.veh)} and is up ${fmtPct((at('01', 'all|vehicles', years.length - 1) / at('01', 'all|vehicles', i19) - 1) * 100)} since 2019.`,
      `<b>Aerospace.</b> ${fmtK(al.aero)} jobs, in the same range as Georgia and well ahead of Tennessee and Kentucky. Huntsville and Mobile are the two poles.`,
      `<b>Factory jobs since 2019.</b> ${fmtPct(al.pct)} on the QCEW annual average, not seasonally adjusted, ahead of Tennessee, Kentucky and Mississippi in this peer set.`
    ].map(t => `<li>${t}</li>`).join('');
    lag.innerHTML = [
      `<b>Electrical and batteries.</b> ${fmtK(al.elec)} jobs, ${al.elecShare.toFixed(1)}% of Alabama manufacturing. North Carolina, Georgia, South Carolina and Tennessee are several times larger.`,
      `<b>Announced EV supply chain.</b> ${ctx ? `Alabama ranks ${ctx.ev.alabamaEoy2025.rank} of the six Atlas/SACE states, at ${d3.format(',')(ctx.ev.alabamaEoy2025.jobs)} anticipated jobs and $${ctx.ev.alabamaEoy2025.investBillion.toFixed(1)} billion, with no growth in that tracker through December 2025.` : 'See the Southeast page for the Atlas/SACE comparison.'}`,
      `<b>Labor force participation.</b> ${ctx ? ctx.lfpr.states['01'].latest.toFixed(1) + '% in ' + ctx.lfpr.asOf + ', against ' + ctx.lfpr.states.US.latest.toFixed(1) + '% nationally and ' + ctx.lfpr.states['13'].latest.toFixed(1) + '% in Georgia.' : ''}`
    ].map(t => `<li>${t}</li>`).join('');
  }
}
