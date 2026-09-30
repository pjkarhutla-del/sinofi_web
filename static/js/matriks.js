(() => {
  const table = document.getElementById('matrixTable');
  const collapsed = new Set();
  const rows = () => [...table.tBodies[0].rows];

  function apply() {
    const pulau = document.getElementById('pulauFilter').value;
    const q = document.getElementById('kawasanSearch').value.trim().toLowerCase();
    rows().forEach((tr) => {
      const p = tr.dataset.pulau; if (!p) return;
      const isHead = tr.classList.contains('pulau-row');
      let show = !pulau || p === pulau;
      if (!isHead) { show = show && !collapsed.has(p) && (!q || tr.dataset.search.includes(q)); }
      tr.classList.toggle('hidden', !show);
    });
    if (q) rows().filter((r) => r.classList.contains('pulau-row')).forEach((h) => {
      const any = rows().some((r) => !r.classList.contains('pulau-row') && r.dataset.pulau === h.dataset.pulau && !r.classList.contains('hidden'));
      h.classList.toggle('hidden', !any);
    });
    rows().filter((r) => r.classList.contains('pulau-row')).forEach((h) => {
      const c = h.querySelector('td'); c.innerHTML = c.innerHTML.replace(/^[▾▸]/, collapsed.has(h.dataset.pulau) ? '▸' : '▾');
    });
  }
  table.addEventListener('click', (e) => {
    const head = e.target.closest('.pulau-row');
    if (head) { const p = head.dataset.pulau; collapsed.has(p) ? collapsed.delete(p) : collapsed.add(p); apply(); return; }
    const cell = e.target.closest('td[data-kid]');
    if (cell) DetailModal.open(cell.dataset.kid, cell.dataset.tanggal);
  });
  document.getElementById('pulauFilter').onchange = apply;
  document.getElementById('kawasanSearch').oninput = apply;
  document.getElementById('expandAll').onclick = () => { collapsed.clear(); apply(); };
  document.getElementById('collapseAll').onclick = () => { rows().forEach((r) => r.classList.contains('pulau-row') && collapsed.add(r.dataset.pulau)); apply(); };
})();
