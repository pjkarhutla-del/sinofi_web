(() => {
  const {esc, badge, STATUS, getJSON, toast} = SIAGA;
  const bm = SIAGA.basemaps();
  const map = L.map('map', {center: [-2.55, 118], zoom: 5, preferCanvas: true, layers: [bm['Satelit (Esri)']]});
  const reportLayer = L.layerGroup().addTo(map), hsIn = L.layerGroup().addTo(map), hsOut = L.layerGroup().addTo(map);
  let kawasan = null;
  const $ = (id) => document.getElementById(id);

  const icon = L.divIcon({className: '', html: '<div class="siaga-triangle-marker"></div>', iconSize: [22, 20], iconAnchor: [11, 18], popupAnchor: [0, -18]});
  function reportMarker(r) {
    const ll = [r.lat, r.lon];
    const m = r.status === 'Upaya Pemadaman' ? L.marker(ll, {icon, riseOnHover: true, zIndexOffset: 500})
      : L.circleMarker(ll, {radius: 9, color: '#fff', weight: 2, fillColor: (STATUS[r.status] || STATUS['Perlu Konfirmasi']).color, fillOpacity: 1});
    m.bindPopup(`<div style="min-width:200px"><p class="m-0 text-[11px] font-bold uppercase text-emerald-900">Laporan Karhutla</p>
      <h4 class="m-0 mt-1 text-sm font-bold">${esc(r.nkws)}</h4><p class="m-0 text-[11px] text-slate-500">${esc(r.nupt)} • ${esc(r.npulau)}</p>
      <div class="mt-2 text-xs leading-5"><b>Tanggal:</b> ${esc(r.tanggal)}<br><b>Status:</b> ${esc(r.status)}<br><b>Luas:</b> ${r.luas} ha<br><b>Koordinat:</b> ${r.lat}, ${r.lon}</div>
      <button class="mt-2 rounded bg-emerald-800 px-2 py-1 text-xs font-semibold text-white" data-detail="${r.kawasan_id}|${r.tanggal}|${r.id}">Lihat detail lengkap</button></div>`);
    return m;
  }
  map.on('popupopen', (e) => {
    const b = e.popup.getElement().querySelector('[data-detail]'); if (!b) return;
    b.onclick = () => { const [k, t, id] = b.dataset.detail.split('|'); map.closePopup(); DetailModal.open(k, t, id); };
  });

  async function refresh() {
    const p = new URLSearchParams(), q = new URLSearchParams();
    const upt = $('fUpt').value, kid = $('fKawasan').value, tgl = $('fTanggal').value;
    if (upt) { p.set('upt', upt); q.set('upt', upt); }
    if (kid) { p.set('kawasan', kid); q.set('kawasan', kid); }
    if (tgl) p.set('tanggal', tgl);
    q.set('dari', $('fDari').value); q.set('sampai', $('fSampai').value);
    $('mapStatus').textContent = 'Memuat data…';
    try {
      const [rep, hs] = await Promise.all([getJSON('/api/laporan/?' + p), getJSON('/api/hotspot/?' + q)]);
      reportLayer.clearLayers(); hsIn.clearLayers(); hsOut.clearLayers();
      // Hanya tampilkan laporan terakhir per kawasan+koordinat bila tidak difilter tanggal (hindari tumpukan marker)
      let list = rep.results;
      if (!tgl) { const last = new Map(); list.forEach((r) => last.set(`${r.kawasan_id}|${r.lat}|${r.lon}`, r)); list = [...last.values()]; }
      list.forEach((r) => reportMarker(r).addTo(reportLayer));
      hs.results.forEach((h) => {
        const high = h.conf === 'high';
        const m = L.circleMarker([h.lat, h.lon], {radius: high ? 5 : 4, fillColor: high ? '#f97316' : '#fde047', color: '#7c2d12', weight: 1, fillOpacity: .95});
        m.bindPopup(`<b>Confidence:</b> ${esc(h.conf)}<br><b>Waktu:</b> ${esc(h.waktu || h.tanggal)}<br><b>Satelit:</b> ${esc(h.sat || '-')}<br><b>X, Y :</b> ${h.lon.toFixed(5)}, ${h.lat.toFixed(5)}`);
        (h.kid ? hsIn : hsOut).addLayer(m);
      });
      $('mapStatus').textContent = `${list.length} titik laporan • ${hs.summary.total} hotspot di dalam kawasan (High ${hs.summary.high}, Medium ${hs.summary.medium}) • periode hotspot ${hs.dari} s/d ${hs.sampai}`;
      const pts = list.map((r) => [r.lat, r.lon]); if ((kid || upt || tgl) && pts.length) map.fitBounds(pts, {maxZoom: 12, padding: [40, 40]});
    } catch (e) { $('mapStatus').textContent = 'Gagal memuat data.'; toast('Gagal memuat data peta.', true); }
  }

  SIAGA.loadKawasan(map, {onClickPopup: true}).then((k) => {
    kawasan = k;
    L.control.layers(bm, {'Laporan Karhutla': reportLayer, 'Hotspot Dalam Kawasan': hsIn, 'Hotspot Luar Kawasan': hsOut, 'Batas Kawasan': k.layer, 'Label': k.labelGroup}, {collapsed: false}).addTo(map);
    k.layer.bringToBack();
  }).catch(() => $('mapStatus').textContent = 'Batas kawasan gagal dimuat.');

  // pilihan kawasan mengikuti UPT
  $('fUpt').onchange = () => { const u = $('fUpt').value;
    [...$('fKawasan').options].forEach((o) => { o.hidden = !!(u && o.value && o.dataset.upt !== u); }); $('fKawasan').value = ''; };
  $('fApply').onclick = refresh;
  refresh();
})();
