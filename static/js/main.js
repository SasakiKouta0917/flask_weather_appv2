// ==========================================
// Global State & Config
// ==========================================
const CONFIG = {
    defaultLat: 39.3051,
    defaultLng: 141.1195,
    wmoCodes: {
        0: '快晴', 1: '晴れ', 2: '一部曇り', 3: '曇り',
        45: '霧', 48: '着氷霧',
        51: '霧雨(弱)', 53: '霧雨(中)', 55: '霧雨(強)',
        61: '雨(弱)', 63: '雨(中)', 65: '雨(強)',
        71: '雪(弱)', 73: '雪(中)', 75: '雪(強)',
        80: 'にわか雨(弱)', 81: 'にわか雨(中)', 82: 'にわか雨(強)',
        95: '雷雨', 96: '雷雨(雹)', 99: '雷雨(強雹)'
    },
    weatherColors: {
        sunny: 'rgb(255, 159, 64)',
        cloudy: 'rgb(156, 163, 175)',
        rain: 'rgb(59, 130, 246)',
        snow: 'rgb(6, 182, 212)',
        thunder: 'rgb(168, 85, 247)'
    }
};

let currentWeatherData = null;
let weatherChartInstance = null;
let mapInstance = null;
let markerInstance = null;

function getWeatherColor(code) {
    if ([0, 1].includes(code)) return CONFIG.weatherColors.sunny;
    if ([2, 3, 45, 48].includes(code)) return CONFIG.weatherColors.cloudy;
    if ([71, 73, 75].includes(code)) return CONFIG.weatherColors.snow;
    if ([95, 96, 99].includes(code)) return CONFIG.weatherColors.thunder;
    return CONFIG.weatherColors.rain;
}

// ==========================================
// 1. Map Module
// ==========================================
const MapModule = {
    init: async () => {
        mapInstance = L.map('map').setView([CONFIG.defaultLat, CONFIG.defaultLng], 10);

        const baseLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors'
        }).addTo(mapInstance);

        try {
            const response = await fetch('https://tilecache.rainviewer.com/api/maps.json');
            const results = await response.json();
            
            if (results && results.length > 0) {
                const time = results[results.length - 1];
                const rainLayer = L.tileLayer(`https://tilecache.rainviewer.com/v2/radar/${time}/256/{z}/{x}/{y}/2/1_1.png`, {
                    opacity: 0.6,
                    attribution: 'Radar data &copy; <a href="https://www.rainviewer.com" target="_blank">RainViewer</a>'
                });

                const overlays = { "RainViewer 雨雲": rainLayer };
                L.control.layers({"Base Map": baseLayer}, overlays).addTo(mapInstance);
                rainLayer.addTo(mapInstance);
            }
        } catch (e) {
            console.error("RainViewer fetch failed:", e);
        }

        markerInstance = L.marker([CONFIG.defaultLat, CONFIG.defaultLng], {draggable: true}).addTo(mapInstance);
        
        mapInstance.on('click', (e) => {
            MapModule.updateMarker(e.latlng.lat, e.latlng.lng);
        });

        markerInstance.on('dragend', (e) => {
            const pos = markerInstance.getLatLng();
            MapModule.handleLocationUpdate(pos.lat, pos.lng);
        });

        MapModule.handleLocationUpdate(CONFIG.defaultLat, CONFIG.defaultLng);
    },

    updateMarker: (lat, lng) => {
        markerInstance.setLatLng([lat, lng]);
        MapModule.handleLocationUpdate(lat, lng);
    },

    handleLocationUpdate: (lat, lng) => {
        document.getElementById('coordinates').innerText = `Lat: ${lat.toFixed(4)} / Lon: ${lng.toFixed(4)}`;
        WeatherModule.fetchData(lat, lng);
    }
};

