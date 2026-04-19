// @ts-check
// Hermes Agent - Webview Script (Full Feature Parity)
const vscode = acquireVsCodeApi();

const S = {
  isGenerating: false,
  streamingText: '',
  currentAssistantEl: null,
  messages: [],
  settings: {},
  activeFile: null,
  currentModel: 'Default',
  permissionMode: 'default',
  sessionId: null,
  pendingPermission: null,
  mcpServers: /** @type {Array<{name:string,status:string}>} */ ([]),
};

const $ = (id) => document.getElementById(id);
const $messages = $('messages');
const $messagesContainer = $('messages-container');
const $welcomeScreen = $('welcome-screen');
const $userInput = $('user-input');
const $sendBtn = $('send-btn');
const $stopBtn = $('stop-btn');
const $newChatBtn = $('new-chat-btn');
const $newChatBtnTop = $('new-chat-btn-top');
const $toolProgress = $('tool-progress');
const $toolProgressText = $toolProgress?.querySelector('.tool-progress-text');
const $contextBadge = $('context-badge');
const $contextFilename = $('context-filename');
const $contextDismiss = $('context-dismiss');
const $modelBtn = $('model-btn');
const $modelLabel = $('model-label');
const $sessionsBtn = $('sessions-btn');
const $settingsBtn = $('settings-btn');
const $modeBtn = $('mode-btn');
const $permissionBar = $('permission-bar');
const $permAllow = $('perm-allow');
const $permDeny = $('perm-deny');

// ============================================================
// Markdown
// ============================================================
function md(text) {
  if (!text) return '';
  let h = esc(text);
  h = h.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) =>
    `<div class="code-block" data-lang="${lang}"><div class="code-header"><span class="code-lang">${lang || 'text'}</span><div class="code-actions"><button class="code-btn copy-btn" onclick="copyCode(this)">Copy</button><button class="code-btn apply-btn" onclick="applyCode(this)">Apply</button></div></div><pre><code>${code}</code></pre></div>`);
  h = h.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');
  h = h.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  h = h.replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, '<em>$1</em>');
  h = h.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="#" onclick="openUrl(\'$2\');return false" class="chat-link">$1</a>');
  h = h.replace(/^### (.+)$/gm, '<h4 class="chat-h">$1</h4>');
  h = h.replace(/^## (.+)$/gm, '<h3 class="chat-h">$1</h3>');
  h = h.replace(/^# (.+)$/gm, '<h2 class="chat-h">$1</h2>');
  h = h.replace(/^- (.+)$/gm, '<li>$1</li>');
  h = h.replace(/(<li>[\s\S]*?<\/li>)/g, '<ul>$1</ul>');
  h = h.replace(/<\/ul>\s*<ul>/g, '');
  h = h.replace(/\n\n/g, '</p><p>');
  h = `<p>${h}</p>`;
  h = h.replace(/<p><\/p>/g, '');
  h = h.replace(/\n/g, '<br>');
  return h;
}
function esc(t) { return t.replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[m])); }
window.copyCode = (btn) => { const c = btn.closest('.code-block')?.querySelector('code')?.textContent || ''; navigator.clipboard.writeText(c).then(() => { btn.textContent = 'Copied!'; setTimeout(() => btn.textContent = 'Copy', 2000); }); };
window.applyCode = (btn) => { const c = btn.closest('.code-block')?.querySelector('code')?.textContent || ''; vscode.postMessage({ type: 'applyEdit', content: c, filePath: '' }); };
window.openUrl = (url) => { vscode.postMessage({ type: 'open_url', url }); };

// ============================================================
// Messages
// ============================================================
function addUserMessage(content) {
  hideWelcome();
  const el = document.createElement('div');
  el.className = 'message message-user';
  el.innerHTML = `<div class="message-avatar avatar-user"><svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><circle cx="8" cy="5" r="3"/><path d="M2 14c0-3.3 2.7-6 6-6s6 2.7 6 6"/></svg></div><div class="message-body"><div class="message-role">You</div><div class="message-content">${md(content)}</div></div>`;
  $messages.appendChild(el);
  S.messages.push({ role: 'user', content });
  scrollBottom();
}

