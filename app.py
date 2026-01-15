from flask import Flask, render_template, request, jsonify
from chatgpt_api import suggest_outfit
from datetime import datetime, timedelta
from collections import deque
import time

# 掲示板モジュールをインポート
from board_api import (
    board_register_name,
    board_get_username,
    board_create_post,
    board_get_posts,
    board_report_post
)

app = Flask(__name__)

# ==========================================
# レート制限システム（既存）
# ==========================================
class RateLimiter:
    def __init__(self):
        self.last_request = {}
        self.wait_time = {}
        self.request_history = {}
        self.initial_wait = 300
        self.max_requests_per_hour = 50
        self.history_duration = 3600
    
    def get_client_ip(self):
        if request.headers.get('X-Forwarded-For'):
            return request.headers.get('X-Forwarded-For').split(',')[0].strip()
        return request.remote_addr
    
    def clean_old_history(self, ip):
        if ip not in self.request_history:
            self.request_history[ip] = deque()
        
        now = time.time()
        while self.request_history[ip] and now - self.request_history[ip][0] > self.history_duration:
            self.request_history[ip].popleft()
    
    def check_hourly_limit(self, ip):
        self.clean_old_history(ip)
        
        if ip not in self.request_history:
            return True, 0
        
        count = len(self.request_history[ip])
        if count >= self.max_requests_per_hour:
            return False, count
        
        return True, count
    
    def check_rate_limit(self, ip):
        now = time.time()
        
        allowed, count = self.check_hourly_limit(ip)
        if not allowed:
            return False, 0, f"リクエスト上限に達しました。過去1時間に{count}件のリクエストが送信されています。1時間後に再試行してください。"
        
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
        now = time.time()
        
        if ip not in self.request_history:
            self.request_history[ip] = deque()
        self.request_history[ip].append(now)
        
        if success:
            self.last_request[ip] = now
            
            if ip in self.wait_time:
                self.wait_time[ip] = min(self.wait_time[ip] * 2, 3600)
            else:
                self.wait_time[ip] = self.initial_wait
            
            print(f"[RATE LIMIT] IP: {ip} - Next wait time: {self.wait_time[ip]}秒")
    
    def get_stats(self, ip):
        self.clean_old_history(ip)
        
        count = len(self.request_history.get(ip, []))
        next_wait = self.wait_time.get(ip, self.initial_wait)
        
        return {
            "requests_in_last_hour": count,
            "next_wait_time_seconds": next_wait,
            "max_requests_per_hour": self.max_requests_per_hour
        }

rate_limiter = RateLimiter()

# ==========================================
# Routes（既存）
# ==========================================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/suggest_outfit', methods=['POST'])
def suggest_outfit_api():
    client_ip = rate_limiter.get_client_ip()
    
    allowed, remaining_time, error_msg = rate_limiter.check_rate_limit(client_ip)
    
    if not allowed:
        print(f"[RATE LIMIT BLOCKED] IP: {client_ip} - {error_msg}")
        return jsonify({
            "error": "rate_limit_exceeded",
            "message": error_msg,
            "remaining_time": remaining_time
        }), 429
    
    data = request.json
    weather = data.get('weather_data')
    
    options = {
        "mode": data.get('mode', 'simple'),
        "scene": data.get('scene', ''),
        "gender": data.get('gender', 'unspecified'),
        "preference": data.get('preference', ''),
        "wardrobe": data.get('wardrobe', '')
    }
    
    if not weather:
        return jsonify({"error": "No weather data provided"}), 400
    
    result = suggest_outfit(weather, options)
    
    if result.get("type") == "success":
        rate_limiter.record_request(client_ip, success=True)
        print(f"[AI SUCCESS] IP: {client_ip}")
    else:
        rate_limiter.record_request(client_ip, success=False)
        print(f"[AI ERROR] IP: {client_ip} - Error occurred, wait time not increased")
    
    status_code = 500 if result.get("type") == "error" else 200
    return jsonify(result), status_code

@app.route('/api/rate_limit_stats', methods=['GET'])
def rate_limit_stats():
    client_ip = rate_limiter.get_client_ip()
    stats = rate_limiter.get_stats(client_ip)
    return jsonify(stats)

# ==========================================
# 掲示板API（新規追加）
# ==========================================
@app.route('/api/board/register_name', methods=['POST'])
def api_board_register_name():
    return board_register_name()

@app.route('/api/board/get_username', methods=['GET'])
def api_board_get_username():
    return board_get_username()

@app.route('/api/board/create_post', methods=['POST'])
def api_board_create_post():
    return board_create_post()

@app.route('/api/board/get_posts', methods=['GET'])
def api_board_get_posts():
    return board_get_posts()

@app.route('/api/board/report_post', methods=['POST'])
def api_board_report_post():
    return board_report_post()

if __name__ == '__main__':
    app.run(debug=True)
