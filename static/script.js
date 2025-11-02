// === 設定（北上コンピュータ・アカデミー：初期位置） ===
const INIT_LAT = 39.30506946;
const INIT_LON = 141.11956806;

let map, marker;
let hourlyChart = null;

function setText(id, v) {
  const e = document.getElementById(id);
  if (!e) return;
  e.textContent = (v === undefined || v === null) ? '--' : v;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  }[c]));
}

// ---- ページ読込後 ----
document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('theme-toggle');
  if (btn) {
    btn.textContent = document.body.classList.contains('dark') ? "ライトテーマ" : "ダークテーマ";
  }

  initMap();

  const updateBtn = document.getElementById('update-btn');
  if (updateBtn) {
    updateBtn.addEventListener('click', async () => {
      marker.setLatLng([INIT_LAT, INIT_LON]);
      map.setView([INIT_LAT, INIT_LON], 13);
      await fetchWeather(INIT_LAT, INIT_LON);
    });
  }

  const sbtn = document.getElementById("suggest-btn");
  if (sbtn) {
    sbtn.addEventListener('click', async () => {
      const w = {
        weather: document.getElementById("weather-main").textContent,
        temp: document.getElementById("temperature").textContent,
        temp_max: document.getElementById("max-temp").textContent,
        temp_min: document.getElementById("min-temp").textContent,
        humidity: document.getElementById("humidity").textContent,
        precipitation: document.getElementById("precipitation").textContent
      };
      await fetchSuggest(w);
    });
  }

  if (btn) {
    btn.addEventListener('click', () => {
      document.body.classList.toggle('dark');
      btn.textContent = document.body.classList.contains('dark') ? 'ライトテーマ' : 'ダークテーマ';
    });
  }
});

// === 地図 ===
function initMap() {
  map = L.map('map').setView([INIT_LAT, INIT_LON], 13);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(map);

  marker = L.marker([INIT_LAT, INIT_LON]).addTo(map);

  setText('location', '北上コンピュータ・アカデミー');

  map.on('click', async (e) => {
    const lat = e.latlng.lat;
    const lon = e.latlng.lng;
    marker.setLatLng([lat, lon]);
    await fetchWeather(lat, lon);
    showPopup(lat, lon, '現在地の天気を取得しました');
  });

  fetchWeather(INIT_LAT, INIT_LON);
}

// ポップアップを5秒後に閉じる関数
function showPopup(lat, lon, text) {
  const pop = L.popup()
    .setLatLng([lat, lon])
    .setContent(text)
    .openOn(map);

  // 5秒後に自動で閉じる
  setTimeout(() => { map.closePopup(pop); }, 5000);
}

// ✅ Amedas＋Open-Meteo
async function fetchWeather(lat, lon) {
  try {
    const res = await fetch(`/api/weather?lat=${lat}&lon=${lon}`);
    const j = await res.json();

    if (!j || j.status !== "ok") {
      applyWeatherDummy();
      return;
    }

    setText('location', j.station_name);
    setText('weather-main', j.weather);
    setText('temperature', j.temperature);
    setText('humidity', j.humidity);
    setText('pressure', j.pressure);
    setText('precipitation', j.precipitation);
    setText('max-temp', j.temp_max);
    setText('min-temp', j.temp_min);

    if (j.hourly) {
      renderHourlyPanel(j.hourly);
      drawTempChartFromHourly(j.hourly);
    }

  } catch (e) {
    applyWeatherDummy();
  }
}

// ---- 12時間 ----
function renderHourlyPanel(arr) {
  const sc = document.getElementById('overlay-scroll');
  if (!sc) return;
  sc.innerHTML = '';
  arr.forEach(h => {
    const icon = (h.weather.includes('雨')) ? '🌧️' : '☀️';
    const div = document.createElement('div');
    div.className = 'overlay-hour-tile';
    div.innerHTML = `<div style="font-size:12px;color:#555">${h.label}</div>
                     <div style="font-size:20px;margin:6px 0">${icon}</div>
                     <div style="font-weight:700">${Math.round(h.temp)}℃</div>
                     <div style="font-size:12px;color:#777">${h.weather}</div>`;
    sc.appendChild(div);
  });
}

// ---- チャート ----
function drawTempChartFromHourly(arr) {
  const c = document.getElementById('hourly-chart');
  if (!c) return;

  const labels = arr.map(h => h.label);
  const data = arr.map(h => Math.round(h.temp));

  const ctx = c.getContext('2d');
  if (hourlyChart) hourlyChart.destroy();
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
        borderWidth: 2
      }]
    },
    options: {
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false } },
        y: { beginAtZero: false }
      },
      maintainAspectRatio: false
    }
  });
}