function createAssistantEl() {
  hideWelcome();
  const el = document.createElement('div');
  el.className = 'message message-assistant';
  el.innerHTML = `<div class="message-avatar avatar-assistant"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg></div><div class="message-body"><div class="message-role">Hermes</div><div class="message-content"><span class="streaming-cursor"></span></div></div>`;
  $messages.appendChild(el);
  scrollBottom();
  return el;
}

function updateAssistant(el, text) {
  const c = el?.querySelector('.message-content');
  if (!c) return;
  c.innerHTML = md(text) + '<span class="streaming-cursor"></span>';
  scrollBottom();
}

function finalizeAssistant(el, text) {
  const c = el?.querySelector('.message-content');
  if (!c) return;
  c.innerHTML = md(text);
  scrollBottom();
}

function addToolMessage(name, status) {
  const el = document.createElement('div');
  el.className = 'message message-tool';
  el.innerHTML = `<div class="message-avatar avatar-tool"><svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M14.12 1.88a3 3 0 00-4.24 0L1.59 10.17a2 2 0 00-.52 1.02L.05 14.83a.5.5 0 00.62.62l3.64-1.02a2 2 0 001.02-.52l8.29-8.29a3 3 0 000-4.24z"/></svg></div><div class="message-body"><div class="tool-header"><span class="tool-name">${esc(name || 'Tool')}</span><span class="tool-status">${status || 'running'}</span></div></div>`;
  $messages.appendChild(el);
  scrollBottom();
}

function addErrorMessage(content) {
  const el = document.createElement('div');
  el.className = 'message message-error';
  el.innerHTML = `<div class="message-avatar avatar-error"><svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><circle cx="8" cy="8" r="7"/><path d="M8 4v5M8 11v1" stroke="white" stroke-width="1.5"/></svg></div><div class="message-body"><div class="message-role">Error</div><div class="message-content">${esc(content)}</div></div>`;
  $messages.appendChild(el);
  scrollBottom();
}

function addResultMessage(cost, duration, turns) {
  const parts = [];
  if (cost) parts.push(`Cost: $${cost.toFixed(4)}`);
  if (duration) parts.push(`Time: ${(duration / 1000).toFixed(1)}s`);
  if (turns) parts.push(`Turns: ${turns}`);
  if (!parts.length) return;
  const el = document.createElement('div');
  el.className = 'message message-result';
  el.innerHTML = `<div class="result-meta">${parts.join(' &middot; ')}</div>`;
  $messages.appendChild(el);
  scrollBottom();
}

// ============================================================
// UI Helpers
// ============================================================
function hideWelcome() { if ($welcomeScreen) $welcomeScreen.style.display = 'none'; if ($messagesContainer) $messagesContainer.style.display = 'flex'; }
function showWelcome() { if ($welcomeScreen) $welcomeScreen.style.display = 'flex'; if ($messagesContainer) $messagesContainer.style.display = 'none'; }
function scrollBottom() { requestAnimationFrame(() => { if ($messagesContainer) $messagesContainer.scrollTop = $messagesContainer.scrollHeight; }); }
function showStop() { $sendBtn.style.display = 'none'; $stopBtn.style.display = 'flex'; }
function showSend() { $sendBtn.style.display = 'flex'; $stopBtn.style.display = 'none'; }
function showToolProgress(name, elapsed) { if (!$toolProgress) return; $toolProgress.style.display = 'flex'; if ($toolProgressText) $toolProgressText.textContent = `${name || 'Working'} ${elapsed ? elapsed.toFixed(1) + 's' : '...'}`; }
function hideToolProgress() { if ($toolProgress) $toolProgress.style.display = 'none'; }
function autoResize() { if (!$userInput) return; $userInput.style.height = 'auto'; $userInput.style.height = Math.min($userInput.scrollHeight, 200) + 'px'; }

function showPermissionBar(request) {
  if (!$permissionBar) return;
  $permissionBar.style.display = 'flex';
  const text = $permissionBar.querySelector('.permission-text');
  if (text) text.textContent = `${request?.tool_name || 'Tool'} wants to ${request?.input ? JSON.stringify(request.input).slice(0, 80) : 'execute'}`;
  S.pendingPermission = request;
}

