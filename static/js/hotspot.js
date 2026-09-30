(() => {
  const {esc, getJSON, post, toast} = SIAGA;
  const $ = (id) => document.getElementById(id);
  const bm = SIAGA.basemaps();
  const map = L.map('map', {center: [-2.55, 118], zoom: 5, preferCanvas: true, layers: [bm['Satelit (Esri)']]});
  const inL = L.layerGroup().addTo(map), outL = L.layerGroup().addTo(map);
  let kaw = null, topChart = null, weekChart = null, weekly = null;
  const range = () => `dari=${$('fDari').value}&sampai=${$('fSampai').value}`;

  function updateExports() {
    const scope = $('exAll').checked ? 'semua' : 'dalam';
    ['xlsx', 'csv', 'shp'].forEach((f) => { $('ex' + f[0].toUpperCase() + f.slice(1)).href = `/hotspot/ekspor/${f}/?${range()}&scope=${scope}`; });
  }

  async function loadMap() {
    $('mapStatus').textContent = 'Memuat hotspot…';
    const d = await getJSON('/api/hotspot/?' + range());
    inL.clearLayers(); outL.clearLayers();
    const byK = {};
    d.results.forEach((h) => {
      const high = h.conf === 'high';
      const m = L.circleMarker([h.lat, h.lon], {radius: high ? 6 : 4, fillColor: high ? '#ff0000' : '#ffff00', color: '#000', weight: 1, fillOpacity: .95});
      const k = h.kid && kaw?.byId[h.kid]?.props;
      m.bindPopup(`<b>Confidence:</b> ${esc(h.conf)}<br><b>Waktu:</b> ${esc(h.waktu || h.tanggal)}<br><b>Kawasan:</b> ${esc(k ? k.nkws : 'Di luar kawasan')}<br><b>X, Y :</b> ${h.lon.toFixed(5)}, ${h.lat.toFixed(5)}`);
      (h.kid ? inL : outL).addLayer(m);
      if (h.kid) { const c = byK[h.kid] ||= {high: 0, medium: 0}; c[h.conf]++; }
    });
    if (kaw) Object.entries(kaw.byId).forEach(([id, {props, layer}]) => {
      const c = byK[id] || {high: 0, medium: 0};
      layer.bindPopup(`<b>${esc(props.nkws)}</b><br>${esc(props.nupt)}<hr style="margin:5px 0">High: <span style="color:red">${c.high}</span> | Medium: <span style="color:#d99b00">${c.medium}</span><br>Total: <b>${c.high + c.medium}</b>`);
    });
    $('cHigh').textContent = d.summary.high; $('cMed').textContent = d.summary.medium; $('cTotal').textContent = d.summary.total;
    $('mapStatus').textContent = `Periode ${d.dari} s/d ${d.sampai} • ${d.results.length} titik High/Medium (${inL.getLayers().length} dalam kawasan, ${outL.getLayers().length} di luar).`;
  }

  async function loadStats() {
    const s = await getJSON('/api/hotspot/stats/?' + range());
    weekly = s.weekly;
    if (topChart) topChart.destroy();
    topChart = new Chart($('chTop'), {type: 'bar',
      data: {labels: s.top.map((k) => k.nkws), datasets: [
        {label: 'Medium', data: s.top.map((k) => k.medium), backgroundColor: '#ffa500'},
        {label: 'High', data: s.top.map((k) => k.high), backgroundColor: '#ff4d4d'}]},
      options: {responsive: true, maintainAspectRatio: false, scales: {x: {stacked: true}, y: {stacked: true, beginAtZero: true, ticks: {precision: 0}}}}});
    drawWeekly();
  }
  function drawWeekly() {
    const upt = $('selUpt').value; if (weekChart) weekChart.destroy();
    const colors = ['#d9534f', '#0275d8', '#f0ad4e', '#5cb85c', '#8c38d1', '#e67e22', '#1abc9c', '#e74c3c'];
    const series = (weekly && upt && weekly.series[upt]) || {};
    weekChart = new Chart($('chWeekly'), {type: 'line',
      data: {labels: (weekly?.dates || []).map((d) => new Date(d + 'T12:00').toLocaleDateString('id-ID', {day: '2-digit', month: 'short'})),
        datasets: Object.entries(series).map(([n, data], i) => ({label: n, data, borderColor: colors[i % 8], backgroundColor: colors[i % 8], tension: .1}))},
      options: {responsive: true, maintainAspectRatio: false, plugins: {title: {display: !upt, text: 'Pilih UPT terlebih dahulu.'}}, scales: {y: {beginAtZero: true, ticks: {precision: 0}}}}});
  }

  document.querySelectorAll('.tab-btn').forEach((b) => b.onclick = () => {
    document.querySelectorAll('.tab-btn').forEach((x) => { x.classList.toggle('bg-forest-700', x === b); x.classList.toggle('text-white', x === b); x.classList.toggle('bg-slate-200', x !== b); });
    $('tab-top').classList.toggle('hidden', b.dataset.tab !== 'top'); $('tab-weekly').classList.toggle('hidden', b.dataset.tab !== 'weekly');
    b.dataset.tab === 'weekly' ? drawWeekly() : null;
  });
  $('selUpt').onchange = drawWeekly;
  $('exAll').onchange = updateExports;
  $('fApply').onclick = () => { history.replaceState(null, '', '?' + range()); updateExports(); loadMap(); loadStats(); };
  if ($('btnSync')) $('btnSync').onclick = async () => {
    $('btnSync').disabled = true; toast('Menyinkronkan dari SIPONGI…');
    try { const r = await post('/hotspot/sinkron/'); toast(r.message); setTimeout(() => location.reload(), 1200); }
    catch (e) { toast(e.message, true); $('btnSync').disabled = false; }
  };

  SIAGA.loadKawasan(map).then((k) => {
    kaw = k;
    L.control.layers(bm, {'Hotspot Dalam': inL, 'Hotspot Luar': outL, 'Batas Kawasan': k.layer, 'Label': k.labelGroup}, {collapsed: false}).addTo(map);
    const lg = L.control({position: 'bottomright'});
    lg.onAdd = () => { const d = L.DomUtil.create('div', 'legend'); d.innerHTML = '<b>Legenda</b><br><i style="background:#f00"></i>High<br><i style="background:#ff0"></i>Medium<br><i style="border:2px solid #8c38d1;background:rgba(140,56,209,.15);border-radius:0"></i>Batas Kawasan'; return d; };
    lg.addTo(map); return loadMap();
  }).catch(() => toast('Batas kawasan gagal dimuat.', true));
  updateExports(); loadStats().catch(() => toast('Gagal memuat statistik.', true));
})();
