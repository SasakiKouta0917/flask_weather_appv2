import os
import json
import traceback
import google.generativeai as genai

# --- API初期化設定 ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    print("[ERROR] GOOGLE_API_KEY is not set in environment variables!")
else:
    # transport='rest' を指定することで、v1betaエラー(404)を回避し安定させます
    genai.configure(api_key=GOOGLE_API_KEY, transport='rest')

def suggest_outfit(weather, options):
    """
    天候情報とユーザーの要望からGeminiに服装提案をさせる関数
    """
    # 1. パラメータの展開
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

    # 2. プロンプト構築
    prompt = f"""
あなたはプロのファッションスタイリストです。以下の条件に合わせて1つのまとまった服装提案を作成してください。

# 天気条件
- 天気: {weather_desc}
- 気温: {temp}℃ (最高:{temp_max}℃ / 最低:{temp_min}℃)
- 湿度: {humidity}%, 降水: {precipitation}mm

# ユーザー条件
- 性別タイプ: {gender_str}
- 利用シーン: {scene}
- 好み/気分: {preference}
- 手持ちの服: {wardrobe}

# 指示
- 天候に適した快適さと、シーンに合うおしゃれさを両立させてください。
- 時間帯による気温変化への対応（羽織りもの等）も含めてください。
- 文章は400文字程度で、親しみやすく丁寧な口調にしてください。
"""

    # 3. Gemini API 呼び出し
    # モデル名は 'models/gemini-1.5-flash' とフルパスで指定
    model_name = 'models/gemini-1.5-flash'
    
    try:
        print(f"[INFO] Using model: {model_name}")
        model = genai.GenerativeModel(model_name)

        # JSONモードを強制し、解析エラーを防ぐ
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.7,
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "suggestion": {"type": "STRING"}
                    }
                }
            ),
            # 安全フィルターによるブロック（空の応答）を防止
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
        )

        # 応答の解析
        if not response.text:
            raise ValueError("Empty response from API")
            
        result = json.loads(response.text)
        print(f"[SUCCESS] Style suggestion generated via {model_name}")

        return {
            "type": "success",
            "suggestions": result
        }

    except Exception as e:
        print(f"[ERROR] Gemini API Error: {str(e)}")
        traceback.print_exc()
        
        return {
            "type": "error",
            "suggestions": {
                "suggestion": "AIとの通信中にエラーが発生しました。気温に合わせた服装でお出かけください。"
            }
        }
