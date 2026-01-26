from flask import Flask, render_template, request, jsonify
from chatgpt_api import suggest_outfit
from datetime import datetime, timedelta
from collections import deque
import time
import threading

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
# AI リクエストキューシステム
# ==========================================
class AIRequestQueue:
    def __init__(self):
        self.max_concurrent = 10  # 同時処理数
        self.max_queue = 20       # 待機キュー
        self.active_count = 0     # 現在処理中の数
        self.queue_count = 0      # 現在待機中の数
        self.lock = threading.Lock()
        
        print("[AI QUEUE] ==========================================")
        print(f"[AI QUEUE] Initialized: Max concurrent={self.max_concurrent}, Max queue={self.max_queue}")
        print("[AI QUEUE] ==========================================")
    
    def get_status(self):
        """現在の処理状況を取得"""
        with self.lock:
            return {
                "active": self.active_count,
                "queue": self.queue_count,
                "total": self.active_count + self.queue_count
            }
    
    def can_accept(self):
        """リクエストを受け入れ可能か判定"""
        with self.lock:
            total = self.active_count + self.queue_count
            if total >= (self.max_concurrent + self.max_queue):
                return False, f"混雑しています（処理中{self.active_count}人、待機中{self.queue_count}人）。しばらく待ってから再試行してください。"
            return True, ""
    
    def acquire(self):
        """処理スロットを取得（待機が必要な場合はキューに入れる）"""
        with self.lock:
            if self.active_count < self.max_concurrent:
                # 即座に処理開始
                self.active_count += 1
                print(f"[AI QUEUE] ✅ Slot acquired (active: {self.active_count}/{self.max_concurrent})")
                return True, 0  # 待機なし
            else:
                # キューに入る
                self.queue_count += 1
                position = self.queue_count
                print(f"[AI QUEUE] ⏳ Queued (position: {position}, queue: {self.queue_count}/{self.max_queue})")
                return False, position  # 待機あり
    
    def wait_for_slot(self):
        """キューから処理スロットが空くまで待機"""
        while True:
            with self.lock:
                if self.active_count < self.max_concurrent:
                    self.active_count += 1
                    self.queue_count -= 1
                    print(f"[AI QUEUE] ✅ Slot acquired from queue (active: {self.active_count}/{self.max_concurrent}, queue: {self.queue_count})")
                    return True
            time.sleep(1)  # 1秒ごとにチェック
    
    def release(self):
        """処理スロットを解放"""
        with self.lock:
            self.active_count = max(0, self.active_count - 1)
            print(f"[AI QUEUE] 🔓 Slot released (active: {self.active_count}/{self.max_concurrent})")

ai_queue = AIRequestQueue()

# ==========================================
# レート制限システム（デバイスID対応）
# ==========================================
class RateLimiter:
    def __init__(self):
        self.last_request = {}
        self.wait_time = {}
        self.request_history = {}
        self.initial_wait = 300
        self.max_requests_per_hour = 50
        self.history_duration = 3600
    
    def clean_old_history(self, device_id):
        if device_id not in self.request_history:
            self.request_history[device_id] = deque()
        
        now = time.time()
        while self.request_history[device_id] and now - self.request_history[device_id][0] > self.history_duration:
            self.request_history[device_id].popleft()
    
    def check_hourly_limit(self, device_id):
        self.clean_old_history(device_id)
        
        if device_id not in self.request_history:
            return True, 0
        
        count = len(self.request_history[device_id])
        if count >= self.max_requests_per_hour:
            return False, count
        
        return True, count
    
    def check_rate_limit(self, device_id):
        now = time.time()
        
        allowed, count = self.check_hourly_limit(device_id)
        if not allowed:
            return False, 0, f"リクエスト上限に達しました。過去1時間に{count}件のリクエストが送信されています。1時間後に再試行してください。"
        
        if device_id in self.last_request:
            elapsed = now - self.last_request[device_id]
            required_wait = self.wait_time.get(device_id, self.initial_wait)
            
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
    
    def record_request(self, device_id, success=True):
        """成功時のみレート制限を記録"""
        if not success:
            print(f"[RATE LIMIT] ❌ Request failed - NOT recording rate limit for device: {device_id[:16]}...")
            return
        
        now = time.time()
        
        if device_id not in self.request_history:
            self.request_history[device_id] = deque()
        self.request_history[device_id].append(now)
        
        self.last_request[device_id] = now
        
        if device_id in self.wait_time:
            self.wait_time[device_id] = min(self.wait_time[device_id] * 2, 3600)
        else:
            self.wait_time[device_id] = self.initial_wait
        
        print(f"[RATE LIMIT] ✅ Success recorded for device: {device_id[:16]}... - Next wait time: {self.wait_time[device_id]}秒")
    
    def get_stats(self, device_id):
        self.clean_old_history(device_id)
        
        count = len(self.request_history.get(device_id, []))
        next_wait = self.wait_time.get(device_id, self.initial_wait)
        
        return {
            "requests_in_last_hour": count,
            "next_wait_time_seconds": next_wait,
            "max_requests_per_hour": self.max_requests_per_hour
        }

