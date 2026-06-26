"""Main chatbot orchestrator — supports codebase and incident RCA modes."""
from typing import List, Dict, Optional
from .github_client import git_client
from .code_chunker import code_chunker, CodeChunk
from .log_chunker import log_chunker
from .vector_store import vector_store
from .llm_client import LLMClient


class CodebaseChatbot:
    def __init__(self):
        self.llm = LLMClient()
        self.mode: Optional[str] = None  # 'repo' | 'incident'
        self.current_repo: Optional[Dict] = None
        self.repo_info: Optional[Dict] = None
        self.incident_info: Optional[Dict] = None
        self.timeline: List[Dict] = []
        self.alarms: List[Dict] = []
        self.indexed_files = 0
        self.total_chunks = 0
        self.languages: Dict = {}
        self.chat_history: List[Dict] = []

    @property
    def is_loaded(self) -> bool:
        return self.mode is not None and self.repo_info is not None

    async def load_repository(self, repo_url: str) -> Dict:
        try:
            repo_data = git_client.parse_repo_url(repo_url)
            repo_path = git_client.clone_repo(repo_data)

            try:
                files = git_client.get_code_files(repo_path)
                if not files:
                    return {'status': 'error', 'message': 'No code files found in repository'}

                all_chunks: List[CodeChunk] = []
                for file_data in files:
                    chunks = code_chunker.chunk_file(file_data)
                    all_chunks.extend(chunks)

                if not all_chunks:
                    return {'status': 'error', 'message': 'Could not parse code from repository'}

                vector_store.clear()
                vector_store.build_index(all_chunks)

                self.mode = 'repo'
                self.current_repo = repo_data
                self.incident_info = None
                self.timeline = []
                self.alarms = []
                self.indexed_files = len(files)
                self.total_chunks = len(all_chunks)
                self.languages = self._detect_languages(files)
                self.chat_history = []
                self.repo_info = {
                    'name': f"{repo_data['owner']}/{repo_data['repo']}",
                    'platform': repo_data['platform'],
                    'url': repo_url
                }

                return {
                    'status': 'success',
                    'mode': 'repo',
                    'repo_info': self.repo_info,
                    'stats': {
                        'files_indexed': self.indexed_files,
                        'total_chunks': self.total_chunks,
                        'languages': self.languages,
                        'total_lines': sum(f['lines'] for f in files)
                    }
                }
            finally:
                git_client.cleanup()

        except ValueError as e:
            return {'status': 'error', 'message': str(e)}
        except RuntimeError as e:
            return {'status': 'error', 'message': str(e)}
        except Exception as e:
            return {'status': 'error', 'message': f"Unexpected error: {str(e)}"}

    def load_incident(self, incident_data: Dict) -> Dict:
        """Load and index incident logs, alarms, and postmortems."""
        try:
            chunks = log_chunker.chunk_incident(incident_data)
            if not chunks:
                return {'status': 'error', 'message': 'No incident data to index'}

            vector_store.clear()
            vector_store.build_index(chunks)

            metadata = incident_data.get('metadata', {})
            stats_data = incident_data.get('summary', {})

            self.mode = 'incident'
            self.current_repo = {'platform': 'incident', 'id': metadata.get('id')}
            self.incident_info = {
                'name': metadata.get('id', 'INC-UNKNOWN'),
                'title': metadata.get('title', 'Incident'),
                'description': stats_data.get('impact', ''),
                'severity': metadata.get('severity', 'P2'),
                'status': metadata.get('status', 'investigating'),
                'started_at': metadata.get('started_at', ''),
                'services': metadata.get('services', []),
                'platform': 'incident',
            }
            self.repo_info = self.incident_info
            self.timeline = incident_data.get('timeline', [])
            self.alarms = incident_data.get('alarms', [])
            self.indexed_files = len(incident_data.get('logs', []))
            self.total_chunks = len(chunks)
            self.languages = self._count_chunk_types(chunks)
            self.chat_history = []

            return {
                'status': 'success',
                'mode': 'incident',
                'incident_info': self.incident_info,
                'timeline': self.timeline,
                'alarms': self.alarms,
                'stats': {
                    'log_sources': self.indexed_files,
                    'alarms': len(self.alarms),
                    'past_incidents': len(incident_data.get('past_incidents', [])),
                    'total_chunks': self.total_chunks,
                    'chunk_types': self.languages,
                    'total_lines': sum(
                        log.get('content', '').count('\n') + 1
                        for log in incident_data.get('logs', [])
                    ),
                },
            }
        except Exception as e:
            return {'status': 'error', 'message': f"Failed to load incident: {str(e)}"}

    def apply_demo_incident_state(self, demo_result: Dict):
        """Apply state after demo incident is indexed externally."""
        self.mode = 'incident'
        self.current_repo = {'platform': 'incident'}
        self.incident_info = demo_result['incident_info']
        self.repo_info = self.incident_info
        self.timeline = demo_result.get('timeline', [])
        self.alarms = demo_result.get('alarms', [])
        stats = demo_result.get('stats', {})
        self.indexed_files = stats.get('log_sources', 0)
        self.total_chunks = stats.get('total_chunks', 0)
        self.languages = stats.get('chunk_types', {})
        self.chat_history = []

    def _expand_search_query(self, question: str) -> str:
        """Boost retrieval for common question patterns."""
        q = question.lower()
        extras = []
        if any(w in q for w in ['what does', 'overview', 'purpose', 'about', 'project do']):
            extras.append('README overview description main application entry point app.py flask')
        if any(w in q for w in ['architecture', 'structure', 'design pattern', 'how is it built']):
            extras.append('architecture modules components structure design')
        if any(w in q for w in ['function', 'class', 'key', 'main']):
            extras.append('def class function main entry')
        if any(w in q for w in ['auth', 'login', 'security']):
            extras.append('authentication login security token')
        if any(w in q for w in ['dependency', 'dependencies', 'requirements', 'install']):
            extras.append('requirements.txt dependencies packages install')
        if any(w in q for w in ['api', 'endpoint', 'route']):
            extras.append('route endpoint api handler')
        if self.mode == 'incident':
            extras.append('error alarm log root cause failure timeout exception')
        if not extras:
            return question
        return f"{question} {' '.join(extras)}"

    def _detect_languages(self, files: List[Dict]) -> Dict:
        lang_map = {
            '.py': 'Python', '.js': 'JavaScript', '.jsx': 'JavaScript',
            '.ts': 'TypeScript', '.tsx': 'TypeScript', '.java': 'Java',
            '.go': 'Go', '.rs': 'Rust', '.cpp': 'C++', '.c': 'C',
            '.rb': 'Ruby', '.php': 'PHP', '.cs': 'C#', '.kt': 'Kotlin',
            '.swift': 'Swift', '.scala': 'Scala', '.sh': 'Shell',
            '.md': 'Markdown', '.json': 'JSON', '.yml': 'YAML',
            '.yaml': 'YAML', '.html': 'HTML', '.css': 'CSS', '.sql': 'SQL'
        }
        languages = {}
        for f in files:
            lang = lang_map.get(f['extension'], 'Other')
            languages[lang] = languages.get(lang, 0) + 1
        return dict(sorted(languages.items(), key=lambda x: -x[1]))

    def _count_chunk_types(self, chunks: List[CodeChunk]) -> Dict:
        counts = {}
        for chunk in chunks:
            counts[chunk.chunk_type] = counts.get(chunk.chunk_type, 0) + 1
        return dict(sorted(counts.items(), key=lambda x: -x[1]))

    def chat(self, user_message: str) -> Dict:
        if not self.is_loaded:
            return {
                'response': "**No incident or repository loaded!**\n\nLoad a demo incident or repository to begin analysis.",
                'references': []
            }

        self.chat_history.append({'role': 'user', 'content': user_message})

        search_query = self._expand_search_query(user_message)
        relevant_chunks = vector_store.search(search_query, top_k=6)
        context = self._build_context(relevant_chunks)
        response = self._generate_response(user_message, context)

        self.chat_history.append({'role': 'assistant', 'content': response})

        ref_label = 'source' if self.mode == 'incident' else 'file_path'
        return {
            'response': response,
            'mode': self.mode,
            'references': [
                {
                    'file_path': c['file_path'],
                    'lines': f"{c['start_line']}-{c['end_line']}",
                    'chunk_type': c['chunk_type'],
                    'name': c['name'],
                    'relevance': c['relevance_score'],
                    'preview': c['content'][:300] + ('...' if len(c['content']) > 300 else '')
                }
                for c in relevant_chunks
            ]
        }

    def _build_context(self, chunks):
        if not chunks:
            if self.mode == 'incident':
                return "No directly relevant logs, alarms, or incident records found."
            return "No directly relevant code found in the indexed codebase."

        label = "Evidence" if self.mode == 'incident' else "Reference"
        parts = []
        for i, chunk in enumerate(chunks, 1):
            parts.append(f"\n--- {label} {i}: {chunk['file_path']} (lines {chunk['start_line']}-{chunk['end_line']}) ---")
            parts.append(f"Type: {chunk['chunk_type']} | Name: {chunk['name']} | Language: {chunk['language']}")
            parts.append(f"Relevance: {chunk['relevance_score']:.2%}")
            parts.append("```")
            parts.append(chunk['content'][:1500])
            parts.append("```")

        if self.mode == 'incident' and self.timeline:
            parts.append("\n--- Incident Timeline (summary) ---")
            for event in self.timeline[:6]:
                parts.append(f"[{event.get('time')}] {event.get('title')}: {event.get('details')}")

        return "\n".join(parts)

    def _generate_response(self, question, context):
        if self.mode == 'incident':
            return self._generate_incident_response(question, context)
        return self._generate_repo_response(question, context)

    def _generate_incident_response(self, question, context):
        incident_id = self.incident_info.get('name', 'the incident') if self.incident_info else 'the incident'
        incident_title = self.incident_info.get('title', '') if self.incident_info else ''

        system_prompt = f"""You are a senior Site Reliability Engineer performing root cause analysis on incident `{incident_id}`: {incident_title}.

Your job is to help on-call engineers reduce MTTR by analyzing logs, alarms, and past incidents.

Your responses must be:
- **Evidence-based**: Cite specific log lines, alarms, and timestamps from the retrieved evidence
- **Actionable**: Provide clear next steps for remediation
- **Structured**: Use markdown headers, bullet points, and timelines
- **Correlated**: Connect alarms → logs → deploys → root cause

When identifying root cause, consider:
1. What changed recently (deploys, config)?
2. Which alarm fired first?
3. What do error logs show across services?
4. Have we seen this before in past incidents?

Format: Start with a brief summary, then root cause hypothesis with confidence level, then evidence, then recommended actions."""

        user_prompt = f"""Engineer Question: {question}

{context}

Analyze the evidence above and answer the engineer's question. Reference specific log sources and line numbers."""

        return self.llm.generate(system_prompt, user_prompt, max_tokens=2500)

    def _generate_repo_response(self, question, context):
        repo_name = self.repo_info.get('name', 'the repository') if self.repo_info else 'the repository'

        system_prompt = f"""You are an expert software engineer who has thoroughly analyzed the repository `{repo_name}`.

Your responses should be:
- **Specific**: Reference actual code, functions, files with line numbers
- **Helpful**: Answer as if you're a senior engineer who has read every file
- **Conversational**: Be friendly, direct, and clear
- **Practical**: Give actionable insights and examples

Format responses with markdown:
- Use code blocks with language hints
- Use headers for organization
- Use bullet points for lists
- Reference files like `src/main.py:42` when relevant"""

        user_prompt = f"""User Question: {question}

{context}

Please answer the user's question based on the code references above."""

        return self.llm.generate(system_prompt, user_prompt, max_tokens=2500)

    def get_status(self):
        return {
            'loaded': self.is_loaded,
            'mode': self.mode,
            'repo_info': self.repo_info,
            'incident_info': self.incident_info,
            'timeline': self.timeline if self.mode == 'incident' else None,
            'alarms': self.alarms if self.mode == 'incident' else None,
            'stats': {
                'files_indexed': self.indexed_files,
                'total_chunks': self.total_chunks,
                'languages': self.languages
            } if self.is_loaded else None,
            'chat_history_length': len(self.chat_history)
        }

    def clear(self):
        self.mode = None
        self.current_repo = None
        self.repo_info = None
        self.incident_info = None
        self.timeline = []
        self.alarms = []
        self.indexed_files = 0
        self.total_chunks = 0
        self.languages = {}
        self.chat_history = []
        vector_store.clear()


chatbot = CodebaseChatbot()