function hidePermissionBar() { if ($permissionBar) $permissionBar.style.display = 'none'; S.pendingPermission = null; }

// ============================================================
// Core
// ============================================================
function sendMessage() {
  const content = $userInput?.value?.trim();
  if (!content || S.isGenerating) return;
  $userInput.value = '';
  autoResize();
  addUserMessage(content);
  S.streamingText = '';
  S.currentAssistantEl = createAssistantEl();
  vscode.postMessage({ type: 'sendMessage', content, options: { includeFile: true } });
}

function stopGeneration() {
  vscode.postMessage({ type: 'stopGeneration' });
  S.isGenerating = false;
  showSend();
  hideToolProgress();
  hidePermissionBar();
  if (S.currentAssistantEl) { finalizeAssistant(S.currentAssistantEl, S.streamingText); S.currentAssistantEl = null; }
}

function newConversation() {
  S.messages = [];
  S.streamingText = '';
  S.currentAssistantEl = null;
  if ($messages) $messages.innerHTML = '';
  showWelcome();
  showSend();
  hideToolProgress();
  hidePermissionBar();
  vscode.postMessage({ type: 'newConversation' });
  vscode.postMessage({ type: 'generate_session_title' });
}

// ============================================================
// Handlers
// ============================================================
function handleMsg(msg) {
  switch (msg.type) {
    case 'init_response': S.settings = msg; break;
    case 'generationStarted': S.isGenerating = true; showStop(); hideToolProgress(); break;
    case 'systemInit':
      if (msg.mcp_servers) { S.mcpServers = msg.mcp_servers; updateMcpBadge(); }
      if (msg.model) { S.currentModel = msg.model; if ($modelLabel) $modelLabel.textContent = msg.model; }
      break;
    case 'streamToken': handleStreamToken(msg.event); break;
    case 'assistantMessage': handleAssistantMsg(msg.message); break;
    case 'toolProgress': showToolProgress(msg.tool_name || msg.toolName, msg.elapsed_time_seconds || msg.elapsed); break;
    case 'tool_permission_request':
      showPermissionBar(msg.request || msg);
      vscode.postMessage({ type: 'control_response', request_id: msg.request_id || msg.requestId, response: { approved: true } });
      break;
    case 'result':
      hideToolProgress();
      hidePermissionBar();
      if (msg.costUsd || msg.durationMs || msg.numTurns) addResultMessage(msg.costUsd, msg.durationMs, msg.numTurns);
      if (msg.isError && msg.result) {
        addErrorMessage(msg.result);
        if (S.currentAssistantEl) { S.currentAssistantEl.remove(); S.currentAssistantEl = null; }
      } else if (msg.result && !S.streamingText) {
        S.streamingText = msg.result;
        if (S.currentAssistantEl) finalizeAssistant(S.currentAssistantEl, S.streamingText);
        else { const el = createAssistantEl(); finalizeAssistant(el, S.streamingText); }
      } else if (S.currentAssistantEl) { finalizeAssistant(S.currentAssistantEl, S.streamingText); S.currentAssistantEl = null; }
      break;
    case 'generationComplete':
      S.isGenerating = false; showSend(); hideToolProgress(); hidePermissionBar();
      if (S.currentAssistantEl) { finalizeAssistant(S.currentAssistantEl, S.streamingText); S.currentAssistantEl = null; }
      vscode.postMessage({ type: 'generate_session_title' });
      break;
    case 'error':
      S.isGenerating = false; showSend(); hideToolProgress(); hidePermissionBar();
      addErrorMessage(msg.content || msg.message || 'Unknown error');
      if (S.currentAssistantEl) { S.currentAssistantEl.remove(); S.currentAssistantEl = null; }
      break;
    case 'rawText':
      S.streamingText += msg.text;
      if (S.currentAssistantEl) updateAssistant(S.currentAssistantEl, S.streamingText);
      break;
    case 'newConversation':
      S.messages = []; S.streamingText = ''; S.currentAssistantEl = null;
      if ($messages) $messages.innerHTML = '';
      showWelcome(); showSend(); hideToolProgress(); hidePermissionBar();
      S.sessionId = msg.sessionId;
      break;
    case 'focusInput': $userInput?.focus(); break;
    case 'blurInput': $userInput?.blur(); break;

    // Model
    case 'get_auth_status_response':
      if (msg.model) { S.currentModel = msg.model; if ($modelLabel) $modelLabel.textContent = msg.model; }
      break;
    case 'set_model_response':
      S.currentModel = msg.model;
      if ($modelLabel) $modelLabel.textContent = msg.model || 'Default';
      break;

    // Permission mode
    case 'set_permission_mode_response':
      S.permissionMode = msg.mode;
      if ($modeBtn) $modeBtn.textContent = msg.mode === 'default' ? 'Default' : msg.mode === 'plan' ? 'Plan' : msg.mode === 'acceptEdits' ? 'Accept Edits' : msg.mode;
      break;

    // Sessions
    case 'list_sessions_response':
      showSessionsPanel(msg.sessions || []);
      break;
    case 'get_session_response':
      if (msg.messages?.length) {
        if ($messages) $messages.innerHTML = '';
        showWelcome(); showSend();
        for (const m of msg.messages) {
          if (m.role === 'user') addUserMessage(m.content);
          else if (m.role === 'assistant') {
            const el = createAssistantEl();
            finalizeAssistant(el, m.content);
          }
        }
        S.messages = msg.messages;
        S.sessionId = msg.sessionId;
      }
      break;

    // Selection
    case 'selection_changed':
      if (msg.fileName && $contextBadge && $contextFilename) {
        $contextFilename.textContent = msg.fileName.split('/').pop();
        $contextBadge.style.display = 'flex';
        S.activeFile = msg;
      }
      break;

    case 'insertMention':
      if ($userInput && msg.mention) { $userInput.value += msg.mention + ' '; $userInput.focus(); autoResize(); }
      break;

    case 'getSettings':
      S.settings = msg.settings || {};
      if (S.settings.model && $modelLabel) $modelLabel.textContent = S.settings.model;
      if (S.settings.permissionMode && $modeBtn) $modeBtn.textContent = S.settings.permissionMode;
      break;

    case 'generate_session_title_response':
      document.title = msg.title ? `Hermes - ${msg.title}` : 'Hermes Agent';
      break;

    case 'applyEdit':
      break;

    case 'get_mcp_servers_response':
      S.mcpServers = msg.servers || [];
      updateMcpBadge();
      break;

    case 'check_git_status_response':
      break;
  }
}

