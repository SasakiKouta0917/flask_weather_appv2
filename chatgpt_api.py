import os
import json
import requests
import traceback

def suggest_outfit(weather, options):
    api_key = os.environ.get("GOOGLE_API_KEY")
    
    if not api_key:
        print("[ERROR] GOOGLE_API_KEY is not set!")
        return {"type": "error", "suggestions": {"suggestion": "APIキーが設定されていません。"}}

    # --- 1. 接続設定 ---
    url = "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key
    }

    # --- 2. データの展開 ---
    temp = weather.get("temp")
    temp_max = weather.get("temp_max")
    temp_min = weather.get("temp_min")
    weather_desc = weather.get("weather")
    humidity = weather.get("humidity")
    precipitation = weather.get("precipitation")
    
    mode = options.get("mode")
    scene = options.get("scene") or "特になし"
    gender = options.get("gender")
    preference = options.get("preference") or "特になし"
    wardrobe = options.get("wardrobe") or "特になし"

    gender_str = "レディース" if gender == "ladies" else "メンズ" if gender == "mens" else "指定なし(ユニセックス)"

    # --- 3. プロンプト構築 ---
    base_info = f"""
天気情報：{weather_desc}、気温：{temp}℃ (最高:{temp_max} / 最低:{temp_min})、湿度：{humidity}%、降水：{precipitation}mm
条件：利用シーンは「{scene}」、対象は「{gender_str}」です。
"""

    if mode == "detailed":
        instruction = f"要望：{preference}、手持ちの服：{wardrobe}。これらを考慮して具体的に提案してください。"
    else:
        instruction = "天気とシーンから、具体的な商品名は避けて、服装の方向性を提案してください。"

    prompt = f"""
{base_info}
{instruction}

# 指示
上記条件に合う服装の提案を400文字程度の文章で作成してください。
出力は必ず以下のJSON形式のみで行ってください。

{{
  "suggestion": "ここに提案文章を記述"
}}
"""

    # --- 4. リクエスト送信 (API仕様に合わせた形式) ---
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.7,
            # 直接APIを叩く際は snake_case を使用
            "response_mime_type": "application/json"
        }
    }

    try:
        print("[INFO] Gemini APIに修正版リクエストを送信中...")
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        
        if response.status_code != 200:
            print(f"[ERROR] APIエラー: {response.status_code}")
            print(f"詳細: {response.text}")
            return {"type": "error", "suggestions": {"suggestion": "AIとの接続に失敗しました。"}}

        # 応答の解析
        data = response.json()
        content = data['candidates'][0]['content']['parts'][0]['text']
        
        # JSON部分だけを抽出する堅牢な処理
        start_index = content.find('{')
        end_index = content.rfind('}') + 1
        if start_index != -1 and end_index != 0:
            json_str = content[start_index:end_index]
            suggestions = json.loads(json_str)
        else:
            # 万が一JSON形式でなかった場合の予備
            suggestions = {"suggestion": content.strip()}

        print("[SUCCESS] Gemini APIから正常に応答を受け取りました")
        return {
            "type": "success",
            "suggestions": suggestions
        }

    except Exception as e:
        print(f"[ERROR] 重大なエラー: {e}")
        traceback.print_exc()
        return {
            "type": "error",
            "suggestions": {"suggestion": "通信エラーが発生しました。時間を置いて再度お試しください。"}
        }
