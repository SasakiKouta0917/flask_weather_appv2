// === 設定（北上コンピュータ・アカデミー：初期位置） ===
const INIT_LAT = 39.30506946;
const INIT_LON = 141.11956806;

let map, marker;
let hourlyChart = null;

// helper
function setText(id, v){
  const e = document.getElementById(id);
  if(!e) return;
  e.textContent = (v === undefined || v === null) ? '--' : v;
}
function escapeHtml(s){
  return String(s).replace(/[&<>"']/g, c => (
    {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]
  ));
}

// === 逆ジオコーディング ===
async function fetchPlaceName(lat, lon){
  try{
    const url = `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}&zoom=14&addressdetails=1`;
    const res = await fetch(url, { headers: { 'User-Agent': 'weather-app' }});
    if(!res.ok) throw new Error("reverse geocode error");
    const j = await res.json();
    return j.display_name || `${lat.toFixed(5)}, ${lon.toFixed(5)}`;
  }catch(e){
    console.error(e);
    return `${lat.toFixed(5)}, ${lon.toFixed(5)}`;
  }
}

// === マップ初期化 ===
function initMap(){
  map = L.map('map', { zoomControl: true }).setView([INIT_LAT, INIT_LON], 13);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(map);

  marker = L.marker([INIT_LAT, INIT_LON]).addTo(map);

  // 初期表示
  setText('location', '北上コンピュータ・アカデミー');
  marker.bindPopup('<div>北上コンピュータ・アカデミー</div>').openPopup();

  // クリックでピン移動＋地名取得＋天気更新
  map.on('click', async (e) => {
    const lat = e.latlng.lat;
    const lon = e.latlng.lng;

    // ピンを移動
    marker.setLatLng([lat, lon]);

    // 地名を取得
    const name = await fetchPlaceName(lat, lon);

    // 画面の「現在地」更新
    setText('location', name);

    // ピンの上にポップアップ表示
    marker.bindPopup(`<div>${escapeHtml(name)}</div>`).openPopup();

    // 天気データ更新
    await fetchWeather(lat, lon);
    await fetchHourly(lat, lon);
  });

  // 初期ロード
  fetchWeather(INIT_LAT, INIT_LON);
  fetchHourly(INIT_LAT, INIT_LON);
}

// === 現在の天気（Flask /update） ===
async function fetchWeather(lat, lon){
  try{
    const res = await fetch('/update', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ lat, lon })
    });
    if(!res.ok) throw new Error('update endpoint error');
    const j = await res.json();
    if(j.status !== 'ok' || !j.weather) throw new Error('bad weather payload');

    const w = j.weather;
    setText('weather-main', w.weather);
    setText('temperature', Math.round(w.temp));
    setText('humidity', w.humidity);
    setText('precipitation', w.precipitation); // 単位はHTML側に任せる
    setText('pressure', Math.round(w.pressure));
    setText('max-temp', Math.round(w.temp_max));
    setText('min-temp', Math.round(w.temp_min));

  }catch(err){
    console.error('fetchWeather error:', err);
  }
}

// === 12時間予報（Flask /hourly） ===
async function fetchHourly(lat, lon){
  try{
    const res = await fetch(`/hourly?lat=${lat}&lon=${lon}`);
    if(!res.ok) throw new Error('hourly endpoint error');
    const j = await res.json();
    if(j.status !== 'ok' || !Array.isArray(j.hourly)) throw new Error('bad hourly payload');

    renderHourlyPanel(j.hourly);
    drawTempChartFromHourly(j.hourly);

  }catch(err){
    console.error('fetchHourly error:', err);
    document.getElementById('overlay-scroll').innerHTML = '';
    if(hourlyChart){ hourlyChart.destroy(); hourlyChart = null; }
  }
}

