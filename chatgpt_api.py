import os
import json
import requests
import traceback

def suggest_outfit(weather, options):
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

    # --- 🔧 修正箇所1: 正しいモデル名に変更 (-latest を削除) ---
    url = f"[https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=](https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=){api_key}"
    
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 1000,
            # --- 🔧 修正箇所2: JSONモードを強制する設定を追加 (パースエラー防止) ---
            "responseMimeType": "application/json"
        }
    }

    try:
        print("[INFO] Sending request to Gemini API (v1beta)...")
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        print(f"[INFO] Response status: {response.status_code}")
        
        if response.status_code != 200:
            error_text = response.text
            print(f"[ERROR] API Error Response: {error_text}")
            
            # エラー詳細を抽出
            try:
                error_json = response.json()
                error_message = error_json.get('error', {}).get('message', 'Unknown error')
                print(f"[ERROR] Error message: {error_message}")
            except:
                error_message = "詳細不明"
            
            return {
                "type": "error",
                "suggestions": {
                    "suggestion": f"AI通信エラーが発生しました。\n\nエラー詳細: {error_message}\n\n管理者に連絡してください。"
                }
            }

        data = response.json()
        # print(f"[DEBUG] Response data keys: {data.keys()}") # ログが多すぎる場合はコメントアウト推奨
        
        # レスポンス構造を確認
        if 'candidates' not in data:
            print(f"[ERROR] No 'candidates' in response: {data}")
            return {
                "type": "error",
                "suggestions": {
                    "suggestion": "AIから有効な回答が得られませんでした。もう一度お試しください。"
                }
            }
        
        if len(data['candidates']) == 0:
            print(f"[ERROR] Empty candidates array")
            return {
                "type": "error",
                "suggestions": {
                    "suggestion": "AIから回答がありませんでした。もう一度お試しください。"
                }
            }
        
        # テキスト抽出
        candidate = data['candidates'][0]
        if 'content' not in candidate:
            print(f"[ERROR] No 'content' in candidate: {candidate}")
            return {
                "type": "error",
                "suggestions": {
                    "suggestion": "AI応答の形式が不正です。"
                }
            }
        
        parts = candidate['content'].get('parts', [])
        if not parts or 'text' not in parts[0]:
            print(f"[ERROR] No text in parts: {parts}")
            return {
                "type": "error",
                "suggestions": {
                    "suggestion": "AI応答にテキストが含まれていません。"
                }
            }
        
        content = parts[0]['text'].strip()
        print(f"[SUCCESS] Got response from Gemini API")
        print(f"[DEBUG] Response text (first 100 chars): {content[:100]}")

        # JSONクリーニング
        # responseMimeTypeを指定しましたが、念のため既存のクリーニング処理も残しておきます
        clean_json = content.replace("```json", "").replace("```", "").strip()
        
        # JSONパース
        try:
            suggestions = json.loads(clean_json)
            print(f"[SUCCESS] JSON parsed successfully")
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON Parse Error: {e}")
            print(f"[ERROR] Content: {clean_json[:200]}")
            return {
                "type": "error",
                "suggestions": {
                    "suggestion": "AI応答の解析に失敗しました。もう一度お試しください。"
                }
            }

        return {
            "type": "success",
            "suggestions": suggestions
        }

    except requests.exceptions.Timeout:
        print("[ERROR] Request timeout (30s)")
        return {
            "type": "error",
            "suggestions": {
                "suggestion": "リクエストがタイムアウトしました。ネットワーク接続を確認して、もう一度お試しください。"
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
                "suggestion": f"予期せぬエラーが発生しました。管理者に連絡してください。\n\nエラー: {str(e)[:100]}"
            }
        }
