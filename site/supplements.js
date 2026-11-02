// Charts for the sourced files in data/supplements.json.
const SE_FIPS = ['01', '13', '47', '45', '37', '21', '28', '12'];
const STATE_NAME = {
  '01': 'Alabama', '12': 'Florida', '13': 'Georgia', '21': 'Kentucky', '28': 'Mississippi',
  '37': 'North Carolina', '45': 'South Carolina', '47': 'Tennessee', '48': 'Texas', 'US': 'United States',
};

function supplementBars(el, rows, fmt, caption) {
  if (!el) return;
  const max = d3.max(rows, d => Math.abs(d.v)) || 1;
  el.innerHTML = `<div class="hbar">` + rows.map(d => {
    const color = d.id === '01' ? '#9E1B32' : (d.v < 0 ? '#9A4410' : '#6FA077');
    return `<div class="row${d.id === '01' ? ' is-focus' : ''}"><div class="name">${d.name}</div><div class="track"><div style="width:${Math.max(0, d.v) / max * 100}%;background:${color}"></div></div><div class="val">${fmt(d.v)}</div></div>`;
  }).join('') + `</div><p class="panel-note">${caption}</p>`;
}

function drawElectricity(root, data, peerIds) {
  const el = root.querySelector('[data-chart="electricity"]');
  if (!el || !data) return;
  const ids = [...peerIds, 'US'];
  const rows = ids.map(id => ({
    id, name: id === 'US' ? 'United States' : STATE_NAME[id] || id,
    v: data.states[id] ? data.states[id].cents : null,
  })).filter(d => d.v != null).sort((a, b) => a.v - b.v);
  const al = data.states['01'];
  supplementBars(el, rows, v => v.toFixed(2) + '¢',
    `Industrial retail price, ${data.month}, cents per kilowatthour. Alabama was ${al.cents.toFixed(2)}¢, against ${data.states.US.cents.toFixed(2)}¢ for the U.S. A year earlier Alabama was ${al.centsYearAgo.toFixed(2)}¢. One month, not an annual average. ${data.source}`);
}

function drawExports(root, data, peerIds) {
  const el = root.querySelector('[data-chart="exports"]');
  if (!el || !data) return;
  const rows = peerIds.map(id => ({
    id, name: STATE_NAME[id] || id, v: (data.dollars[id] || 0) / 1e9,
  })).sort((a, b) => b.v - a.v);
  supplementBars(el, rows, v => '$' + v.toFixed(1) + 'B',
    `Manufacturing exports in ${data.year}, origin of movement, billions of dollars. ${data.source}`);
}

function drawRobotics(root, data, peerIds) {
  const el = root.querySelector('[data-chart="robotics"]');
  if (!el || !data) return;
  const codes = Object.entries(data.codes);
  el.innerHTML = codes.map(([code, series]) => {
    const rows = [...peerIds, 'US'].map(id => ({
      id, name: id === 'US' ? 'United States' : STATE_NAME[id] || id,
      v: series.employment[id],
    }));
    const body = rows.map(d => `<tr class="${d.id === '01' ? 'is-focus' : ''}"><td>${d.name}</td><td>${d.v == null ? 'Not published' : d3.format(',')(d.v)}</td></tr>`).join('');
    return `<h3>${code}</h3><p class="panel-note">${series.label}</p><div class="table-scroll"><table class="data-table"><thead><tr><th>State</th><th>Jobs, ${data.year}</th></tr></thead><tbody>${body}</tbody></table></div>`;
  }).join('') + `<p class="panel-note">${data.source} These are not a count of robots installed in factories.</p>`;
}

function drawChips(root, data) {
  const el = root.querySelector('[data-chart="chips"]');
  if (!el || !data) return;
  const highlight = new Set(SE_FIPS);
  for (const extra of ['AL', 'KY', 'MS']) if (!data.states[extra]) data.states[extra] = { directMillion: 0, projects: 0 };
  const rows = Object.entries(data.states).map(([abbr, row]) => {
    const fips = abbr.length === 2 && abbr === abbr.toUpperCase()
      ? ({ AL: '01', GA: '13', TN: '47', SC: '45', NC: '37', KY: '21', MS: '28', FL: '12', TX: '48' }[abbr] || abbr)
      : abbr;
    return { abbr, fips, ...row };
  });
  // states object is keyed by postal abbreviation from the NIST parser.
  const order = rows.sort((a, b) => (b.abbr === 'AL') - (a.abbr === 'AL') || (b.directMillion || 0) - (a.directMillion || 0) || a.abbr.localeCompare(b.abbr));
  // Always show Alabama even when it sorts with the zeros.
  const body = order.map(r => {
    const se = highlight.has(r.fips) || SE_FIPS.includes(r.fips);
    const al = r.abbr === 'AL' || r.fips === '01';
    const cls = al ? 'is-focus' : (se ? 'is-se' : '');
    const dollars = r.directMillion ? '$' + (r.directMillion >= 1000 ? (r.directMillion / 1000).toFixed(2) + ' billion' : r.directMillion.toFixed(1) + ' million') : (r.projects ? 'None assigned' : 'None on this list');
    return `<tr class="${cls}"><td>${r.abbr === 'AL' || r.fips === '01' ? 'Alabama' : r.abbr}</td><td>${dollars}</td><td>${r.projects || 0}</td></tr>`;
  }).join('');
  el.innerHTML = `<div class="table-scroll"><table class="data-table"><thead><tr><th>State</th><th>Direct funding assigned to this state</th><th>Rows on the NIST list</th></tr></thead><tbody>${body}</tbody></table></div>` +
    `<p class="panel-note">${data.source} Alabama is highlighted. Other Southeast rows are shaded. A multi-state award is not divided among those states, and the same total printed on two Texas locations for Samsung is counted once. Proposed awards are on the list but not in this column. Micron's Virginia, New York, and Idaho rows do not state a dollar amount. <a href="${data.url}">NIST source</a>.</p>`;
}

function mountSupplements(root, data, peerIds) {
  if (!data) return;
  drawElectricity(root, data.electricity, peerIds);
  drawExports(root, data.exports, peerIds);
  drawRobotics(root, data.robotics, peerIds);
  drawChips(root, data.chips);
}
