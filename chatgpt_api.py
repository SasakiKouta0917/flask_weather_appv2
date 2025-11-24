import os
import openai
import json

openai.api_key = os.environ.get("OPENAI_API_KEY")

def suggest_outfit(weather):
    temp = weather.get("temp")
    weather_desc = weather.get("weather")
    humidity = weather.get("humidity")
    precipitation = weather.get("precipitation")

    prompt = f"""
あなたは親切で実用的なスタイリストです。
以下の天気情報をもとに、朝晩と昼間の服装を日本語で簡潔に提案してください。

- 天気: {weather_desc}
- 気温: {temp}℃
- 湿度: {humidity}%
- 降水量: {precipitation}mm

フォーマットは以下のようにしてください：
[
  {{ "period": "朝晩", "any": "提案内容" }},
  {{ "period": "昼間", "any": "提案内容" }}
]
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "あなたは天気に応じた服装を提案するアシスタントです。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )

        content = response.choices[0].message.content.strip()
        suggestions = json.loads(content)

        return {
            "type": "any",
            "suggestions": suggestions
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "type": "any",
            "suggestions": [
                {"period": "朝晩", "any": "長袖シャツと軽い羽織"},
                {"period": "昼間", "any": "半袖＋日よけ対策"}
            ]
        }
