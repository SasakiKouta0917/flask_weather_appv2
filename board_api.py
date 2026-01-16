"""
掲示板API - Github自動バックアップ対応版
既存のboard_api.pyを完全に置き換えてください
"""

from flask import jsonify, request
from datetime import datetime, timedelta
import hashlib
import re
import html
import json
import os
from pathlib import Path
import requests
import base64
import time

class BoardModule:
    def __init__(self):
        # データ保存用ディレクトリとファイルパス
        self.data_dir = Path('board_data')
        self.posts_file = self.data_dir / 'posts.json'
        self.users_file = self.data_dir / 'users.json'
        self.reports_file = self.data_dir / 'reports.json'
        self.bans_file = self.data_dir / 'bans.json'
        self.rate_limit_file = self.data_dir / 'rate_limits.json'
        
        # Github設定
        self.github_token = os.environ.get('GITHUB_TOKEN')
        self.github_repo = os.environ.get('GITHUB_REPO')  # 例: 'username/repo-name'
        self.github_api_base = 'https://api.github.com'
        
        # Github API使用可否チェック
        self.use_github_backup = bool(self.github_token and self.github_repo)
        
        if self.use_github_backup:
            print(f"[BOARD] Github backup enabled: {self.github_repo}")
        else:
            print("[BOARD] Github backup disabled (missing GITHUB_TOKEN or GITHUB_REPO)")
        
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
        
        print("[BOARD] BoardModule initialized with Github auto-backup")
    
    def github_get_file(self, filepath):
        """GithubからファイルのSHAとコンテンツを取得"""
        if not self.use_github_backup:
            return None, None
        
        url = f"{self.github_api_base}/repos/{self.github_repo}/contents/{filepath}"
        headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                content = base64.b64decode(data['content']).decode('utf-8')
                return data['sha'], content
            elif response.status_code == 404:
                # ファイルが存在しない（初回）
                return None, None
            else:
                print(f"[BOARD] Github GET error: {response.status_code}")
                return None, None
                
        except Exception as e:
            print(f"[BOARD] Github GET exception: {e}")
            return None, None
    
    def github_update_file(self, filepath, content, message, max_retries=3):
        """Githubのファイルを更新（リトライ機能付き）"""
        if not self.use_github_backup:
            return False
        
        url = f"{self.github_api_base}/repos/{self.github_repo}/contents/{filepath}"
        headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        for attempt in range(max_retries):
            try:
                # 現在のSHAを取得
                sha, _ = self.github_get_file(filepath)
                
                # Base64エンコード
                content_base64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')
                
                # データ準備
                data = {
                    'message': message,
                    'content': content_base64,
                    'branch': 'main'
                }
                
                # SHAがあれば追加（更新時）
                if sha:
                    data['sha'] = sha
                
                # APIリクエスト
                response = requests.put(url, json=data, headers=headers, timeout=15)
                
                if response.status_code in [200, 201]:
                    print(f"[BOARD] Github backup success: {filepath}")
                    return True
                elif response.status_code == 409:
                    # Conflict: リトライ
                    print(f"[BOARD] Conflict detected, retry {attempt + 1}/{max_retries}")
                    time.sleep(1)
                    continue
                else:
                    print(f"[BOARD] Github backup error: {response.status_code}")
                    print(f"[BOARD] Response: {response.text[:200]}")
                    return False
                    
            except Exception as e:
                print(f"[BOARD] Github backup exception (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                return False
        
        print(f"[BOARD] Github backup failed after {max_retries} attempts")
        return False
    
    def load_data(self):
        """保存されたデータを読み込み（Github優先）"""
        try:
            # Githubからデータを取得を試みる
            if self.use_github_backup:
                print("[BOARD] Trying to load data from Github...")
                
                # 投稿データ
                sha, content = self.github_get_file('board_data/posts.json')
                if content:
                    data = json.loads(content)
                    self.posts = data.get('posts', [])
                    self.next_post_id = data.get('next_post_id', 1)
                    print(f"[BOARD] Loaded {len(self.posts)} posts from Github")
                
                # ユーザーデータ
                sha, content = self.github_get_file('board_data/users.json')
                if content:
                    self.users = json.loads(content)
                    print(f"[BOARD] Loaded {len(self.users)} users from Github")
                
                # 通報データ
                sha, content = self.github_get_file('board_data/reports.json')
                if content:
                    data = json.loads(content)
                    self.reports = {int(k): v for k, v in data.items()}
                    print(f"[BOARD] Loaded {len(self.reports)} reports from Github")
                
                # BANデータ
                sha, content = self.github_get_file('board_data/bans.json')
                if content:
                    data = json.loads(content)
                    now = datetime.now()
                    self.banned_devices = {
                        device_id: datetime.fromisoformat(timestamp)
                        for device_id, timestamp in data.items()
                        if datetime.fromisoformat(timestamp) > now
                    }
                    print(f"[BOARD] Loaded {len(self.banned_devices)} active bans from Github")
            
            # ローカルファイルからも読み込み（フォールバック）
            if self.posts_file.exists():
                with open(self.posts_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Githubデータがなければローカルを使用
                    if not self.posts:
                        self.posts = data.get('posts', [])
                        self.next_post_id = data.get('next_post_id', 1)
                        print(f"[BOARD] Loaded {len(self.posts)} posts from local file")
            
            if self.users_file.exists():
                with open(self.users_file, 'r', encoding='utf-8') as f:
                    if not self.users:
                        self.users = json.load(f)
                        print(f"[BOARD] Loaded {len(self.users)} users from local file")
            
            if self.reports_file.exists():
                with open(self.reports_file, 'r', encoding='utf-8') as f:
                    if not self.reports:
                        data = json.load(f)
                        self.reports = {int(k): v for k, v in data.items()}
                        print(f"[BOARD] Loaded {len(self.reports)} reports from local file")
            
            if self.bans_file.exists():
                with open(self.bans_file, 'r', encoding='utf-8') as f:
                    if not self.banned_devices:
                        data = json.load(f)
                        now = datetime.now()
                        self.banned_devices = {
                            device_id: datetime.fromisoformat(timestamp)
                            for device_id, timestamp in data.items()
                            if datetime.fromisoformat(timestamp) > now
                        }
                        print(f"[BOARD] Loaded {len(self.banned_devices)} active bans from local file")
            
            if self.rate_limit_file.exists():
                with open(self.rate_limit_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
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
    
    def save_data(self):
        """データをローカルとGithubの両方に保存"""
        try:
            # ① ローカルファイルに保存（既存機能）
            with open(self.posts_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'posts': self.posts,
                    'next_post_id': self.next_post_id
                }, f, ensure_ascii=False, indent=2)
            
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
            
            with open(self.reports_file, 'w', encoding='utf-8') as f:
                reports_serializable = {str(k): v for k, v in self.reports.items()}
                json.dump(reports_serializable, f, ensure_ascii=False, indent=2)
            
            with open(self.bans_file, 'w', encoding='utf-8') as f:
                bans_serializable = {
                    device_id: timestamp.isoformat()
                    for device_id, timestamp in self.banned_devices.items()
                }
                json.dump(bans_serializable, f, ensure_ascii=False, indent=2)
            
            with open(self.rate_limit_file, 'w', encoding='utf-8') as f:
                rate_limit_serializable = {
                    device_id: [ts.isoformat() for ts in timestamps]
                    for device_id, timestamps in self.post_count.items()
                }
                json.dump(rate_limit_serializable, f, ensure_ascii=False, indent=2)
            
            print("[BOARD] Local data saved successfully")
            
            # ② Githubにバックアップ（新機能）
            if self.use_github_backup:
                # 投稿データ
                posts_content = json.dumps({
                    'posts': self.posts,
                    'next_post_id': self.next_post_id
                }, ensure_ascii=False, indent=2)
                
                self.github_update_file(
                    'board_data/posts.json',
                    posts_content,
                    f'Auto backup: {len(self.posts)} posts'
                )
                
                # ユーザーデータ
                users_content = json.dumps(self.users, ensure_ascii=False, indent=2)
                self.github_update_file(
                    'board_data/users.json',
                    users_content,
                    f'Auto backup: {len(self.users)} users'
                )
                
                # 通報データ
                reports_content = json.dumps(
                    {str(k): v for k, v in self.reports.items()},
                    ensure_ascii=False,
                    indent=2
                )
                self.github_update_file(
                    'board_data/reports.json',
                    reports_content,
                    f'Auto backup: {len(self.reports)} reports'
                )
                
                # BANデータ
                bans_content = json.dumps(
                    {device_id: ts.isoformat() for device_id, ts in self.banned_devices.items()},
                    ensure_ascii=False,
                    indent=2
                )
                self.github_update_file(
                    'board_data/bans.json',
                    bans_content,
                    f'Auto backup: {len(self.banned_devices)} bans'
                )
            
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
                self.save_data()
        return False, 0
    
    def check_rate_limit(self, device_id):
        """投稿回数制限チェック（1時間に10件まで）"""
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)
        
        if device_id in self.post_count:
            self.post_count[device_id] = [
                timestamp for timestamp in self.post_count[device_id]
                if timestamp > one_hour_ago
            ]
        else:
            self.post_count[device_id] = []
        
        if len(self.post_count[device_id]) >= 10:
            oldest = min(self.post_count[device_id])
            remaining = (oldest + timedelta(hours=1) - now).total_seconds()
            return False, f"1時間に10件までしか投稿できません。残り待機時間: {int(remaining//60)}分{int(remaining%60)}秒"
        
        return True, ""
    
    def contains_suspicious_link(self, content):
        """怪しいリンク検出"""
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
        
        old_count = len(self.posts)
        self.posts = [
            post for post in self.posts
            if datetime.fromisoformat(post['timestamp']) > three_days_ago
        ]
        
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
        
        self.save_data()
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
        self.save_data()  # Githubに自動バックアップ
        
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
        
        self.save_data()  # Githubに自動バックアップ
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

# APIエンドポイント（app.pyに追加する関数群）

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
