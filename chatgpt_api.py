from datetime import datetime, timedelta

# ===== フォールバック関数群 =====
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
