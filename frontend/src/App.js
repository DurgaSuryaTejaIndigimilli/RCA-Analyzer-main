import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import {
  FiSend, FiGithub, FiCode, FiCpu, FiFileText, FiRefreshCw,
  FiTrash2, FiZap, FiX, FiSearch, FiBookOpen, FiAlertTriangle,
  FiActivity, FiClock
} from 'react-icons/fi';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import './App.css';

// Relative URLs use the CRA dev-server proxy (works in GitHub Codespaces).
// Only set REACT_APP_API_URL for a split production deploy.
const API_BASE = process.env.REACT_APP_API_URL || '';

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [repoUrl, setRepoUrl] = useState('');
  const [showLoadModal, setShowLoadModal] = useState(true);
  const [sessionLoaded, setSessionLoaded] = useState(false);
  const [mode, setMode] = useState(null);
  const [sessionInfo, setSessionInfo] = useState(null);
  const [sessionStats, setSessionStats] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [alarms, setAlarms] = useState([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [suggestedQuestions, setSuggestedQuestions] = useState([]);
  const [loadStatus, setLoadStatus] = useState('');
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (sessionLoaded && mode) {
      axios.get(`${API_BASE}/api/suggested-questions?mode=${mode}`)
        .then(res => setSuggestedQuestions(res.data.questions))
        .catch(() => {});
    }
  }, [sessionLoaded, mode]);

  const addMessage = (role, content, extras = {}) => {
    setMessages(prev => [...prev, {
      id: Date.now().toString() + Math.random(),
      role, content, timestamp: new Date().toISOString(),
      ...extras
    }]);
  };

  const applySession = (data, sessionMode) => {
    const info = data.incident_info || data.repo_info;
    setSessionInfo(info);
    setSessionStats(data.stats);
    setMode(sessionMode);
    setTimeline(data.timeline || []);
    setAlarms(data.alarms || []);
    setSessionLoaded(true);
    setShowLoadModal(false);
  };

  const beginLoad = (status) => {
    setShowLoadModal(false);
    setIsLoading(true);
    setLoadStatus(status);
  };

  const endLoad = () => {
    setIsLoading(false);
    setLoadStatus('');
  };

  const formatLoadError = (error, fallback) => {
    if (error.code === 'ECONNABORTED') {
      return '**Request timed out.** The backend is still processing — check that it is running and try a smaller repo, or wait and retry.';
    }
    if (error.message === 'Network Error' || !error.response) {
      return '**Cannot reach the API.** Start the backend: `cd backend && PORT=8001 python main.py`';
    }
    return `**${fallback}**: ${error.response?.data?.detail || error.message}`;
  };

  const loadIncidentDemo = async () => {
    beginLoad('Indexing incident evidence (first run may take 1–2 min)...');
    addMessage('user', 'Loading demo incident: INC-2026-0847');
    try {
      const response = await axios.post(`${API_BASE}/api/demo-incident`, null, {
        timeout: 300000,
      });
      applySession(response.data, 'incident');
      const s = response.data.stats;
      addMessage('assistant',
        `**Incident loaded — ${response.data.incident_info.id}**\n\n` +
        `**${response.data.incident_info.title}**\n\n` +
        `**Indexed evidence:**\n` +
        `- Log sources: ${s.log_sources}\n` +
        `- Alarms: ${s.alarms}\n` +
        `- Past incidents: ${s.past_incidents}\n` +
        `- Evidence chunks: ${s.total_chunks}\n\n` +
        `I'm ready to investigate. Ask about root cause, timeline, similar incidents, or remediation.`,
        { isSessionLoaded: true }
      );
    } catch (error) {
      addMessage('assistant', formatLoadError(error, 'Failed to load incident'), { isError: true });
    } finally {
      endLoad();
    }
  };

  const loadRepository = async (url) => {
    beginLoad('Cloning repository and building index (first run may take 1–2 min)...');
    addMessage('user', `Loading repository: ${url}`);
    try {
      const response = await axios.post(`${API_BASE}/api/load-repo`, { repo_url: url }, {
        timeout: 300000,
      });
      applySession(response.data, 'repo');
      addMessage('assistant',
        `**Repository loaded successfully!**\n\n` +
        `Files: ${response.data.stats.files_indexed} | Chunks: ${response.data.stats.total_chunks}\n\n` +
        `Ask me anything about the codebase.`,
        { isSessionLoaded: true }
      );
    } catch (error) {
      addMessage('assistant', formatLoadError(error, 'Failed to load repository'), { isError: true });
    } finally {
      endLoad();
    }
  };

  const loadRepoDemo = async () => {
    beginLoad('Loading demo repository (first run may take 1–2 min)...');
    addMessage('user', 'Loading demo repository');
    try {
      const response = await axios.post(`${API_BASE}/api/demo`, null, {
        timeout: 300000,
      });
      applySession(response.data, 'repo');
      addMessage('assistant',
        `**Demo repository loaded!** (${response.data.stats.files_indexed} files)\n\nAsk me anything about the codebase!`,
        { isSessionLoaded: true }
      );
    } catch (error) {
      addMessage('assistant', formatLoadError(error, 'Demo failed'), { isError: true });
    } finally {
      endLoad();
    }
  };

  const sendMessage = async (messageText = null) => {
    const text = messageText || input;
    if (!text.trim() || isLoading) return;

    addMessage('user', text);
    setInput('');
    setIsLoading(true);

    try {
      const response = await axios.post(`${API_BASE}/api/chat`, { message: text });
      addMessage('assistant', response.data.response, {
        references: response.data.references || [],
        mode: response.data.mode || mode,
      });
    } catch (error) {
      addMessage('assistant',
        `Error: ${error.response?.data?.detail || error.message}`,
        { isError: true }
      );
    } finally {
      setIsLoading(false);
    }
  };

  const clearChat = async () => {
    try {
      await axios.post(`${API_BASE}/api/clear`);
      setMessages([]);
      setSessionLoaded(false);
      setSessionInfo(null);
      setSessionStats(null);
      setMode(null);
      setTimeline([]);
      setAlarms([]);
      setShowLoadModal(true);
    } catch (error) {
      console.error('Clear failed:', error);
    }
  };

  const isIncident = mode === 'incident';

  return (
    <div className="app">
      <div className="bg-animation">
        <div className="bg-gradient-1"></div>
        <div className="bg-gradient-2"></div>
        <div className="bg-gradient-3"></div>
      </div>

      {sidebarOpen && sessionLoaded && (
        <aside className="sidebar open">
          <div className="sidebar-header">
            <div className="logo-container">
              <div className="logo-icon">{isIncident ? <FiAlertTriangle /> : <FiCpu />}</div>
              <div className="logo-text">
                <div className="logo-title">RCA Analyzer</div>
                <div className="logo-subtitle">{isIncident ? 'Incident Investigation' : 'Code Analysis'}</div>
              </div>
            </div>
          </div>

          {sessionInfo && (
            <div className="sidebar-section">
              <div className="section-label">{isIncident ? 'ACTIVE INCIDENT' : 'LOADED REPOSITORY'}</div>
              <div className="repo-card">
                <div className="repo-name">
                  {isIncident ? <FiAlertTriangle /> : <FiGithub />} {sessionInfo.name}
                </div>
                {(sessionInfo.title || sessionInfo.description) && (
                  <div className="repo-description">{sessionInfo.title || sessionInfo.description}</div>
                )}
                <div className="repo-meta">
                  {isIncident && (
                    <>
                      <span className="repo-badge severity">{sessionInfo.severity}</span>
                      <span className="repo-badge">{sessionInfo.status}</span>
                    </>
                  )}
                  {!isIncident && <span className="repo-badge">{sessionInfo.platform}</span>}
                </div>
              </div>
            </div>
          )}

          {sessionStats && (
            <div className="sidebar-section">
              <div className="section-label">INDEXED EVIDENCE</div>
              {isIncident ? (
                <>
                  <div className="stat-card">
                    <div className="stat-icon"><FiFileText /></div>
                    <div className="stat-info">
                      <div className="stat-value">{sessionStats.log_sources}</div>
                      <div className="stat-label">Log Sources</div>
                    </div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-icon"><FiAlertTriangle /></div>
                    <div className="stat-info">
                      <div className="stat-value">{sessionStats.alarms}</div>
                      <div className="stat-label">Alarms</div>
                    </div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-icon"><FiActivity /></div>
                    <div className="stat-info">
                      <div className="stat-value">{sessionStats.total_chunks}</div>
                      <div className="stat-label">Chunks</div>
                    </div>
                  </div>
                </>
              ) : (
                <>
                  <div className="stat-card">
                    <div className="stat-icon"><FiFileText /></div>
                    <div className="stat-info">
                      <div className="stat-value">{sessionStats.files_indexed}</div>
                      <div className="stat-label">Files</div>
                    </div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-icon"><FiCode /></div>
                    <div className="stat-info">
                      <div className="stat-value">{sessionStats.total_chunks}</div>
                      <div className="stat-label">Chunks</div>
                    </div>
                  </div>
                </>
              )}
            </div>
          )}

          {isIncident && alarms.length > 0 && (
            <div className="sidebar-section">
              <div className="section-label">FIRING ALARMS</div>
              <div className="alarms-list">
                {alarms.slice(0, 4).map((alarm, i) => (
                  <div key={i} className="alarm-item">
                    <span className={`alarm-severity ${alarm.severity}`}>{alarm.severity}</span>
                    <span className="alarm-name">{alarm.name}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {isIncident && timeline.length > 0 && (
            <div className="sidebar-section">
              <div className="section-label">TIMELINE</div>
              <div className="timeline-list">
                {timeline.slice(0, 5).map((event, i) => (
                  <div key={i} className="timeline-item">
                    <FiClock className="timeline-icon" />
                    <div>
                      <div className="timeline-time">{event.time?.split('T')[1]?.replace('Z', '') || event.time}</div>
                      <div className="timeline-title">{event.title}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="sidebar-section">
            <button className="sidebar-btn" onClick={clearChat}>
              <FiTrash2 /> New Investigation
            </button>
          </div>

          <div className="sidebar-footer">
            <div className="footer-title">Harris IoT Ideathon 2026</div>
          </div>
        </aside>
      )}

      <main className="main-content">
        <header className="top-bar">
          <div className="top-bar-left">
            {!sidebarOpen && sessionLoaded && (
              <button className="icon-btn" onClick={() => setSidebarOpen(true)}>
                <FiCode />
              </button>
            )}
            <div className="chat-title">
              <div className="title-main">
                {sessionLoaded ? (sessionInfo?.title || sessionInfo?.name) : 'RCA Analyzer'}
              </div>
              <div className="title-sub">
                <span className="status-dot"></span>
                {isLoading
                  ? (loadStatus || (isIncident ? 'Correlating evidence...' : 'Analyzing...'))
                  : (sessionLoaded ? 'Ready' : 'Awaiting incident data')}
              </div>
            </div>
          </div>
          <div className="top-bar-right">
            {sessionLoaded && (
              <button className="icon-btn" onClick={() => setSidebarOpen(!sidebarOpen)}>
                {sidebarOpen ? <FiX /> : <FiCode />}
              </button>
            )}
          </div>
        </header>

        <div className="messages-container">
          {messages.length === 0 && !sessionLoaded && (
            <div className="welcome-screen">
              <div className="welcome-icon"><FiAlertTriangle /></div>
              <h1>RCA Analyzer</h1>
              <p>AI-powered root cause analysis — correlate logs, alarms, and past incidents in minutes</p>
              <button className="cta-button" onClick={() => setShowLoadModal(true)}>
                <FiZap /> Start Demo Investigation
              </button>
            </div>
          )}

          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} defaultMode={mode} />
          ))}

          {isLoading && (
            <div className="message-row assistant">
              <div className="avatar assistant-avatar"></div>
              <div className="message-content-wrapper">
                <div className="message-bubble assistant loading">
                  <div className="typing-indicator">
                    <span></span><span></span><span></span>
                  </div>
                  <div className="loading-text">
                    {loadStatus || (isIncident ? 'Correlating evidence...' : 'Analyzing...')}
                  </div>
                  {loadStatus && (
                    <div className="loading-hint">Please wait — downloading models or cloning repo on first run.</div>
                  )}
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {sessionLoaded && suggestedQuestions.length > 0 && !isLoading && (
          <div className="suggestions-container">
            <div className="suggestions-label">Suggested questions:</div>
            <div className="suggestions-list">
              {suggestedQuestions.slice(0, 4).map((q, i) => (
                <button key={i} className="suggestion-btn" onClick={() => sendMessage(q)} disabled={isLoading}>
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {sessionLoaded && (
          <div className="input-container">
            <div className="input-wrapper">
              <textarea
                className="message-input"
                placeholder={isIncident ? "Ask about root cause, timeline, remediation..." : "Ask anything about the codebase..."}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                  }
                }}
                rows={1}
                disabled={isLoading}
              />
              <button className="send-btn" onClick={() => sendMessage()} disabled={!input.trim() || isLoading}>
                {isLoading ? <FiRefreshCw className="spinning" /> : <FiSend />}
              </button>
            </div>
            <div className="input-hint">
              <kbd>Enter</kbd> send · <kbd>Shift+Enter</kbd> new line
            </div>
          </div>
        )}
      </main>

      {showLoadModal && !isLoading && (
        <LoadModal
          repoUrl={repoUrl}
          setRepoUrl={setRepoUrl}
          onIncidentDemo={loadIncidentDemo}
          onLoadRepo={loadRepository}
          onRepoDemo={loadRepoDemo}
          onClose={() => sessionLoaded && setShowLoadModal(false)}
          isLoading={isLoading}
        />
      )}
    </div>
  );
}

function LoadModal({ repoUrl, setRepoUrl, onIncidentDemo, onLoadRepo, onRepoDemo, onClose, isLoading }) {
  const [tab, setTab] = useState('incident');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (repoUrl.trim()) onLoadRepo(repoUrl);
  };

  return (
    <div className="modal-overlay modal-overlay--dialog" onClick={isLoading ? undefined : onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        {onClose && !isLoading && (
          <button className="modal-close" onClick={onClose} aria-label="Close"></button>
        )}
        <div className="modal-icon"><FiAlertTriangle /></div>
        <h2>RCA Analyzer</h2>
        <p className="modal-subtitle">Investigate incidents with AI — logs, alarms, and history</p>

        <div className="modal-tabs">
          <button className={`modal-tab ${tab === 'incident' ? 'active' : ''}`} onClick={() => setTab('incident')}>
            Incident RCA
          </button>
          <button className={`modal-tab ${tab === 'repo' ? 'active' : ''}`} onClick={() => setTab('repo')}>
            Code Repo
          </button>
        </div>

        {tab === 'incident' ? (
          <>
            <div className="demo-card">
              <div className="demo-card-title">INC-2026-0847</div>
              <div className="demo-card-desc">Payment Service Degradation — P1 checkout failures</div>
              <div className="demo-card-meta">4 services · 4 alarms · 2 past incidents</div>
            </div>
            <button className="modal-btn primary" onClick={onIncidentDemo} disabled={isLoading}>
              {isLoading ? <><FiRefreshCw className="spinning" /> Indexing evidence...</> : <><FiZap /> Load Demo Incident</>}
            </button>
          </>
        ) : (
          <>
            <form onSubmit={handleSubmit}>
              <div className="input-group">
                <FiGithub className="input-icon" />
                <input
                  type="text"
                  className="repo-input"
                  placeholder="https://github.com/owner/repo"
                  value={repoUrl}
                  onChange={(e) => setRepoUrl(e.target.value)}
                  disabled={isLoading}
                />
              </div>
              <button type="submit" className="modal-btn primary" disabled={!repoUrl.trim() || isLoading}>
                {isLoading ? <><FiRefreshCw className="spinning" /> Loading...</> : <><FiSearch /> Analyze Repo</>}
              </button>
            </form>
            <div className="modal-divider"><span>OR</span></div>
            <button className="modal-btn demo" onClick={onRepoDemo} disabled={isLoading}>
              <FiZap /> Try Demo Repository
            </button>
          </>
        )}
      </div>
    </div>
  );
}

function MessageBubble({ message, defaultMode }) {
  const isUser = message.role === 'user';
  const msgMode = message.mode || defaultMode;
  const isIncident = msgMode === 'incident';
  const copyToClipboard = () => navigator.clipboard.writeText(message.content);

  return (
    <div className={`message-row ${message.role} animate-fade-in`}>
      <div className={`avatar ${isUser ? 'user-avatar' : 'assistant-avatar'}`}>
        {isUser ? '' : <FiCpu />}
      </div>
      <div className="message-content-wrapper">
        <div className="message-meta">
          <span className="message-author">{isUser ? 'You' : 'RCA Analyzer'}</span>
          <span className="message-time">{new Date(message.timestamp).toLocaleTimeString()}</span>
        </div>
        <div className={`message-bubble ${message.role} ${message.isError ? 'error' : ''}`}>
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              code({ node, inline, className, children, ...props }) {
                const match = /language-(\w+)/.exec(className || '');
                return !inline && match ? (
                  <SyntaxHighlighter style={vscDarkPlus} language={match[1]} PreTag="div" {...props}>
                    {String(children).replace(/\n$/, '')}
                  </SyntaxHighlighter>
                ) : (<code className={className} {...props}>{children}</code>);
              }
            }}
          >
            {message.content}
          </ReactMarkdown>
        </div>

        {message.references && message.references.length > 0 && (
          <div className="references-section">
            <div className="references-label">
              <FiBookOpen /> {isIncident ? 'Evidence' : 'Code References'} ({message.references.length})
            </div>
            {message.references.map((ref, i) => (
              <details key={i} className="reference-item">
                <summary>
                  <FiFileText />
                  <span className="ref-path">{ref.file_path}</span>
                  <span className="ref-lines">L{ref.lines}</span>
                  <span className="ref-type">{ref.chunk_type}</span>
                </summary>
                <div className="reference-preview">
                  <div className="ref-name">{ref.name}</div>
                  <pre><code>{ref.preview}</code></pre>
                </div>
              </details>
            ))}
          </div>
        )}

        <div className="message-actions">
          <button className="action-btn" onClick={copyToClipboard}>Copy</button>
        </div>
      </div>
    </div>
  );
}

export default App;
