import os
import json
import requests
import traceback

def suggest_outfit(weather, options):
    # APIキーの取得
    api_key = os.environ.get("GOOGLE_API_KEY")
    
    if not api_key:
        print("[ERROR] GOOGLE_API_KEY is not set!")
        return {"type": "error", "suggestions": {"suggestion": "APIキーが設定されていません。"}}

    # --- 1. 接続設定 (v1安定版を直接指定) ---
    url = "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key  # キーをヘッダーに隠して安全に送信
    }

    # --- 2. データの展開 (既存ロジックを継承) ---
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

    # --- 3. プロンプト構築 (既存ロジックを継承) ---
    base_info = f"""
# 天気情報
- 天気: {weather_desc}
- 気温: {temp}℃ (最高:{temp_max}℃ / 最低:{temp_min}℃)
- 湿度: {humidity}%
- 降水量: {precipitation}mm

# 基本条件
- 利用シーン: {scene}
- スタイル対象: {gender_str}
"""

    if mode == "detailed":
        instruction = f"""
# ユーザーの要望データ
- **着たい服・気分**: {preference}
- **手持ちの服リスト**: {wardrobe}

# 指示
1. ユーザーの「着たい服」を可能な限り取り入れたコーディネートを考えてください。
2. 「手持ちの服リスト」にあるアイテムを優先的に組み合わせてください。
3. 気温や雨を考慮し、具体的にアドバイスしてください。
"""
    else:
        instruction = """
# 指示
1. 天気情報と利用シーンから、最適な服装の「方向性」を提案してください。
2. 具体的な商品名は避け、「厚手の防寒アウター」のような抽象的な表現を用いてください。
"""

    format_instruction = """
# 出力形式
必ず以下のJSON形式で、1つのまとまった文章(400文字程度)として出力してください。
{ "suggestion": "ここに提案文章..." }
"""

    prompt = base_info + instruction + format_instruction

    # --- 4. リクエスト送信 ---
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "responseMimeType": "application/json", # JSONモードを強制
        }
    }

    try:
        print("[INFO] Gemini 1.5 Flash (Direct API) にリクエスト送信中...")
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        
        if response.status_code != 200:
            print(f"[ERROR] APIエラー: {response.status_code}")
            print(f"詳細: {response.text}")
            return {"type": "error", "suggestions": {"suggestion": "AIとの接続に失敗しました。"}}

        # 応答の解析
        data = response.json()
        content = data['candidates'][0]['content']['parts'][0]['text']
        suggestions = json.loads(content)

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
            "suggestions": {"suggestion": "エラーが発生しました。気温に合わせた服装でお出かけください。"}
        }
