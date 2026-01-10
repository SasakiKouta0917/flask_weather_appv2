import os
import google.generativeai as genai
import json
import traceback

# APIキーの設定（環境変数から読み込み）
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

# APIキー確認
if not GOOGLE_API_KEY:
    print("[ERROR] GOOGLE_API_KEY is not set!")
else:
    genai.configure(api_key=GOOGLE_API_KEY)

def suggest_outfit(weather, options):
    # --- 1. 情報の展開 ---
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

    gender_str = "メンズ" if gender == "mens" else "レディース" if gender == "ladies" else "ユニセックス"

    # --- 2. プロンプト作成 ---
    # JSONモードを使うため、プロンプトでの「JSON形式で...」という細かい指示は削除してシンプルにします
    
    base_instruction = f"""
    あなたはプロのスタイリストです。以下の天気と条件に合わせて最適な服装を提案してください。

    # 天気情報
    - 天気: {weather_desc}, 気温: {temp}℃ (最高:{temp_max} / 最低:{temp_min})
    - 湿度: {humidity}%, 降水: {precipitation}mm

    # 条件
    - 対象: {gender_str}
    - シーン: {scene}
    """

    if mode == "detailed":
        detail_instruction = f"""
        # 要望
        - 気分: {preference}
        - 手持ち服: {wardrobe}
        
        # 指示
        手持ちの服を優先的に使い、気温や天気を考慮した具体的なコーディネートを提案してください。
        """
    else:
        detail_instruction = f"""
        # 指示
        具体的な商品名は避け、「厚手のアウター」「通気性の良いシャツ」のように機能性や素材感を重視した抽象的な表現で提案してください。
        """

    final_prompt = base_instruction + detail_instruction + "\n\nこの内容で、以下のJSONスキーマに従って出力してください。"

    # --- 3. Gemini API 呼び出し ---
    # 確実に動くモデルを1つだけ指定
    model_name = 'gemini-1.5-flash'

    try:
        print(f"[INFO] Using model: {model_name}")
        model = genai.GenerativeModel(model_name)

        response = model.generate_content(
            final_prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.7,
                max_output_tokens=1000,
                # ★重要: これで確実にJSONが返ってきます
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "suggestion": {"type": "STRING"}
                    }
                }
            ),
            # ★重要: 服装（肌の露出など）に関する誤判定を防ぐ
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
        )

        # JSONモードなのでそのままパース可能
        result = json.loads(response.text)
        
        return {
            "type": "success",
            "suggestions": result
        }

    except Exception as e:
        print(f"[ERROR] Gemini API Error: {e}")
        traceback.print_exc()
        
        return {
            "type": "error",
            "suggestions": {
                "suggestion": "申し訳ありません。AIの通信中にエラーが発生しました。天気予報を確認してお出かけください。"
            }
        }
