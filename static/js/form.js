(() => {
  const {esc, post, toast} = SIAGA; const $ = (id) => document.getElementById(id);
  const tree = JSON.parse($('kawasanTree').textContent);
  const selected = JSON.parse($('selectedKawasan').textContent || 'null');
  const PULAU = ['SUMATERA', 'KALIMANTAN', 'JAWA', 'BALI NUSRA', 'SULAWESI', 'MALUKU', 'PAPUA'];
  const opts = (arr, cur) => arr.map(([v, t]) => `<option value="${esc(v)}" ${String(v) === String(cur) ? 'selected' : ''}>${esc(t)}</option>`).join('');

  function fillPulau(cur) { const have = [...new Set(tree.map((k) => k.npulau))]; $('selPulau').innerHTML = opts(PULAU.filter((p) => have.includes(p)).map((p) => [p, p]), cur); }
  function fillUpt(pulau, cur) { const u = [...new Set(tree.filter((k) => k.npulau === pulau).map((k) => k.nupt))].sort(); $('selUpt').innerHTML = opts(u.map((x) => [x, x]), cur); }
  function fillKws(pulau, upt, cur) { $('selKws').innerHTML = '<option value="">— pilih kawasan —</option>' + opts(tree.filter((k) => k.npulau === pulau && k.nupt === upt).map((k) => [k.id, k.nkws]), cur); }
  function setKawasan(id) {
    const k = tree.find((x) => String(x.id) === String(id)); if (!k) return false;
    fillPulau(k.npulau); fillUpt(k.npulau, k.nupt); fillKws(k.npulau, k.nupt, k.id); return true;
  }
  $('selPulau').onchange = () => { fillUpt($('selPulau').value); fillKws($('selPulau').value, $('selUpt').value); };
  $('selUpt').onchange = () => fillKws($('selPulau').value, $('selUpt').value);
  if (!setKawasan(selected)) { fillPulau(); fillUpt($('selPulau').value); fillKws($('selPulau').value, $('selUpt').value); }

  // ---- titik dinamis
  const total = document.getElementById('id_pt-TOTAL_FORMS');
  function addPoint(v = {}) {
    const n = +total.value; const html = $('pointTpl').innerHTML.replace(/__prefix__/g, n);
    const wrap = document.createElement('div'); wrap.innerHTML = html; const row = wrap.firstElementChild; $('points').appendChild(row);
    const set = (name, val) => { const el = row.querySelector(`[name="pt-${n}-${name}"]`); if (el && val !== undefined && val !== '') el.value = val; };
    set('lat', v.lat); set('lon', v.lon); set('status', v.status || 'Upaya Pemadaman'); set('luas', v.luas ?? 0);
    total.value = n + 1;
  }
  function reindex() {
    [...$('points').querySelectorAll('.point-row')].forEach((row, i) => row.querySelectorAll('[name]').forEach((el) => {
      el.name = el.name.replace(/pt-\d+-/, `pt-${i}-`); el.id = 'id_' + el.name; }));
    total.value = $('points').querySelectorAll('.point-row').length;
  }
  $('addPoint').onclick = () => addPoint();
  $('points').addEventListener('click', (e) => { if (!e.target.classList.contains('remove-point')) return;
    if ($('points').querySelectorAll('.point-row').length < 2) return toast('Minimal satu titik koordinat.', true);
    e.target.closest('.point-row').remove(); reindex(); });

  // ---- parser
  $('parseBtn').onclick = async () => {
    const text = $('rawText').value; if (!text.trim()) return toast('Tempel teks laporan terlebih dahulu.', true);
    $('id_laporan').value = text.trim();
    try {
      const r = await post('/laporan/parse/', {text});
      if (r.tanggal) $('id_tanggal').value = r.tanggal;
      let kaw = '';
      if (r.kawasan_id && setKawasan(r.kawasan_id)) kaw = ' kawasan dikenali,';
      ['upaya', 'rencana', 'personel', 'kendala', 'kebutuhan'].forEach((k) => { if (r[k]) $('id_' + k).value = r[k]; });
      $('points').innerHTML = ''; total.value = 0;
      (r.points.length ? r.points : [{}]).forEach((p) => addPoint({...p, status: r.status}));
      $('parserNotes').innerHTML = `<b>Parser selesai:</b> status ${esc(r.status)},${kaw} ${r.points.length} koordinat, luas ${r.luas ?? 'belum terdeteksi'} ha, tanggal ${r.tanggal ?? 'belum terdeteksi'}. Periksa hasil sebelum simpan.`;
      toast('Hasil parser masuk ke form.');
    } catch (e) { toast(e.message, true); }
  };
})();
