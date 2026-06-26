"""Code chunker - splits code into semantic chunks."""
import re
from typing import List
from dataclasses import dataclass


@dataclass
class CodeChunk:
    content: str
    file_path: str
    start_line: int
    end_line: int
    chunk_type: str
    name: str
    language: str


class CodeChunker:
    LANGUAGE_MAP = {
        '.py': 'python', '.js': 'javascript', '.jsx': 'javascript',
        '.ts': 'typescript', '.tsx': 'typescript', '.java': 'java',
        '.go': 'go', '.rs': 'rust', '.cpp': 'cpp', '.c': 'c',
        '.rb': 'ruby', '.php': 'php', '.cs': 'csharp', '.kt': 'kotlin',
        '.swift': 'swift', '.scala': 'scala', '.sh': 'bash',
        '.json': 'json', '.yml': 'yaml', '.yaml': 'yaml',
        '.html': 'html', '.css': 'css', '.sql': 'sql', '.md': 'markdown'
    }

    def chunk_file(self, file_data: dict) -> List[CodeChunk]:
        ext = file_data['extension']
        content = file_data['content']
        path = file_data['path']
        language = self.LANGUAGE_MAP.get(ext, 'text')

        if ext == '.py':
            chunks = self._chunk_python(content, path, language)
        elif ext in {'.js', '.jsx', '.ts', '.tsx'}:
            chunks = self._chunk_javascript(content, path, language)
        elif ext in {'.java', '.kt', '.cs', '.scala'}:
            chunks = self._chunk_jvm(content, path, language)
        elif ext in {'.go', '.rs'}:
            chunks = self._chunk_go_rust(content, path, language)
        else:
            chunks = []

        if not chunks:
            chunks = self._chunk_by_lines(content, path, language)

        return chunks

    def _chunk_python(self, content: str, path: str, language: str) -> List[CodeChunk]:
        chunks = []
        lines = content.split('\n')
        pattern = re.compile(r'^(\s*)(class|def|async def)\s+(\w+)')

        chunk_start = 0
        chunk_name = 'module'
        chunk_type = 'module'

        for i, line in enumerate(lines):
            match = pattern.match(line)
            if match:
                if chunk_start < i:
                    chunk_content = '\n'.join(lines[chunk_start:i])
                    if chunk_content.strip():
                        chunks.append(self._make_chunk(chunk_content, path, chunk_start+1, i, chunk_type, chunk_name, language))
                chunk_type = 'class' if match.group(2) == 'class' else 'function'
                chunk_name = f"{match.group(2)} {match.group(3)}"
                chunk_start = i

        if chunk_start < len(lines):
            chunk_content = '\n'.join(lines[chunk_start:])
            if chunk_content.strip():
                chunks.append(self._make_chunk(chunk_content, path, chunk_start+1, len(lines), chunk_type, chunk_name, language))

        return chunks

    def _chunk_javascript(self, content: str, path: str, language: str) -> List[CodeChunk]:
        chunks = []
        lines = content.split('\n')
        patterns = [
            re.compile(r'^\s*(export\s+)?(default\s+)?(async\s+)?function\s+(\w+)'),
            re.compile(r'^\s*(export\s+)?(default\s+)?class\s+(\w+)'),
            re.compile(r'^\s*(export\s+)?(default\s+)?const\s+(\w+)\s*[:=]'),
        ]

        chunk_start = 0
        chunk_name = 'module'
        chunk_type = 'module'

        for i, line in enumerate(lines):
            for pattern in patterns:
                match = pattern.match(line)
                if match:
                    if chunk_start < i:
                        chunk_content = '\n'.join(lines[chunk_start:i])
                        if chunk_content.strip():
                            chunks.append(self._make_chunk(chunk_content, path, chunk_start+1, i, chunk_type, chunk_name, language))
                    if 'function' in pattern.pattern:
                        chunk_type = 'function'
                        chunk_name = f"function {match.group(4)}"
                    elif 'class' in pattern.pattern:
                        chunk_type = 'class'
                        chunk_name = f"class {match.group(3)}"
                    else:
                        chunk_type = 'component'
                        chunk_name = f"const {match.group(3)}"
                    chunk_start = i
                    break

        if chunk_start < len(lines):
            chunk_content = '\n'.join(lines[chunk_start:])
            if chunk_content.strip():
                chunks.append(self._make_chunk(chunk_content, path, chunk_start+1, len(lines), chunk_type, chunk_name, language))

        return chunks

    def _chunk_jvm(self, content: str, path: str, language: str) -> List[CodeChunk]:
        chunks = []
        lines = content.split('\n')
        pattern = re.compile(r'^\s*(public|private|protected)?\s*(static\s+)?(class|interface|void|int|String|boolean|def|fun)\s+(\w+)')

        chunk_start = 0
        chunk_name = 'module'
        chunk_type = 'module'

        for i, line in enumerate(lines):
            match = pattern.match(line)
            if match and match.group(3) in ('class', 'interface'):
                if chunk_start < i:
                    chunk_content = '\n'.join(lines[chunk_start:i])
                    if chunk_content.strip():
                        chunks.append(self._make_chunk(chunk_content, path, chunk_start+1, i, chunk_type, chunk_name, language))
                chunk_type = 'class'
                chunk_name = f"class {match.group(5)}"
                chunk_start = i

        if chunk_start < len(lines):
            chunk_content = '\n'.join(lines[chunk_start:])
            if chunk_content.strip():
                chunks.append(self._make_chunk(chunk_content, path, chunk_start+1, len(lines), chunk_type, chunk_name, language))

        return chunks

    def _chunk_go_rust(self, content: str, path: str, language: str) -> List[CodeChunk]:
        chunks = []
        lines = content.split('\n')

        if language == 'go':
            pattern = re.compile(r'^(func\s+(\([^)]+\)\s+)?(\w+)|^type\s+(\w+)\s+struct)')
        else:
            pattern = re.compile(r'^\s*(pub\s+)?(fn|struct|impl|enum)\s+(\w+)')

        chunk_start = 0
        chunk_name = 'module'
        chunk_type = 'module'

        for i, line in enumerate(lines):
            match = pattern.match(line)
            if match:
                if chunk_start < i:
                    chunk_content = '\n'.join(lines[chunk_start:i])
                    if chunk_content.strip():
                        chunks.append(self._make_chunk(chunk_content, path, chunk_start+1, i, chunk_type, chunk_name, language))
                if language == 'go':
                    if match.group(4):
                        chunk_type = 'class'
                        chunk_name = f"struct {match.group(4)}"
                    else:
                        chunk_type = 'function'
                        chunk_name = f"func {match.group(3)}"
                else:
                    chunk_type = 'function' if match.group(2) == 'fn' else 'class'
                    chunk_name = f"{match.group(2)} {match.group(3)}"
                chunk_start = i

        if chunk_start < len(lines):
            chunk_content = '\n'.join(lines[chunk_start:])
            if chunk_content.strip():
                chunks.append(self._make_chunk(chunk_content, path, chunk_start+1, len(lines), chunk_type, chunk_name, language))

        return chunks

    def _chunk_by_lines(self, content: str, path: str, language: str, chunk_size: int = 80) -> List[CodeChunk]:
        chunks = []
        lines = content.split('\n')
        for i in range(0, len(lines), chunk_size):
            chunk_lines = lines[i:i + chunk_size]
            chunks.append(self._make_chunk(
                '\n'.join(chunk_lines), path, i+1,
                min(i + chunk_size, len(lines)),
                'block', f"lines {i+1}-{min(i+chunk_size, len(lines))}", language
            ))
        return chunks

    def _make_chunk(self, content, file_path, start, end, chunk_type, name, language):
        return CodeChunk(
            content=content, file_path=file_path,
            start_line=start, end_line=end,
            chunk_type=chunk_type, name=name, language=language
        )


code_chunker = CodeChunker()
