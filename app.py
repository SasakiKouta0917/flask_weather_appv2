from flask import Flask, render_template, request, jsonify
# chatgpt_api.py から関数をインポート
from chatgpt_api import suggest_outfit

app = Flask(__name__)

# NOTE: openai.api_keyの設定は chatgpt_api.py 側で行われるため、
# ここには openai 関連のコードは一切記述しません。

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/suggest_outfit', methods=['POST'])
def suggest_outfit_api():
    # フロントエンドから天気情報とシーンを受け取る
    data = request.json
    weather = data.get('weather_data')
    scene = data.get('scene', '通学')

    if not weather:
        return jsonify({"error": "No weather data provided"}), 400

    # 別ファイルに切り出したAIロジックを呼び出す
    result = suggest_outfit(weather, scene)

    # 結果に応じたステータスコードの設定
    status_code = 500 if result.get("type") == "error" else 200

    return jsonify(result), status_code

if __name__ == '__main__':
    app.run(debug=True)
