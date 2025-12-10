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
    weatherIcons: {
        0: 'fa-sun text-orange-500', 1: 'fa-sun text-orange-500', 2: 'fa-cloud-sun text-orange-400', 3: 'fa-cloud text-gray-500',
        45: 'fa-smog text-gray-400', 48: 'fa-smog text-gray-400',
        51: 'fa-cloud-rain text-blue-400', 53: 'fa-cloud-rain text-blue-400', 55: 'fa-cloud-rain text-blue-500',
        61: 'fa-umbrella text-blue-500', 63: 'fa-umbrella text-blue-600', 65: 'fa-umbrella text-blue-700',
        71: 'fa-snowflake text-cyan-400', 73: 'fa-snowflake text-cyan-500', 75: 'fa-snowflake text-cyan-600',
        80: 'fa-cloud-showers-heavy text-blue-500', 81: 'fa-cloud-showers-heavy text-blue-600', 82: 'fa-cloud-showers-heavy text-blue-700',
        95: 'fa-bolt text-yellow-500', 96: 'fa-bolt text-yellow-500', 99: 'fa-bolt text-yellow-600'
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

function getWeatherIconClass(code) {
    return CONFIG.weatherIcons[code] || 'fa-question text-gray-400';
}

// ==========================================
// Time Module
// ==========================================
const TimeModule = {
    lastUpdated: null,
    intervalId: null,
    hasTriggeredAutoShow: false,

    init: () => {
        TimeModule.lastUpdated = new Date();
        TimeModule.startTimer();
    },

    reset: () => {
        TimeModule.lastUpdated = new Date();
        TimeModule.hasTriggeredAutoShow = false;
        TimeModule.updateDisplay();
    },

    startTimer: () => {
        if (TimeModule.intervalId) clearInterval(TimeModule.intervalId);
        TimeModule.intervalId = setInterval(TimeModule.updateDisplay, 1000);
    },

    updateDisplay: () => {
        const now = new Date();
        const diffMs = now - TimeModule.lastUpdated;
        const diffSec = Math.floor(diffMs / 1000);

        if (diffSec === 5 && !TimeModule.hasTriggeredAutoShow) {
            TimeModule.hasTriggeredAutoShow = true;
            ThemeModule.triggerAutoShow();
        }

        let text = "";
        
        if (diffSec < 60) {
            text = `前回の更新から ${String(diffSec).padStart(2, '0')}秒`;
        } else if (diffSec < 3600) {
            const min = Math.floor(diffSec / 60);
            text = `前回の更新から ${String(min).padStart(2, '0')}分`;
        } else {
            const hour = Math.floor(diffSec / 3600);
            text = `前回の更新から ${String(hour).padStart(2, '0')}時間`;
        }

        const timerEl = document.getElementById('update-timer');
        if (timerEl) {
            timerEl.innerText = text;
        }
    }
};

// ==========================================
// 1. Map Module
// ==========================================
const MapModule = {
    rainLayer: null,
    layerControl: null,

    init: async () => {
        mapInstance = L.map('map').setView([CONFIG.defaultLat, CONFIG.defaultLng], 10);

        const baseLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors'
        }).addTo(mapInstance);

        MapModule.layerControl = L.control.layers({"Base Map": baseLayer}, {}).addTo(mapInstance);
        await MapModule.updateRadar();

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

    updateRadar: async () => {
        if (MapModule.rainLayer) {
            mapInstance.removeLayer(MapModule.rainLayer);
            MapModule.layerControl.removeLayer(MapModule.rainLayer);
            MapModule.rainLayer = null;
        }

        try {
            const response = await fetch('https://tilecache.rainviewer.com/api/maps.json');
            const results = await response.json();
            
            if (results && results.length > 0) {
                const time = results[results.length - 1]; 
                MapModule.rainLayer = L.tileLayer(`https://tilecache.rainviewer.com/v2/radar/${time}/256/{z}/{x}/{y}/2/1_1.png`, {
                    opacity: 0.6,
                    attribution: 'Radar data &copy; <a href="https://www.rainviewer.com" target="_blank">RainViewer</a>'
                });
                MapModule.rainLayer.addTo(mapInstance);
                MapModule.layerControl.addOverlay(MapModule.rainLayer, "RainViewer 雨雲");
            }
        } catch (e) {
            console.error("RainViewer update failed:", e);
        }
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
            const weatherUrl = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lng}&current=temperature_2m,relative_humidity_2m,precipitation,weather_code,surface_pressure&hourly=temperature_2m,relative_humidity_2m,precipitation,precipitation_probability,weather_code&daily=temperature_2m_max,temperature_2m_min,weather_code,precipitation_probability_max&timezone=auto&forecast_days=8`;
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
        const hourly = data.hourly;
        const daily = data.daily;

        const weatherDesc = CONFIG.wmoCodes[current.weather_code] || `不明(${current.weather_code})`;

        currentWeatherData = {
            location: locationName,
            temp: current.temperature_2m,
            humidity: current.relative_humidity_2m,
            precipitation: current.precipitation,
            weather: weatherDesc,
            temp_max: daily.temperature_2m_max[0],
            temp_min: daily.temperature_2m_min[0],
            pressure: current.surface_pressure
        };

        document.getElementById('location-name').innerText = locationName;
        document.getElementById('current-temp').innerText = `${current.temperature_2m}℃`;
        document.getElementById('current-humidity').innerText = `${current.relative_humidity_2m}%`;
        document.getElementById('current-rain').innerText = `${current.precipitation}mm`;
        document.getElementById('current-weather-desc').innerText = weatherDesc;
        
        document.getElementById('temp-max').innerText = daily.temperature_2m_max[0];
        document.getElementById('temp-min').innerText = daily.temperature_2m_min[0];

        document.getElementById('card-pressure').innerText = `${current.surface_pressure}hPa`;

        const now = new Date();
        now.setMinutes(0, 0, 0);
        let startIndex = hourly.time.findIndex(t => new Date(t).getTime() >= now.getTime());
        if(startIndex === -1) startIndex = 0;
        
        const endIndex = startIndex + 12;
        const next12hHumid = hourly.relative_humidity_2m.slice(startIndex, endIndex);
        const next12hPrecip = hourly.precipitation.slice(startIndex, endIndex);
        const next12hCodes = hourly.weather_code.slice(startIndex, endIndex);

        const maxHumid = Math.max(...next12hHumid);
        const minHumid = Math.min(...next12hHumid);
        document.getElementById('card-humid-max').innerText = `${maxHumid}%`;
        document.getElementById('card-humid-min').innerText = `${minHumid}%`;

        const maxPrecip = Math.max(...next12hPrecip);
        document.getElementById('card-rain-max').innerText = `${maxPrecip}mm`;

        const currentCode = current.weather_code;
        let changeIndex = -1;
        for(let i = 0; i < next12hCodes.length; i++) {
            if(next12hCodes[i] !== currentCode) {
                changeIndex = i;
                break;
            }
        }

        if(changeIndex !== -1) {
            const nextCode = next12hCodes[changeIndex];
            const nextWeather = CONFIG.wmoCodes[nextCode] || '-';
            document.getElementById('card-weather-time').innerText = `${changeIndex}時間後`;
            document.getElementById('card-weather-val').innerText = nextWeather;
        } else {
            document.getElementById('card-weather-time').innerText = `当面`;
            document.getElementById('card-weather-val').innerText = `変化なし`;
        }

        TimeModule.reset();

        WeatherModule.renderWeeklyForecast(daily);
        ChartModule.render(hourly);
    },

    renderWeeklyForecast: (daily) => {
        const container = document.getElementById('weekly-forecast-container');
        let html = '';

        for (let i = 0; i < daily.time.length; i++) {
            const dateStr = daily.time[i]; 
            const date = new Date(dateStr);
            const dayOfWeek = ['日', '月', '火', '水', '木', '金', '土'][date.getDay()];
            const isToday = i === 0;
            const displayDate = `${date.getMonth() + 1}/${date.getDate()}(${dayOfWeek})`;

            const code = daily.weather_code[i];
            const maxTemp = Math.round(daily.temperature_2m_max[i]);
            const minTemp = Math.round(daily.temperature_2m_min[i]);
            const precipProb = daily.precipitation_probability_max ? daily.precipitation_probability_max[i] : 0;
            
            const iconClass = getWeatherIconClass(code);
            const weatherName = CONFIG.wmoCodes[code] || '-';

            html += `
                <div class="flex items-center py-1 px-2 rounded hover:bg-gray-50 dark:hover:bg-slate-700/50 transition border-b border-gray-100 dark:border-slate-700/50 last:border-0">
                    <div class="w-16 text-sm ${isToday ? 'font-bold text-blue-600 dark:text-blue-400' : 'text-gray-700 dark:text-slate-300'}">
                        ${isToday ? '今日' : displayDate}
                    </div>
                    
                    <div class="flex-1 flex items-center gap-2 pl-2 overflow-hidden">
                        <i class="fa-solid ${iconClass} text-lg w-6 text-center"></i>
                        <span class="text-xs text-gray-500 dark:text-slate-400 truncate">${weatherName}</span>
                    </div>

                    <div class="w-16 text-center">
                        <span class="text-xs font-bold text-blue-500">${precipProb}%</span>
                    </div>

                    <div class="w-16 flex items-center justify-end text-sm">
                        <span class="w-5 text-right text-blue-500 dark:text-blue-400 font-medium">${minTemp}°</span>
                        <span class="w-3 text-center text-gray-300 dark:text-slate-600">/</span>
                        <span class="w-5 text-right text-red-500 dark:text-red-400 font-bold">${maxTemp}°</span>
                    </div>
                </div>
            `;
        }
        container.innerHTML = html;
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
                        datalabels: {
                            align: 'top',
                            anchor: 'end',
                            offset: 6,
                            color: textColor,
                            font: { size: 12, weight: 'bold' },
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
                layout: {
                    padding: { top: 25 }
                },
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
                        title: { display: false },
                        suggestedMax: Math.max(...temps) + 2
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
        let scene = document.getElementById('scene-select').value;
        const customScene = document.getElementById('scene-custom-input').value.trim();
        const gender = document.getElementById('gender-select').value;
        
        // モード判定
        const selectedMode = document.querySelector('input[name="proposal-mode"]:checked');
        const mode = selectedMode ? selectedMode.value : 'simple';

        const preference = document.getElementById('preference-input').value;
        const wardrobe = document.getElementById('wardrobe-input').value;

        if (scene === 'その他' && customScene) {
            scene = customScene;
        } else if (scene === 'その他' && !customScene) {
            alert("シーンを入力してください。");
            return;
        }

        if (!currentWeatherData) {
            alert("先に地図をクリックして天気情報を取得してください。");
            return;
        }

        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 取得中...';

        ThemeModule.triggerButtonAnim(btn);

        try {
            const response = await fetch("/api/suggest_outfit", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    weather_data: currentWeatherData,
                    mode: mode,
                    scene: scene,
                    gender: gender,
                    preference: preference,
                    wardrobe: wardrobe
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

    renderResult: (data) => {
        const resultArea = document.getElementById('ai-result-area');
        const text = data.suggestion || "提案を取得できませんでした。";

        resultArea.innerHTML = `
            <div class="bg-white dark:bg-slate-700 border border-purple-200 dark:border-slate-600 rounded-lg p-6 shadow-sm fade-in-up">
                <h4 class="font-bold text-purple-600 dark:text-purple-400 mb-3 border-b border-purple-100 dark:border-slate-600 pb-2 flex items-center gap-2">
                    <i class="fa-solid fa-shirt"></i> コーディネート提案
                </h4>
                <p class="text-gray-700 dark:text-slate-200 text-sm md:text-base leading-relaxed whitespace-pre-wrap">${text}</p>
            </div>
        `;
    }
};

// ==========================================
// 5. Theme & Interaction Module
// ==========================================
const ThemeModule = {
    init: () => {
        TimeModule.init();

        const toggleBtn = document.getElementById('theme-toggle-btn');
        const btnText = document.getElementById('theme-btn-text');
        
        toggleBtn.addEventListener('click', () => {
            ThemeModule.triggerButtonAnim(toggleBtn);
            
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

        const refreshBtn = document.getElementById('refresh-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                 ThemeModule.triggerButtonAnim(refreshBtn);
            });
        }

        // --- モード切替時の表示制御 ---
        const modeRadios = document.querySelectorAll('input[name="proposal-mode"]');
        const detailedInputs = document.getElementById('detailed-inputs');

        function updateInputs() {
            const selected = document.querySelector('input[name="proposal-mode"]:checked');
            if (selected && selected.value === 'detailed') {
                detailedInputs.classList.remove('hidden');
            } else {
                detailedInputs.classList.add('hidden');
            }
        }
        
        modeRadios.forEach(radio => {
            radio.addEventListener('change', updateInputs);
        });
        
        // 初期化時にも実行
        updateInputs();


        const sceneSelect = document.getElementById('scene-select');
        const customInput = document.getElementById('scene-custom-input');
        
        sceneSelect.addEventListener('change', () => {
            if (sceneSelect.value === 'その他') {
                customInput.classList.remove('hidden');
                customInput.focus();
            } else {
                customInput.classList.add('hidden');
            }
        });

        // -----------------------------------------------------
        // Interactive Card Click Logic (Toggle & 3s Auto-Close)
        // -----------------------------------------------------
        const cards = document.querySelectorAll('.interactive-card');
        cards.forEach(card => {
            card._timeoutId = null;

            card.addEventListener('click', (e) => {
                e.stopPropagation(); // 重要: バブリング防止
                
                if (card.classList.contains('show-detail')) {
                    card.classList.remove('show-detail');
                    if (card._timeoutId) {
                        clearTimeout(card._timeoutId);
                        card._timeoutId = null;
                    }
                } 
                else {
                    card.classList.add('show-detail');
                    if (card._timeoutId) clearTimeout(card._timeoutId);
                    card._timeoutId = setTimeout(() => {
                        card.classList.remove('show-detail');
                        card._timeoutId = null;
                    }, 3000);
                }
            });
        });

        // --- Scroll to Top Logic ---
        const scrollBtn = document.getElementById('scroll-to-top');
        if (scrollBtn) {
            window.addEventListener('scroll', () => {
                const scrollBottom = document.documentElement.scrollHeight - window.innerHeight - window.scrollY;
                if (scrollBottom < 300) {
                    scrollBtn.classList.add('show');
                } else {
                    scrollBtn.classList.remove('show');
                }
            });

            scrollBtn.addEventListener('click', () => {
                window.scrollTo({ top: 0, behavior: 'smooth' });
            });
        }
    },

    triggerAutoShow: () => {
        const cards = document.querySelectorAll('.interactive-card');
        cards.forEach(card => {
            card.classList.add('show-detail');
            if (card._timeoutId) clearTimeout(card._timeoutId);
            card._timeoutId = setTimeout(() => {
                card.classList.remove('show-detail');
                card._timeoutId = null;
            }, 5000); // 5s after auto-show (total 10s mark)
        });
    },

    triggerButtonAnim: (btn) => {
        btn.classList.add('is-active');
        setTimeout(() => {
            btn.classList.remove('is-active');
        }, 500);
    }
};

document.addEventListener('DOMContentLoaded', () => {
    MapModule.init();
    ThemeModule.init();

    document.getElementById('refresh-btn').addEventListener('click', () => {
        MapModule.updateMarker(CONFIG.defaultLat, CONFIG.defaultLng);
        mapInstance.setView([CONFIG.defaultLat, CONFIG.defaultLng], 10);
        MapModule.updateRadar();
    });

    document.getElementById('ai-suggest-btn').addEventListener('click', () => {
        AIModule.suggestOutfit();
    });
});
