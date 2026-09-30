/* Modal detail laporan (carousel) — dipakai matriks dan peta. Bergantung pada #detailModal. */
window.DetailModal = (() => {
  const {esc, badge, getJSON, post, toast, fmtDate} = SIAGA;
  const $ = (id) => document.getElementById(id);
  let items = [], idx = 0;
  const field = (label, v) => v ? `<div><dt class="text-xs font-bold uppercase tracking-wide text-slate-400">${label}</dt><dd class="mt-1 whitespace-pre-wrap text-sm text-slate-700">${esc(v)}</dd></div>` : '';

  function render() {
    const r = items[idx]; if (!r) return;
    $('dmTitle').textContent = r.nkws;
    $('dmSub').textContent = `${r.nupt} • ${r.npulau} • ${fmtDate(r.tanggal)}`;
    $('dmNav').classList.toggle('hidden', items.length < 2); $('dmNav').classList.toggle('flex', items.length > 1);
    $('dmPos').textContent = `Data ${idx + 1} dari ${items.length}`;
    $('dmPrev').disabled = idx === 0; $('dmNext').disabled = idx === items.length - 1;
    $('dmBody').innerHTML = `
      <div class="mb-4 flex flex-wrap items-center gap-3">${badge(r.status)}
        <span class="text-sm text-slate-600"><b>${r.luas}</b> ha</span>
        <a class="text-sm text-forest-700 underline" target="_blank" rel="noopener" href="https://www.google.com/maps?q=${r.lat},${r.lon}">${r.lat}, ${r.lon}</a></div>
      <dl class="grid gap-4 sm:grid-cols-2">
        ${field('Upaya', r.upaya)}${field('Rencana tindak lanjut', r.rencana)}${field('Personel', r.personel)}
        ${field('Kendala', r.kendala)}${field('Kebutuhan / saran', r.kebutuhan)}${field('Penegakan hukum', r.gakkum)}
      </dl>
      ${r.laporan ? `<details class="mt-4 rounded-lg border border-slate-200 p-3"><summary class="cursor-pointer text-sm font-semibold">Narasi laporan lengkap</summary><div class="mt-2 whitespace-pre-wrap text-sm leading-7 text-slate-700">${esc(r.laporan)}</div></details>` : ''}
      <p class="mt-4 text-xs text-slate-400">Terakhir diperbarui ${esc(r.updated_at)}</p>`;
    const edit = $('dmEdit'), del = $('dmDelete');
    edit.classList.toggle('hidden', !r.edit_url); if (r.edit_url) edit.href = r.edit_url;
    del.classList.toggle('hidden', !r.delete_url);
  }
  function close() { $('detailModal').classList.add('hidden'); $('detailModal').classList.remove('flex'); document.body.classList.remove('modal-open'); }
  function show(list, start = 0) {
    items = list; idx = Math.min(start, list.length - 1); render();
    $('detailModal').classList.remove('hidden'); $('detailModal').classList.add('flex'); document.body.classList.add('modal-open');
  }
  async function open(kawasanId, tanggal, focusId = null) {
    try {
      const {results} = await getJSON(`/api/laporan/detail/?kawasan=${kawasanId}&tanggal=${tanggal}`);
      if (!results.length) return toast('Data laporan tidak ditemukan.', true);
      show(results, Math.max(0, results.findIndex((r) => r.id === focusId)));
    } catch (e) { toast('Gagal memuat detail laporan.', true); }
  }
  document.addEventListener('click', (e) => { if (e.target.closest('[data-close]') || e.target === $('detailModal')) close(); });
  document.addEventListener('keydown', (e) => {
    if ($('detailModal').classList.contains('hidden')) return;
    if (e.key === 'Escape') close();
    if (e.key === 'ArrowLeft' && idx > 0) { idx--; render(); }
    if (e.key === 'ArrowRight' && idx < items.length - 1) { idx++; render(); }
  });
  $('dmPrev').onclick = () => { if (idx > 0) { idx--; render(); } };
  $('dmNext').onclick = () => { if (idx < items.length - 1) { idx++; render(); } };
  $('dmDelete').onclick = async () => {
    const r = items[idx];
    if (!r?.delete_url || !confirm(`Hapus laporan ${r.nkws} (${r.tanggal}, titik ${r.lat}, ${r.lon})? Tindakan ini tidak dapat dibatalkan.`)) return;
    try { await post(r.delete_url); toast('Laporan dihapus.'); location.reload(); }
    catch (e) { toast(e.message, true); }
  };
  return {open, show};
})();
