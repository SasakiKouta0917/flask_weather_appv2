from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta, timezone
import traceback
import requests
import time

from chatgpt_api import suggest_outfit  # ✅ Render用に明示的にimport

app = Flask(__name__, template_folder='templates', static_folder='static')

# ---- キャッシュ ----
CACHE = {}
CACHE_TTL = 45
SESSION = requests.Session()
SESSION.headers.update({"User-Agent":"weather-app/1.0"})

JMA_URL = "https://api.open-meteo.com/v1/jma"

WEATHERCODE_MAP = {
    0: "快晴", 1: "晴れ時々曇り", 2: "曇り時々晴れ", 3: "曇り",
    45: "霧", 48: "霧氷", 51: "弱い霧雨", 53: "霧雨", 55: "強い霧雨",
    56: "弱い凍結霧雨", 57: "強い凍結霧雨", 61: "弱い雨", 63: "雨", 65: "強い雨",
    66: "弱い凍結雨", 67: "強い凍結雨", 71: "弱い雪", 73: "雪", 75: "強い雪",
    77: "霰（あられ）", 80: "にわか雨（弱）", 81: "にわか雨（中）", 82: "にわか雨（強）",
    85: "弱いにわか雪", 86: "強いにわか雪", 95: "雷雨", 96: "雷雨（雹を伴う可能性あり）", 99: "激しい雷雨（雹を伴う可能性大）"
}

def code_to_label(c): return WEATHERCODE_MAP.get(int(c), "不明")

def cache_get(k):
    item = CACHE.get(k)
    if not item: return None
    ts, val = item
    if time.time() - ts > CACHE_TTL:
        del CACHE[k]
        return None
    return val

def cache_set(k, v):
    CACHE[k] = (time.time(), v)

def round_coord(x): return round(float(x), 4)

# ---- 現在の天気 ----
def get_weather_by_coords(lat, lon):
    key = f"current_jma:{round_coord(lat)}:{round_coord(lon)}"
    cached = cache_get(key)
    if cached: return cached

    try:
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": ["temperature_2m", "relative_humidity_2m", "surface_pressure", "precipitation", "weather_code"],
            "daily": ["temperature_2m_max", "temperature_2m_min"],
            "timezone": "Asia/Tokyo"
        }
        r = SESSION.get(JMA_URL, params=params, timeout=7)
        r.raise_for_status()
        j = r.json()

        current = j.get("current", {})
        daily = j.get("daily", {})

        result = {
            "lat": lat, "lon": lon,
            "city": None,
            "weather": code_to_label(current.get("weather_code")),
            "weathercode": current.get("weather_code"),
            "temp": current.get("temperature_2m"),
            "humidity": current.get("relative_humidity_2m"),
            "precipitation": current.get("precipitation"),
            "pressure": current.get("surface_pressure"),
            "temp_max": daily.get("temperature_2m_max", [None])[0],
            "temp_min": daily.get("temperature_2m_min", [None])[0],
            "source": "open-meteo-jma"
        }

        cache_set(key, result)
        return result

    except Exception:
        traceback.print_exc()
        dummy = {
            "lat": lat, "lon": lon,
            "weather": "晴れ",
            "temp": 18.2, "temp_max": 22, "temp_min": 12,
            "humidity": 55, "precipitation": 0, "pressure": 1012,
            "source": "fallback"
        }
        cache_set(key, dummy)
        return dummy
# ---- 12時間予報 ----
def get_hourly_by_coords(lat, lon):
    key = f"hourly_jma:{round_coord(lat)}:{round_coord(lon)}"
    cached = cache_get(key)
    if cached: return cached

    try:
        params = {
            "latitude": lat, "longitude": lon,
            "hourly": ["temperature_2m", "relative_humidity_2m","precipitation","weather_code"],
            "timezone": "Asia/Tokyo"
        }
        r = SESSION.get(JMA_URL, params=params, timeout=7)
        r.raise_for_status()
        j = r.json()
        hourly = j.get("hourly", {})

        times = hourly.get("time", [])
        temps = hourly.get("temperature_2m", [])
        codes = hourly.get("weather_code", [])
        precs = hourly.get("precipitation", [])
        hums = hourly.get("relative_humidity_2m", [])

        JST = timezone(timedelta(hours=9))
        now = datetime.now(JST)
        start = 0
        for i, t in enumerate(times):
            try:
                dt = datetime.strptime(t, "%Y-%m-%dT%H:%M").replace(tzinfo=JST)
                if dt >= now:
                    start = i
                    break
            except Exception:
                continue

        out = []
        for i in range(start, min(start+12, len(times))):
            t = times[i]
            dt = datetime.strptime(t, "%Y-%m-%dT%H:%M").replace(tzinfo=JST)
            out.append({
                "time": t,
                "label": dt.strftime("%H:%M"),
                "temp": temps[i] if i < len(temps) else None,
                "weather": code_to_label(codes[i]) if i < len(codes) else "不明",
                "weathercode": codes[i] if i < len(codes) else 0,
                "precipitation": precs[i] if i < len(precs) else None,
                "humidity": hums[i] if i < len(hums) else None
            })

        cache_set(key, out)
        return out

    except Exception:
        traceback.print_exc()
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        out = []
        for i in range(12):
            t = now + timedelta(hours=i+1)
            out.append({
                "time": t.isoformat(timespec="minutes"),
                "label": t.strftime("%H:%M"),
                "temp": 12+(i%6)*2,
                "weather": "晴れ" if i%5!=0 else "雨",
                "weathercode": 0 if i%5!=0 else 61
            })
        cache_set(key, out)
        return out

# ==== Flask endpoints ====

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/update', methods=['POST'])
def update():
    try:
        body = request.get_json() or {}
        lat = float(body.get('lat', 39.30506946))
        lon = float(body.get('lon', 141.11956806))
        data = get_weather_by_coords(lat, lon)
        return jsonify({"status":"ok","weather":data})
    except Exception:
        traceback.print_exc()
        dummy = get_weather_by_coords(39.30506946,141.11956806)
        return jsonify({"status":"ok","weather":dummy})

@app.route('/hourly', methods=['GET'])
def hourly():
    try:
        lat = float(request.args.get('lat', 39.30506946))
        lon = float(request.args.get('lon', 141.11956806))
        arr = get_hourly_by_coords(lat, lon)
        return jsonify({"status":"ok","hourly":arr})
    except Exception:
        traceback.print_exc()
        arr = get_hourly_by_coords(39.30506946,141.11956806)
        return jsonify({"status":"ok","hourly":arr})

@app.route('/suggest', methods=['POST'])
def suggest():
    try:
        body = get_weather_by_coords(39.30506946,141.11956806)
        s = suggest_outfit(body)
        return jsonify({"status":"ok","suggestion":s})
    except Exception:
        traceback.print_exc()
        dummy = {"type":"any","suggestions":[
            {"period":"朝晩","any":"薄手のジャケット"},
            {"period":"昼間","any":"半袖＋羽織"}
        ]}
        return jsonify({"status":"ok","suggestion":dummy})