// ==========================================
// 2. Weather Module
// ==========================================
const WeatherModule = {
    fetchData: async (lat, lng) => {
        const btn = document.getElementById('refresh-btn');
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 取得中...';
        
        try {
            // NOTE: hourlyに relative_humidity_2m, precipitation を追加
            const weatherUrl = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lng}&current=temperature_2m,relative_humidity_2m,precipitation,weather_code,surface_pressure&hourly=temperature_2m,relative_humidity_2m,precipitation,precipitation_probability,weather_code&daily=temperature_2m_max,temperature_2m_min&timezone=auto&forecast_days=2`;
            const weatherRes = await fetch(weatherUrl);
            const weatherData = await weatherRes.json();

            let locationName = "指定地点";
            const isKitakamiAcademy = Math.abs(lat - CONFIG.defaultLat) < 0.0005 && Math.abs(lng - CONFIG.defaultLng) < 0.0005;

            if (isKitakamiAcademy) {
                locationName = "北上コンピュータ・アカデミー";
            } else {
                try {
                    const geoUrl = `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}`;
                    const geoRes = await fetch(geoUrl);
                    const geoData = await geoRes.json();
                    const address = geoData.address;
                    locationName = address.city || address.town || address.village || address.county || address.state || "指定地点";
                } catch (e) {
                    console.error("Geocoding failed", e);
                }
            }

            WeatherModule.updateUI(locationName, weatherData);
            
        } catch (error) {
            console.error("Weather fetch error:", error);
            alert("天気情報の取得に失敗しました。");
        } finally {
            btn.innerHTML = '<i class="fa-solid fa-rotate-right"></i> 更新';
        }
    },

    updateUI: (locationName, data) => {
        const current = data.current;
        const daily = data.daily;
        const hourly = data.hourly;
        
        const weatherDesc = CONFIG.wmoCodes[current.weather_code] || `不明(${current.weather_code})`;

        currentWeatherData = {
            location: locationName,
            temp: current.temperature_2m,
            humidity: current.relative_humidity_2m,
            precipitation: current.precipitation,
            weather: weatherDesc,
            temp_max: daily.temperature_2m_max[0],
            temp_min: daily.temperature_2m_min[0]
        };

        // --- 基本情報の更新 ---
        document.getElementById('location-name').innerText = locationName;
        document.getElementById('current-temp').innerText = `${current.temperature_2m}℃`;
        document.getElementById('current-humidity').innerText = `${current.relative_humidity_2m}%`;
        document.getElementById('current-rain').innerText = `${current.precipitation}mm`;
        document.getElementById('current-weather-desc').innerText = weatherDesc;
        
        document.getElementById('temp-max').innerText = daily.temperature_2m_max[0];
        document.getElementById('temp-min').innerText = daily.temperature_2m_min[0];

        // --- 詳細カード情報の算出 (12時間推移から) ---
        
        // 現在時刻のインデックスを取得
        const now = new Date();
        now.setMinutes(0, 0, 0);
        let startIndex = hourly.time.findIndex(t => new Date(t).getTime() >= now.getTime());
        if(startIndex === -1) startIndex = 0;
        
        // 12時間分スライス
        const endIndex = startIndex + 12;
        const next12hTemps = hourly.temperature_2m.slice(startIndex, endIndex); // 気温(未使用だが参照用)
        const next12hHumid = hourly.relative_humidity_2m.slice(startIndex, endIndex);
        const next12hPrecip = hourly.precipitation.slice(startIndex, endIndex);
        const next12hCodes = hourly.weather_code.slice(startIndex, endIndex);

        // 1. 気温詳細 (最高/最低)
        document.getElementById('card-temp-max').innerText = `${daily.temperature_2m_max[0]}℃`;
        document.getElementById('card-temp-min').innerText = `${daily.temperature_2m_min[0]}℃`;

        // 2. 湿度詳細 (最高/最低) - 12時間以内から算出
        const maxHumid = Math.max(...next12hHumid);
        const minHumid = Math.min(...next12hHumid);
        document.getElementById('card-humid-max').innerText = `${maxHumid}%`;
        document.getElementById('card-humid-min').innerText = `${minHumid}%`;

        // 3. 降水量詳細 (最大) - 12時間以内から算出
        const maxPrecip = Math.max(...next12hPrecip);
        document.getElementById('card-rain-max').innerText = `${maxPrecip}mm`;

        // 4. 天気詳細 (変化予測)
        const currentCode = current.weather_code;
        let changeIndex = -1;
        
        // 現在と違う天気になる最初の時間を探す
        for(let i = 0; i < next12hCodes.length; i++) {
            if(next12hCodes[i] !== currentCode) {
                changeIndex = i;
                break;
            }
        }

        if(changeIndex !== -1) {
            // 変化あり
            const nextCode = next12hCodes[changeIndex];
            const nextWeather = CONFIG.wmoCodes[nextCode] || '-';
            document.getElementById('card-weather-time').innerText = `${changeIndex}時間後`;
            document.getElementById('card-weather-val').innerText = nextWeather;
        } else {
            // 変化なし
            document.getElementById('card-weather-time').innerText = `当面`;
            document.getElementById('card-weather-val').innerText = `変化なし`;
        }

        ChartModule.render(data.hourly);
    }
};

// ==========================================
// 3. Chart Module
// ==========================================
const ChartModule = {
    render: (hourly) => {
        const ctx = document.getElementById('weatherChart').getContext('2d');
        const isDark = document.documentElement.classList.contains('dark');
        const textColor = isDark ? '#e2e8f0' : '#666';

        const now = new Date();
        now.setMinutes(0, 0, 0); 

        let startIndex = hourly.time.findIndex(t => new Date(t).getTime() >= now.getTime());
        if(startIndex === -1) startIndex = 0;

        const sliceEnd = startIndex + 12;
        const labels = hourly.time.slice(startIndex, sliceEnd).map(t => t.slice(11, 16));
        const temps = hourly.temperature_2m.slice(startIndex, sliceEnd);
        const precipprobs = hourly.precipitation_probability.slice(startIndex, sliceEnd);
        const weatherCodes = hourly.weather_code.slice(startIndex, sliceEnd);

        if (weatherChartInstance) {
            weatherChartInstance.destroy();
        }

        weatherChartInstance = new Chart(ctx, {
            type: 'line',
            plugins: [ChartDataLabels],
            data: {
                labels: labels,
                datasets: [
                    {
                        label: '気温 (℃)',
                        data: temps,
                        segment: {
                            borderColor: ctx => {
                                const index = ctx.p1DataIndex;
                                const code = weatherCodes[index];
                                return getWeatherColor(code);
                            }
                        },
                        borderColor: 'rgb(255, 99, 132)',
                        backgroundColor: 'rgba(255, 99, 132, 0.2)',
                        yAxisID: 'y',
                        tension: 0.4,
                        animation: {
                            duration: 1500,
                            easing: 'easeOutQuart'
                        },
                        datalabels: {
                            align: 'top',
                            anchor: 'end',
                            offset: 4,
                            color: textColor,
                            font: {
                                size: 10,
                                weight: 'bold'
                            },
                            formatter: (value, context) => {
                                const index = context.dataIndex;
                                if (index === 0) return CONFIG.wmoCodes[weatherCodes[index]];
                                if (weatherCodes[index] !== weatherCodes[index - 1]) return CONFIG.wmoCodes[weatherCodes[index]];
                                return null;
                            }
                        }
                    },
                    {
                        label: '降水確率 (%)',
                        data: precipprobs,
                        type: 'bar',
                        backgroundColor: 'rgba(54, 162, 235, 0.5)',
                        yAxisID: 'y1',
                        datalabels: { display: false }
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                scales: {
                    x: { ticks: { color: textColor } },
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        ticks: { display: true, color: textColor },
                        title: { display: false }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        grid: { drawOnChartArea: false },
                        min: 0, max: 100,
                        ticks: { display: false }, 
                        title: { display: false }
                    }
                },
                plugins: {
                    legend: { labels: { color: textColor } }
                }
            }
        });
    }
};

// ==========================================
// 4. AI Module
// ==========================================
const AIModule = {
    suggestOutfit: async () => {
        const btn = document.getElementById('ai-suggest-btn');
        const scene = document.getElementById('scene-select').value;

        if (!currentWeatherData) {
            alert("先に地図をクリックして天気情報を取得してください。");
            return;
        }

        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 取得中...';

        try {
            const response = await fetch("/api/suggest_outfit", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    weather_data: currentWeatherData,
                    scene: scene
                })
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.error || "Server API Error");
            }

            const data = await response.json();
            AIModule.renderResult(data.suggestions);
            btn.innerHTML = '<i class="fa-solid fa-robot"></i> 再取得';

        } catch (error) {
            console.error("AI Error:", error);
            alert(`エラーが発生しました: ${error.message}`);
            btn.innerHTML = '<i class="fa-solid fa-rotate-right"></i> 再試行';
        } finally {
            btn.disabled = false;
        }
    },

    renderResult: (suggestions) => {
        const resultArea = document.getElementById('ai-result-area');
        let html = '';

        suggestions.forEach((item, index) => {
            const delay = index * 0.1;
            html += `
                <div class="bg-white dark:bg-slate-700 border border-purple-200 dark:border-slate-600 rounded-lg p-4 hover:border-purple-300 dark:hover:border-purple-500 transition shadow-sm hover:shadow-md fade-in-up" style="animation-delay: ${delay}s">
                    <h4 class="font-bold text-purple-600 dark:text-purple-400 mb-2 border-b border-purple-100 dark:border-slate-600 pb-1">
                        <i class="fa-regular fa-clock"></i> ${item.period}
                    </h4>
                    <p class="text-gray-700 dark:text-slate-200 text-sm whitespace-pre-wrap leading-relaxed">${item.any}</p>
                </div>
            `;
        });
        resultArea.innerHTML = `<div class="flex flex-col gap-4 w-full">${html}</div>`;
    }
};

// ==========================================
// 5. Theme & Interaction Module
// ==========================================
const ThemeModule = {
    init: () => {
        const toggleBtn = document.getElementById('theme-toggle-btn');
        const btnText = document.getElementById('theme-btn-text');
        
        toggleBtn.addEventListener('click', () => {
            document.documentElement.classList.toggle('dark');
            const isDark = document.documentElement.classList.contains('dark');
            btnText.innerText = isDark ? 'ライト' : 'ダーク';
            
            if(weatherChartInstance) {
                const textColor = isDark ? '#e2e8f0' : '#666';
                weatherChartInstance.options.scales.x.ticks.color = textColor;
                weatherChartInstance.options.scales.y.ticks.color = textColor;
                weatherChartInstance.options.plugins.legend.labels.color = textColor;
                weatherChartInstance.data.datasets[0].datalabels.color = textColor;
                weatherChartInstance.update();
            }
        });

        // 4つのカード全てにインタラクションを追加
        // interactive-cardクラスを持つ要素を全て取得
        const cards = document.querySelectorAll('.interactive-card');
        cards.forEach(card => {
            card.addEventListener('click', () => {
                card.classList.toggle('show-detail');
            });
        });
    }
};

document.addEventListener('DOMContentLoaded', () => {
    MapModule.init();
    ThemeModule.init();

    document.getElementById('refresh-btn').addEventListener('click', () => {
        MapModule.updateMarker(CONFIG.defaultLat, CONFIG.defaultLng);
        mapInstance.setView([CONFIG.defaultLat, CONFIG.defaultLng], 10);
        
        const btn = document.getElementById('refresh-btn');
        btn.classList.add('bg-gray-200', 'dark:bg-slate-600');
        setTimeout(() => btn.classList.remove('bg-gray-200', 'dark:bg-slate-600'), 200);
    });

    document.getElementById('ai-suggest-btn').addEventListener('click', () => {
        AIModule.suggestOutfit();
    });
});
