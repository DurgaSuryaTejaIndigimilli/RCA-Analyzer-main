"""Sample data for demo mode - downloads and indexes a real small repo."""
import os
import tempfile
import shutil
import subprocess

from core.github_client import git_client
from core.code_chunker import code_chunker, CodeChunk
from core.vector_store import vector_store


# Small, fast-to-clone repositories for demo
DEMO_REPOS = [
    {
        'url': 'https://github.com/pallets/click.git',
        'name': 'pallets/click',
        'description': 'Python composable command line interface toolkit',
        'language': 'Python'
    },
    {
        'url': 'https://github.com/requests/requests.git',
        'name': 'requests/requests',
        'description': 'A simple, yet elegant HTTP library',
        'language': 'Python'
    },
]


async def load_demo_repo():
    """Loads a real small repository for demo."""
    # Try first repo
    repo_data = None
    repo_info_data = None

    for demo in DEMO_REPOS:
        try:
            parsed = git_client.parse_repo_url(demo['url'])
            repo_data = parsed
            repo_info_data = demo
            break
        except Exception:
            continue

    if repo_data is None:
        return {
            'status': 'error',
            'message': 'Could not parse demo repository URL'
        }

    # Clone it
    try:
        repo_path = git_client.clone_repo(repo_data)

        try:
            # Read files
            files = git_client.get_code_files(repo_path)
            if not files:
                return {'status': 'error', 'message': 'No code files in demo repo'}

            # Chunk
            all_chunks = []
            for file_data in files:
                chunks = code_chunker.chunk_file(file_data)
                all_chunks.extend(chunks)

            if not all_chunks:
                return {'status': 'error', 'message': 'Could not parse code'}

            # Build index
            vector_store.clear()
            vector_store.build_index(all_chunks)

            # Return success with real data
            languages = _detect_languages(files)

            return {
                'status': 'success',
                'repo_info': {
                    'name': repo_info_data['name'],
                    'platform': repo_data['platform'],
                    'description': repo_info_data['description'],
                    'language': repo_info_data['language'],
                    'url': demo['url']
                },
                'stats': {
                    'files_indexed': len(files),
                    'total_chunks': len(all_chunks),
                    'languages': languages,
                    'total_lines': sum(f['lines'] for f in files)
                }
            }
        finally:
            git_client.cleanup()

    except Exception as e:
        return {
            'status': 'error',
            'message': f'Demo failed: {str(e)}. Try loading a real repo instead.'
        }


def _detect_languages(files):
    lang_map = {
        '.py': 'Python', '.js': 'JavaScript', '.jsx': 'JavaScript',
        '.ts': 'TypeScript', '.tsx': 'TypeScript', '.java': 'Java',
        '.go': 'Go', '.rs': 'Rust', '.md': 'Markdown',
        '.yml': 'YAML', '.yaml': 'YAML', '.json': 'JSON',
        '.html': 'HTML', '.css': 'CSS', '.txt': 'Text'
    }
    languages = {}
    for f in files:
        lang = lang_map.get(f['extension'], 'Other')
        languages[lang] = languages.get(lang, 0) + 1
    return dict(sorted(languages.items(), key=lambda x: -x[1]))


async def get_demo_status():
    """Returns demo status without loading."""
    return {
        'available': True,
        'message': 'Demo will load a real small repository (pallets/click) and index its code for you to chat with.'
    }
