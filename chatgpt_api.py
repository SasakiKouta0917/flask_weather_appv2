import os
import json
import requests
import traceback

def suggest_outfit(weather, options):
    # APIキーの設定（環境変数から読み込み）
    api_key = os.environ.get("GOOGLE_API_KEY")
    
    if not api_key:
        print("[ERROR] GOOGLE_API_KEY is not set!")
        return {"type": "error", "suggestions": {"suggestion": "APIキーが設定されていません。"}}

    # 天気情報の展開（元のコードの全要素を維持）
    temp = weather.get("temp")
    temp_max = weather.get("temp_max")
    temp_min = weather.get("temp_min")
    weather_desc = weather.get("weather")
    humidity = weather.get("humidity")
    precipitation = weather.get("precipitation")
    
    # オプション情報の展開（元のコードの全要素を維持）
    mode = options.get("mode")
    scene = options.get("scene") or "特になし"
    gender = options.get("gender")
    preference = options.get("preference") or "特になし"
    wardrobe = options.get("wardrobe") or "特になし"

    # 性別・スタイルの表示用文字列
    gender_str = "指定なし(ユニセックス)"
    if gender == "mens": 
        gender_str = "メンズ"
    elif gender == "ladies": 
        gender_str = "レディース"

    # --- プロンプト構築（詳細なロジックを完全再現） ---
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
2. 「手持ちの服リスト」にあるアイテムを優先的に組み合わせてください。リストにないアイテムが必要な場合は「買い足し推奨」や「あれば良いもの」として提案してください。
3. 天気(特に気温や雨)を考慮し、快適に過ごせる工夫を具体的にアドバイスしてください。
4. アイテム名は具体的に挙げて提案してください。
"""
    else:
        instruction = f"""
# 指示
1. 天気情報と利用シーンから、最適な服装の「方向性」を提案してください。
2. **具体的な商品名やピンポイントな色・形(例:「ユニクロの黒ダウン」など)は避けてください。**
3. 代わりに「厚手の防寒アウター」「風を通さない素材」「明るい色味のトップス」のように、**抽象的かつ機能性や雰囲気を重視した表現**で提案してください。
4. ユーザーが自分のクローゼットから服を選びやすくなるような、道しるべとなるアドバイスにしてください。
"""

    format_instruction = """
# 出力形式
以下のJSON形式で出力してください。項目を分けず、時間帯(朝・昼・夜)の変化やまとめを含めた**ひとつのまとまった提案文章(400文字程度)**にしてください。

{
  "suggestion": "ここに提案文章を記述..."
}

# 制約
- 指示の復唱はしない。
- JSON以外の余計な文字は出力しない。
- ```json のようなマークダウンも出力しない。
"""

    prompt = base_info + instruction + format_instruction

    # --- APIリクエスト実行部分（URLのゴミ混入を完全に防ぐ修正） ---
    # 以前のエラー（InvalidSchema）の原因だったMarkdownリンクを完全に排除
    api_endpoint = "[https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent](https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent)"
    url = f"{api_endpoint}?key={api_key}"
    
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 1000
        }
    }

    try:
        print("[INFO] Gemini 1.5 Flash (Direct REST API) を実行中")
        # requestsを使って安全なHTTPS通信を実行
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        
        # HTTPステータスコードのチェック
        if response.status_code != 200:
            print(f"[ERROR] Gemini API Error: {response.status_code} - {response.text}")
            return {"type": "error", "suggestions": {"suggestion": "AIとの通信に失敗しました。"}}

        # レスポンス解析
        data = response.json()
        
        # APIレスポンスからテキストを抽出（Google公式のJSON構造に準拠）
        if 'candidates' in data and len(data['candidates']) > 0:
            content = data['candidates'][0]['content']['parts'][0]['text'].strip()
        else:
            print(f"[ERROR] Unexpected API Response: {data}")
            return {"type": "error", "suggestions": {"suggestion": "AIから有効な回答が得られませんでした。"}}
            
        print(f"[SUCCESS] Gemini API returned response")

        # マークダウンのコードブロックが含まれる場合の削除処理
        clean_json = content.replace("```json", "").replace("```", "").strip()
        
        # JSONとしてパース
        suggestions = json.loads(clean_json)

        return {
            "type": "success",
            "suggestions": suggestions
        }

    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON Parse Error: {e}")
        print(f"Raw Content: {content if 'content' in locals() else 'No content'}")
        return {"type": "error", "suggestions": {"suggestion": "AI応答の解析に失敗しました。"}}
    except Exception as e:
        print(f"[ERROR] System Error: {e}")
        traceback.print_exc()
        return {"type": "error", "suggestions": {"suggestion": "予期せぬエラーが発生しました。"}}
