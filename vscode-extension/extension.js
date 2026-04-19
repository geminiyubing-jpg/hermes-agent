const vscode = require('vscode');
const { spawn, execSync } = require('child_process');
const { createInterface } = require('readline');
const path = require('path');
const fs = require('fs');
const os = require('os');
const crypto = require('crypto');

// ============================================================
// Constants
// ============================================================
const WEBVIEW_ID = 'hermes.chatView';
const OUTPUT_CHANNEL_NAME = 'Hermes Agent';
const SESSIONS_DIR = path.join(os.homedir(), '.hermes', 'vscode-sessions');

// ============================================================
// Global State
// ============================================================
let outputChannel;
let sidebarProvider;
let panelProvider;

// ============================================================
// Session Storage
// ============================================================
class SessionStore {
  constructor() {
    this.sessionsDir = SESSIONS_DIR;
    if (!fs.existsSync(this.sessionsDir)) {
      fs.mkdirSync(this.sessionsDir, { recursive: true });
    }
  }

  getSessionDir(sessionId) {
    return path.join(this.sessionsDir, sessionId);
  }

  listSessions() {
    if (!fs.existsSync(this.sessionsDir)) return [];
    return fs.readdirSync(this.sessionsDir)
      .filter(d => fs.statSync(path.join(this.sessionsDir, d)).isDirectory())
      .map(id => {
        const metaPath = path.join(this.sessionsDir, id, 'meta.json');
        try {
          const meta = JSON.parse(fs.readFileSync(metaPath, 'utf8'));
          return { id, ...meta };
        } catch {
          return { id, title: 'Untitled', createdAt: Date.now() };
        }
      })
      .sort((a, b) => (b.createdAt || 0) - (a.createdAt || 0));
  }

  saveSessionMeta(sessionId, meta) {
    const dir = this.getSessionDir(sessionId);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    const metaPath = path.join(dir, 'meta.json');
    let existing = {};
    try { existing = JSON.parse(fs.readFileSync(metaPath, 'utf8')); } catch {}
    fs.writeFileSync(metaPath, JSON.stringify({ ...existing, ...meta }, null, 2));
  }

  saveMessages(sessionId, messages) {
    const dir = this.getSessionDir(sessionId);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, 'messages.json'), JSON.stringify(messages, null, 2));
  }

  loadMessages(sessionId) {
    try {
      return JSON.parse(fs.readFileSync(path.join(this.getSessionDir(sessionId), 'messages.json'), 'utf8'));
    } catch { return []; }
  }

  deleteSession(sessionId) {
    const dir = this.getSessionDir(sessionId);
    if (fs.existsSync(dir)) {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  }
}

const sessionStore = new SessionStore();

