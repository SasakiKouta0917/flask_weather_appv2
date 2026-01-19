import os
import json
import requests
import traceback

def suggest_outfit(weather, options):
    """
    Gemini APIを使用して服装提案を行う
    
    2026年1月時点の最新情報:
    - 利用可能モデル: gemini-2.5-flash, gemini-2.0-flash, gemini-2.5-pro
    - gemini-1.5-flash は廃止済み
    - 公式ドキュメント: https://ai.google.dev/gemini-api/docs/models
    """
    
    # APIキーの取得
    api_key = os.environ.get("GOOGLE_API_KEY")
    
    if not api_key:
        print("[ERROR] GOOGLE_API_KEY is not set in environment variables!")
        return {
            "type": "error",
            "suggestions": {
                "suggestion": "❌ APIキーが設定されていません。\n\n環境変数 GOOGLE_API_KEY を設定してください。"
            }
        }
    
    # APIキーの形式チェック
    if not api_key.startswith("AIza"):
        print(f"[WARNING] API key format may be incorrect. Expected to start with 'AIza', got: {api_key[:4]}...")
    
    print(f"[INFO] API Key loaded: {api_key[:10]}... (length: {len(api_key)})")

    # 天気情報の展開
    temp = weather.get("temp", "不明")
    temp_max = weather.get("temp_max", "不明")
    temp_min = weather.get("temp_min", "不明")
    weather_desc = weather.get("weather", "不明")
    humidity = weather.get("humidity", "不明")
    precipitation = weather.get("precipitation", 0)
    pressure = weather.get("pressure", "不明")
    
    # 🔧 新機能: 時系列データの取得
    hourly_forecast = weather.get("hourly_forecast", [])
    
    # オプション情報の展開
    mode = options.get("mode", "simple")
    scene = options.get("scene") or "特になし"
    gender = options.get("gender", "unspecified")
    outfit_detail = options.get("preference") or "特になし"
    user_question = options.get("wardrobe") or "特になし"

    # 性別の表示文字列
    gender_map = {
        "mens": "メンズ",
        "ladies": "レディース",
        "unspecified": "指定なし(ユニセックス)"
    }
    gender_str = gender_map.get(gender, "指定なし(ユニセックス)")

    # 🔧 新機能: 時系列天候情報を整形
    hourly_info = ""
    if hourly_forecast and len(hourly_forecast) > 0:
        hourly_info = "\n# 今後12時間の天候推移\n"
        for i, hour_data in enumerate(hourly_forecast[:12]):  # 最大12時間分
            time_label = hour_data.get("time", f"{i}時間後")
            temp_h = hour_data.get("temperature", "不明")
            precip_h = hour_data.get("precipitation", 0)
            precip_prob_h = hour_data.get("precipitation_probability", 0)
            weather_h = hour_data.get("weather", "不明")
            
            hourly_info += f"{time_label}: 気温{temp_h}℃, {weather_h}, 降水量{precip_h}mm, 降水確率{precip_prob_h}%\n"
    else:
        hourly_info = "\n# 今後の天候推移\n（データなし）\n"

    # プロンプト構築
    base_info = f"""
# 現在の天気情報
- 天気: {weather_desc}
- 気温: {temp}℃ (最高:{temp_max}℃ / 最低:{temp_min}℃)
- 湿度: {humidity}%
- 降水量: {precipitation}mm
- 気圧: {pressure}hPa

{hourly_info}

# 基本条件
- 利用シーン: {scene}
- スタイル対象: {gender_str}

# 【重要】安全性チェック（最優先で確認）
「利用シーン」が以下に該当する場合は、必ず次の文言のみを返してください：
「その提案・質問にはお答えできません」

**該当するケース：**
- 服装提案に一切関係のない内容（政治討論、株式投資、料理レシピ、医療診断、技術指導など）
- 犯罪やそれに近い行為を示唆するもの（盗撮、ストーカー、不法侵入、詐欺、脅迫など）
- Gemini利用規約に違反する内容（暴力行為、性的搾取、差別的言動、危険な行為の助長など）
- 他人を傷つける・騙す・脅迫する目的の内容

**注意：旅行先、デート、通勤・通学、冠婚葬祭などは利用シーンとして適切です。**

上記に該当しない場合のみ、以下の指示で提案を行ってください。
"""

    if mode == "detailed":
        instruction = f"""
# ユーザーの要望
- **服装の詳細**: {outfit_detail}
- **質問・要望**: {user_question}

# 指示（詳細モード）

## 1. 質問・要望の安全性チェック
「質問・要望」の内容が以下に該当する場合は、必ず次の文言のみを返してください：
「その提案・質問にはお答えできません」

**該当するケース：**
- 服装提案に一切関係のない内容（プログラミング、医療診断、法律相談、投資助言など）
- 犯罪やそれに近い行為を示唆するもの（盗撮、ストーカー、不法侵入、詐欺など）
- Gemini利用規約に違反する内容（暴力、性的搾取、差別、危険行為の助長など）
- 他人を傷つける・騙す目的の内容

上記に該当しない場合のみ、以下の手順で提案を行ってください。

## 2. 時系列データの活用
「今後12時間の天候推移」のデータを必ず考慮してください：
- ユーザーが「N時間後」「午後」「夕方」などの時間指定をした場合、該当時刻の天候を確認
- 「散歩」「外出」などの活動時間を推測し、その時間帯の天候を重視
- 天候が変化する場合（例：今は晴れだが3時間後に雨）は必ず言及
- 気温の変化が大きい場合（5℃以上）は重ね着や脱ぎ着のアドバイス

**例：**
- 「2時間後に散歩」→ 2時間後の天候データを確認
- 「今日の午後に外出」→ 現在から6時間後程度の天候を確認
- 「夕方まで外出」→ 現在から12時間の天候推移全体を考慮

## 3. 服装の詳細の解釈
「服装の詳細」に入力された内容を以下のように処理：

**具体的な服装が入力された場合：**
- その服装を着用する前提で提案を行う
- 現在および今後の天候情報と照らし合わせて適切かチェック
- 不適切な場合は明確に「その服装は○時間後の天候には適していません」と伝え、理由を説明し、代替案を提示

**色や形だけの場合：**
- できるだけユーザーの意図を汲み取り、その色・形を取り入れた提案を行う
- 例：「白いニット」→「白系のニットに○○を合わせる」

**持ち物（傘、バッグなど）が含まれる場合：**
- 持ち物も含めたトータルコーディネートを提案
- 今後の天候に応じて持ち物の適切性もアドバイス（例：3時間後に雨予報なのに傘の記載がない場合は推奨）

## 4. 質問・要望への対応
「質問・要望」が具体的な質問や条件である場合：
- その質問に明確に答える
- 時間指定がある場合は、該当時刻の天候データを参照
- 複雑な条件（例：「動きやすく、かつフォーマル」など）も考慮

## 5. 時間帯ごとの調整
今後12時間の気温変化を確認し、必要に応じて：
- 重ね着のアドバイス
- 脱ぎ着しやすい服装の提案
- 持ち運び用の上着やストールの推奨

## 6. 最終確認と安全性チェック
提案を出力する前に、以下を必ず確認してください：

**内容の適切性チェック：**
- 提案内容がGemini利用規約に違反していないか
- 暴力的、性的、差別的、危険な表現が含まれていないか
- 犯罪を助長する内容になっていないか
- 他人を傷つける可能性のある内容ではないか

上記に該当する場合は、代わりに「その提案・質問にはお答えできません」と返してください。

**品質チェック：**
- 現在の天気だけでなく、今後の推移も考慮しているか
- 時間指定がある場合、該当時刻の天候を参照しているか
- 実用的で実行可能な提案になっているか
- 280〜320文字以内に収まっているか

すべて問題なければ、提案を出力してください。
"""
    else:
        instruction = f"""
# 指示（おまかせモード）

## 1. 時系列データの活用
「今後12時間の天候推移」のデータを必ず考慮してください：
- 現在だけでなく、今後の天候変化も提案に含める
- 天候が変化する場合（例：現在晴れ→3時間後雨）は必ず言及
- 気温の変化が大きい場合（5℃以上）は対応策を提案
- 「利用シーン」に時間的要素がある場合（散歩、外出など）は、活動時間帯の天候を重視

**例：**
- 利用シーン「散歩」→ 通常1〜2時間の活動と推測し、その間の天候を確認
- 利用シーン「通学」→ 往復を考慮し、帰宅時の天候もチェック
- 利用シーン「デート」→ 長時間の外出を想定し、天候推移全体を考慮

## 2. 基本的な服装提案
現在および今後の天気情報と利用シーンから、最適な服装の「方向性」を提案してください。

**注意点：**
- 具体的な商品名は避け、「厚手の防寒アウター」「風を通さない素材」など機能性重視の表現を使用
- ユーザーが自分のクローゼットから選びやすいアドバイス
- 気温変化に応じた調整方法も含める（今後の推移データを活用）
- 天候変化がある場合は、必ずその時刻と対応策を明記

## 3. 服装の詳細が入力されている場合
「服装の詳細」に内容がある場合（{outfit_detail}）：
- その服装・アイテムを考慮に入れた提案を行う
- 現在および今後の天候に対して適切かチェック
- 不適切であれば理由を説明し、改善案を提示

## 4. 質問・要望への対応
「質問・要望」に内容がある場合（{user_question}）：
- 服装提案に関連する質問であれば答える
- 時間指定がある場合は、該当時刻の天候データを参照
- 服装と無関係、犯罪助長、利用規約違反の内容は「その提案・質問にはお答えできません」と返す

## 5. 最終確認と安全性チェック
提案を出力する前に、以下を必ず確認してください：

**内容の適切性チェック：**
- 提案内容がGemini利用規約に違反していないか
- 暴力的、性的、差別的、危険な表現が含まれていないか
- 犯罪を助長する内容になっていないか
- 他人を傷つける可能性のある内容ではないか

上記に該当する場合は、代わりに「その提案・質問にはお答えできません」と返してください。

**品質チェック：**
- 現在の天気だけでなく、今後の推移も考慮しているか
- 実用的で実行可能な提案になっているか
- 280〜320文字以内に収まっているか

すべて問題なければ、提案を出力してください。
"""

    format_instruction = """
# 出力形式
以下のJSON形式で出力してください:

{
  "suggestion": "提案文章をここに記述（280〜320文字程度・簡潔に）"
}

# 制約
- 指示の復唱はしない
- JSON以外の余計な文字は出力しない
- マークダウン記号（```json など）は使用しない
- suggestionキーは必須
- **文字数は必ず320文字以内に収めること（重要）**
"""

    prompt = base_info + instruction + format_instruction

    # 🔧 2026年1月対応: 最新の利用可能モデルを使用
    model_name = "gemini-2.5-flash"
    base_url = "https://generativelanguage.googleapis.com"
    endpoint = f"{base_url}/v1beta/models/{model_name}:generateContent"
    
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key
    }
    
    payload = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }],
        "generationConfig": {
            "temperature": 0.7,
            "topP": 0.8,
            "topK": 40,
            "maxOutputTokens": 1536,
            "responseMimeType": "application/json"
        },
        "safetySettings": [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            }
        ]
    }

    try:
        print(f"[INFO] Sending request to Gemini API")
        print(f"[DEBUG] Model: {model_name}")
        print(f"[DEBUG] Hourly forecast data points: {len(hourly_forecast)}")
        
        response = requests.post(
            endpoint,
            headers=headers,
            json=payload,
            timeout=60
        )
        
        print(f"[INFO] Response status: {response.status_code}")
        
        # ステータスコード別エラーハンドリング
        if response.status_code == 400:
            error_detail = response.text[:500]
            print(f"[ERROR] Bad Request (400): {error_detail}")
            return {
                "type": "error",
                "suggestions": {
                    "suggestion": "❌ リクエスト内容に問題があります。\n\n入力内容を確認してください。\n（エラーコード: 400）"
                }
            }
        
        if response.status_code == 403:
            print(f"[ERROR] Forbidden (403)")
            return {
                "type": "error",
                "suggestions": {
                    "suggestion": "🚫 APIキーに権限がありません。\n\nGoogle AI Studioで新しいAPIキーを作成してください。\n（エラーコード: 403）"
                }
            }
        
        if response.status_code == 404:
            error_detail = response.text[:500]
            print(f"[ERROR] Not Found (404): {error_detail}")
            return {
                "type": "error",
                "suggestions": {
                    "suggestion": f"❌ モデル '{model_name}' が見つかりません。\n\n現在のAPIキーで利用可能なモデルを確認してください。\n（エラーコード: 404）"
                }
            }
        
        if response.status_code == 429:
            print(f"[ERROR] Rate Limit Exceeded (429)")
            return {
                "type": "error",
                "suggestions": {
                    "suggestion": "⏱️ レート制限に達しました。\n\n無料枠: 15リクエスト/分, 1500リクエスト/日\n\n1分ほど待ってから再度お試しください。"
                }
            }
        
        if response.status_code == 500:
            print(f"[ERROR] Internal Server Error (500)")
            return {
                "type": "error",
                "suggestions": {
                    "suggestion": "🔧 Googleサーバーでエラーが発生しました。\n\nしばらく待ってから再度お試しください。\n（エラーコード: 500）"
                }
            }
        
        if response.status_code != 200:
            error_text = response.text[:500]
            print(f"[ERROR] Unexpected status code: {response.status_code}")
            print(f"[ERROR] Response: {error_text}")
            return {
                "type": "error",
                "suggestions": {
                    "suggestion": f"❌ 予期しないエラーが発生しました。\n\nステータスコード: {response.status_code}\n\n管理者に連絡してください。"
                }
            }

        try:
            data = response.json()
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse JSON response: {e}")
            print(f"[ERROR] Response text: {response.text[:500]}")
            return {
                "type": "error",
                "suggestions": {
                    "suggestion": "❌ APIからの応答が不正です。\n\nもう一度お試しください。"
                }
            }
        
        print(f"[DEBUG] Response keys: {list(data.keys())}")
        
        if 'candidates' not in data:
            print(f"[ERROR] No 'candidates' in response")
            print(f"[DEBUG] Full response: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}")
            return {
                "type": "error",
                "suggestions": {
                    "suggestion": "❌ AIから有効な応答が得られませんでした。\n\nもう一度お試しください。"
                }
            }
        
        if not data['candidates'] or len(data['candidates']) == 0:
            print(f"[ERROR] Empty candidates array")
            return {
                "type": "error",
                "suggestions": {
                    "suggestion": "❌ AIから回答が得られませんでした。\n\n入力内容を見直してください。"
                }
            }

        candidate = data['candidates'][0]
        finish_reason = candidate.get('finishReason', 'UNKNOWN')
        print(f"[DEBUG] Finish reason: {finish_reason}")
        
        if finish_reason == "SAFETY":
            print(f"[WARNING] Content filtered by safety settings")
            return {
                "type": "error",
                "suggestions": {
                    "suggestion": "⚠️ 安全フィルターにより回答が生成されませんでした。\n\n入力内容を見直してください。"
                }
            }
        
        if 'content' not in candidate:
            print(f"[ERROR] No 'content' in candidate")
            return {
                "type": "error",
                "suggestions": {
                    "suggestion": "❌ AI応答の形式が不正です。"
                }
            }
        
        content_parts = candidate['content'].get('parts', [])
        if not content_parts or 'text' not in content_parts[0]:
            print(f"[ERROR] No text in parts")
            return {
                "type": "error",
                "suggestions": {
                    "suggestion": "❌ AI応答にテキストが含まれていません。"
                }
            }
        
        content = content_parts[0]['text'].strip()
        print(f"[SUCCESS] Got response from Gemini API")
        print(f"[DEBUG] Response length: {len(content)} chars")

        clean_json = content.replace("```json", "").replace("```", "").strip()
        
        if finish_reason == "MAX_TOKENS":
            if not clean_json.endswith("}"):
                if clean_json.count('"') % 2 != 0:
                    clean_json += '"'
                clean_json += "\n}"
            print(f"[WARNING] Attempting to repair truncated JSON")
        
        try:
            suggestions = json.loads(clean_json)
            print(f"[DEBUG] Parsed JSON keys: {list(suggestions.keys())}")
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON Parse Error: {e}")
            print(f"[ERROR] Content: {clean_json[:300]}")
            
            if finish_reason == "MAX_TOKENS":
                import re
                match = re.search(r'"suggestion"\s*:\s*"([^"]*)', clean_json)
                if match:
                    partial_text = match.group(1)
                    print(f"[WARNING] Using partial text from truncated response: {len(partial_text)} chars")
                    return {
                        "type": "success",
                        "suggestions": {
                            "suggestion": partial_text + "...\n\n（応答が途中で切れました。もう一度お試しください）"
                        }
                    }
            
            return {
                "type": "error",
                "suggestions": {
                    "suggestion": "❌ AI応答の解析に失敗しました。\n\nもう一度お試しください。"
                }
            }
        
        if "suggestion" not in suggestions:
            for key in ["text", "advice", "outfit", "recommendation", "response"]:
                if key in suggestions:
                    suggestions = {"suggestion": suggestions[key]}
                    print(f"[WARNING] Used alternative key: {key}")
                    break
            else:
                suggestions = {"suggestion": str(suggestions)}
                print(f"[WARNING] No valid key found, using full content")
        
        suggestion_text = suggestions.get("suggestion", "").strip()
        if not suggestion_text or len(suggestion_text) < 10:
            print(f"[ERROR] Suggestion too short: {len(suggestion_text)} chars")
            return {
                "type": "error",
                "suggestions": {
                    "suggestion": "❌ AIから十分な提案が得られませんでした。\n\nもう一度お試しください。"
                }
            }
        
        print(f"[SUCCESS] JSON parsed successfully")
        print(f"[SUCCESS] Suggestion length: {len(suggestion_text)} chars")
        
        return {
            "type": "success",
            "suggestions": suggestions
        }

    except requests.exceptions.Timeout:
        print("[ERROR] Request timeout (60s)")
        return {
            "type": "error",
            "suggestions": {
                "suggestion": "⏱️ 処理がタイムアウトしました。\n\nネットワーク接続を確認して、もう一度お試しください。"
            }
        }
    
    except requests.exceptions.ConnectionError as e:
        print(f"[ERROR] Connection error: {e}")
        return {
            "type": "error",
            "suggestions": {
                "suggestion": "🌐 ネットワーク接続エラーが発生しました。\n\nインターネット接続を確認してください。"
            }
        }
    
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Request Exception: {e}")
        traceback.print_exc()
        return {
            "type": "error",
            "suggestions": {
                "suggestion": "❌ 通信エラーが発生しました。\n\nしばらく待ってから再度お試しください。"
            }
        }
    
    except Exception as e:
        print(f"[ERROR] Unexpected Error: {type(e).__name__}: {e}")
        traceback.print_exc()
        return {
            "type": "error",
            "suggestions": {
                "suggestion": f"❌ システムエラーが発生しました。\n\nエラー: {str(e)[:100]}"
            }
        }