// === 予報パネル描画 ===
function renderHourlyPanel(arr){
  const sc = document.getElementById('overlay-scroll');
  sc.innerHTML = '';
  arr.forEach(h => {
    const temp = (h.temp !== undefined && h.temp !== null) ? Math.round(h.temp) : '--';
    const icon = weatherEmojiFromCode(h.weathercode);

    const div = document.createElement('div');
    div.className = 'overlay-hour-tile';
    div.innerHTML =
      `<div style="font-size:12px;color:#555">${escapeHtml(h.label || '')}</div>
       <div style="font-size:20px;margin:6px 0">${icon}</div>
       <div style="font-weight:700">${temp}℃</div>
       <div style="font-size:12px;color:#777">${escapeHtml(h.weather || '')}</div>
       <div style="font-size:12px;color:#777">${(h.precipitation ?? '--')} mm</div>`;
    sc.appendChild(div);
  });
}

// === 天気コード→絵文字 ===
function weatherEmojiFromCode(code){
  if(code === 0) return '☀️';
  if(code >= 1 && code <= 3) return '⛅';
  if(code >= 61 && code < 70) return '🌧️';
  if(code >= 71 && code < 80) return '❄️';
  if(code >= 95) return '⛈️';
  return '🌤️';
}

// === 気温折れ線グラフ ===
function drawTempChartFromHourly(arr){
  const labels = arr.map(h => h.label || '');
  const data = arr.map(h => {
    const t = h.temp;
    return (t === undefined || t === null) ? null : Math.round(t);
  });

  const ctx = document.getElementById('hourly-chart').getContext('2d');
  if(hourlyChart) hourlyChart.destroy();

  hourlyChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: '気温 (℃)',
        data,
        borderColor: 'rgba(11,108,255,0.9)',
        backgroundColor: 'rgba(11,108,255,0.08)',
        tension: 0.3,
        pointRadius: 3,
        borderWidth: 2,
        spanGaps: true
      }]
    },
    options: {
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false } },
        y: { beginAtZero: false, grid: { color: 'rgba(0,0,0,0.06)' } }
      },
      maintainAspectRatio: false
    }
  });
}

// === 服装提案 ===
async function fetchSuggest(){
  try{
    const res = await fetch('/suggest', { method:'POST' });
    if(!res.ok) throw new Error('suggest endpoint error');
    const j = await res.json();

    const box = document.getElementById('suggestions');
    box.innerHTML = '';

    if(j && j.status === 'ok' && j.suggestion){
      const arr = j.suggestion.suggestions || [];
      arr.forEach(it => {
        const p = document.createElement('p');
        const period = it.period || '';
        const any = it.any || '';
        p.innerHTML = `<b>${escapeHtml(period)}</b>： ${escapeHtml(any)}`;
        box.appendChild(p);
      });
    } else {
      box.textContent = '提案が取得できませんでした';
    }
  }catch(err){
    console.error('fetchSuggest error:', err);
    document.getElementById('suggestions').textContent = '服装提案取得エラー';
  }
}

// === 初期化＆イベント ===
document.addEventListener('DOMContentLoaded', () => {
  // マップ
  initMap();

  // テーマボタン初期テキスト
  const themeBtn = document.getElementById('theme-toggle');
  themeBtn.textContent = document.body.classList.contains('dark') ? 'ライトテーマ' : 'ダークテーマ';

  // 最新の天気を更新（初期位置へ戻る）
  document.getElementById('update-btn').addEventListener('click', async () => {
    marker.setLatLng([INIT_LAT, INIT_LON]);
    map.setView([INIT_LAT, INIT_LON], 13);

    // 初期位置の地名を再表示（Nominatimで取得してもOK）
    setText('location', '北上コンピュータ・アカデミー');
    marker.bindPopup('<div>北上コンピュータ・アカデミー</div>').openPopup();

    await fetchWeather(INIT_LAT, INIT_LON);
    await fetchHourly(INIT_LAT, INIT_LON);
  });

  // テーマ切替
  themeBtn.addEventListener('click', () => {
    document.body.classList.toggle('dark');
    themeBtn.textContent = document.body.classList.contains('dark') ? 'ライトテーマ' : 'ダークテーマ';
  });

  // 服装提案
  document.getElementById('suggest-btn').addEventListener('click', fetchSuggest);
});

