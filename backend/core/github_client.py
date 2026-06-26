"""GitHub/Bitbucket repository client."""
import os
import re
import tempfile
import shutil
import subprocess
from typing import List, Dict


class GitClient:
    CODE_EXTENSIONS = {
        '.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.kt', '.swift',
        '.go', '.rs', '.cpp', '.c', '.h', '.hpp', '.cs', '.rb', '.php',
        '.scala', '.r', '.sql', '.sh', '.bash', '.yml', '.yaml', '.json',
        '.xml', '.html', '.css', '.scss', '.vue', '.svelte', '.md', '.txt',
        '.toml', '.ini', '.cfg', '.tf', '.dart', '.ex', '.exs', '.elm'
    }

    IGNORE_DIRS = {
        'node_modules', '.git', '__pycache__', '.venv', 'venv', 'env',
        'dist', 'build', 'target', '.next', '.nuxt', 'coverage',
        '.idea', '.vscode', '.pytest_cache', '.mypy_cache', 'vendor',
        'bin', 'obj', '.gradle', '.terraform', 'migrations', '.expo',
        '.cache', 'tmp', 'temp', 'logs', '.angular', '.svelte-kit'
    }

    def __init__(self):
        self.github_token = os.getenv('GITHUB_TOKEN', '')
        self.temp_dir = None

    def parse_repo_url(self, url: str) -> Dict:
        url = url.strip().rstrip('/').rstrip('.git')

        github_match = re.search(r'github\.com[:/]([^/]+)/([^/\s]+?)(?:\.git)?$', url)
        if github_match:
            owner, repo = github_match.group(1), github_match.group(2)
            return {
                'platform': 'github',
                'owner': owner,
                'repo': repo,
                'clone_url': f'https://github.com/{owner}/{repo}.git'
            }

        bitbucket_match = re.search(r'bitbucket\.org[:/]([^/]+)/([^/\s]+?)(?:\.git)?$', url)
        if bitbucket_match:
            owner, repo = bitbucket_match.group(1), bitbucket_match.group(2)
            return {
                'platform': 'bitbucket',
                'owner': owner,
                'repo': repo,
                'clone_url': f'https://bitbucket.org/{owner}/{repo}.git'
            }

        raise ValueError(f"Invalid URL. Use format: https://github.com/owner/repo")

    def clone_repo(self, repo_data: Dict) -> str:
        self.cleanup()
        self.temp_dir = tempfile.mkdtemp(prefix='repo_')

        try:
            if self.github_token and repo_data['platform'] == 'github':
                token_url = repo_data['clone_url'].replace(
                    'https://', f'https://x-access-token:{self.github_token}@'
                )
                subprocess.run(
                    ['git', 'clone', '--depth', '1', token_url, self.temp_dir],
                    check=True, capture_output=True, timeout=180
                )
            else:
                subprocess.run(
                    ['git', 'clone', '--depth', '1', repo_data['clone_url'], self.temp_dir],
                    check=True, capture_output=True, timeout=180
                )
            return self.temp_dir
        except subprocess.CalledProcessError as e:
            self.cleanup()
            err = e.stderr.decode() if e.stderr else str(e)
            if 'not found' in err.lower():
                raise RuntimeError(f"Repository not found or is private")
            elif 'authentication' in err.lower():
                raise RuntimeError(f"Authentication required. For private repos, set GITHUB_TOKEN")
            else:
                raise RuntimeError(f"Clone failed: {err[:200]}")
        except subprocess.TimeoutExpired:
            self.cleanup()
            raise RuntimeError("Clone timed out (>180s). Repository may be too large.")

    def get_code_files(self, repo_path: str) -> List[Dict]:
        files = []
        for root, dirs, filenames in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in self.IGNORE_DIRS and not d.startswith('.')]

            for filename in filenames:
                ext = os.path.splitext(filename)[1].lower()
                if ext in self.CODE_EXTENSIONS or filename in {'Dockerfile', 'Makefile', 'README'}:
                    filepath = os.path.join(root, filename)
                    rel_path = os.path.relpath(filepath, repo_path).replace('\\', '/')
                    try:
                        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        if len(content) > 500_000 or len(content) < 10:
                            continue
                        files.append({
                            'path': rel_path,
                            'filename': filename,
                            'extension': ext,
                            'content': content,
                            'size': len(content),
                            'lines': content.count('\n') + 1
                        })
                    except Exception:
                        continue
        return files

    def cleanup(self):
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
            except Exception:
                pass
            self.temp_dir = None


git_client = GitClient()
