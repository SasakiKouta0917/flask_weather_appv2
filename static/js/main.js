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
// Favorite Locations Module
// ==========================================
const FavoriteModule = {
    storageKey: 'weatherapp_favorites',
    
    getFavorites: () => {
        const data = localStorage.getItem(FavoriteModule.storageKey);
        return data ? JSON.parse(data) : [];
    },
    
    saveFavorites: (favorites) => {
        localStorage.setItem(FavoriteModule.storageKey, JSON.stringify(favorites));
    },
    
    addFavorite: (lat, lng, name) => {
        const favorites = FavoriteModule.getFavorites();
        const id = Date.now();
        favorites.push({ id, lat, lng, name });
        FavoriteModule.saveFavorites(favorites);
        FavoriteModule.render();
    },
    
    removeFavorite: (id) => {
        let favorites = FavoriteModule.getFavorites();
        favorites = favorites.filter(f => f.id !== id);
        FavoriteModule.saveFavorites(favorites);
        FavoriteModule.render();
    },
    
    render: () => {
        const container = document.getElementById('favorite-locations');
        const favorites = FavoriteModule.getFavorites();
        
        if (favorites.length === 0) {
            container.innerHTML = '<p class="text-gray-400 dark:text-slate-500 text-center py-2">登録なし</p>';
            return;
        }
        
        container.innerHTML = favorites.map(fav => `
            <div class="flex items-center justify-between bg-gray-50 dark:bg-slate-700 p-2 rounded hover:bg-gray-100 dark:hover:bg-slate-600 transition">
                <button onclick="FavoriteModule.jumpTo(${fav.lat}, ${fav.lng})" class="flex-1 text-left text-gray-700 dark:text-slate-200 hover:text-blue-600 dark:hover:text-blue-400 truncate">
                    <i class="fa-solid fa-location-dot text-blue-500 mr-1"></i>
                    ${fav.name}
                </button>
                <button onclick="FavoriteModule.removeFavorite(${fav.id})" class="ml-2 text-red-500 hover:text-red-700">
                    <i class="fa-solid fa-trash text-xs"></i>
                </button>
            </div>
        `).join('');
    },
    
    jumpTo: (lat, lng) => {
        MapModule.updateMarker(lat, lng);
        mapInstance.setView([lat, lng], 13);
    },
    
    init: () => {
        FavoriteModule.render();
        
        const addBtn = document.getElementById('add-favorite-btn');
        if (addBtn) {
            addBtn.addEventListener('click', () => {
                const pos = markerInstance.getLatLng();
                const locationName = document.getElementById('location-name').innerText || '地点';
                
                const customName = prompt('この地点の名前を入力してください:', locationName);
                if (customName && customName.trim()) {
                    FavoriteModule.addFavorite(pos.lat, pos.lng, customName.trim());
                    alert('お気に入りに追加しました!');
                }
            });
        }
    }
};

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
    },

    getCurrentLocation: () => {
        const btn = document.getElementById('geolocation-btn');
        
        if (!navigator.geolocation) {
            alert('このブラウザは位置情報に対応していません。');
            return;
        }
        
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 取得中...';
        
        navigator.geolocation.getCurrentPosition(
            (position) => {
                const lat = position.coords.latitude;
                const lng = position.coords.longitude;
                
                MapModule.updateMarker(lat, lng);
                mapInstance.setView([lat, lng], 13);
                
                btn.innerHTML = '<i class="fa-solid fa-location-crosshairs"></i> 現在地';
                btn.disabled = false;
            },
            (error) => {
                console.error('Geolocation error:', error);
                alert('現在地の取得に失敗しました。位置情報の許可を確認してください。');
                btn.innerHTML = '<i class="fa-solid fa-location-crosshairs"></i> 現在地';
                btn.disabled = false;
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 0
            }
        );
    }
};

