from flask import Flask, render_template, request, jsonify
from chatgpt_api import suggest_outfit
from datetime import datetime, timedelta
from collections import deque
import time

app = Flask(__name__)

# ==========================================
# レート制限システム
# ==========================================
class RateLimiter:
    def __init__(self):
        # IPアドレスごとの最終リクエスト時刻を記録
        self.last_request = {}
        # IPアドレスごとの待機時間（秒）を記録
        self.wait_time = {}
        # IPアドレスごとのリクエスト履歴（過去1時間）
        self.request_history = {}
        
        # 設定
        self.initial_wait = 300  # 初回成功後: 5分 (300秒)
        self.max_requests_per_hour = 50  # 1時間あたり最大50リクエスト
        self.history_duration = 3600  # 履歴保持期間: 1時間 (3600秒)
    
    def get_client_ip(self):
        """クライアントのIPアドレスを取得"""
        # プロキシ経由の場合も考慮
        if request.headers.get('X-Forwarded-For'):
            return request.headers.get('X-Forwarded-For').split(',')[0].strip()
        return request.remote_addr
    
    def clean_old_history(self, ip):
        """1時間以上前のリクエスト履歴を削除"""
        if ip not in self.request_history:
            self.request_history[ip] = deque()
        
        now = time.time()
        # 古い履歴を削除
        while self.request_history[ip] and now - self.request_history[ip][0] > self.history_duration:
            self.request_history[ip].popleft()
    
    def check_hourly_limit(self, ip):
        """過去1時間のリクエスト数をチェック"""
        self.clean_old_history(ip)
        
        if ip not in self.request_history:
            return True, 0
        
        count = len(self.request_history[ip])
        if count >= self.max_requests_per_hour:
            return False, count
        
        return True, count
    
    def check_rate_limit(self, ip):
        """
        レート制限をチェック
        
        Returns:
            tuple: (許可するか, 残り待機時間, エラーメッセージ)
        """
        now = time.time()
        
        # 1時間あたりのリクエスト数チェック
        allowed, count = self.check_hourly_limit(ip)
        if not allowed:
            return False, 0, f"リクエスト上限に達しました。過去1時間に{count}件のリクエストが送信されています。1時間後に再試行してください。"
        
        # 待機時間チェック
        if ip in self.last_request:
            elapsed = now - self.last_request[ip]
            required_wait = self.wait_time.get(ip, self.initial_wait)
            
            if elapsed < required_wait:
                remaining = int(required_wait - elapsed)
                minutes = remaining // 60
                seconds = remaining % 60
                
                if minutes > 0:
                    time_str = f"{minutes}分{seconds}秒"
                else:
                    time_str = f"{seconds}秒"
                
                return False, remaining, f"前回のリクエストから{time_str}経過する必要があります。しばらくお待ちください。"
        
        return True, 0, ""
    
    def record_request(self, ip, success=True):
        """リクエストを記録"""
        now = time.time()
        
        # リクエスト履歴に追加
        if ip not in self.request_history:
            self.request_history[ip] = deque()
        self.request_history[ip].append(now)
        
        # 成功したリクエストのみ待機時間を記録
        if success:
            self.last_request[ip] = now
            
            # 待機時間を倍増（初回: 5分 → 10分 → 20分 → ...）
            if ip in self.wait_time:
                self.wait_time[ip] = min(self.wait_time[ip] * 2, 3600)  # 最大1時間
            else:
                self.wait_time[ip] = self.initial_wait
            
            print(f"[RATE LIMIT] IP: {ip} - Next wait time: {self.wait_time[ip]}秒")
    
    def get_stats(self, ip):
        """統計情報を取得（デバッグ用）"""
        self.clean_old_history(ip)
        
        count = len(self.request_history.get(ip, []))
        next_wait = self.wait_time.get(ip, self.initial_wait)
        
        return {
            "requests_in_last_hour": count,
            "next_wait_time_seconds": next_wait,
            "max_requests_per_hour": self.max_requests_per_hour
        }

# レート制限インスタンス
rate_limiter = RateLimiter()

# ==========================================
# Routes
# ==========================================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/suggest_outfit', methods=['POST'])
def suggest_outfit_api():
    # クライアントIPを取得
    client_ip = rate_limiter.get_client_ip()
    
    # レート制限チェック
    allowed, remaining_time, error_msg = rate_limiter.check_rate_limit(client_ip)
    
    if not allowed:
        print(f"[RATE LIMIT BLOCKED] IP: {client_ip} - {error_msg}")
        return jsonify({
            "error": "rate_limit_exceeded",
            "message": error_msg,
            "remaining_time": remaining_time
        }), 429  # 429 Too Many Requests
    
    # リクエストデータを取得
    data = request.json
    weather = data.get('weather_data')
    
    # 提案オプション情報の取得
    options = {
        "mode": data.get('mode', 'simple'),
        "scene": data.get('scene', ''),
        "gender": data.get('gender', 'unspecified'),
        "preference": data.get('preference', ''),
        "wardrobe": data.get('wardrobe', '')
    }
    
    if not weather:
        return jsonify({"error": "No weather data provided"}), 400
    
    # AI処理を実行
    result = suggest_outfit(weather, options)
    
    # 結果に応じてレート制限を記録
    if result.get("type") == "success":
        rate_limiter.record_request(client_ip, success=True)
        print(f"[AI SUCCESS] IP: {client_ip}")
    else:
        rate_limiter.record_request(client_ip, success=False)
        print(f"[AI ERROR] IP: {client_ip} - Error occurred, wait time not increased")
    
    # 結果に応じたステータスコードの設定
    status_code = 500 if result.get("type") == "error" else 200
    return jsonify(result), status_code

@app.route('/api/rate_limit_stats', methods=['GET'])
def rate_limit_stats():
    """レート制限の統計情報を取得（デバッグ用）"""
    client_ip = rate_limiter.get_client_ip()
    stats = rate_limiter.get_stats(client_ip)
    return jsonify(stats)

if __name__ == '__main__':
    app.run(debug=True)
