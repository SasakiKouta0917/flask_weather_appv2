// ==========================================
// Global State & Config
// ==========================================
const CONFIG = {
    // ユーザー指定: 北上コンピュータ・アカデミーの座標
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
    // 天気ごとの色定義
    weatherColors: {
        sunny: 'rgb(255, 159, 64)', // Orange
        cloudy: 'rgb(156, 163, 175)', // Gray
        rain: 'rgb(59, 130, 246)',    // Blue
        snow: 'rgb(6, 182, 212)',     // Cyan
        thunder: 'rgb(168, 85, 247)'  // Purple
    }
};

let currentWeatherData = null; // AIプロンプト用にデータを保持
let weatherChartInstance = null;
let mapInstance = null;
let markerInstance = null;

// Helper: 天気コードから色を取得
function getWeatherColor(code) {
    if ([0, 1].includes(code)) return CONFIG.weatherColors.sunny;
    if ([2, 3, 45, 48].includes(code)) return CONFIG.weatherColors.cloudy;
    if ([71, 73, 75].includes(code)) return CONFIG.weatherColors.snow;
    if ([95, 96, 99].includes(code)) return CONFIG.weatherColors.thunder;
    // その他は雨とみなす
    return CONFIG.weatherColors.rain;
}

// ==========================================
// 1. Map Module (Leaflet + RainViewer)
// ==========================================
const MapModule = {
    init: async () => {
        // マップ初期化
        mapInstance = L.map('map').setView([CONFIG.defaultLat, CONFIG.defaultLng], 14);

        // Base Map (OpenStreetMap)
        const baseLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors'
        }).addTo(mapInstance);

        // RainViewer Layer logic
        try {
            const response = await fetch('https://tilecache.rainviewer.com/api/maps.json');
            const results = await response.json();
            
            if (results && results.length > 0) {
                const time = results[results.length - 1]; // Latest timestamp
                const rainLayer = L.tileLayer(`https://tilecache.rainviewer.com/v2/radar/${time}/256/{z}/{x}/{y}/2/1_1.png`, {
                    opacity: 0.6,
                    attribution: 'Radar data &copy; <a href="https://www.rainviewer.com" target="_blank">RainViewer</a>'
                });

                const overlays = {
                    "RainViewer 雨雲": rainLayer
                };
                L.control.layers({"Base Map": baseLayer}, overlays).addTo(mapInstance);
                rainLayer.addTo(mapInstance); // Enable by default
            }
        } catch (e) {
            console.error("RainViewer fetch failed:", e);
        }

        // Marker Logic (Initial position)
        markerInstance = L.marker([CONFIG.defaultLat, CONFIG.defaultLng], {draggable: true}).addTo(mapInstance);
        
        // Map Click Event
        mapInstance.on('click', (e) => {
            MapModule.updateMarker(e.latlng.lat, e.latlng.lng);
        });

        // Marker Drag Event
        markerInstance.on('dragend', (e) => {
            const pos = markerInstance.getLatLng();
            MapModule.handleLocationUpdate(pos.lat, pos.lng);
        });

        // Initial Load
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
// 2. Weather Module (OpenMeteo)
// ==========================================
const WeatherModule = {
    fetchData: async (lat, lng) => {
        const btn = document.getElementById('refresh-btn');
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 取得中...';
        
        try {
            // 2.1 Fetch Weather Data
            // NOTE: hourlyにweather_codeを追加して取得
            const weatherUrl = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lng}&current=temperature_2m,relative_humidity_2m,precipitation,weather_code,surface_pressure&hourly=temperature_2m,precipitation_probability,weather_code&daily=temperature_2m_max,temperature_2m_min&timezone=auto&forecast_days=2`;
            const weatherRes = await fetch(weatherUrl);
            const weatherData = await weatherRes.json();

            // 2.2 Reverse Geocoding
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

            // Update UI
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

        document.getElementById('location-name').innerText = locationName;
        document.getElementById('current-temp').innerText = `${current.temperature_2m}℃`;
        document.getElementById('current-humidity').innerText = `${current.relative_humidity_2m}%`;
        document.getElementById('current-rain').innerText = `${current.precipitation}mm`;
        document.getElementById('current-weather-desc').innerText = weatherDesc;
        document.getElementById('temp-max').innerText = daily.temperature_2m_max[0];
        document.getElementById('temp-min').innerText = daily.temperature_2m_min[0];

        ChartModule.render(data.hourly);
    }
};

// ==========================================
// 3. Chart Module (Chart.js)
// ==========================================
const ChartModule = {
    render: (hourly) => {
        const ctx = document.getElementById('weatherChart').getContext('2d');
        const isDark = document.documentElement.classList.contains('dark');
        const textColor = isDark ? '#e2e8f0' : '#666';

        // 現在時刻（時）のインデックスを取得
        const now = new Date();
        now.setMinutes(0, 0, 0); 

        let startIndex = hourly.time.findIndex(t => {
            const dataTime = new Date(t);
            return dataTime.getTime() >= now.getTime();
        });
        
        if(startIndex === -1) startIndex = 0;

        // 次の12時間をスライス
        const sliceEnd = startIndex + 12;
        const labels = hourly.time.slice(startIndex, sliceEnd).map(t => t.slice(11, 16));
        const temps = hourly.temperature_2m.slice(startIndex, sliceEnd);
        const precipprobs = hourly.precipitation_probability.slice(startIndex, sliceEnd);
        const weatherCodes = hourly.weather_code.slice(startIndex, sliceEnd);

        if (weatherChartInstance) {
            weatherChartInstance.destroy();
        }

        // ChartDataLabelsプラグインの登録（CDNで読み込んだ場合、グローバルにある場合もあるが明示的に）
        // Chart.js 3+ では plugins 配列で指定可能
        
        weatherChartInstance = new Chart(ctx, {
            type: 'line',
            plugins: [ChartDataLabels], // プラグインを有効化
            data: {
                labels: labels,
                datasets: [
                    {
                        label: '気温 (℃)',
                        data: temps,
                        // 線の色: セグメントごとに変更
                        segment: {
                            borderColor: ctx => {
                                // セグメントの終点の天気で色を決める
                                const index = ctx.p1DataIndex;
                                const code = weatherCodes[index];
                                return getWeatherColor(code);
                            }
                        },
                        // デフォルト色（フォールバック）
                        borderColor: 'rgb(255, 99, 132)',
                        backgroundColor: 'rgba(255, 99, 132, 0.2)',
                        yAxisID: 'y',
                        tension: 0.4,
                        animation: {
                            duration: 1500,
                            easing: 'easeOutQuart'
                        },
                        // データラベル（天候テキスト）の設定
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
                                // 最初(現在)は必ず表示
                                if (index === 0) {
                                    return CONFIG.wmoCodes[weatherCodes[index]];
                                }
                                // 天気が変わった時だけ表示
                                if (weatherCodes[index] !== weatherCodes[index - 1]) {
                                    return CONFIG.wmoCodes[weatherCodes[index]];
                                }
                                return null; // 表示しない
                            }
                        }
                    },
                    {
                        label: '降水確率 (%)',
                        data: precipprobs,
                        type: 'bar',
                        backgroundColor: 'rgba(54, 162, 235, 0.5)',
                        yAxisID: 'y1',
                        datalabels: {
                            display: false // 棒グラフにはラベルを表示しない
                        }
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
                    x: {
                        ticks: { color: textColor }
                    },
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        // 修正: 縦軸ラベルを表示する
                        ticks: { 
                            display: true,
                            color: textColor 
                        },
                        title: { display: false }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        grid: { drawOnChartArea: false },
                        min: 0,
                        max: 100,
                        ticks: { 
                            display: false // 降水確率は縦軸なしのまま（見やすさ優先）
                        }, 
                        title: { display: false }
                    }
                },
                plugins: {
                    legend: {
                        labels: { color: textColor }
                    }
                }
            }
        });
    }
};

// ==========================================
// 4. AI Module (Backend Integration)
// ==========================================
const AIModule = {
    suggestOutfit: async () => {
        const btn = document.getElementById('ai-suggest-btn');
        const resultArea = document.getElementById('ai-result-area');
        const scene = document.getElementById('scene-select').value;

        if (!currentWeatherData) {
            alert("先に地図をクリックして天気情報を取得してください。");
            return;
        }

        // Update Button State
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 取得中...';

        try {
            // Call Python Backend
            const response = await fetch("/api/suggest_outfit", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
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
            
            if (data.type === "error") {
                AIModule.renderResult(data.suggestions);
            } else {
                AIModule.renderResult(data.suggestions);
            }

            btn.innerHTML = '<i class="fa-solid fa-robot"></i> 再取得';

        } catch (error) {
            console.error("AI Error:", error);
            resultArea.innerHTML = `<div class="bg-red-50 text-red-600 p-4 rounded">エラーが発生しました: ${error.message}</div>`;
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
// 5. Theme Module
// ==========================================
const ThemeModule = {
    init: () => {
        const toggleBtn = document.getElementById('theme-toggle-btn');
        const btnText = document.getElementById('theme-btn-text');
        
        toggleBtn.addEventListener('click', () => {
            document.documentElement.classList.toggle('dark');
            const isDark = document.documentElement.classList.contains('dark');
            
            // ボタンテキストの切り替え
            btnText.innerText = isDark ? 'ライト' : 'ダーク';
            
            // グラフの色再描画
            if(weatherChartInstance) {
                const textColor = isDark ? '#e2e8f0' : '#666';
                weatherChartInstance.options.scales.x.ticks.color = textColor;
                weatherChartInstance.options.scales.y.ticks.color = textColor; // Y軸も更新
                weatherChartInstance.options.plugins.legend.labels.color = textColor;
                weatherChartInstance.data.datasets[0].datalabels.color = textColor; // データラベルの色も更新
                weatherChartInstance.update();
            }
        });
    }
};

// ==========================================
// Event Listeners
// ==========================================
document.addEventListener('DOMContentLoaded', () => {
    MapModule.init();
    ThemeModule.init();

    // 更新ボタン: 初期位置（北上コンピュータ・アカデミー）に戻す機能
    document.getElementById('refresh-btn').addEventListener('click', () => {
        MapModule.updateMarker(CONFIG.defaultLat, CONFIG.defaultLng);
        mapInstance.setView([CONFIG.defaultLat, CONFIG.defaultLng], 14);
        
        const btn = document.getElementById('refresh-btn');
        btn.classList.add('bg-gray-200', 'dark:bg-slate-600');
        setTimeout(() => btn.classList.remove('bg-gray-200', 'dark:bg-slate-600'), 200);
    });

    document.getElementById('ai-suggest-btn').addEventListener('click', () => {
        AIModule.suggestOutfit();
    });
});