function handleStreamToken(event) {
  if (!event) return;
  if (event.type === 'content_block_delta') {
    const d = event.delta;
    if (d?.type === 'text_delta' && d.text) {
      S.streamingText += d.text;
      if (S.currentAssistantEl) updateAssistant(S.currentAssistantEl, S.streamingText);
    }
  } else if (event.type === 'content_block_start') {
    if (event.content_block?.type === 'tool_use') addToolMessage(event.content_block.name, 'running');
  } else if (event.type === 'content_block_stop') {
    hideToolProgress();
  }
}

function handleAssistantMsg(message) {
  if (!message?.content) return;
  for (const block of message.content) {
    if (block.type === 'tool_use') addToolMessage(block.name, 'complete');
  }
}

// ============================================================
// Sessions Panel (overlay)
// ============================================================
function showSessionsPanel(sessions) {
  let panel = document.getElementById('sessions-panel');
  if (panel) { panel.remove(); return; }
  panel = document.createElement('div');
  panel.id = 'sessions-panel';
  panel.className = 'sessions-panel';
  panel.innerHTML = `
    <div class="sp-header">
      <span>Past Conversations</span>
      <button class="sp-close" onclick="document.getElementById('sessions-panel').remove()">&times;</button>
    </div>
    <div class="sp-list">
      ${sessions.length ? sessions.map(s => `
        <div class="sp-item" data-id="${s.id}">
          <div class="sp-title">${esc(s.title || 'Untitled')}</div>
          <div class="sp-date">${s.createdAt ? new Date(s.createdAt).toLocaleDateString() : ''}</div>
          <button class="sp-delete" data-id="${s.id}" title="Delete">&times;</button>
        </div>
      `).join('') : '<div class="sp-empty">No past conversations</div>'}
    </div>`;
  document.body.appendChild(panel);
  panel.querySelectorAll('.sp-item').forEach(el => {
    el.addEventListener('click', (e) => {
      if (e.target.classList.contains('sp-delete')) {
        vscode.postMessage({ type: 'delete_session', sessionId: e.target.dataset.id });
        e.target.closest('.sp-item')?.remove();
        return;
      }
      vscode.postMessage({ type: 'get_session', sessionId: el.dataset.id });
      panel.remove();
    });
  });
}

