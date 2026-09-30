/* Utilitas bersama SIAGA */
window.SIAGA = (() => {
  const csrf = () => document.querySelector('meta[name="csrf-token"]').content;
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const STATUS = {
    'Upaya Pemadaman': {badge: 'bg-red-600', icon: '♨', color: '#dc2626'},
    'Proses Groundcheck': {badge: 'bg-amber-500', icon: '⌖', color: '#eab308'},
    'Sudah Padam': {badge: 'bg-blue-600', icon: '✓', color: '#2563eb'},
    'Perlu Konfirmasi': {badge: 'bg-purple-600', icon: '!', color: '#9333ea'},
    'False Hotspot': {badge: 'bg-gray-600', icon: '×', color: '#6b7280'},
  };
  const badge = (s) => { const m = STATUS[s] || STATUS['Perlu Konfirmasi'];
    return `<span class="inline-flex items-center gap-1 rounded-full ${m.badge} px-2 py-1 text-xs font-bold text-white">${m.icon} ${esc(s)}</span>`; };
  async function getJSON(url) {
    const r = await fetch(url, {headers: {Accept: 'application/json'}, credentials: 'same-origin'});
    if (r.status === 401) { location.href = '/masuk/?next=' + encodeURIComponent(location.pathname + location.search); throw new Error('login'); }
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.json();
  }
  async function post(url, body) {
    const r = await fetch(url, {method: 'POST', credentials: 'same-origin',
      headers: {'X-CSRFToken': csrf(), Accept: 'application/json', ...(body ? {'Content-Type': 'application/json'} : {})},
      body: body ? JSON.stringify(body) : undefined});
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.error || 'HTTP ' + r.status);
    return data;
  }
  function toast(msg, bad = false) {
    let e = document.getElementById('toast');
    if (!e) { e = document.createElement('div'); e.id = 'toast'; document.body.appendChild(e); }
    e.className = `fixed bottom-5 right-5 z-[99999] max-w-sm rounded-xl px-4 py-3 text-sm font-medium text-white shadow-xl ${bad ? 'bg-red-700' : 'bg-slate-900'}`;
    e.textContent = msg; clearTimeout(e._t); e._t = setTimeout(() => e.classList.add('hidden'), 3500);
  }
  const basemaps = () => ({
    'Satelit (Esri)': L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {maxZoom: 19, attribution: 'Tiles &copy; Esri'}),
    'OpenStreetMap': L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 19, attribution: '&copy; OpenStreetMap'}),
  });
  /* Batas kawasan + label dinamis. Kembalikan {layer, byId}. */
  async function loadKawasan(map, {onClickPopup = true, labels = true} = {}) {
    const data = await getJSON('/api/kawasan/geojson/');
    const byId = {}; const labelGroup = L.layerGroup().addTo(map);
    const layer = L.geoJSON(data, {
      style: {color: '#8c38d1', weight: 2, opacity: .9, fillColor: '#8c38d1', fillOpacity: .05},
      onEachFeature: (f, l) => { byId[f.properties.id] = {props: f.properties, layer: l};
        if (onClickPopup) l.bindPopup(`<b>${esc(f.properties.nkws)}</b><br>${esc(f.properties.nupt)}`); },
    }).addTo(map);
    function renderLabels() {
      labelGroup.clearLayers();
      const z = map.getZoom(); if (!labels || z < 9) return;
      const b = map.getBounds();
      Object.values(byId).forEach(({props, layer: l}) => {
        if (!b.intersects(l.getBounds())) return;
        const c = l.getBounds().getCenter();
        labelGroup.addLayer(L.marker(c, {interactive: false, icon: L.divIcon({className: 'kawasan-label',
          html: `<div style="font-size:${Math.max(8, 9 + (z - 9) * 1.1)}px">${esc(props.nkws)}</div>`, iconSize: [0, 0]})}));
      });
    }
    map.on('moveend zoomend', renderLabels); renderLabels();
    return {layer, byId, labelGroup};
  }
  const fmtDate = (iso) => new Intl.DateTimeFormat('id-ID', {day: '2-digit', month: 'short', year: 'numeric'}).format(new Date(iso + 'T12:00:00'));
  return {csrf, esc, STATUS, badge, getJSON, post, toast, basemaps, loadKawasan, fmtDate};
})();
