import os
import json
import requests
import traceback

def suggest_outfit(weather, options):
    """
    Gemini APIを使用して、天気とオプションに基づいた服装提案を行う関数
    """
    
    # APIキーの設定（環境変数から読み込み）
    api_key = os.environ.get("GOOGLE_API_KEY")
    
    if not api_key:
        print("[ERROR] GOOGLE_API_KEY is not set!")
        return {
            "type": "error",
            "suggestions": {"suggestion": "APIキーが設定されていません。管理者に連絡してください。"}
        }
    
    print(f"[INFO] API Key loaded: {api_key[:15]}...")

    # 天気情報の展開
    temp = weather.get("temp")
    temp_max = weather.get("temp_max")
    temp_min = weather.get("temp_min")
    weather_desc = weather.get("weather")
    humidity = weather.get("humidity")
    precipitation = weather.get("precipitation")
    
    # オプション情報の展開
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

    # --- プロンプト構築 ---
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

    # モードによる指示の分岐
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

    # --- APIリクエスト設定 ---
    # 【修正】Markdown記号混入を物理的に防ぐため、変数を分割して結合
    base_url = "[https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent](https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent)"
    url = f"{base_url}?key={api_key}"
    
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 1000,
            "responseMimeType": "application/json"
        }
    }

    try:
        print("[INFO] Sending request to Gemini API (v1beta)...")
        # タイムアウトを60秒に設定
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        
        print(f"[INFO] Response status: {response.status_code}")
        
        # エラーハンドリング
        if response.status_code != 200:
            error_text = response.text
            print(f"[ERROR] API Error Response: {error_text}")
            
            # 429 Too Many Requests 対応
            if response.status_code == 429:
                return {
                    "type": "error",
                    "suggestions": {"suggestion": "アクセスが集中しています。しばらく待ってから再度お試しください。"}
                }

            try:
                error_json = response.json()
                error_message = error_json.get('error', {}).get('message', 'Unknown error')
            except:
                error_message = "詳細不明"
            
            return {
                "type": "error",
                "suggestions": {
                    "suggestion": f"AI通信エラーが発生しました。\n詳細: {error_message}"
                }
            }

        data = response.json()
        
        # レスポンス構造のチェック
        if 'candidates' not in data or not data['candidates']:
            return {"type": "error", "suggestions": {"suggestion": "AIから回答が得られませんでした。"}}

        candidate = data['candidates'][0]

        # セーフティフィルタ検知
        finish_reason = candidate.get('finishReason')
        if finish_reason == "SAFETY":
             return {
                "type": "error",
                "suggestions": {"suggestion": "不適切な表現が含まれる可能性があるため、回答が生成されませんでした。入力内容を見直してください。"}
            }

        if 'content' not in candidate:
             return {"type": "error", "suggestions": {"suggestion": "AI応答の形式が不正です。"}}
        
        parts = candidate['content'].get('parts', [])
        if not parts or 'text' not in parts[0]:
             return {"type": "error", "suggestions": {"suggestion": "AI応答にテキストが含まれていません。"}}
        
        content = parts[0]['text'].strip()
        print(f"[SUCCESS] Got response from Gemini API")

        # JSONクリーニング
        clean_json = content.replace("```json", "").replace("```", "").strip()
        
        try:
            suggestions = json.loads(clean_json)
            
            # JSONキーの揺らぎ対策
            if "suggestion" not in suggestions:
                found_text = suggestions.get("text") or suggestions.get("advice") or str(suggestions)
                suggestions = {"suggestion": found_text}

            print(f"[SUCCESS] JSON parsed successfully")
            
            # 成功を返す
            return {
                "type": "success",
                "suggestions": suggestions
            }
            
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON Parse Error: {e}")
            return {
                "type": "error",
                "suggestions": {
                    "suggestion": "AI応答の解析に失敗しました。もう一度お試しください。"
                }
            }

    except requests.exceptions.Timeout:
        print("[ERROR] Request timeout")
        return {
            "type": "error",
            "suggestions": {
                "suggestion": "処理がタイムアウトしました。もう一度お試しください。"
            }
        }
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Request Exception: {e}")
        traceback.print_exc()
        return {
            "type": "error",
            "suggestions": {
                "suggestion": "通信エラーが発生しました。ネットワーク接続を確認してください。"
            }
        }
    except Exception as e:
        print(f"[ERROR] Unexpected Error: {e}")
        traceback.print_exc()
        return {
            "type": "error",
            "suggestions": {
                "suggestion": f"システムエラーが発生しました。\n{str(e)[:100]}"
            }
        }
