import os
import google.generativeai as genai
import json

# APIキーの設定（環境変数から読み込み）
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    print("[ERROR] GOOGLE_API_KEY is not set!")
else:
    print(f"[INFO] API Key loaded (length: {len(GOOGLE_API_KEY)})")

genai.configure(api_key=GOOGLE_API_KEY)

def suggest_outfit(weather, options):
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

    try:
        print("[INFO] Using Gemini 1.5 Flash")
        
        # モデル名: gemini-1.5-flash（シンプル形式）
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.7,
                max_output_tokens=1000,
            )
        )

        content = response.text.strip()
        print(f"[SUCCESS] Gemini API returned response")
        
        # マークダウンのコードブロックを削除
        clean_json = content.replace("```json", "").replace("```", "").strip()
        
        # JSONをパース
        suggestions = json.loads(clean_json)

        return {
            "type": "success",
            "suggestions": suggestions
        }

    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON Parse Error: {e}")
        print(f"Response: {content if 'content' in locals() else 'No content'}")
        return {
            "type": "error",
            "suggestions": {
                "suggestion": "AI応答の解析に失敗しました。\n\n天気予報を確認し、気温の変化に対応しやすい服装でお出かけください。"
            }
        }
    except Exception as e:
        print(f"[ERROR] Gemini API Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "type": "error",
            "suggestions": {
                "suggestion": f"通信エラーが発生しました。天気予報を確認し、気温の変化に対応しやすい服装でお出かけください。\n\n({str(e)[:100]})"
            }
        }
