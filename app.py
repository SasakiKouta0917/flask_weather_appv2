from flask import Flask, request, jsonify, render_template
import requests
import time
import json
import os
from datetime import datetime
import traceback

from chatgpt_api import suggest_outfit

app = Flask(__name__, template_folder='templates', static_folder='static')

# === キャッシュ ===
CACHE = {}
CACHE_TTL = 60
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "amedas-weather-app/2.0"})

# === 観測所一覧 ===
base = os.path.dirname(os.path.abspath(__file__))
json_path = os.path.join(base, "amedas_points.json")
with open(json_path, encoding="utf-8") as f:
    AMEDAS_POINTS = json.load(f)

# === 最寄り観測所 ===
def nearest_station(lat, lon):
    best = None
    best_dist = 9e9
    for p in AMEDAS_POINTS:
        d = (lat - p['lat'])**2 + (lon - p['lon'])**2
        if d < best_dist:
            best_dist = d
            best = p
    return best

# === Amedas JSON 現在観測 ===
def fetch_amedas_json(st_id):
    key = f"amedas:{st_id}"
    c = CACHE.get(key)
    if c and time.time() - c[0] < CACHE_TTL:
        return c[1]

    try:
        t = SESSION.get(
            "https://www.jma.go.jp/bosai/amedas/data/latest_time.txt",
            timeout=6
        )
        latest = t.text.strip()
        day = latest[:8]    # YYYYMMDD

        url = f"https://www.jma.go.jp/bosai/amedas/data/{day}/{st_id}.json"
        r = SESSION.get(url, timeout=6)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return {
            "weather": "不明",
            "temperature": None,
            "humidity": None,
            "precipitation": None,
            "pressure": None,
            "temp_max": None,
            "temp_min": None
        }

    out = {
        "weather": "晴れ",        # 現在天気は Amedas で取れない → 仮
        "temperature": None,
        "humidity": None,
        "precipitation": None,
        "pressure": None,
        "temp_max": None,
        "temp_min": None
    }

    if "temp" in data and data["temp"] and data["temp"][-1] is not None:
        out["temperature"] = data["temp"][-1]

    if "humidity" in data and data["humidity"] and data["humidity"][-1] is not None:
        out["humidity"] = data["humidity"][-1]

    if "precipitation1h" in data and data["precipitation1h"] and data["precipitation1h"][-1] is not None:
        out["precipitation"] = data["precipitation1h"][-1]

    if "pressure" in data and data["pressure"] and data["pressure"][-1] is not None:
        out["pressure"] = data["pressure"][-1]

    CACHE[key] = (time.time(), out)
    return out

# === Open-Meteo（12時間予報） ===
def fetch_hourly(lat, lon):
    key = f"om:{round(lat,2)}:{round(lon,2)}"
    c = CACHE.get(key)
    if c and time.time() - c[0] < CACHE_TTL:
        return c[1]

    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}"
            f"&hourly=temperature_2m,weathercode"
            f"&timezone=Asia%2FTokyo"
        )
        r = SESSION.get(url, timeout=6)
        r.raise_for_status()
        j = r.json()

        arr = []
        times = j["hourly"]["time"]
        temps = j["hourly"]["temperature_2m"]
        codes = j["hourly"]["weathercode"]

        for i in range(min(12, len(times))):
            t = datetime.fromisoformat(times[i])
            w = "雨" if codes[i] in [51,61,63,65,80,81,82] else "晴れ"
            arr.append({
                "label": f"{t.hour}:00",
                "temp": temps[i],
                "weather": w
            })

        CACHE[key] = (time.time(), arr)
        return arr

    except Exception:
        return None

# === API: 天気データ ===
@app.route("/api/weather")
def api_weather():
    try:
        lat = float(request.args.get("lat", 39.30506946))
        lon = float(request.args.get("lon", 141.11956806))

        st = nearest_station(lat, lon)
        if not st:
            return jsonify({"status": "error", "message":"観測所なし"})

        obs = fetch_amedas_json(st["id"])
        hourly = fetch_hourly(lat, lon)

        return jsonify({
            "status": "ok",
            "station_name": st["name"],
            **obs,
            "hourly": hourly
        })

    except Exception:
        traceback.print_exc()
        return jsonify({"status": "error"})

# === API: 服装提案 ===
@app.route("/api/suggest", methods=["POST"])
def api_suggest():
    try:
        w = request.json
        if not w:
            return jsonify({"status":"error"})

        res = suggest_outfit(w)
        return jsonify({"status":"ok", "data":res})

    except Exception:
        traceback.print_exc()
        return jsonify({"status":"error"})

@app.route("/")
def index():
    return render_template("index.html")

# Render/Heroku用
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