// ==========================================
// 2. Weather Module
// ==========================================
const WeatherModule = {
    fetchData: async (lat, lng) => {
        const btn = document.getElementById('refresh-btn');
        if (btn) btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 取得中...';
        
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
            if (btn) btn.innerHTML = '<i class="fa-solid fa-rotate-right"></i> 更新';
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
        if (!container) return;
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
// 4. AI Module (Rate Limit対応・カウントダウン付き・完全版)
// ==========================================
const AIModule = {
    countdownTimer: null,
    countdownInterval: null,
    errorCountdownInterval: null, // エラー表示用カウントダウン

    getDummyData: () => {
        return {
            "suggestion": "通信エラーが発生したか、AIが応答しませんでした。\n\n【標準的なアドバイス】\n天気予報を確認し、気温の変化に対応しやすい服装でお出かけください。\n寒暖差がある場合は羽織るものを持つと安心です。(ダミーデータ)"
        };
    },

    formatTime: (seconds) => {
        const minutes = Math.floor(seconds / 60);
        const secs = seconds % 60;
        if (minutes > 0) {
            return `${minutes}分${secs}秒`;
        }
        return `${secs}秒`;
    },

    suggestOutfit: async () => {
        const btn = document.getElementById('ai-suggest-btn');
        const resetBtn = document.getElementById('ai-reset-btn');
        const inputContainer = document.getElementById('ai-input-container');

        const sceneInput = document.getElementById('scene-input');
        const scene = sceneInput ? sceneInput.value.trim() : '';
        
        const genderSelect = document.getElementById('gender-select');
        const gender = genderSelect ? genderSelect.value : 'unspecified';
        
        const selectedMode = document.querySelector('input[name="proposal-mode"]:checked');
        const mode = selectedMode ? selectedMode.value : 'simple';

        const preferenceInput = document.getElementById('preference-input');
        const preference = preferenceInput ? preferenceInput.value : '';
        
        const wardrobeInput = document.getElementById('wardrobe-input');
        const wardrobe = wardrobeInput ? wardrobeInput.value : '';

        const finalScene = scene || '特になし';

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
                    scene: finalScene,
                    gender: gender,
                    preference: preference,
                    wardrobe: wardrobe
                })
            });

            if (response.status === 429) {
                const errorData = await response.json();
                const remainingTime = errorData.remaining_time || 0;
                const timeStr = AIModule.formatTime(remainingTime);
                
                alert(`⏱️ リクエスト制限\n\n${errorData.message}\n\n残り待機時間: ${timeStr}`);
                
                AIModule.renderRateLimitError(errorData.message, remainingTime);
                btn.innerHTML = '<i class="fa-solid fa-clock"></i> 待機中...';
                
                if (inputContainer) inputContainer.classList.add('hidden');
                if (resetBtn) resetBtn.classList.remove('hidden');
                
                AIModule.startCountdown(remainingTime, btn);
                return;
            }

            if (!response.ok) {
                console.warn("Server API Error, using dummy data.");
                const dummy = AIModule.getDummyData();
                AIModule.renderResult(dummy);
            } else {
                const data = await response.json();
                AIModule.renderResult(data.suggestions);
            }

            btn.innerHTML = '<i class="fa-solid fa-robot"></i> 再取得';
            
            if (inputContainer) inputContainer.classList.add('hidden');
            if (resetBtn) resetBtn.classList.remove('hidden');

        } catch (error) {
            console.error("AI Fetch Error:", error);
            const dummy = AIModule.getDummyData();
            AIModule.renderResult(dummy);
            
            btn.innerHTML = '<i class="fa-solid fa-robot"></i> 再取得';
            if (inputContainer) inputContainer.classList.add('hidden');
            if (resetBtn) resetBtn.classList.remove('hidden');

        } finally {
            btn.disabled = false;
        }
    },

    startCountdown: (seconds, btn) => {
        // 既存のタイマーをクリア
        if (AIModule.countdownTimer) {
            clearTimeout(AIModule.countdownTimer);
            AIModule.countdownTimer = null;
        }
        if (AIModule.countdownInterval) {
            clearInterval(AIModule.countdownInterval);
            AIModule.countdownInterval = null;
        }

        let remaining = seconds;
        
        const updateButton = () => {
            if (remaining > 0) {
                const timeStr = AIModule.formatTime(remaining);
                btn.innerHTML = `<i class="fa-solid fa-clock"></i> 待機中 (${timeStr})`;
                remaining--;
            } else {
                AIModule.stopCountdown();
                btn.innerHTML = '<i class="fa-solid fa-robot"></i> AI服装提案を取得';
                btn.disabled = false;
            }
        };
        
        // 初回実行
        btn.disabled = true;
        updateButton();
        
        // 1秒ごとに更新
        AIModule.countdownInterval = setInterval(updateButton, 1000);
        
        // 最終的なタイムアウト（バックアップ）
        AIModule.countdownTimer = setTimeout(() => {
            AIModule.stopCountdown();
            btn.innerHTML = '<i class="fa-solid fa-robot"></i> AI服装提案を取得';
            btn.disabled = false;
        }, (seconds + 1) * 1000);
    },

    stopCountdown: () => {
        if (AIModule.countdownTimer) {
            clearTimeout(AIModule.countdownTimer);
            AIModule.countdownTimer = null;
        }
        if (AIModule.countdownInterval) {
            clearInterval(AIModule.countdownInterval);
            AIModule.countdownInterval = null;
        }
    },

    renderRateLimitError: (message, remainingTime) => {
        const resultArea = document.getElementById('ai-result-area');
        const timeStr = AIModule.formatTime(remainingTime);
        
        // カウントダウン表示用のID付きspan
        const countdownId = 'countdown-display';
        
        resultArea.innerHTML = `
            <div class="bg-orange-50 dark:bg-orange-900/20 border-2 border-orange-300 dark:border-orange-700 rounded-lg p-6 shadow-sm fade-in-up">
                <h4 class="font-bold text-orange-700 dark:text-orange-400 mb-3 border-b border-orange-200 dark:border-orange-700 pb-2 flex items-center gap-2">
                    <i class="fa-solid fa-clock"></i> リクエスト制限
                </h4>
                <p class="text-gray-700 dark:text-slate-200 text-sm md:text-base leading-relaxed mb-4">${message}</p>
                <div class="bg-white dark:bg-slate-800 rounded p-3 text-center">
                    <p class="text-xs text-gray-500 dark:text-slate-400 mb-1">残り待機時間</p>
                    <p id="${countdownId}" class="text-2xl font-bold text-orange-600 dark:text-orange-400">${timeStr}</p>
                </div>
                <p class="text-xs text-gray-500 dark:text-slate-400 mt-4">
                    💡 ヒント: APIの使用量を節約するため、リクエスト間隔を設けています。
                </p>
            </div>
        `;
        
        // エラー表示内のカウントダウンを開始
        AIModule.startErrorCountdown(remainingTime, countdownId);
    },
    
    startErrorCountdown: (seconds, elementId) => {
        // 既存のエラーカウントダウンをクリア
        if (AIModule.errorCountdownInterval) {
            clearInterval(AIModule.errorCountdownInterval);
            AIModule.errorCountdownInterval = null;
        }
        
        let remaining = seconds;
        
        const updateDisplay = () => {
            const element = document.getElementById(elementId);
            if (!element) {
                // 要素が消えたらタイマー停止
                if (AIModule.errorCountdownInterval) {
                    clearInterval(AIModule.errorCountdownInterval);
                    AIModule.errorCountdownInterval = null;
                }
                return;
            }
            
            if (remaining > 0) {
                const timeStr = AIModule.formatTime(remaining);
                element.textContent = timeStr;
                remaining--;
            } else {
                element.textContent = '0秒';
                if (AIModule.errorCountdownInterval) {
                    clearInterval(AIModule.errorCountdownInterval);
                    AIModule.errorCountdownInterval = null;
                }
            }
        };
        
        // 初回表示
        updateDisplay();
        
        // 1秒ごとに更新
        AIModule.errorCountdownInterval = setInterval(updateDisplay, 1000);
    },

    renderResult: (data) => {
        // エラー表示のカウントダウンをクリア
        if (AIModule.errorCountdownInterval) {
            clearInterval(AIModule.errorCountdownInterval);
            AIModule.errorCountdownInterval = null;
        }
        
        const resultArea = document.getElementById('ai-result-area');
        const text = data.suggestion || "提案を取得できませんでした。";

        resultArea.innerHTML = `
            <div class="bg-white dark:bg-slate-700 border border-purple-200 dark:border-slate-600 rounded-lg p-6 shadow-sm fade-in-up">
                <div class="flex items-center justify-between mb-3 border-b border-purple-100 dark:border-slate-600 pb-2">
                    <h4 class="font-bold text-purple-600 dark:text-purple-400 flex items-center gap-2">
                        <i class="fa-solid fa-shirt"></i> コーディネート提案
                    </h4>
                    <button onclick="AIModule.copyToClipboard()" class="text-gray-500 hover:text-purple-600 dark:text-slate-400 dark:hover:text-purple-400 transition">
                        <i class="fa-solid fa-copy"></i>
                    </button>
                </div>
                <p class="text-gray-700 dark:text-slate-200 text-sm md:text-base leading-relaxed whitespace-pre-wrap mb-4">${text}</p>
                <div class="flex items-center justify-end gap-2 md:gap-3 pt-3 border-t border-gray-100 dark:border-slate-600">
                    <span class="text-xs text-gray-500 dark:text-slate-400 hidden sm:inline">この提案は役に立ちましたか?</span>
                    <button onclick="AIModule.rateSuggestion('good')" class="px-3 py-1.5 bg-green-100 hover:bg-green-200 dark:bg-green-900/30 dark:hover:bg-green-900/50 text-green-700 dark:text-green-400 rounded-full text-sm transition">
                        <i class="fa-solid fa-thumbs-up"></i><span class="hidden sm:inline ml-1">良い</span>
                    </button>
                    <button onclick="AIModule.rateSuggestion('bad')" class="px-3 py-1.5 bg-red-100 hover:bg-red-200 dark:bg-red-900/30 dark:hover:bg-red-900/50 text-red-700 dark:text-red-400 rounded-full text-sm transition">
                        <i class="fa-solid fa-thumbs-down"></i><span class="hidden sm:inline ml-1">悪い</span>
                    </button>
                </div>
            </div>
        `;
    },

    copyToClipboard: () => {
        const resultArea = document.getElementById('ai-result-area');
        const textElement = resultArea.querySelector('p');
        
        if (!textElement) {
            alert('コピーする内容がありません。');
            return;
        }
        
        const text = textElement.innerText;
        
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(() => {
                alert('📋 クリップボードにコピーしました!');
            }).catch(() => {
                alert('❌ コピーに失敗しました。');
            });
        } else {
            const textarea = document.createElement('textarea');
            textarea.value = text;
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            document.body.removeChild(textarea);
            alert('📋 クリップボードにコピーしました!');
        }
    },

    rateSuggestion: (rating) => {
        const ratingData = JSON.parse(localStorage.getItem('weatherapp_ratings') || '{"good": 0, "bad": 0}');
        ratingData[rating]++;
        localStorage.setItem('weatherapp_ratings', JSON.stringify(ratingData));
        
        const emoji = rating === 'good' ? '👍' : '👎';
        alert(`${emoji} フィードバックありがとうございます!`);
        
        console.log('評価統計:', ratingData);
    },

    reset: () => {
        const resetBtn = document.getElementById('ai-reset-btn');
        const inputContainer = document.getElementById('ai-input-container');
        const resultArea = document.getElementById('ai-result-area');
        const btn = document.getElementById('ai-suggest-btn');
        
        const sceneInput = document.getElementById('scene-input');
        const preferenceInput = document.getElementById('preference-input');
        const wardrobeInput = document.getElementById('wardrobe-input');
        
        if (sceneInput) sceneInput.value = "";
        if (preferenceInput) preferenceInput.value = "";
        if (wardrobeInput) wardrobeInput.value = "";
        
        if (inputContainer) inputContainer.classList.remove('hidden');
        if (resetBtn) resetBtn.classList.add('hidden');
        
        // すべてのタイマーをクリア
        AIModule.stopCountdown();
        
        if (AIModule.errorCountdownInterval) {
            clearInterval(AIModule.errorCountdownInterval);
            AIModule.errorCountdownInterval = null;
        }
        
        if (btn) {
            btn.innerHTML = '<i class="fa-solid fa-robot"></i> AI服装提案を取得';
            btn.disabled = false;
        }
        
        resultArea.innerHTML = `
            <div class="bg-gray-50 dark:bg-slate-700/30 border border-dashed border-gray-300 dark:border-slate-600 rounded-lg p-6 md:p-8 text-center text-sm md:text-base text-gray-400 dark:text-slate-500 h-full flex items-center justify-center flex-grow transition duration-500">
                ここにAIからの提案が表示されます
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
        if (toggleBtn) {
            const btnText = document.getElementById('theme-btn-text');
            toggleBtn.addEventListener('click', () => {
                ThemeModule.triggerButtonAnim(toggleBtn);
                document.documentElement.classList.toggle('dark');
                const isDark = document.documentElement.classList.contains('dark');
                if (btnText) btnText.innerText = isDark ? 'ライト' : 'ダーク';
                
                if(weatherChartInstance) {
                    const textColor = isDark ? '#e2e8f0' : '#666';
                    weatherChartInstance.options.scales.x.ticks.color = textColor;
                    weatherChartInstance.options.scales.y.ticks.color = textColor;
                    weatherChartInstance.options.plugins.legend.labels.color = textColor;
                    weatherChartInstance.data.datasets[0].datalabels.color = textColor;
                    weatherChartInstance.update();
                }
            });
        }

        const refreshBtn = document.getElementById('refresh-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                 ThemeModule.triggerButtonAnim(refreshBtn);
            });
        }

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
        modeRadios.forEach(radio => radio.addEventListener('change', updateInputs));
        updateInputs();

        const cards = document.querySelectorAll('.interactive-card');
        cards.forEach(card => {
            card._timeoutId = null;

            card.addEventListener('click', (e) => {
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
            }, 5000);
        });
    },

    triggerButtonAnim: (btn) => {
        btn.classList.add('is-active');
        setTimeout(() => {
            btn.classList.remove('is-active');
        }, 500);
    }
};

// ==========================================
// Board Module（掲示板機能）
// main.jsの末尾（DOMContentLoadedの前）に追加してください
// ==========================================

const BoardModule = {
    currentUsername: null,
    replyToPostId: null,
    autoRefreshInterval: null,
    
    init: () => {
        BoardModule.setupEventListeners();
        BoardModule.loadUsername();
        BoardModule.loadPosts();
        
        // 30秒ごとに自動更新
        BoardModule.autoRefreshInterval = setInterval(() => {
            BoardModule.loadPosts(true); // サイレント更新
        }, 30000);
    },
    
    setupEventListeners: () => {
        // 名前登録
        const registerBtn = document.getElementById('board-register-btn');
        if (registerBtn) {
            registerBtn.addEventListener('click', BoardModule.registerUsername);
        }
        
        // 投稿内容の文字数カウント
        const postContent = document.getElementById('board-post-content');
        if (postContent) {
            postContent.addEventListener('input', (e) => {
                const count = e.target.value.length;
                document.getElementById('board-char-count').textContent = `${count} / 300`;
                BoardModule.updateSubmitButton();
            });
        }
        
        // 返信内容の文字数カウント
        const replyContent = document.getElementById('board-reply-content');
        if (replyContent) {
            replyContent.addEventListener('input', (e) => {
                const count = e.target.value.length;
                document.getElementById('board-reply-char-count').textContent = `${count} / 300`;
                BoardModule.updateReplySubmitButton();
            });
        }
        
        // チェックボックス
        const confirmCheckbox = document.getElementById('board-confirm-checkbox');
        if (confirmCheckbox) {
            confirmCheckbox.addEventListener('change', BoardModule.updateSubmitButton);
        }
        
        const replyConfirmCheckbox = document.getElementById('board-reply-confirm-checkbox');
        if (replyConfirmCheckbox) {
            replyConfirmCheckbox.addEventListener('change', BoardModule.updateReplySubmitButton);
        }
        
        // 投稿ボタン
        const submitBtn = document.getElementById('board-submit-btn');
        if (submitBtn) {
            submitBtn.addEventListener('click', BoardModule.submitPost);
        }
        
        // 返信投稿ボタン
        const replySubmitBtn = document.getElementById('board-reply-submit-btn');
        if (replySubmitBtn) {
            replySubmitBtn.addEventListener('click', BoardModule.submitReply);
        }
        
        // 返信キャンセル
        const cancelReplyBtn = document.getElementById('board-cancel-reply-btn');
        if (cancelReplyBtn) {
            cancelReplyBtn.addEventListener('click', BoardModule.cancelReply);
        }
        
        // 手動更新ボタン
        const refreshBtn = document.getElementById('board-refresh-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                BoardModule.loadPosts();
            });
        }
    },
    
    updateSubmitButton: () => {
        const content = document.getElementById('board-post-content').value.trim();
        const checkbox = document.getElementById('board-confirm-checkbox').checked;
        const btn = document.getElementById('board-submit-btn');
        
        btn.disabled = !content || !checkbox;
    },
    
    updateReplySubmitButton: () => {
        const content = document.getElementById('board-reply-content').value.trim();
        const checkbox = document.getElementById('board-reply-confirm-checkbox').checked;
        const btn = document.getElementById('board-reply-submit-btn');
        
        btn.disabled = !content || !checkbox;
    },
    
    loadUsername: async () => {
        try {
            const response = await fetch('/api/board/get_username');
            const data = await response.json();
            
            if (data.username) {
                BoardModule.currentUsername = data.username;
                document.getElementById('board-name-input-area').classList.add('hidden');
                document.getElementById('board-name-display-area').classList.remove('hidden');
                document.getElementById('board-current-username').textContent = data.username;
            }
        } catch (error) {
            console.error('[BOARD] Failed to load username:', error);
        }
    },
    
    registerUsername: async () => {
        const input = document.getElementById('board-username-input');
        const username = input.value.trim();
        
        if (!username) {
            alert('名前を入力してください。');
            return;
        }
        
        const btn = document.getElementById('board-register-btn');
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
        
        try {
            const response = await fetch('/api/board/register_name', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username })
            });
            
            const data = await response.json();
            
            if (data.success) {
                BoardModule.currentUsername = username;
                document.getElementById('board-name-input-area').classList.add('hidden');
                document.getElementById('board-name-display-area').classList.remove('hidden');
                document.getElementById('board-current-username').textContent = username;
                alert('✅ ' + data.message);
            } else {
                alert('❌ ' + data.message);
            }
        } catch (error) {
            console.error('[BOARD] Failed to register username:', error);
            alert('名前の登録に失敗しました。もう一度お試しください。');
        } finally {
            btn.disabled = false;
            btn.innerHTML = '登録';
        }
    },
    
    submitPost: async () => {
        const content = document.getElementById('board-post-content').value.trim();
        
        if (!content) return;
        
        const btn = document.getElementById('board-submit-btn');
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 送信中...';
        
        try {
            const response = await fetch('/api/board/create_post', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content })
            });
            
            const data = await response.json();
            
            if (data.success) {
                document.getElementById('board-post-content').value = '';
                document.getElementById('board-confirm-checkbox').checked = false;
                document.getElementById('board-char-count').textContent = '0 / 300';
                BoardModule.loadPosts();
                alert('✅ 投稿しました！');
            } else {
                alert('❌ ' + data.message);
            }
        } catch (error) {
            console.error('[BOARD] Failed to submit post:', error);
            alert('投稿に失敗しました。もう一度お試しください。');
        } finally {
            btn.innerHTML = '<i class="fa-solid fa-paper-plane"></i> 投稿';
            BoardModule.updateSubmitButton();
        }
    },
    
    submitReply: async () => {
        const content = document.getElementById('board-reply-content').value.trim();
        
        if (!content || !BoardModule.replyToPostId) return;
        
        if (!BoardModule.currentUsername) {
            alert('返信するには名前を登録してください。');
            return;
        }
        
        const btn = document.getElementById('board-reply-submit-btn');
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 送信中...';
        
        try {
            const response = await fetch('/api/board/create_post', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    content,
                    parent_id: BoardModule.replyToPostId
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                BoardModule.cancelReply();
                BoardModule.loadPosts();
                alert('✅ 返信しました！');
            } else {
                alert('❌ ' + data.message);
            }
        } catch (error) {
            console.error('[BOARD] Failed to submit reply:', error);
            alert('返信に失敗しました。もう一度お試しください。');
        } finally {
            btn.innerHTML = '<i class="fa-solid fa-paper-plane"></i> 返信を投稿';
            BoardModule.updateReplySubmitButton();
        }
    },
    
    showReplyForm: (postId, username) => {
        BoardModule.replyToPostId = postId;
        document.getElementById('board-reply-to-username').textContent = username;
        document.getElementById('board-reply-form').classList.remove('hidden');
        document.getElementById('board-reply-content').focus();
        
        // 返信フォームまでスクロール
        document.getElementById('board-reply-form').scrollIntoView({ behavior: 'smooth', block: 'center' });
    },
    
    cancelReply: () => {
        BoardModule.replyToPostId = null;
        document.getElementById('board-reply-form').classList.add('hidden');
        document.getElementById('board-reply-content').value = '';
        document.getElementById('board-reply-confirm-checkbox').checked = false;
        document.getElementById('board-reply-char-count').textContent = '0 / 300';
    },
    
    loadPosts: async (silent = false) => {
        try {
            const response = await fetch('/api/board/get_posts');
            const data = await response.json();
            
            BoardModule.renderPosts(data.posts);
            
            if (!silent) {
                console.log('[BOARD] Posts loaded:', data.posts.length);
            }
        } catch (error) {
            console.error('[BOARD] Failed to load posts:', error);
            
            if (!silent) {
                const container = document.getElementById('board-posts-container');
                container.innerHTML = `
                    <div class="text-center text-sm text-red-400 py-8">
                        <i class="fa-solid fa-exclamation-triangle text-3xl mb-2"></i>
                        <p>読み込みに失敗しました</p>
                        <button onclick="BoardModule.loadPosts()" class="mt-2 text-blue-500 hover:text-blue-700">
                            <i class="fa-solid fa-rotate-right"></i> 再読み込み
                        </button>
                    </div>
                `;
            }
        }
    },
    
    renderPosts: (posts) => {
        const container = document.getElementById('board-posts-container');
        
        if (posts.length === 0) {
            container.innerHTML = `
                <div class="text-center text-sm text-gray-400 dark:text-slate-500 py-8">
                    <i class="fa-solid fa-comment-slash text-3xl mb-2"></i>
                    <p>まだ投稿がありません</p>
                    <p class="text-xs mt-1">最初の投稿をしてみましょう！</p>
                </div>
            `;
            return;
        }
        
        // 親投稿のみを抽出
        const parentPosts = posts.filter(p => !p.parent_id);
        
        let html = '';
        
        parentPosts.forEach(post => {
            html += BoardModule.renderPost(post, posts);
        });
        
        container.innerHTML = html;
        
        // イベントリスナーを再設定
        BoardModule.attachPostEventListeners();
    },
    
    renderPost: (post, allPosts, isReply = false) => {
        const date = new Date(post.timestamp);
        const timeStr = `${date.getMonth() + 1}/${date.getDate()} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
        
        // XSS対策：HTMLエスケープ済みのcontentをそのまま使用
        const contentHtml = post.content_hidden
            ? `<div class="bg-gray-100 dark:bg-slate-600 p-2 rounded text-xs text-gray-500 dark:text-slate-400 flex items-center justify-between">
                    <span>${post.content}</span>
                    <button class="show-content-btn text-blue-500 hover:text-blue-700 dark:text-blue-400 ml-2 flex-shrink-0" data-post-id="${post.id}">
                        <i class="fa-solid fa-eye"></i> 内容を見る
                    </button>
               </div>`
            : `<p class="text-sm text-gray-700 dark:text-slate-200 whitespace-pre-wrap break-words">${post.content}</p>`;
        
        // 返信を取得
        const replies = allPosts.filter(p => p.parent_id === post.id);
        
        let html = `
            <div class="bg-white dark:bg-slate-700/50 border border-gray-200 dark:border-slate-600 rounded-lg p-3 transition hover:shadow-md ${isReply ? 'ml-6 mt-2 border-l-4 border-l-purple-300 dark:border-l-purple-700' : ''}">
                <div class="flex items-start justify-between mb-2">
                    <div class="flex items-center gap-2">
                        <i class="fa-solid fa-user-circle text-gray-400 dark:text-slate-500"></i>
                        <span class="font-semibold text-sm text-gray-700 dark:text-slate-200">${post.username}</span>
                        ${post.is_own ? '<span class="text-xs bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-300 px-2 py-0.5 rounded">自分</span>' : ''}
                        ${isReply ? '<span class="text-xs bg-purple-100 dark:bg-purple-900 text-purple-600 dark:text-purple-300 px-2 py-0.5 rounded"><i class="fa-solid fa-reply"></i></span>' : ''}
                    </div>
                    <span class="text-xs text-gray-400 dark:text-slate-500">${timeStr}</span>
                </div>
                
                ${contentHtml}
                
                <div class="flex items-center gap-3 mt-2 pt-2 border-t border-gray-100 dark:border-slate-600">
                    <button class="reply-btn text-xs text-blue-500 hover:text-blue-700 dark:text-blue-400 transition" data-post-id="${post.id}" data-username="${post.username}">
                        <i class="fa-solid fa-reply"></i> 返信
                    </button>
                    ${!post.is_own ? `
                        <button class="report-btn text-xs text-red-500 hover:text-red-700 dark:text-red-400 transition" data-post-id="${post.id}">
                            <i class="fa-solid fa-flag"></i> 通報${post.report_count > 0 ? `(${post.report_count})` : ''}
                        </button>
                    ` : ''}
                    ${replies.length > 0 ? `
                        <span class="text-xs text-gray-400 dark:text-slate-500">
                            <i class="fa-solid fa-comment"></i> ${replies.length}件の返信
                        </span>
                    ` : ''}
                </div>
                
                <!-- 返信一覧 -->
                ${replies.length > 0 ? `
                    <div class="replies mt-2 space-y-2">
                        ${replies.map(reply => BoardModule.renderPost(reply, allPosts, true)).join('')}
                    </div>
                ` : ''}
            </div>
        `;
        
        return html;
    },
    
    attachPostEventListeners: () => {
        // 返信ボタン
        document.querySelectorAll('.reply-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const postId = parseInt(e.currentTarget.dataset.postId);
                const username = e.currentTarget.dataset.username;
                BoardModule.showReplyForm(postId, username);
            });
        });
        
        // 通報ボタン
        document.querySelectorAll('.report-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const postId = parseInt(e.currentTarget.dataset.postId);
                BoardModule.reportPost(postId);
            });
        });
        
        // 内容を見るボタン
        document.querySelectorAll('.show-content-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const postId = parseInt(e.currentTarget.dataset.postId);
                BoardModule.showHiddenContent(postId);
            });
        });
    },
    
    showHiddenContent: async (postId) => {
        try {
            const response = await fetch('/api/board/get_posts');
            const data = await response.json();
            
            const post = data.posts.find(p => p.id === postId);
            if (post && post.original_content) {
                const warningText = post.is_hidden 
                    ? '⚠️ この投稿は通報により非表示になっています。' 
                    : '⚠️ この投稿にはリンクが含まれている可能性があります。';
                
                alert(`【投稿内容】\n\n${post.original_content}\n\n${warningText}\n\n不適切な内容の場合は通報してください。`);
            }
        } catch (error) {
            console.error('[BOARD] Failed to show content:', error);
            alert('内容の表示に失敗しました。');
        }
    },
    
    reportPost: async (postId) => {
        if (!confirm('この投稿を通報しますか？\n\n不適切な内容（誹謗中傷、差別、脅迫、違法行為の助長など）が含まれる投稿のみ通報してください。\n\n3件以上の通報で投稿が非表示になり、投稿者は24時間制限されます。')) {
            return;
        }
        
        try {
            const response = await fetch('/api/board/report_post', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ post_id: postId })
            });
            
            const data = await response.json();
            
            if (data.success) {
                alert('✅ ' + data.message);
                BoardModule.loadPosts();
            } else {
                alert('❌ ' + data.message);
            }
        } catch (error) {
            console.error('[BOARD] Failed to report post:', error);
            alert('通報に失敗しました。もう一度お試しください。');
        }
    }
};