rate_limiter = RateLimiter()

# ==========================================
# Routes
# ==========================================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/ai_queue_status', methods=['GET'])
def ai_queue_status():
    """AIキューの状態を取得（10秒ごとにポーリング用）"""
    status = ai_queue.get_status()
    return jsonify(status)

@app.route('/api/suggest_outfit', methods=['POST'])
def suggest_outfit_api():
    # 🔧 修正: JSONを一度だけ読み込む
    data = request.get_json()
    
    # デバイスIDを取得（フロントエンドから送信）
    device_id = data.get('device_id')
    if not device_id:
        print("[AI] ⚠️ No device_id provided, rejecting request")
        return jsonify({
            "error": "invalid_request",
            "message": "デバイスIDが送信されていません。ページを再読み込みしてください。"
        }), 400
    
    print(f"[AI] 📱 Request from device: {device_id[:16]}...")
    
    # キュー受付チェック
    can_accept, error_msg = ai_queue.can_accept()
    if not can_accept:
        print(f"[AI QUEUE] ❌ Queue full - Rejected device: {device_id[:16]}...")
        return jsonify({
            "error": "queue_full",
            "message": error_msg,
            "status": ai_queue.get_status()
        }), 503  # Service Unavailable
    
    # レート制限チェック
    allowed, remaining_time, error_msg = rate_limiter.check_rate_limit(device_id)
    
    if not allowed:
        print(f"[RATE LIMIT BLOCKED] Device: {device_id[:16]}... - {error_msg}")
        return jsonify({
            "error": "rate_limit_exceeded",
            "message": error_msg,
            "remaining_time": remaining_time
        }), 429
    
    # スロット取得（即座 or キュー待ち）
    immediate, position = ai_queue.acquire()
    
    if not immediate:
        # キュー待ち
        print(f"[AI QUEUE] ⏳ Waiting in queue (position: {position}) - Device: {device_id[:16]}...")
        ai_queue.wait_for_slot()
    
    try:
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
        
        print(f"[AI REQUEST] 🚀 Processing - Device: {device_id[:16]}...")
        result = suggest_outfit(weather, options)
        
        # 成功時のみレート制限を記録
        if result.get("type") == "success":
            rate_limiter.record_request(device_id, success=True)
            print(f"[AI SUCCESS] ✅ Device: {device_id[:16]}...")
            status_code = 200
        else:
            # エラー時はレート制限を記録しない
            print(f"[AI ERROR] ❌ Device: {device_id[:16]}... - Error occurred, NOT recording rate limit")
            status_code = 500
        
        return jsonify(result), status_code
        
    except Exception as e:
        print(f"[AI EXCEPTION] ❌ Device: {device_id[:16]}... - Exception: {e}")
        # 例外時もレート制限を記録しない
        return jsonify({
            "type": "error",
            "suggestions": {
                "suggestion": f"❌ システムエラーが発生しました。\n\nエラー: {str(e)[:100]}"
            }
        }), 500
        
    finally:
        # 必ずスロットを解放
        ai_queue.release()

@app.route('/api/rate_limit_stats', methods=['POST'])  # 🔧 修正: GET → POST
def rate_limit_stats():
    """レート制限統計を取得（デバイスID必須）"""
    data = request.get_json()
    device_id = data.get('device_id')
    
    if not device_id:
        return jsonify({
            "error": "invalid_request",
            "message": "デバイスIDが必要です"
        }), 400
    
    stats = rate_limiter.get_stats(device_id)
    return jsonify(stats)

# ==========================================
# 掲示板API
# ==========================================
@app.route('/api/board/register_name', methods=['POST'])
def api_board_register_name():
    return board_register_name()

@app.route('/api/board/get_username', methods=['POST'])  # 🔧 修正: GET → POST
def api_board_get_username():
    return board_get_username()

@app.route('/api/board/create_post', methods=['POST'])
def api_board_create_post():
    return board_create_post()

@app.route('/api/board/get_posts', methods=['POST'])  # 🔧 修正: GET → POST
def api_board_get_posts():
    return board_get_posts()

@app.route('/api/board/report_post', methods=['POST'])
def api_board_report_post():
    return board_report_post()

if __name__ == '__main__':
    app.run(debug=True)
