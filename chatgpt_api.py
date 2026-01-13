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
    
    # オプション情報の展開
    mode = options.get("mode", "simple")
    scene = options.get("scene") or "特になし"
    gender = options.get("gender", "unspecified")
    preference = options.get("preference") or "特になし"
    wardrobe = options.get("wardrobe") or "特になし"

    # 性別の表示文字列
    gender_map = {
        "mens": "メンズ",
        "ladies": "レディース",
        "unspecified": "指定なし(ユニセックス)"
    }
    gender_str = gender_map.get(gender, "指定なし(ユニセックス)")

    # プロンプト構築
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
# ユーザーの要望
- 着たい服・気分: {preference}
- 手持ちの服リスト: {wardrobe}

# 指示
1. ユーザーの「着たい服」を取り入れたコーディネートを提案
2. 「手持ちの服リスト」のアイテムを優先的に使用
3. 天気を考慮した快適な工夫を具体的にアドバイス
4. 時間帯（朝・昼・夜）ごとの調整方法も含める
"""
    else:
        instruction = """
# 指示
1. 天気と利用シーンから最適な服装の「方向性」を提案
2. 具体的な商品名は避け、「厚手の防寒アウター」「風を通さない素材」など機能性重視の表現を使用
3. ユーザーが自分のクローゼットから選びやすいアドバイス
4. 気温変化に応じた調整方法も含める
"""

    format_instruction = """
# 出力形式
以下のJSON形式で出力してください:

{
  "suggestion": "提案文章をここに記述（350〜450文字程度）"
}

# 制約
- 指示の復唱はしない
- JSON以外の余計な文字は出力しない
- マークダウン記号（```json など）は使用しない
- suggestionキーは必須
"""

    prompt = base_info + instruction + format_instruction

    # 🔧 2026年1月対応: 最新の利用可能モデルを使用
    # 公式ドキュメント: https://ai.google.dev/gemini-api/docs/models
    model_name = "gemini-2.5-flash"  # 最新の高速モデル
    base_url = "https://generativelanguage.googleapis.com"
    endpoint = f"{base_url}/v1beta/models/{model_name}:generateContent"
    
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key  # ヘッダーでも送信（推奨される方法）
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
            "maxOutputTokens": 1024,
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
        print(f"[DEBUG] Endpoint: {endpoint}")
        print(f"[DEBUG] Payload size: {len(json.dumps(payload))} bytes")
        
        # リクエスト送信（タイムアウト60秒）
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

        # レスポンスのパース
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
        
        # レスポンス構造のチェック
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
        print(f"[DEBUG] Candidate keys: {list(candidate.keys())}")

        # 完了理由のチェック
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
        
        if finish_reason == "MAX_TOKENS":
            print(f"[WARNING] Response truncated due to max tokens")
        
        # コンテンツの取得
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
        print(f"[DEBUG] Response preview: {content[:150]}...")

        # JSONクリーニング
        clean_json = content.replace("```json", "").replace("```", "").strip()
        
        # JSONパース
        try:
            suggestions = json.loads(clean_json)
            print(f"[DEBUG] Parsed JSON keys: {list(suggestions.keys())}")
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON Parse Error: {e}")
            print(f"[ERROR] Content: {clean_json[:300]}")
            return {
                "type": "error",
                "suggestions": {
                    "suggestion": "❌ AI応答の解析に失敗しました。\n\nもう一度お試しください。"
                }
            }
        
        # キーの正規化
        if "suggestion" not in suggestions:
            for key in ["text", "advice", "outfit", "recommendation", "response"]:
                if key in suggestions:
                    suggestions = {"suggestion": suggestions[key]}
                    print(f"[WARNING] Used alternative key: {key}")
                    break
            else:
                suggestions = {"suggestion": str(suggestions)}
                print(f"[WARNING] No valid key found, using full content")
        
        # 空チェック
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
        
        # 成功を返す
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
