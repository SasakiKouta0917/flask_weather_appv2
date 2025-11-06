from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
import traceback

# ===== 実APIが無い環境でも動くフォールバック =====
try:
    from weather_api import get_weather_by_coords, get_hourly_by_coords
    from chatgpt_api import suggest_outfit
except Exception:
    def get_weather_by_coords(lat, lon):
        return {
            "lat": lat, "lon": lon,
            "name": "北上コンピュータ・アカデミー（ダミー）",
            "weather": "晴れ",
            "temp": 18.2,
            "temp_max": 22.1,
            "temp_min": 12.0,
            "humidity": 55,
            "precipitation": 0,
            "pressure": 1012
        }

    def get_hourly_by_coords(lat, lon):
        now = datetime.utcnow()
        out = []
        for i in range(12):
            t = now + timedelta(hours=i+1)
            out.append({
                "time": t.isoformat(),
                "label": f"{t.hour:02d}:00",
                "temp": 12 + (i % 6) * 2,
                "weather": "晴れ" if i % 5 != 0 else "雨",
                "weathercode": 0 if i % 5 != 0 else 61
            })
        return out

    def suggest_outfit(weather):
        return {
            "type": "any",
            "suggestions": [
                {"period": "朝晩", "any": "薄手のジャケットと長袖。"},
                {"period": "昼間", "any": "半袖＋軽い羽織。"}
            ]
        }

# ===== Flask =====
app = Flask(__name__, template_folder='templates', static_folder='static')
weather_cache = {}

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

        if not data or not isinstance(data, dict):
            data = get_weather_by_coords(lat, lon)

        normalized = {
            "lat": data.get("lat", lat),
            "lon": data.get("lon", lon),
            "city": data.get("name") or data.get("city") or "不明",
            "weather": data.get("weather") or data.get("weather_main") or "不明",
            "temp": data.get("temp") or data.get("temperature"),
            "temp_max": data.get("temp_max") or data.get("max_temp"),
            "temp_min": data.get("temp_min") or data.get("min_temp"),
            "humidity": data.get("humidity"),
            "precipitation": data.get("precipitation") or data.get("rain",{}).get("1h",0),
            "pressure": data.get("pressure") or (data.get("main") and data.get("main").get("pressure")),
        }

        weather_cache['data'] = normalized
        return jsonify({"status":"ok","weather":normalized})
    except Exception:
        traceback.print_exc()
        dummy = get_weather_by_coords(39.30506946, 141.11956806)
        weather_cache['data'] = dummy
        return jsonify({"status":"ok","weather":dummy})

@app.route('/hourly', methods=['GET'])
def hourly():
    try:
        lat = float(request.args.get('lat', 39.30506946))
        lon = float(request.args.get('lon', 141.11956806))
        arr = get_hourly_by_coords(lat, lon)

        out = []
        if not arr or not isinstance(arr, list):
            arr = get_hourly_by_coords(lat, lon)

        for i, it in enumerate(arr[:12]):
            time = it.get('time') or (datetime.utcnow() + timedelta(hours=i+1)).isoformat()
            out.append({
                "time": time,
                "label": it.get('label') or datetime.fromisoformat(time).strftime("%H:%M"),
                "temp": it.get('temp') or 0,
                "weather": it.get('weather') or "不明",
                "weathercode": it.get('weathercode') if 'weathercode' in it else (0 if "晴" in str(it) else 61)
            })

        return jsonify({"status":"ok","hourly":out})
    except Exception:
        traceback.print_exc()
        out = get_hourly_by_coords(39.30506946, 141.11956806)
        return jsonify({"status":"ok","hourly":out})

@app.route('/suggest', methods=['POST'])
def suggest():
    try:
        if 'data' not in weather_cache:
            weather_cache['data'] = get_weather_by_coords(39.30506946, 141.11956806)

        s = suggest_outfit(weather_cache['data'])
        if isinstance(s, str):
            s = {"type":"any","suggestions":[{"period":"全体","any":s}]}

        if isinstance(s, dict) and "suggestions" not in s:
            s = {"type": s.get("type","any"), "suggestions":[{"period":"全体","any":str(s)}]}

        return jsonify({"status":"ok","suggestion":s})
    except Exception:
        traceback.print_exc()
        dummy = {"type":"any","suggestions":[{"period":"朝晩","any":"薄手のジャケット。"},{"period":"昼間","any":"半袖＋羽織。"}]}
        return jsonify({"status":"ok","suggestion":dummy})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