// ==========================================
// DOMContentLoaded（既存要素すべて保持）
// ==========================================
document.addEventListener('DOMContentLoaded', () => {
    MapModule.init();
    ThemeModule.init();
    FavoriteModule.init();

    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            MapModule.updateMarker(CONFIG.defaultLat, CONFIG.defaultLng);
            mapInstance.setView([CONFIG.defaultLat, CONFIG.defaultLng], 10);
            MapModule.updateRadar();
        });
    }

    const geoBtn = document.getElementById('geolocation-btn');
    if (geoBtn) {
        geoBtn.addEventListener('click', () => {
            ThemeModule.triggerButtonAnim(geoBtn);
            MapModule.getCurrentLocation();
        });
    }

    const aiBtn = document.getElementById('ai-suggest-btn');
    if (aiBtn) {
        aiBtn.addEventListener('click', () => {
            AIModule.suggestOutfit();
        });
    }

    const aiResetBtn = document.getElementById('ai-reset-btn');
    if (aiResetBtn) {
        aiResetBtn.addEventListener('click', () => {
            ThemeModule.triggerButtonAnim(aiResetBtn);
            AIModule.reset();
        });
    }

    // 掲示板の初期化（スマホのみ）
    if (window.innerWidth < 768) {
        BoardModule.init();
    }
    });
    
    // ==========================================
    // 折りたたみボタン機能（スマホ専用・新規追加）
    // ==========================================
    
    // 天候推移の折りたたみ
    const toggleChartBtn = document.getElementById('toggle-chart-btn');
    const chartContent = document.getElementById('chart-content');

    if (toggleChartBtn && chartContent) {
        toggleChartBtn.addEventListener('click', () => {
            toggleChartBtn.classList.toggle('active');
            chartContent.classList.toggle('collapsed');
        });
    }

    // 週間予報の折りたたみ
    const toggleForecastBtn = document.getElementById('toggle-forecast-btn');
    const forecastContent = document.getElementById('forecast-content');

    if (toggleForecastBtn && forecastContent) {
        toggleForecastBtn.addEventListener('click', () => {
            toggleForecastBtn.classList.toggle('active');
            forecastContent.classList.toggle('collapsed');
        });
    }
});