// ============================================================
// MCP Server Management
// ============================================================
function updateMcpBadge() {
  const connected = S.mcpServers.filter(s => s.status === 'connected').length;
  const total = S.mcpServers.length;
  const $badge = $('mcp-badge');
  if ($badge) $badge.textContent = connected > 0 ? connected : '';
}

function showMcpPanel() {
  let panel = document.getElementById('mcp-panel');
  if (panel) { panel.remove(); return; }
  panel = document.createElement('div');
  panel.id = 'mcp-panel';
  panel.className = 'mcp-panel';
  panel.innerHTML = `
    <div class="sp-header">
      <span>MCP Servers</span>
      <button class="sp-close" onclick="document.getElementById('mcp-panel').remove()">&times;</button>
    </div>
    <div class="sp-list">
      ${S.mcpServers.length ? S.mcpServers.map(s => `
        <div class="mcp-item" data-name="${esc(s.name)}">
          <div class="mcp-status-dot ${s.status === 'connected' ? 'mcp-on' : 'mcp-off'}"></div>
          <div class="mcp-info">
            <div class="mcp-name">${esc(s.name)}</div>
            <div class="mcp-status-text">${s.status}</div>
          </div>
          <div class="mcp-actions">
            ${s.status === 'connected'
              ? `<button class="mcp-btn mcp-disable" data-name="${esc(s.name)}">Disable</button>`
              : `<button class="mcp-btn mcp-enable" data-name="${esc(s.name)}">Enable</button>`}
            <button class="mcp-btn mcp-reconnect" data-name="${esc(s.name)}">Reconnect</button>
          </div>
        </div>
      `).join('') : '<div class="sp-empty">No MCP servers configured</div>'}
    </div>`;
  document.body.appendChild(panel);
  panel.querySelectorAll('.mcp-enable').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      vscode.postMessage({ type: 'mcp_toggle', name: btn.dataset.name, enabled: true });
      btn.closest('.mcp-item').querySelector('.mcp-status-dot').className = 'mcp-status-dot mcp-on';
      btn.closest('.mcp-item').querySelector('.mcp-status-text').textContent = 'connected';
    });
  });
  panel.querySelectorAll('.mcp-disable').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      vscode.postMessage({ type: 'mcp_toggle', name: btn.dataset.name, enabled: false });
      btn.closest('.mcp-item').querySelector('.mcp-status-dot').className = 'mcp-status-dot mcp-off';
      btn.closest('.mcp-item').querySelector('.mcp-status-text').textContent = 'disabled';
    });
  });
  panel.querySelectorAll('.mcp-reconnect').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      vscode.postMessage({ type: 'reconnect_mcp_server', name: btn.dataset.name });
    });
  });
  setTimeout(() => {
    const closeHandler = (e) => { if (!panel.contains(e.target)) { panel.remove(); document.removeEventListener('click', closeHandler); } };
    document.addEventListener('click', closeHandler);
  }, 100);
}

