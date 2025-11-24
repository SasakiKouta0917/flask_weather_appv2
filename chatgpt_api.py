import os
import openai
import json

openai.api_key = os.environ.get("OPENAI_API_KEY")

def suggest_outfit(weather):
    temp = weather.get("temp")
    temp_max = weather.get("temp_max")
    temp_min = weather.get("temp_min")
    weather_desc = weather.get("weather")
    humidity = weather.get("humidity")
    precipitation = weather.get("precipitation")
    scene = "通学"

    prompt = f"""
以下の天気情報と利用シーンをもとに、その日に適した服装を日本語で提案してください。

# 天気情報
- 現在の天気: {weather_desc}
- 現在の気温: {temp}℃
- 最高気温: {temp_max}℃
- 最低気温: {temp_min}℃
- 湿度: {humidity}%
- 降水量: {precipitation}mm

# 利用シーン
- {scene}

# 条件
1. 上記の天気情報と利用シーンを考慮して、その日に適した服装を提案してください。
- 気温が低い場合は、防寒対策を提案してください。
- 気温が高い場合は、涼しい服装を提案してください。
- 雨が予想される場合は、雨具や防水対策を提案してください。

2. 提案する服装は以下のカテゴリに分けてください：
- 上着
- インナー
- ボトム
- アクセサリー（例: 帽子、マフラー、日傘など）
- 靴

3. 出力形式は以下の通り、**JSON形式**で出力してください：

[
  {{ "period": "朝晩", "any": "ここに提案内容を記載" }},
  {{ "period": "昼間", "any": "ここに提案内容を記載" }}
]

# 補足
- 指示の復唱はしないでください。
- 自己評価はしないでください。
- 結論やまとめは書かないでください。
- 最終成果物以外は出力しないでください。
- 出力結果をダブルクォーテーション("")で囲わないでください。
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

    except Exception:
        return {
            "type": "any",
            "suggestions": [
                {"period": "朝晩", "any": "取得できませんでした。"},
                {"period": "昼間", "any": "取得できませんでした。"}
            ]
        }
