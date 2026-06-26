"""Chunk logs, alarms, and incident reports for vector search."""
import re
from typing import List, Dict
from .code_chunker import CodeChunk


class LogChunker:
    ERROR_MARKERS = ('ERROR', 'FATAL', 'CRITICAL', 'Exception', 'Traceback', 'panic:')

    def chunk_incident(self, incident: Dict) -> List[CodeChunk]:
        chunks: List[CodeChunk] = []

        for alarm in incident.get('alarms', []):
            chunks.append(self._make_chunk(
                content=self._format_alarm(alarm),
                file_path='alarms/dashboard',
                start_line=1,
                end_line=1,
                chunk_type='alarm',
                name=alarm.get('name', 'alarm'),
                language='alarm',
            ))

        for event in incident.get('timeline', []):
            chunks.append(self._make_chunk(
                content=self._format_timeline_event(event),
                file_path='incident/timeline',
                start_line=event.get('order', 1),
                end_line=event.get('order', 1),
                chunk_type='timeline',
                name=event.get('title', 'event'),
                language='timeline',
            ))

        for log_source in incident.get('logs', []):
            chunks.extend(self._chunk_log_source(log_source))

        for postmortem in incident.get('past_incidents', []):
            chunks.append(self._make_chunk(
                content=self._format_postmortem(postmortem),
                file_path=f"postmortems/{postmortem.get('id', 'unknown')}.md",
                start_line=1,
                end_line=postmortem.get('content', '').count('\n') + 1,
                chunk_type='postmortem',
                name=postmortem.get('title', 'past incident'),
                language='markdown',
            ))

        summary = incident.get('summary', {})
        if summary:
            chunks.append(self._make_chunk(
                content=self._format_summary(summary, incident.get('metadata', {})),
                file_path='incident/summary',
                start_line=1,
                end_line=10,
                chunk_type='summary',
                name=incident.get('metadata', {}).get('id', 'incident'),
                language='text',
            ))

        return chunks

    def _chunk_log_source(self, log_source: Dict) -> List[CodeChunk]:
        service = log_source.get('service', 'unknown')
        content = log_source.get('content', '')
        lines = content.split('\n')
        chunks: List[CodeChunk] = []

        error_blocks = self._split_error_blocks(lines)
        if error_blocks:
            for idx, (start, end, block_lines) in enumerate(error_blocks, 1):
                block_text = '\n'.join(block_lines)
                chunks.append(self._make_chunk(
                    content=block_text,
                    file_path=f"logs/{service}.log",
                    start_line=start,
                    end_line=end,
                    chunk_type='error_block' if self._is_error_block(block_text) else 'log_block',
                    name=f"{service} block {idx}",
                    language='log',
                ))
        else:
            chunks.extend(self._chunk_by_window(lines, service))

        return chunks

    def _split_error_blocks(self, lines: List[str]) -> List[tuple]:
        blocks = []
        current_start = None
        current_lines = []

        for i, line in enumerate(lines, 1):
            is_error = self._is_error_line(line)
            is_continuation = line.startswith((' ', '\t', 'at ', 'Caused by:', '...'))

            if is_error:
                if current_lines and not is_continuation:
                    blocks.append((current_start, i - 1, current_lines))
                    current_lines = []
                if not current_lines:
                    current_start = i
                current_lines.append(line)
            elif current_lines and (is_continuation or line.strip() == ''):
                current_lines.append(line)
            elif current_lines:
                blocks.append((current_start, i - 1, current_lines))
                current_lines = []
                current_start = None

        if current_lines:
            blocks.append((current_start, current_start + len(current_lines) - 1, current_lines))

        return blocks

    def _chunk_by_window(self, lines: List[str], service: str, window: int = 25) -> List[CodeChunk]:
        chunks = []
        for i in range(0, len(lines), window):
            block = lines[i:i + window]
            if not any(line.strip() for line in block):
                continue
            chunks.append(self._make_chunk(
                content='\n'.join(block),
                file_path=f"logs/{service}.log",
                start_line=i + 1,
                end_line=min(i + window, len(lines)),
                chunk_type='log_block',
                name=f"{service} lines {i + 1}",
                language='log',
            ))
        return chunks

    def _is_error_line(self, line: str) -> bool:
        upper = line.upper()
        return any(marker in upper or marker in line for marker in self.ERROR_MARKERS)

    def _is_error_block(self, text: str) -> bool:
        return self._is_error_line(text)

    def _format_alarm(self, alarm: Dict) -> str:
        return (
            f"ALARM: {alarm.get('name')}\n"
            f"Severity: {alarm.get('severity')}\n"
            f"Service: {alarm.get('service')}\n"
            f"Fired at: {alarm.get('fired_at')}\n"
            f"Status: {alarm.get('status')}\n"
            f"Message: {alarm.get('message')}\n"
            f"Metric: {alarm.get('metric', 'N/A')}"
        )

    def _format_timeline_event(self, event: Dict) -> str:
        return (
            f"[{event.get('time')}] {event.get('title')}\n"
            f"Source: {event.get('source', 'system')}\n"
            f"Details: {event.get('details')}"
        )

    def _format_postmortem(self, postmortem: Dict) -> str:
        return (
            f"Past Incident: {postmortem.get('id')} - {postmortem.get('title')}\n"
            f"Date: {postmortem.get('date')}\n"
            f"Similarity tags: {', '.join(postmortem.get('tags', []))}\n"
            f"Root cause: {postmortem.get('root_cause')}\n"
            f"Resolution: {postmortem.get('resolution')}\n\n"
            f"{postmortem.get('content', '')}"
        )

    def _format_summary(self, summary: Dict, metadata: Dict) -> str:
        return (
            f"Incident: {metadata.get('id')} - {metadata.get('title')}\n"
            f"Severity: {metadata.get('severity')}\n"
            f"Status: {metadata.get('status')}\n"
            f"Affected services: {', '.join(metadata.get('services', []))}\n"
            f"Started: {metadata.get('started_at')}\n"
            f"Deploy: {summary.get('deploy', 'N/A')}\n"
            f"Impact: {summary.get('impact')}\n"
            f"Known hypothesis: {summary.get('hypothesis')}"
        )

    def _make_chunk(self, content, file_path, start_line, end_line, chunk_type, name, language):
        return CodeChunk(
            content=content,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            chunk_type=chunk_type,
            name=name,
            language=language,
        )


log_chunker = LogChunker()
