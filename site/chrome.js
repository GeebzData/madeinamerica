// Shared footer and a compact menu on narrow screens.
(function () {
  const header = document.querySelector('.site-header');
  const nav = header && header.querySelector('.site-nav');
  if (header && nav) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'nav-toggle';
    btn.setAttribute('aria-expanded', 'false');
    btn.setAttribute('aria-controls', 'site-nav');
    nav.id = 'site-nav';
    btn.textContent = 'Menu';
    btn.addEventListener('click', () => {
      const open = header.classList.toggle('nav-open');
      btn.setAttribute('aria-expanded', String(open));
      btn.textContent = open ? 'Close' : 'Menu';
    });
    header.insertBefore(btn, nav);
  }

  const foot = document.createElement('footer');
  foot.className = 'site-footer';
  foot.innerHTML =
    '<p>Made in America is a public data project by <a href="https://gerardbarile.com/">Gerard Barile</a>, a venture capital principal at Wave Digital Assets.</p>' +
    '<p id="site-built">Loading the data build date…</p>';
  document.body.appendChild(foot);

  fetch('data/meta.json')
    .then(r => r.json())
    .then(meta => {
      const end = meta.years[meta.years.length - 1];
      const plants = meta.plantsNote ? ` ${meta.plantsNote}` : '';
      document.getElementById('site-built').textContent =
        `Employment and establishment figures run through ${end}. Data files built ${meta.built}.${plants}`;
    })
    .catch(() => {
      document.getElementById('site-built').textContent = '';
    });
})();
