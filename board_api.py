"""
掲示板API - データ永続化対応版（JSON形式）
サーバー再起動後もデータを保持
"""

from flask import jsonify, request
from datetime import datetime, timedelta
import hashlib
import re
import html
import json
import os
from pathlib import Path

class BoardModule:
    def __init__(self):
        # データ保存用ディレクトリとファイルパス
        self.data_dir = Path('board_data')
        self.posts_file = self.data_dir / 'posts.json'
        self.users_file = self.data_dir / 'users.json'
        self.reports_file = self.data_dir / 'reports.json'
        self.bans_file = self.data_dir / 'bans.json'
        self.rate_limit_file = self.data_dir / 'rate_limits.json'
        
        # ディレクトリが存在しない場合は作成
        self.data_dir.mkdir(exist_ok=True)
        
        # データ構造
        self.posts = []
        self.users = {}
        self.post_count = {}
        self.reports = {}
        self.banned_devices = {}
        self.next_post_id = 1
        
        # データを読み込み
        self.load_data()
        
        print("[BOARD] BoardModule initialized with persistent storage")
    
    def load_data(self):
        """保存されたデータを読み込み"""
        try:
            # 投稿データ
            if self.posts_file.exists():
                with open(self.posts_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.posts = data.get('posts', [])
                    self.next_post_id = data.get('next_post_id', 1)
                print(f"[BOARD] Loaded {len(self.posts)} posts")
            
            # ユーザーデータ
            if self.users_file.exists():
                with open(self.users_file, 'r', encoding='utf-8') as f:
                    self.users = json.load(f)
                print(f"[BOARD] Loaded {len(self.users)} users")
            
            # 通報データ
            if self.reports_file.exists():
                with open(self.reports_file, 'r', encoding='utf-8') as f:
                    self.reports = json.load(f)
                    # キーを整数に変換
                    self.reports = {int(k): v for k, v in self.reports.items()}
                print(f"[BOARD] Loaded {len(self.reports)} reports")
            
            # BANデータ
            if self.bans_file.exists():
                with open(self.bans_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # タイムスタンプをdatetimeに変換
                    self.banned_devices = {
                        device_id: datetime.fromisoformat(timestamp)
                        for device_id, timestamp in data.items()
                    }
                    # 期限切れのBANを削除
                    now = datetime.now()
                    self.banned_devices = {
                        k: v for k, v in self.banned_devices.items()
                        if v > now
                    }
                print(f"[BOARD] Loaded {len(self.banned_devices)} active bans")
            
            # レート制限データ
            if self.rate_limit_file.exists():
                with open(self.rate_limit_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # タイムスタンプをdatetimeに変換
                    now = datetime.now()
                    one_hour_ago = now - timedelta(hours=1)
                    self.post_count = {}
                    for device_id, timestamps in data.items():
                        recent = [
                            datetime.fromisoformat(ts)
                            for ts in timestamps
                            if datetime.fromisoformat(ts) > one_hour_ago
                        ]
                        if recent:
                            self.post_count[device_id] = recent
                print(f"[BOARD] Loaded rate limit data for {len(self.post_count)} devices")
            
            # 古いデータをクリーンアップ
            self.clean_old_posts()
            
        except Exception as e:
            print(f"[BOARD] Error loading data: {e}")
            # エラーが発生しても初期化は続行
    
    def save_data(self):
        """データをファイルに保存"""
        try:
            # 投稿データ
            with open(self.posts_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'posts': self.posts,
                    'next_post_id': self.next_post_id
                }, f, ensure_ascii=False, indent=2)
            
            # ユーザーデータ
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
            
            # 通報データ
            with open(self.reports_file, 'w', encoding='utf-8') as f:
                # キーを文字列に変換（JSONの制約）
                reports_serializable = {str(k): v for k, v in self.reports.items()}
                json.dump(reports_serializable, f, ensure_ascii=False, indent=2)
            
            # BANデータ
            with open(self.bans_file, 'w', encoding='utf-8') as f:
                # datetimeをISO形式文字列に変換
                bans_serializable = {
                    device_id: timestamp.isoformat()
                    for device_id, timestamp in self.banned_devices.items()
                }
                json.dump(bans_serializable, f, ensure_ascii=False, indent=2)
            
            # レート制限データ
            with open(self.rate_limit_file, 'w', encoding='utf-8') as f:
                # datetimeをISO形式文字列に変換
                rate_limit_serializable = {
                    device_id: [ts.isoformat() for ts in timestamps]
                    for device_id, timestamps in self.post_count.items()
                }
                json.dump(rate_limit_serializable, f, ensure_ascii=False, indent=2)
            
            print("[BOARD] Data saved successfully")
            
        except Exception as e:
            print(f"[BOARD] Error saving data: {e}")
    
    def get_device_id(self):
        """デバイスIDを生成（IPアドレス + User-Agentのハッシュ）"""
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ip:
            ip = ip.split(',')[0].strip()
        user_agent = request.headers.get('User-Agent', '')
        device_string = f"{ip}:{user_agent}"
        return hashlib.sha256(device_string.encode()).hexdigest()
    
    def sanitize_text(self, text):
        """XSS対策：HTMLエスケープ処理"""
        return html.escape(text.strip())
    
    def is_banned(self, device_id):
        """BANチェック"""
        if device_id in self.banned_devices:
            ban_until = self.banned_devices[device_id]
            if datetime.now() < ban_until:
                remaining = (ban_until - datetime.now()).total_seconds()
                return True, remaining
            else:
                del self.banned_devices[device_id]
                self.save_data()  # BAN解除を保存
        return False, 0
    
    def check_rate_limit(self, device_id):
        """投稿回数制限チェック（1時間に10件まで）"""
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)
        
        # 古い記録を削除
        if device_id in self.post_count:
            self.post_count[device_id] = [
                timestamp for timestamp in self.post_count[device_id]
                if timestamp > one_hour_ago
            ]
        else:
            self.post_count[device_id] = []
        
        # 10件以上チェック
        if len(self.post_count[device_id]) >= 10:
            oldest = min(self.post_count[device_id])
            remaining = (oldest + timedelta(hours=1) - now).total_seconds()
            return False, f"1時間に10件までしか投稿できません。残り待機時間: {int(remaining//60)}分{int(remaining%60)}秒"
        
        return True, ""
    
    def contains_suspicious_link(self, content):
        """怪しいリンク検出（/ または . が含まれ、かつURL形式の可能性）"""
        url_patterns = [
            r'https?://',
            r'www\.',
            r'\.[a-z]{2,}',
        ]
        
        for pattern in url_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        
        if '/' in content and '.' in content:
            return True
        
        return False
    
    def clean_old_posts(self):
        """古い投稿を削除（3日経過または100件超過）"""
        three_days_ago = datetime.now() - timedelta(days=3)
        
        # 3日以上古い投稿を削除
        old_count = len(self.posts)
        self.posts = [
            post for post in self.posts
            if datetime.fromisoformat(post['timestamp']) > three_days_ago
        ]
        
        # 100件を超えた場合、古い投稿から削除
        if len(self.posts) > 100:
            self.posts = sorted(self.posts, key=lambda x: x['timestamp'], reverse=True)[:100]
        
        if len(self.posts) < old_count:
            print(f"[BOARD] Cleaned {old_count - len(self.posts)} old posts")
            self.save_data()
    
    def register_username(self, username, device_id):
        """ユーザー名登録"""
        if device_id in self.users:
            return False, "既に名前が登録されています。"
        
        username = username.strip()
        
        if not username or len(username) == 0:
            return False, "名前を入力してください。"
        
        if len(username) > 20:
            return False, "名前は20文字以内にしてください。"
        
        if re.search(r'[<>\"\'`]', username):
            return False, "使用できない文字が含まれています。"
        
        if username in self.users.values():
            return False, "その名前は既に使用されています。"
        
        safe_username = self.sanitize_text(username)
        self.users[device_id] = safe_username
        
        self.save_data()  # 保存
        return True, "名前を登録しました。"
    
    def get_username(self, device_id):
        """ユーザー名取得"""
        return self.users.get(device_id, None)
    
    def create_post(self, content, device_id, parent_id=None):
        """投稿作成"""
        is_banned, remaining = self.is_banned(device_id)
        if is_banned:
            hours = int(remaining // 3600)
            minutes = int((remaining % 3600) // 60)
            return False, f"通報により{hours}時間{minutes}分間投稿が制限されています。"
        
        allowed, message = self.check_rate_limit(device_id)
        if not allowed:
            return False, message
        
        content = content.strip()
        
        if not content or len(content) == 0:
            return False, "投稿内容を入力してください。"
        
        if len(content) > 300:
            return False, "投稿は300文字以内にしてください。"
        
        if parent_id:
            parent_exists = any(post['id'] == parent_id for post in self.posts)
            if not parent_exists:
                return False, "返信先の投稿が見つかりません。"
            
            username = self.get_username(device_id)
            if not username:
                return False, "返信するには名前を登録してください。"
        
        is_suspicious = self.contains_suspicious_link(content)
        safe_content = self.sanitize_text(content)
        
        post = {
            'id': self.next_post_id,
            'content': safe_content,
            'username': self.get_username(device_id) or "名無しさん",
            'device_id': device_id,
            'timestamp': datetime.now().isoformat(),
            'parent_id': parent_id,
            'is_suspicious': is_suspicious,
            'is_hidden': False,
            'report_count': 0
        }
        
        self.posts.append(post)
        self.next_post_id += 1
        self.post_count[device_id].append(datetime.now())
        
        self.clean_old_posts()
        self.save_data()  # 保存
        
        print(f"[BOARD] New post created: ID={post['id']}, User={post['username']}, Suspicious={is_suspicious}")
        
        return True, post
    
    def report_post(self, post_id, reporter_device_id):
        """投稿を通報"""
        post = next((p for p in self.posts if p['id'] == post_id), None)
        if not post:
            return False, "投稿が見つかりません。"
        
        if post['device_id'] == reporter_device_id:
            return False, "自分の投稿は通報できません。"
        
        if post_id not in self.reports:
            self.reports[post_id] = []
        
        if reporter_device_id in self.reports[post_id]:
            return False, "既に通報済みです。"
        
        self.reports[post_id].append(reporter_device_id)
        post['report_count'] = len(self.reports[post_id])
        
        if post['report_count'] >= 3:
            post['is_hidden'] = True
            print(f"[BOARD] Post {post_id} hidden due to reports")
        
        author_device_id = post['device_id']
        author_reported_posts = [
            pid for pid, reporters in self.reports.items()
            if len(reporters) >= 2 and any(p['id'] == pid and p['device_id'] == author_device_id for p in self.posts)
        ]
        
        if len(author_reported_posts) >= 1:
            self.banned_devices[author_device_id] = datetime.now() + timedelta(hours=24)
            print(f"[BOARD] User banned for 24 hours: {author_device_id[:8]}...")
        
        self.save_data()  # 保存
        return True, f"通報しました。（{post['report_count']}件）"
    
    def get_posts(self, device_id):
        """投稿一覧取得"""
        self.clean_old_posts()
        
        filtered_posts = []
        for post in self.posts:
            post_data = post.copy()
            
            if post_data['is_hidden']:
                post_data['content_hidden'] = True
                post_data['original_content'] = post_data['content']
                post_data['content'] = "この投稿は多数の報告によって非表示になっています"
            elif post_data['is_suspicious']:
                post_data['content_hidden'] = True
                post_data['original_content'] = post_data['content']
                post_data['content'] = "この投稿にはリンクが含まれる可能性があります"
            
            post_data['is_own'] = post_data['device_id'] == device_id
            del post_data['device_id']
            
            filtered_posts.append(post_data)
        
        filtered_posts.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return filtered_posts

# グローバルインスタンス
board = BoardModule()

# APIエンドポイント

def board_register_name():
    """名前登録API"""
    device_id = board.get_device_id()
    data = request.json
    username = data.get('username', '').strip()
    
    success, message = board.register_username(username, device_id)
    
    return jsonify({
        'success': success,
        'message': message,
        'username': username if success else None
    })

def board_get_username():
    """現在のユーザー名取得API"""
    device_id = board.get_device_id()
    username = board.get_username(device_id)
    
    return jsonify({
        'username': username
    })

def board_create_post():
    """投稿作成API"""
    device_id = board.get_device_id()
    data = request.json
    
    content = data.get('content', '')
    parent_id = data.get('parent_id', None)
    
    success, result = board.create_post(content, device_id, parent_id)
    
    if success:
        return jsonify({
            'success': True,
            'post': result
        })
    else:
        return jsonify({
            'success': False,
            'message': result
        }), 400

def board_get_posts():
    """投稿一覧取得API"""
    device_id = board.get_device_id()
    posts = board.get_posts(device_id)
    
    return jsonify({
        'posts': posts
    })

def board_report_post():
    """通報API"""
    device_id = board.get_device_id()
    data = request.json
    post_id = data.get('post_id')
    
    success, message = board.report_post(post_id, device_id)
    
    return jsonify({
        'success': success,
        'message': message
    })
