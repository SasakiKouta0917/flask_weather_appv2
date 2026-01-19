"""
掲示板API - スマートバックアップ版
2025年1月 - アクティビティ検知型30分バックアップ対応
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
import threading

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
        self.github_repo = os.environ.get('GITHUB_REPO')
        self.github_api_base = 'https://api.github.com'
        self.github_branch = 'main'
        
        # 🔧 新機能: スマートバックアップ設定
        self.auto_backup_enabled = False  # 投稿時の即座バックアップは無効
        self.scheduled_backup_enabled = bool(self.github_token and self.github_repo)
        self.backup_interval_seconds = 1800  # 30分 = 1800秒
        self.last_backup_time = None
        self.backup_thread = None
        
        # 🔧 新機能: アクティビティ追跡
        self.last_activity_time = datetime.now()  # 最後のユーザーアクション時刻
        self.activity_lock = threading.Lock()  # スレッドセーフな更新
        self.has_pending_changes = False  # 未バックアップの変更があるか
        
        # 初期化ログ
        print("[BOARD] ==========================================")
        print("[BOARD] BoardModule Initialization (Smart Backup)")
        print(f"[BOARD] GITHUB_TOKEN: {'SET (' + self.github_token[:8] + '...)' if self.github_token else 'NOT SET'}")
        print(f"[BOARD] GITHUB_REPO: {self.github_repo if self.github_repo else 'NOT SET'}")
        
        if self.scheduled_backup_enabled:
            print(f"[BOARD] ✅ Smart backup ENABLED: Every {self.backup_interval_seconds // 60} minutes (if active)")
        else:
            print("[BOARD] ⚠️ Smart backup DISABLED")
            if not self.github_token:
                print("[BOARD]   → GITHUB_TOKEN is not set")
            if not self.github_repo:
                print("[BOARD]   → GITHUB_REPO is not set")
        
        print("[BOARD] ==========================================")
        
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
        
        # 🔧 新機能: スマートバックアップスレッド開始
        if self.scheduled_backup_enabled:
            self.start_smart_backup()
    
    # 🔧 新機能: アクティビティ記録
    def record_activity(self):
        """ユーザーアクティビティを記録"""
        with self.activity_lock:
            self.last_activity_time = datetime.now()
            print(f"[BOARD] 👤 Activity recorded at {self.last_activity_time.strftime('%H:%M:%S')}")
    
    def mark_changes_pending(self):
        """未保存の変更をマーク"""
        with self.activity_lock:
            self.has_pending_changes = True
            self.last_activity_time = datetime.now()
    
    def _get_default_branch(self):
        """リポジトリのデフォルトブランチを取得"""
        if not self.github_token or not self.github_repo:
            return 'main'
        
        url = f"{self.github_api_base}/repos/{self.github_repo}"
        headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json',
            'X-GitHub-Api-Version': '2022-11-28'
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                branch = data.get('default_branch', 'main')
                print(f"[BOARD] Detected default branch: {branch}")
                return branch
            else:
                print(f"[BOARD] Failed to get default branch (status {response.status_code}), using 'main'")
                return 'main'
        except Exception as e:
            print(f"[BOARD] Error getting default branch: {e}, using 'main'")
            return 'main'
    
    def github_get_file(self, filepath):
        """GithubからファイルのSHAとコンテンツを取得"""
        if not self.github_token or not self.github_repo:
            return None, None
        
        url = f"{self.github_api_base}/repos/{self.github_repo}/contents/{filepath}"
        headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json',
            'X-GitHub-Api-Version': '2022-11-28'
        }
        
        params = {'ref': self.github_branch}
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                content = base64.b64decode(data['content']).decode('utf-8')
                print(f"[BOARD] ✅ Loaded from GitHub: {filepath} (SHA: {data['sha'][:7]})")
                return data['sha'], content
            elif response.status_code == 404:
                print(f"[BOARD] ℹ️ File not found on GitHub: {filepath} (will create on first save)")
                return None, None
            else:
                print(f"[BOARD] ⚠️ Github GET error: {response.status_code} - {response.text[:200]}")
                return None, None
                
        except Exception as e:
            print(f"[BOARD] ❌ Github GET exception for {filepath}: {e}")
            return None, None
    
    def github_update_file(self, filepath, content, message, max_retries=3):
        """Githubのファイルを更新（リトライ機能付き）"""
        if not self.github_token or not self.github_repo:
            print(f"[BOARD] ⚠️ Skipping GitHub backup (disabled): {filepath}")
            return False
        
        url = f"{self.github_api_base}/repos/{self.github_repo}/contents/{filepath}"
        headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json',
            'X-GitHub-Api-Version': '2022-11-28'
        }
        
        for attempt in range(max_retries):
            try:
                print(f"[BOARD] 📤 Uploading to GitHub: {filepath} (attempt {attempt + 1}/{max_retries})")
                
                sha, _ = self.github_get_file(filepath)
                content_base64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')
                
                data = {
                    'message': message,
                    'content': content_base64,
                    'branch': self.github_branch
                }
                
                if sha:
                    data['sha'] = sha
                    print(f"[BOARD] Updating existing file (SHA: {sha[:7]})")
                else:
                    print(f"[BOARD] Creating new file")
                
                response = requests.put(url, json=data, headers=headers, timeout=15)
                
                if response.status_code in [200, 201]:
                    print(f"[BOARD] ✅ GitHub backup success: {filepath}")
                    return True
                elif response.status_code == 409:
                    print(f"[BOARD] ⚠️ Conflict detected (409), retrying...")
                    time.sleep(1)
                    continue
                elif response.status_code == 404:
                    print(f"[BOARD] ❌ Repository not found (404): {self.github_repo}")
                    return False
                elif response.status_code == 401:
                    print(f"[BOARD] ❌ Authentication failed (401): Invalid GITHUB_TOKEN")
                    return False
                elif response.status_code == 403:
                    print(f"[BOARD] ❌ Permission denied (403): Check token scope (needs 'repo')")
                    return False
                else:
                    print(f"[BOARD] ❌ GitHub backup error: {response.status_code}")
                    print(f"[BOARD] Response: {response.text[:300]}")
                    return False
                    
            except Exception as e:
                print(f"[BOARD] ❌ GitHub backup exception (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                return False
        
        print(f"[BOARD] ❌ GitHub backup failed after {max_retries} attempts")
        return False
    
    # 🔧 新機能: スマートバックアップスレッド
    def start_smart_backup(self):
        """アクティビティ検知型バックアップスレッドを開始"""
        def smart_backup_loop():
            print(f"[BOARD] 🧠 Smart backup thread started (interval: {self.backup_interval_seconds}s)")
            
            while True:
                try:
                    # 30分待機
                    time.sleep(self.backup_interval_seconds)
                    
                    # アクティビティチェック
                    with self.activity_lock:
                        time_since_activity = (datetime.now() - self.last_activity_time).total_seconds()
                        has_changes = self.has_pending_changes
                    
                    # 🔧 判定ロジック
                    if time_since_activity > self.backup_interval_seconds:
                        # 30分間アクティビティなし
                        print(f"[BOARD] 💤 No activity for {int(time_since_activity // 60)} minutes - Skipping backup")
                    elif not has_changes:
                        # アクティビティはあるが変更なし（読み取りのみ）
                        print(f"[BOARD] 👀 Activity detected but no changes - Skipping backup")
                    else:
                        # アクティビティあり＋未保存の変更あり
                        print(f"[BOARD] ⏰ Executing smart backup (activity: {int(time_since_activity)}s ago)...")
                        success = self.execute_github_backup()
                        
                        if success:
                            with self.activity_lock:
                                self.has_pending_changes = False
                    
                except Exception as e:
                    print(f"[BOARD] ❌ Error in smart backup thread: {e}")
                    # エラーが発生してもスレッドは継続
                    time.sleep(60)  # 1分待ってから再開
        
        # デーモンスレッドとして起動（メインプロセス終了時に自動終了）
        self.backup_thread = threading.Thread(target=smart_backup_loop, daemon=True)
        self.backup_thread.start()
        print("[BOARD] ✅ Smart backup thread initialized")
    
    def execute_github_backup(self):
        """GitHubへのバックアップを実行"""
        if not self.github_token or not self.github_repo:
            print("[BOARD] Skipping backup (GitHub not configured)")
            return False
        
        try:
            backup_time = datetime.now()
            
            # posts.json をバックアップ
            posts_content = json.dumps({
                'posts': self.posts,
                'next_post_id': self.next_post_id
            }, ensure_ascii=False, indent=2)
            
            success = self.github_update_file(
                'board_data/posts.json',
                posts_content,
                f'Smart backup: {len(self.posts)} posts at {backup_time.strftime("%Y-%m-%d %H:%M")}'
            )
            
            if success:
                # 他のファイルもバックアップ
                self.github_update_file(
                    'board_data/users.json',
                    json.dumps(self.users, ensure_ascii=False, indent=2),
                    f'Smart backup: {len(self.users)} users'
                )
                
                self.github_update_file(
                    'board_data/reports.json',
                    json.dumps({str(k): v for k, v in self.reports.items()}, ensure_ascii=False, indent=2),
                    f'Smart backup: {len(self.reports)} reports'
                )
                
                self.github_update_file(
                    'board_data/bans.json',
                    json.dumps({device_id: ts.isoformat() for device_id, ts in self.banned_devices.items()}, ensure_ascii=False, indent=2),
                    f'Smart backup: {len(self.banned_devices)} bans'
                )
                
                self.last_backup_time = backup_time
                print(f"[BOARD] ✅ Smart backup completed at {backup_time.strftime('%Y-%m-%d %H:%M:%S')}")
                return True
            else:
                print("[BOARD] ⚠️ Smart backup failed")
                return False
                
        except Exception as e:
            print(f"[BOARD] ❌ Backup execution error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def load_data(self):
        """保存されたデータを読み込み（Github優先、ローカルフォールバック）"""
        try:
            print("[BOARD] ------------------------------------------")
            print("[BOARD] Loading data...")
            
            loaded_from_github = False
            
            # 起動時のみGitHubから読み込み
            if self.github_token and self.github_repo:
                print("[BOARD] 🔍 Trying to load from GitHub...")
                
                sha, content = self.github_get_file('board_data/posts.json')
                if content:
                    data = json.loads(content)
                    self.posts = data.get('posts', [])
                    self.next_post_id = data.get('next_post_id', 1)
                    loaded_from_github = True
                
                sha, content = self.github_get_file('board_data/users.json')
                if content:
                    self.users = json.loads(content)
                
                sha, content = self.github_get_file('board_data/reports.json')
                if content:
                    data = json.loads(content)
                    self.reports = {int(k): v for k, v in data.items()}
                
                sha, content = self.github_get_file('board_data/bans.json')
                if content:
                    data = json.loads(content)
                    now = datetime.now()
                    self.banned_devices = {
                        device_id: datetime.fromisoformat(timestamp)
                        for device_id, timestamp in data.items()
                        if datetime.fromisoformat(timestamp) > now
                    }
                
                if loaded_from_github:
                    print(f"[BOARD] ✅ Loaded from GitHub: {len(self.posts)} posts, {len(self.users)} users")
            
            if not loaded_from_github:
                print("[BOARD] 📁 Loading from local files...")
                
                if self.posts_file.exists():
                    with open(self.posts_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self.posts = data.get('posts', [])
                        self.next_post_id = data.get('next_post_id', 1)
                
                if self.users_file.exists():
                    with open(self.users_file, 'r', encoding='utf-8') as f:
                        self.users = json.load(f)
                
                if self.reports_file.exists():
                    with open(self.reports_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self.reports = {int(k): v for k, v in data.items()}
                
                if self.bans_file.exists():
                    with open(self.bans_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        now = datetime.now()
                        self.banned_devices = {
                            device_id: datetime.fromisoformat(timestamp)
                            for device_id, timestamp in data.items()
                            if datetime.fromisoformat(timestamp) > now
                        }
                
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
                
                print(f"[BOARD] ✅ Loaded from local: {len(self.posts)} posts, {len(self.users)} users")
            
            self.clean_old_posts()
            
            print(f"[BOARD] 📊 Final state: {len(self.posts)} posts, {len(self.users)} users, {len(self.banned_devices)} active bans")
            print("[BOARD] ------------------------------------------")
            
        except Exception as e:
            print(f"[BOARD] ❌ Error loading data: {e}")
            import traceback
            traceback.print_exc()
    
    def save_data(self):
        """データをローカルに保存（GitHubバックアップはスマートバックアップが実行）"""
        try:
            # ローカル保存のみ実行
            with open(self.posts_file, 'w', encoding='utf-8') as f:
                json.dump({'posts': self.posts, 'next_post_id': self.next_post_id}, f, ensure_ascii=False, indent=2)
            
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
            
            with open(self.reports_file, 'w', encoding='utf-8') as f:
                json.dump({str(k): v for k, v in self.reports.items()}, f, ensure_ascii=False, indent=2)
            
            with open(self.bans_file, 'w', encoding='utf-8') as f:
                json.dump({device_id: timestamp.isoformat() for device_id, timestamp in self.banned_devices.items()}, f, ensure_ascii=False, indent=2)
            
            with open(self.rate_limit_file, 'w', encoding='utf-8') as f:
                json.dump({device_id: [ts.isoformat() for ts in timestamps] for device_id, timestamps in self.post_count.items()}, f, ensure_ascii=False, indent=2)
            
            # 🔧 スマートバックアップ: 投稿時のGitHubバックアップは実行しない
            # アクティビティ検知型バックアップスレッドが自動的に実行
            
        except Exception as e:
            print(f"[BOARD] ❌ Error saving data: {e}")
            import traceback
            traceback.print_exc()

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
            cleaned = old_count - len(self.posts)
            print(f"[BOARD] 🧹 Cleaned {cleaned} old posts")
    
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
        
        self.mark_changes_pending()  # 🔧 変更をマーク
        self.save_data()
        print(f"[BOARD] 👤 New user registered: {safe_username}")
        return True, "名前を登録しました。"
    
    def get_username(self, device_id):
        """ユーザー名取得"""
        self.record_activity()  # 🔧 アクティビティ記録（読み取りのみ）
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
        self.mark_changes_pending()  # 🔧 変更をマーク
        self.save_data()
        
        print(f"[BOARD] 📝 New post: ID={post['id']}, User={post['username']}, Suspicious={is_suspicious}")
        
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
            print(f"[BOARD] 🚫 Post {post_id} hidden (reports: {post['report_count']})")
        
        author_device_id = post['device_id']
        author_reported_posts = [
            pid for pid, reporters in self.reports.items()
            if len(reporters) >= 2 and any(p['id'] == pid and p['device_id'] == author_device_id for p in self.posts)
        ]
        
        if len(author_reported_posts) >= 1:
            self.banned_devices[author_device_id] = datetime.now() + timedelta(hours=24)
            print(f"[BOARD] ⛔ User banned (24h): {author_device_id[:8]}...")
        
        self.mark_changes_pending()  # 🔧 変更をマーク
        self.save_data()
        return True, f"通報しました。"
    
    def get_posts(self, device_id):
        """投稿一覧取得"""
        self.record_activity()  # 🔧 アクティビティ記録（読み取りのみ）
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
            del post_data['report_count']
            
            filtered_posts.append(post_data)
        
        filtered_posts.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return filtered_posts

# ==========================================
# グローバルインスタンスの初期化
# ==========================================
board = BoardModule()

# ==========================================
# APIエンドポイント関数群
# ==========================================

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