// ============================================================
// Model Picker
// ============================================================
function showModelPicker() {
  const existing = document.getElementById('model-picker');
  if (existing) { existing.remove(); return; }
  const models = [
    { label: 'Default', value: '' },
    { label: 'Claude Opus 4.6', value: 'anthropic/claude-opus-4-6' },
    { label: 'Claude Sonnet 4.6', value: 'anthropic/claude-sonnet-4-6' },
    { label: 'GPT-4.1', value: 'openai/gpt-4.1' },
    { label: 'Gemini 2.5 Pro', value: 'google/gemini-2.5-pro' },
    { label: 'Qwen 3 235B', value: 'qwen/qwen3-235b-a22b' },
  ];
  const picker = document.createElement('div');
  picker.id = 'model-picker';
  picker.className = 'model-picker';
  if ($modelBtn) {
    const rect = $modelBtn.getBoundingClientRect();
    picker.style.top = (rect.bottom + 4) + 'px';
    picker.style.left = rect.left + 'px';
  }
  picker.innerHTML = `
    <div class="mp-header">Select Model</div>
    ${models.map(m => `<div class="mp-item${m.value === S.currentModel ? ' active' : ''}" data-value="${m.value}">${m.label}</div>`).join('')}`;
  document.body.appendChild(picker);
  picker.querySelectorAll('.mp-item').forEach(el => {
    el.addEventListener('click', (e) => {
      e.stopPropagation();
      S.currentModel = el.dataset.value;
      if ($modelLabel) $modelLabel.textContent = el.textContent;
      vscode.postMessage({ type: 'set_model', model: el.dataset.value });
      picker.remove();
    });
  });
  setTimeout(() => {
    const closeHandler = (e) => { if (!picker.contains(e.target)) { picker.remove(); document.removeEventListener('click', closeHandler); } };
    document.addEventListener('click', closeHandler);
  }, 100);
}

// ============================================================
// Permission Mode Cycle
// ============================================================
const MODES = ['default', 'plan', 'acceptEdits', 'bypassPermissions'];
const MODE_LABELS = { default: 'Default', plan: 'Plan', acceptEdits: 'Accept Edits', bypassPermissions: 'Bypass' };
function cyclePermissionMode() {
  const idx = MODES.indexOf(S.permissionMode);
  const next = MODES[(idx + 1) % MODES.length];
  S.permissionMode = next;
  if ($modeBtn) $modeBtn.textContent = MODE_LABELS[next];
  vscode.postMessage({ type: 'set_permission_mode', mode: next });
}

// ============================================================
// Events
// ============================================================
$sendBtn?.addEventListener('click', sendMessage);
$stopBtn?.addEventListener('click', stopGeneration);
$newChatBtn?.addEventListener('click', newConversation);
$newChatBtnTop?.addEventListener('click', newConversation);
$contextDismiss?.addEventListener('click', () => { if ($contextBadge) $contextBadge.style.display = 'none'; S.activeFile = null; });
$modelBtn?.addEventListener('click', (e) => { e.stopPropagation(); showModelPicker(); });
const $mcpBtn = $('mcp-btn');
$mcpBtn?.addEventListener('click', (e) => { e.stopPropagation(); showMcpPanel(); });
$sessionsBtn?.addEventListener('click', () => vscode.postMessage({ type: 'list_sessions' }));
$settingsBtn?.addEventListener('click', () => vscode.postMessage({ type: 'open_config' }));
$modeBtn?.addEventListener('click', cyclePermissionMode);
$permAllow?.addEventListener('click', () => {
  if (S.pendingPermission) vscode.postMessage({ type: 'control_response', request_id: S.pendingPermission.request_id, response: { approved: true } });
  hidePermissionBar();
});
$permDeny?.addEventListener('click', () => {
  if (S.pendingPermission) vscode.postMessage({ type: 'control_response', request_id: S.pendingPermission.request_id, response: { approved: false } });
  hidePermissionBar();
});

$userInput?.addEventListener('input', autoResize);
$userInput?.addEventListener('keydown', (e) => {
  const useCtrlEnter = S.settings?.useCtrlEnterToSend;
  if (e.key === 'Enter') {
    if (useCtrlEnter) { if (e.metaKey || e.ctrlKey) { e.preventDefault(); sendMessage(); } }
    else { if (!e.shiftKey && !e.metaKey && !e.ctrlKey) { e.preventDefault(); sendMessage(); } }
  }
  if (e.key === '@') {
    vscode.postMessage({ type: 'insertAtMention' });
  }
  if (e.key === '/' && e.target.value === '') {
    // Could show command palette
  }
});

window.addEventListener('message', (event) => { if (event.data?.type) handleMsg(event.data); });

// Init
vscode.postMessage({ type: 'ready' });
vscode.postMessage({ type: 'getSettings' });
vscode.postMessage({ type: 'get_auth_status' });
