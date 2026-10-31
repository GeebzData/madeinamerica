// "What each category includes": every category, its industry groups and the industries in each,
// built from meta.json so it always matches the filters.
function renderCategoryGuide(meta, el) {
  const pieces = Object.entries(meta.pieces);
  el.innerHTML = Object.entries(meta.stories).map(([id, cat]) => {
    const groups = Object.keys(meta.groups).filter(g => pieces.some(([, p]) => p.group === g && p.story === id));
    const rows = groups.map(g => {
      const items = pieces.filter(([, p]) => p.group === g && p.story === id)
        .map(([code, p]) => `${p.name} <span class="naics">${code}</span>`).join(' · ');
      return `<div><dt>${meta.groups[g]}</dt><dd>${items}</dd></div>`;
    }).join('');
    return `<div class="guide-cat"><h3>${cat.name}</h3><p>${cat.blurb}</p><dl>${rows}</dl></div>`;
  }).join('');
}
