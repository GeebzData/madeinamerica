// Renders the top-of-page observations. Each item is { num, claim, why },
// with the wording and figures computed by the page from data it loaded.
function fillPoints(items) {
  const root = document.getElementById('points');
  if (!root || !items) return;
  root.replaceChildren();
  for (const item of items) {
    const art = document.createElement('article');
    art.className = 'point';
    const num = document.createElement('span');
    num.className = 'num';
    num.textContent = item.num;
    const body = document.createElement('p');
    const claim = document.createElement('strong');
    claim.textContent = item.claim;
    body.append(claim);
    if (item.why) body.append(document.createTextNode(' ' + item.why));
    art.append(num, body);
    root.append(art);
  }
}
