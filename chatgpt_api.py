import os
import openai

OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "DUMMY_KEY")

def suggest_outfit(weather):
    if OPENAI_KEY == "DUMMY_KEY":
        return {
            "type": "any",
            "suggestions": [
                {"period": "朝晩", "any": "薄手のジャケットと長袖シャツ。気温差に対応できるようレイヤーがおすすめです。"},
                {"period": "昼間", "any": "半袖Tシャツ＋軽い羽織。湿度が高い日は通気性の良い素材を。"}
            ]
        }

    openai.api_key = OPENAI_KEY

    prompt = f"""次の天気データをもとに、朝晩と昼間の寒暖差に対応した服装を提案してください。できれば男女共用で書いてください。
天気: {weather.get('weather')}
気温: {weather.get('temp')}℃
最高気温: {weather.get('temp_max')}℃
最低気温: {weather.get('temp_min')}℃
湿度: {weather.get('humidity')}%
降水量: {weather.get('precipitation')}mm
"""

    try:
        res = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content":prompt}],
            temperature=0.7
        )
        content = res["choices"][0]["message"]["content"].strip()
        return {"type":"any", "suggestions":[{"period":"提案", "any": content}]}
    except Exception:
        return {
            "type": "any",
            "suggestions": [
                {"period":"全体", "any": "APIエラーのため簡易的な提案：上着を用意しておくのがおすすめです。"}
            ]
        }