// ============================================================
// MCP Server Config (reads from ~/.hermes/config.yaml)
// ============================================================
function getMcpServers() {
  const configPath = path.join(os.homedir(), '.hermes', 'config.yaml');
  const servers = {};
  try {
    const raw = fs.readFileSync(configPath, 'utf8');
    // Minimal YAML parser: extract mcp_servers section
    const match = raw.match(/mcp_servers:\s*\n([\s\S]*?)(?=\n[a-z]|\n*$)/);
    if (match) {
      const section = match[1];
      // Parse simple key-value pairs like:
      //   server_name:
      //     command: ...
      //     args: [...]
      let currentName = null;
      let currentConfig = {};
      for (const line of section.split('\n')) {
        const nameMatch = line.match(/^  (\w+):\s*$/);
        if (nameMatch) {
          if (currentName) servers[currentName] = currentConfig;
          currentName = nameMatch[1];
          currentConfig = {};
          continue;
        }
        const cmdMatch = line.match(/^    command:\s*["']?(.+?)["']?\s*$/);
        if (cmdMatch && currentName) currentConfig.command = cmdMatch[1];
        const argsMatch = line.match(/^    args:\s*\[(.+)\]\s*$/);
        if (argsMatch && currentName) {
          try { currentConfig.args = JSON.parse('[' + argsMatch[1] + ']'); } catch {}
        }
      }
      if (currentName) servers[currentName] = currentConfig;
    }
  } catch {}
  return servers;
}

// ============================================================
// Extension Activate / Deactivate
// ============================================================
function activate(context) {
  outputChannel = vscode.window.createOutputChannel(OUTPUT_CHANNEL_NAME);
  outputChannel.appendLine('Hermes Agent extension activated');

  checkHermesAvailable();

  // Register diff document provider for showing edits
  diffProvider = new DiffDocumentProvider();
  context.subscriptions.push(
    vscode.workspace.registerTextDocumentContentProvider('hermes-diff', diffProvider)
  );

  sidebarProvider = new HermesChatProvider(context, outputChannel, 'sidebar');
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(WEBVIEW_ID, sidebarProvider, {
      webviewOptions: { retainContextWhenHidden: true },
    })
  );

  // All commands
  const commands = {
    'hermes.open': () => openPanel(context),
    'hermes.openInTab': () => openPanel(context),
    'hermes.openInSidebar': () => vscode.commands.executeCommand('workbench.view.extension.hermes-sidebar'),
    'hermes.newConversation': () => getActiveProvider()?.newConversation(),
    'hermes.focus': () => getActiveProvider()?.postMessageToWebview({ type: 'focusInput' }),
    'hermes.blur': () => getActiveProvider()?.postMessageToWebview({ type: 'blurInput' }),
    'hermes.stop': () => getActiveProvider()?.stopGeneration(),
    'hermes.showLogs': () => outputChannel.show(),
    'hermes.insertAtMention': () => getActiveProvider()?.handleInsertAtMention(),
    'hermes.logout': () => getActiveProvider()?.handleLogout(),
  };

  for (const [cmd, handler] of Object.entries(commands)) {
    context.subscriptions.push(vscode.commands.registerCommand(cmd, handler));
  }

  // Track active editor for context
  context.subscriptions.push(
    vscode.window.onDidChangeActiveTextEditor((editor) => {
      getActiveProvider()?.sendSelectionChanged(editor);
    }),
    vscode.window.onDidChangeTextEditorSelection((event) => {
      getActiveProvider()?.sendSelectionChanged(event.textEditor, event.selections[0]);
    })
  );
}

function deactivate() {
  outputChannel?.appendLine('Hermes Agent extension deactivated');
  sidebarProvider?.dispose();
  panelProvider?.dispose();
}

// ============================================================
// Panel Management
// ============================================================
function openPanel(context) {
  if (panelProvider?.panel) { panelProvider.panel.reveal(); return; }
  panelProvider = new HermesChatProvider(context, outputChannel, 'panel');
  const panel = vscode.window.createWebviewPanel('hermesChatPanel', 'Hermes Agent', vscode.ViewColumn.Beside, {
    enableScripts: true, retainContextWhenHidden: true,
    localResourceRoots: [
      vscode.Uri.file(path.join(context.extensionPath, 'webview')),
      vscode.Uri.file(path.join(context.extensionPath, 'resources')),
    ],
  });
  panelProvider.setPanel(panel);
  panel.iconPath = vscode.Uri.file(path.join(context.extensionPath, 'resources', 'hermes-logo.svg'));
  panel.onDidDispose(() => { panelProvider = undefined; });
  context.subscriptions.push(panel);
}

function getActiveProvider() {
  return panelProvider?.panel ? panelProvider : sidebarProvider;
}

// ============================================================
// CLI Runner
// ============================================================
class CliRunner {
  constructor(outputChannel) {
    this.outputChannel = outputChannel;
    this.currentProcess = null;
  }

  getConfig() {
    const config = vscode.workspace.getConfiguration('hermes');
    return {
      cliCommand: config.get('cliCommand', 'hermes'),
      cwd: config.get('workingDirectory', '') || vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || process.cwd(),
      includeActiveFile: config.get('includeActiveFile', true),
      envVars: config.get('environmentVariables', []),
    };
  }

  async *runQuery(prompt, options = {}) {
    const config = this.getConfig();
    const env = { ...process.env };
    for (const { name, value } of config.envVars) { env[name] = value; }

    // Build hermes CLI command
    const cmdParts = config.cliCommand.split(/\s+/);
    const cmd = cmdParts[0];
    const baseArgs = cmdParts.slice(1);
    const args = [...baseArgs, '-q', prompt, '--quiet'];

    if (options.model) args.push('--model', options.model);
    if (options.resumeSessionId) args.push('--resume', options.resumeSessionId);
    if (options.permissionMode === 'bypassPermissions') args.push('--yolo');
    if (options.maxTurns) args.push('--max-turns', String(options.maxTurns));
    if (options.toolsets) args.push('--toolsets', options.toolsets);

    this.outputChannel.appendLine(`[CLI] ${cmd} ${args.join(' ')}`);

    this.currentProcess = spawn(cmd, args, { cwd: config.cwd, env, stdio: ['pipe', 'pipe', 'pipe'] });
    const rl = createInterface({ input: this.currentProcess.stdout });
    const stderrChunks = [];
    this.currentProcess.stderr.on('data', (chunk) => {
      stderrChunks.push(chunk.toString());
      this.outputChannel.appendLine(`[stderr] ${chunk.toString().trim()}`);
    });

    let accumulated = '';
    try {
      for await (const line of rl) {
        if (!line.trim()) continue;
        // In --quiet mode, hermes outputs the response text directly to stdout
        accumulated += line + '\n';
        yield { type: 'raw_text', text: line + '\n' };
      }
      // Parse session_id from stderr (hermes writes "session_id: XXX" to stderr in --quiet mode)
      const stderr = stderrChunks.join('');
      const sessionMatch = stderr.match(/session_id:\s*(\S+)/);
      if (sessionMatch) {
        this.lastSessionId = sessionMatch[1];
      }
      yield { type: 'result', subtype: 'success', result: accumulated.trim() };
    } finally {
      this.currentProcess = null;
    }
  }

  stop() {
    if (this.currentProcess && !this.currentProcess.killed) {
      this.currentProcess.kill('SIGTERM');
      setTimeout(() => { this.currentProcess?.kill?.('SIGKILL'); }, 3000);
      this.currentProcess = null;
    }
  }
}

// ============================================================
// Chat Provider
// ============================================================
class HermesChatProvider {
  constructor(context, outputChannel, mode) {
    this.context = context;
    this.outputChannel = outputChannel;
    this.mode = mode;
    this.view = null;
    this.panel = null;
    this.cliRunner = new CliRunner(outputChannel);
    this.conversationHistory = [];
    this.isGenerating = false;
    this.currentSessionId = crypto.randomUUID();
    this.permissionMode = 'default';
    this.currentModel = '';
    this.disposables = [];
  }

  setPanel(panel) {
    this.panel = panel;
    this.initWebview(panel.webview);
    panel.webview.onDidReceiveMessage((msg) => this.handleWebviewMessage(msg));
    panel.onDidDispose(() => this.dispose(), null, this.disposables);
  }

  resolveWebviewView(webviewView) {
    this.view = webviewView;
    this.initWebview(webviewView.webview);
    webviewView.webview.onDidReceiveMessage((msg) => this.handleWebviewMessage(msg));
  }

  initWebview(webview) {
    webview.options = {
      enableScripts: true,
      localResourceRoots: [
        vscode.Uri.file(path.join(this.context.extensionPath, 'webview')),
        vscode.Uri.file(path.join(this.context.extensionPath, 'resources')),
      ],
    };
    webview.html = this.getHtml(webview);
  }

  // ----------------------------------------------------------
  // FULL Message Handler
  // ----------------------------------------------------------
  async handleWebviewMessage(msg) {
    switch (msg.type) {
      // === Core ===
      case 'ready':
        this.postMessageToWebview({ type: 'init_response', version: '0.1.0' });
        this.sendAuthStatus();
        this.sendMcpServers();
        break;
      case 'sendMessage':
        await this.handleSendMessage(msg.content, msg.options);
        break;
      case 'stopGeneration':
        this.stopGeneration();
        break;
      case 'newConversation':
        this.newConversation();
        break;

      // === Model ===
      case 'set_model':
        this.currentModel = msg.model || '';
        this.postMessageToWebview({ type: 'set_model_response', model: this.currentModel });
        break;
      case 'set_thinking_level':
        this.postMessageToWebview({ type: 'set_thinking_level_response', level: msg.level });
        break;

      // === Permission ===
      case 'set_permission_mode':
        this.permissionMode = msg.mode || 'default';
        this.postMessageToWebview({ type: 'set_permission_mode_response', mode: this.permissionMode });
        break;
      case 'control_response':
        break;

      // === Sessions ===
      case 'list_sessions':
        this.postMessageToWebview({ type: 'list_sessions_response', sessions: sessionStore.listSessions() });
        break;
      case 'get_session':
        const msgs = sessionStore.loadMessages(msg.sessionId);
        this.postMessageToWebview({ type: 'get_session_response', sessionId: msg.sessionId, messages: msgs });
        break;
      case 'delete_session':
        sessionStore.deleteSession(msg.sessionId);
        this.postMessageToWebview({ type: 'delete_session_response', sessionId: msg.sessionId });
        break;
      case 'rename_session':
        sessionStore.saveSessionMeta(msg.sessionId, { title: msg.title });
        this.postMessageToWebview({ type: 'rename_session_response', sessionId: msg.sessionId });
        break;
      case 'fork_conversation':
        const forkedId = crypto.randomUUID();
        sessionStore.saveMessages(forkedId, this.conversationHistory);
        sessionStore.saveSessionMeta(forkedId, { title: 'Forked', createdAt: Date.now() });
        this.postMessageToWebview({ type: 'fork_conversation_response', sessionId: forkedId });
        break;

      // === File Operations ===
      case 'open_file':
        await this.handleOpenFile(msg.filePath, msg.line, msg.column);
        break;
      case 'open_diff':
        await this.handleOpenDiff(msg.filePath, msg.original, msg.modified);
        break;
      case 'open_file_diffs':
        if (msg.diffs) for (const d of msg.diffs) await this.handleOpenDiff(d.filePath, d.original, d.modified);
        break;
      case 'open_in_editor':
        await this.handleOpenFile(msg.filePath);
        break;
      case 'list_files':
        const files = await vscode.workspace.findFiles('**/*', '**/node_modules/**', 100);
        this.postMessageToWebview({ type: 'list_files_response', files: files.map(f => vscode.workspace.asRelativePath(f)) });
        break;
      case 'open_folder':
        vscode.commands.executeCommand('vscode.openFolder', vscode.Uri.file(msg.path));
        break;
      case 'open_folder_in_new_window':
        vscode.commands.executeCommand('vscode.openFolder', vscode.Uri.file(msg.path), true);
        break;
      case 'open_url':
        vscode.env.openExternal(vscode.Uri.parse(msg.url));
        break;
      case 'open_config':
        vscode.commands.executeCommand('workbench.action.openSettings', 'hermes');
        break;
      case 'open_config_file':
        const settingsPath = path.join(os.homedir(), '.hermes', 'config.yaml');
        try {
          const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(settingsPath));
          await vscode.window.showTextDocument(doc);
        } catch { vscode.window.showErrorMessage('Settings file not found'); }
        break;

      // === Edit Operations ===
      case 'applyEdit':
        await this.handleApplyEdit(msg.filePath, msg.content);
        break;
      case 'acceptProposedDiff':
      case 'rejectProposedDiff':
        break;

      // === Git ===
      case 'check_git_status':
        this.handleGitStatus();
        break;
      case 'checkout_branch':
        this.handleCheckoutBranch(msg.branch);
        break;
      case 'create_worktree':
        this.handleCreateWorktree(msg.branch);
        break;

      // === Terminal ===
      case 'open_terminal':
        const term = vscode.window.createTerminal('Hermes');
        term.show();
        term.sendText(msg.command || '');
        this.postMessageToWebview({ type: 'open_terminal_response' });
        break;
      case 'get_terminal_contents':
        this.postMessageToWebview({ type: 'get_terminal_contents_response', content: '' });
        break;
      case 'open_hermes_in_terminal':
        vscode.commands.executeCommand('hermes.openInTerminal');
        break;

      // === Context ===
      case 'get_current_selection':
        this.sendSelectionChanged(vscode.window.activeTextEditor);
        break;
      case 'get_context_usage':
        this.postMessageToWebview({ type: 'get_context_usage_response', used: 0, total: 200000 });
        break;

      // === MCP ===
      case 'get_mcp_servers':
        this.sendMcpServers();
        break;
      case 'set_mcp_server_enabled':
        this.postMessageToWebview({ type: 'set_mcp_server_enabled_response', name: msg.name });
        break;
      case 'reconnect_mcp_server':
        this.postMessageToWebview({ type: 'reconnect_mcp_server_response', name: msg.name });
        break;
      case 'authenticate_mcp_server':
        vscode.window.showInformationMessage(`MCP auth for ${msg.name}`);
        break;
      case 'mcp_toggle':
        this.postMessageToWebview({ type: 'mcp_status', name: msg.name, enabled: msg.enabled });
        break;

      // === Auth ===
      case 'login':
        this.handleLogin();
        break;
      case 'logout':
        this.handleLogout();
        break;
      case 'get_auth_status':
        this.sendAuthStatus();
        break;

      // === Settings ===
      case 'getSettings':
        const cfg = vscode.workspace.getConfiguration('hermes');
        this.postMessageToWebview({
          type: 'getSettings',
          settings: {
            includeActiveFile: cfg.get('includeActiveFile', true),
            autosave: cfg.get('autosave', true),
            useCtrlEnterToSend: cfg.get('useCtrlEnterToSend', false),
            permissionMode: this.permissionMode,
            model: this.currentModel,
          },
        });
        break;
      case 'apply_settings':
        this.postMessageToWebview({ type: 'apply_settings_response', success: true });
        break;

      // === Usage ===
      case 'request_usage_update':
        this.postMessageToWebview({ type: 'request_usage_update_response', usage: {} });
        break;

      // === Misc ===
      case 'insertAtMention':
        await this.handleInsertAtMention();
        break;
      case 'show_notification':
        if (msg.level === 'error') vscode.window.showErrorMessage(msg.message);
        else if (msg.level === 'warning') vscode.window.showWarningMessage(msg.message);
        else vscode.window.showInformationMessage(msg.message || msg.text || '');
        break;
      case 'open_output_panel':
        outputChannel.show();
        break;
      case 'open_help':
        vscode.env.openExternal(vscode.Uri.parse('https://github.com/NousResearch/hermes-agent'));
        break;
      case 'open_markdown_preview':
        if (msg.filePath) {
          const d = await vscode.workspace.openTextDocument(vscode.Uri.file(msg.filePath));
          await vscode.commands.executeCommand('markdown.showPreviewToSide', d.uri);
        }
        break;
      case 'log_event':
        this.outputChannel.appendLine(`[webview] ${msg.event || msg.message || ''}`);
        break;
      case 'dismiss_onboarding':
        vscode.workspace.getConfiguration('hermes').update('hideOnboarding', true, true);
        this.postMessageToWebview({ type: 'dismiss_onboarding_response' });
        break;
      case 'generate_session_title':
        const firstMsg = this.conversationHistory.find(m => m.role === 'user');
        const title = firstMsg?.content?.slice(0, 50) || 'New Chat';
        sessionStore.saveSessionMeta(this.currentSessionId, { title, createdAt: Date.now() });
        this.postMessageToWebview({ type: 'generate_session_title_response', title });
        break;
      case 'exec':
        try {
          const result = execSync(msg.command, { cwd: vscode.workspace.workspaceFolders?.[0]?.uri.fsPath, timeout: 10000 });
          this.postMessageToWebview({ type: 'exec_response', stdout: result.toString(), exitCode: 0 });
        } catch (e) {
          this.postMessageToWebview({ type: 'exec_response', stdout: e.stdout?.toString() || '', stderr: e.stderr?.toString() || e.message, exitCode: e.status || 1 });
        }
        break;
    }
  }

  // ----------------------------------------------------------
  // Core: Send Message
  // ----------------------------------------------------------
  async handleSendMessage(content, options = {}) {
    if (this.isGenerating) return;
    this.isGenerating = true;
    this.postMessageToWebview({ type: 'generationStarted' });

    // Use --resume for subsequent messages in the same session
    const hasHistory = this.conversationHistory.length > 0;
    const resumeId = hasHistory ? this.currentSessionId : undefined;

    let assistantText = '';
    try {
      for await (const cliMsg of this.cliRunner.runQuery(content, {
        model: options?.model || this.currentModel || undefined,
        resumeSessionId: resumeId,
        permissionMode: this.permissionMode !== 'default' ? this.permissionMode : undefined,
      })) {
        this.forwardCliMessage(cliMsg);
        if (cliMsg.type === 'raw_text') {
          assistantText += cliMsg.text;
        } else if (cliMsg.type === 'result' && cliMsg.result && !assistantText) {
          assistantText = cliMsg.result;
        }
      }
      // Capture session ID from CLI if available
      if (this.cliRunner.lastSessionId) {
        this.currentSessionId = this.cliRunner.lastSessionId;
      }
      this.conversationHistory.push({ role: 'user', content }, { role: 'assistant', content: assistantText });
      sessionStore.saveMessages(this.currentSessionId, this.conversationHistory);
      sessionStore.saveSessionMeta(this.currentSessionId, { updatedAt: Date.now() });
    } catch (err) {
      this.outputChannel.appendLine(`Error: ${err.message}`);
      this.postMessageToWebview({ type: 'error', content: err.message });
    }

    this.isGenerating = false;
    this.postMessageToWebview({ type: 'generationComplete' });
  }

  forwardCliMessage(msg) {
    const map = {
      system: { type: 'systemInit' },
      stream_event: { type: 'streamToken' },
      assistant: { type: 'assistantMessage' },
      tool_progress: { type: 'toolProgress' },
      control_request: { type: 'tool_permission_request' },
      raw_text: { type: 'rawText' },
    };
    const mapping = map[msg.type];
    if (!mapping) {
      if (msg.type === 'result') {
        this.postMessageToWebview({
          type: 'result', subtype: msg.subtype, result: msg.result,
          costUsd: msg.total_cost_usd, durationMs: msg.duration_ms,
          numTurns: msg.num_turns, isError: msg.is_error,
        });
      }
      return;
    }
    this.postMessageToWebview({ ...msg, ...mapping });
  }

  // ----------------------------------------------------------
  // Session Management
  // ----------------------------------------------------------
  newConversation() {
    this.conversationHistory = [];
    this.currentSessionId = crypto.randomUUID();
    sessionStore.saveSessionMeta(this.currentSessionId, { title: 'New Chat', createdAt: Date.now() });
    this.postMessageToWebview({ type: 'newConversation', sessionId: this.currentSessionId });
  }

  // ----------------------------------------------------------
  // File Operations
  // ----------------------------------------------------------
  getActiveFileContext() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) return null;
    const doc = editor.document;
    return { filePath: doc.fileName, language: doc.languageId, content: doc.getText(), selection: editor.selection.isEmpty ? null : doc.getText(editor.selection) };
  }

  sendSelectionChanged(editor, selection) {
    if (!editor) return;
    const sel = selection || editor.selection;
    this.postMessageToWebview({
      type: 'selection_changed',
      fileName: editor.document.fileName,
      language: editor.document.languageId,
      selection: sel && !sel.isEmpty ? editor.document.getText(sel) : null,
    });
  }

  async handleOpenFile(filePath, line, column) {
    try {
      const doc = await vscode.workspace.openTextDocument(filePath);
      const editor = await vscode.window.showTextDocument(doc, { preview: true });
      if (line) {
        const pos = new vscode.Position(line - 1, (column || 1) - 1);
        editor.selection = new vscode.Selection(pos, pos);
        editor.revealRange(new vscode.Range(pos, pos));
      }
      this.postMessageToWebview({ type: 'open_file_response', filePath });
    } catch (err) {
      vscode.window.showErrorMessage(`Cannot open file: ${err.message}`);
    }
  }

  async handleOpenDiff(filePath, original, modified) {
    try {
      const name = path.basename(filePath || 'untitled');
      const originalUri = vscode.Uri.parse(`hermes-diff:///${name}.original`);
      const modifiedUri = vscode.Uri.parse(`hermes-diff:///${name}.modified`);
      if (diffProvider) {
        diffProvider.setDocument(originalUri.toString(), original || '');
        diffProvider.setDocument(modifiedUri.toString(), modified || '');
      }
      await vscode.commands.executeCommand('vscode.diff', originalUri, modifiedUri, `${name} (Hermes Diff)`);
      this.postMessageToWebview({ type: 'open_diff_response', filePath });
    } catch (err) {
      vscode.window.showErrorMessage(`Diff error: ${err.message}`);
    }
  }

  async handleApplyEdit(filePath, content) {
    try {
      const cfg = vscode.workspace.getConfiguration('hermes');
      if (cfg.get('autosave', true)) await vscode.workspace.saveAll(false);

      const uri = filePath ? vscode.Uri.file(filePath) : vscode.window.activeTextEditor?.document?.uri;
      if (!uri) { vscode.window.showWarningMessage('No file to apply edit to'); return; }

      const edit = new vscode.WorkspaceEdit();
      try {
        const doc = await vscode.workspace.openTextDocument(uri);
        const fullRange = new vscode.Range(doc.lineAt(0).range.start, doc.lineAt(doc.lineCount - 1).range.end);
        edit.replace(uri, fullRange, content);
      } catch {
        edit.createFile(uri, { ignoreIfExists: true });
        edit.insert(uri, new vscode.Position(0, 0), content);
      }
      await vscode.workspace.applyEdit(edit);
      this.postMessageToWebview({ type: 'applyEdit', success: true, filePath: uri.fsPath });
    } catch (err) {
      vscode.window.showErrorMessage(`Apply failed: ${err.message}`);
      this.postMessageToWebview({ type: 'applyEdit', success: false, error: err.message });
    }
  }

  // ----------------------------------------------------------
  // Git
  // ----------------------------------------------------------
  async handleGitStatus() {
    try {
      const cwd = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
      const status = execSync('git status --porcelain', { cwd, timeout: 5000 }).toString();
      const branch = execSync('git branch --show-current', { cwd, timeout: 5000 }).toString().trim();
      this.postMessageToWebview({ type: 'check_git_status_response', status, branch, clean: !status.trim() });
    } catch (err) {
      this.postMessageToWebview({ type: 'check_git_status_response', status: '', branch: '', clean: true, error: err.message });
    }
  }

  async handleCheckoutBranch(branch) {
    try {
      const cwd = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
      execSync(`git checkout ${branch}`, { cwd, timeout: 10000 });
      this.postMessageToWebview({ type: 'checkout_branch_response', branch, success: true });
      vscode.window.showInformationMessage(`Switched to branch ${branch}`);
    } catch (err) {
      this.postMessageToWebview({ type: 'checkout_branch_response', branch, success: false, error: err.message });
    }
  }

  async handleCreateWorktree(branch) {
    try {
      const cwd = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
      const worktreePath = path.join(cwd, '..', `${path.basename(cwd)}-${branch}`);
      execSync(`git worktree add "${worktreePath}" -b ${branch || 'new-branch'}`, { cwd, timeout: 10000 });
      this.postMessageToWebview({ type: 'create_worktree_response', path: worktreePath, success: true });
      const open = await vscode.window.showInformationMessage(`Worktree created at ${worktreePath}`, 'Open');
      if (open) vscode.commands.executeCommand('vscode.openFolder', vscode.Uri.file(worktreePath), true);
    } catch (err) {
      this.postMessageToWebview({ type: 'create_worktree_response', success: false, error: err.message });
    }
  }

  // ----------------------------------------------------------
  // Auth
  // ----------------------------------------------------------
  sendAuthStatus() {
    const hermesHome = path.join(os.homedir(), '.hermes');
    const envPath = path.join(hermesHome, '.env');
    const configPath = path.join(hermesHome, 'config.yaml');
    const hasEnv = fs.existsSync(envPath);
    const hasConfig = fs.existsSync(configPath);

    this.postMessageToWebview({
      type: 'get_auth_status_response',
      authenticated: hasEnv || hasConfig,
      provider: 'multi',
      model: this.currentModel || 'default',
    });
  }

  async handleLogin() {
    const key = await vscode.window.showInputBox({
      prompt: 'Enter your API key (saved to ~/.hermes/.env)',
      password: true,
      ignoreFocusOut: true,
    });
    if (key) {
      const hermesHome = path.join(os.homedir(), '.hermes');
      if (!fs.existsSync(hermesHome)) fs.mkdirSync(hermesHome, { recursive: true });
      const envPath = path.join(hermesHome, '.env');
      let envContent = '';
      if (fs.existsSync(envPath)) envContent = fs.readFileSync(envPath, 'utf8');
      if (!envContent.includes('OPENAI_API_KEY=')) {
        envContent += `\nOPENAI_API_KEY=${key}`;
      } else {
        envContent = envContent.replace(/OPENAI_API_KEY=.*/, `OPENAI_API_KEY=${key}`);
      }
      fs.writeFileSync(envPath, envContent);
      process.env.OPENAI_API_KEY = key;
      this.postMessageToWebview({ type: 'login_response', success: true });
      vscode.window.showInformationMessage('API key saved to ~/.hermes/.env');
    }
  }

  handleLogout() {
    delete process.env.OPENAI_API_KEY;
    delete process.env.ANTHROPIC_API_KEY;
    this.postMessageToWebview({ type: 'login_response', success: false, loggedOut: true });
    vscode.window.showInformationMessage('Logged out (cleared session keys)');
  }

  // ----------------------------------------------------------
  // MCP
  // ----------------------------------------------------------
  sendMcpServers() {
    const servers = getMcpServers();
    const serverList = Object.entries(servers).map(([name, config]) => ({
      name, command: config.command, enabled: true,
    }));
    this.postMessageToWebview({ type: 'get_mcp_servers_response', servers: serverList });
  }

  // ----------------------------------------------------------
  // @Mention
  // ----------------------------------------------------------
  async handleInsertAtMention() {
    const items = [
      { label: '$(file) File...', kind: vscode.QuickPickItemKind.Default, type: 'file' },
      { label: '$(symbol-method) Symbol...', kind: vscode.QuickPickItemKind.Default, type: 'symbol' },
      { label: '$(selection) Selection', kind: vscode.QuickPickItemKind.Default, type: 'selection' },
      { label: '$(git-branch) Git Branch', kind: vscode.QuickPickItemKind.Default, type: 'git' },
    ];
    const picked = await vscode.window.showQuickPick(items, { placeHolder: 'Insert reference' });
    if (!picked) return;

    if (picked.type === 'file') {
      const files = await vscode.workspace.findFiles('**/*', '**/node_modules/**', 50);
      const fileItems = files.map(f => ({ label: path.basename(f.fsPath), description: vscode.workspace.asRelativePath(f) }));
      const fp = await vscode.window.showQuickPick(fileItems, { placeHolder: 'Select file' });
      if (fp) {
        const fileContent = fs.readFileSync(files.find(f => vscode.workspace.asRelativePath(f) === fp.description)?.fsPath || '', 'utf8').slice(0, 5000);
        this.postMessageToWebview({ type: 'insertMention', mention: `@${fp.description}`, content: fileContent });
      }
    } else if (picked.type === 'selection') {
      const sel = vscode.window.activeTextEditor?.selection;
      if (sel && !sel.isEmpty) {
        const text = vscode.window.activeTextEditor.document.getText(sel);
        this.postMessageToWebview({ type: 'insertMention', mention: text });
      }
    } else if (picked.type === 'git') {
      try {
        const cwd = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        const branches = execSync('git branch -a --format=%(refname:short)', { cwd, timeout: 5000 }).toString().trim().split('\n');
        const bp = await vscode.window.showQuickPick(branches, { placeHolder: 'Select branch' });
        if (bp) this.postMessageToWebview({ type: 'insertMention', mention: `@branch:${bp}` });
      } catch {}
    }
  }

  // ----------------------------------------------------------
  // Stop / Post / Dispose
  // ----------------------------------------------------------
  stopGeneration() {
    this.cliRunner.stop();
    this.isGenerating = false;
    this.postMessageToWebview({ type: 'generationComplete', stopped: true });
  }

  postMessageToWebview(msg) {
    try {
      this.panel?.webview?.postMessage(msg);
      this.view?.webview?.postMessage(msg);
    } catch {}
  }

  dispose() {
    this.cliRunner.stop();
    this.disposables.forEach(d => d.dispose());
    this.disposables = [];
    this.view = null;
    this.panel = null;
  }

  // ----------------------------------------------------------
  // HTML
  // ----------------------------------------------------------
  getHtml(webview) {
    const nonce = getNonce();
    const cssUri = webview.asWebviewUri(vscode.Uri.file(path.join(this.context.extensionPath, 'webview', 'custom.css')));
    const jsUri = webview.asWebviewUri(vscode.Uri.file(path.join(this.context.extensionPath, 'webview', 'index.js')));
    const welcomeDark = webview.asWebviewUri(vscode.Uri.file(path.join(this.context.extensionPath, 'resources', 'welcome-art-dark.svg')));
    const welcomeLight = webview.asWebviewUri(vscode.Uri.file(path.join(this.context.extensionPath, 'resources', 'welcome-art-light.svg')));

    return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline'; img-src ${webview.cspSource}; script-src ${webview.cspSource} 'nonce-${nonce}';">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="${cssUri}">
</head>
<body>
<div id="root">
  <div id="toolbar" class="toolbar">
    <button id="model-btn" class="toolbar-btn" title="Select Model">
      <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M8 1l2 5h5l-4 3.5 1.5 5L8 11.5 3.5 14.5 5 9.5 1 6h5z"/></svg>
      <span id="model-label">Default</span>
    </button>
    <div class="toolbar-spacer"></div>
    <button id="mcp-btn" class="toolbar-btn" title="MCP Servers">
      <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M1.5 1h5l1 3-2 2v4l2 2-1 3h-5l1-3-2-2V6l2-2-1-3zm8 0h5l1 3-2 2v4l2 2-1 3h-5l1-3-2-2V6l2-2-1-3z"/></svg>
      <span id="mcp-badge" class="mcp-badge"></span>
    </button>
    <button id="sessions-btn" class="toolbar-btn" title="Past Conversations">
      <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M1 3a2 2 0 012-2h10a2 2 0 012 2v1H1V3zm0 3h14v7a2 2 0 01-2 2H3a2 2 0 01-2-2V6z"/></svg>
    </button>
    <button id="new-chat-btn-top" class="toolbar-btn" title="New Conversation">
      <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M8 1v14M1 8h14" stroke="currentColor" stroke-width="2" fill="none"/></svg>
    </button>
    <button id="settings-btn" class="toolbar-btn" title="Settings">
      <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M8 4.754a3.246 3.246 0 100 6.492 3.246 3.246 0 000-6.492zM5.754 8a2.246 2.246 0 114.492 0 2.246 2.246 0 01-4.492 0z"/><path d="M9.796 1.343c-.527-1.79-3.065-1.79-3.592 0l-.094.319a.873.873 0 01-1.255.52l-.292-.16c-1.64-.892-3.433.902-2.54 2.541l.159.292a.873.873 0 01-.52 1.255l-.319.094c-1.79.527-1.79 3.065 0 3.592l.319.094a.873.873 0 01.52 1.255l-.16.292c-.892 1.64.901 3.434 2.541 2.54l.292-.159a.873.873 0 011.255.52l.094.319c.527 1.79 3.065 1.79 3.592 0l.094-.319a.873.873 0 011.255-.52l.292.16c1.64.893 3.434-.902 2.54-2.541l-.159-.292a.873.873 0 01.52-1.255l.319-.094c1.79-.527 1.79-3.065 0-3.592l-.319-.094a.873.873 0 01-.52-1.255l.16-.292c.893-1.64-.902-3.433-2.541-2.54l-.292.159a.873.873 0 01-1.255-.52l-.094-.319z"/></svg>
    </button>
  </div>

  <div id="welcome-screen" class="welcome-screen">
    <div class="welcome-content">
      <div class="welcome-art"><img class="welcome-art-dark" src="${welcomeDark}" /><img class="welcome-art-light" src="${welcomeLight}" /></div>
      <h1 class="welcome-title">Hermes Agent</h1>
      <p class="welcome-subtitle">Your self-improving AI coding partner. Ask questions, edit code, understand projects.</p>
      <div class="welcome-hints">
        <div class="hint-item"><span class="hint-icon">@</span> Mention files for context</div>
        <div class="hint-item"><span class="hint-icon">/</span> Use slash commands</div>
        <div class="hint-item"><span class="hint-icon">&#8984;Esc</span> Focus / blur input</div>
      </div>
    </div>
  </div>

  <div id="messages-container" class="messages-container" style="display:none">
    <div id="messages" class="messages"></div>
  </div>

  <div id="tool-progress" class="tool-progress" style="display:none">
    <div class="tool-progress-bar"><div class="tool-progress-fill"></div></div>
    <span class="tool-progress-text"></span>
  </div>

  <div id="permission-bar" class="permission-bar" style="display:none">
    <span class="permission-text"></span>
    <button class="perm-btn perm-allow" id="perm-allow">Allow</button>
    <button class="perm-btn perm-deny" id="perm-deny">Deny</button>
  </div>

  <div id="input-area" class="input-area">
    <div id="context-badge" class="context-badge" style="display:none">
      <span class="context-file-icon">&#128196;</span>
      <span id="context-filename"></span>
      <button id="context-dismiss" class="context-dismiss">&times;</button>
    </div>
    <div class="input-wrapper">
      <textarea id="user-input" placeholder="Ask Hermes..." rows="1" spellcheck="false"></textarea>
      <div class="input-actions">
        <button id="send-btn" class="icon-btn send-btn" title="Send (Enter)">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M1 8l7-7v4h7v6H8v4L1 8z" transform="rotate(90 8 8)"/></svg>
        </button>
        <button id="stop-btn" class="icon-btn stop-btn" style="display:none" title="Stop">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><rect x="3" y="3" width="10" height="10" rx="2"/></svg>
        </button>
      </div>
    </div>
    <div class="input-footer">
      <span class="input-hint">Enter to send, Shift+Enter for new line</span>
      <div class="input-footer-right">
        <button id="mode-btn" class="text-btn" title="Permission mode">Default</button>
        <button id="new-chat-btn" class="text-btn" title="New chat">New chat</button>
      </div>
    </div>
  </div>
</div>
<script nonce="${nonce}" src="${jsUri}"></script>
</body>
</html>`;
  }
}

// ============================================================
// Diff Document Provider
// ============================================================
class DiffDocumentProvider {
  constructor() {
    this.documents = new Map();
  }

  provideTextDocumentContent(uri) {
    return this.documents.get(uri.toString()) || '';
  }

  setDocument(uriStr, content) {
    this.documents.set(uriStr, content);
  }
}

let diffProvider; // Set during activate

// ============================================================
// Utils
// ============================================================
function getNonce() {
  const c = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  let r = '';
  for (let i = 0; i < 32; i++) r += c.charAt(Math.floor(Math.random() * c.length));
  return r;
}

async function checkHermesAvailable() {
  return new Promise(resolve => {
    const p = spawn('hermes', ['--version'], { stdio: 'pipe' });
    p.on('error', () => {
      vscode.window.showWarningMessage('Hermes CLI not found. Install with: pip install hermes-agent');
      resolve(false);
    });
    p.on('close', c => resolve(c === 0));
  });
}

module.exports = { activate, deactivate };
