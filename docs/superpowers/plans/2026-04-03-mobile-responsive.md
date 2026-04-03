# Package F: Mobile-Responsive War Room — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **IMPORTANT:** Use the `frontend-design:frontend-design` skill when implementing Tasks 2, 3, and 4. The mobile UI must be production-grade, touch-optimized, and visually polished — not generic responsive CSS.

**Goal:** Make the War Room fully functional on iPhone — three-tab navigation, touch-optimized controls, file/image upload, PWA support — accessible via Tailscale at `http://100.119.47.67:5680`.

**Architecture:** Single HTML file with CSS media queries at 768px breakpoint. Mobile layout uses a bottom tab bar to switch between Chat, Agents, and Files panels. New upload endpoint stores files in the project directory. PWA manifest enables Add to Home Screen.

**Tech Stack:** CSS media queries, vanilla JS, FastAPI (upload endpoint), PWA manifest

**Design Spec:** `docs/superpowers/specs/2026-04-03-mobile-responsive-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `server.py` | Modify | Upload endpoint, serve uploaded files, serve manifest/icons |
| `static/index.html` | Modify | Mobile CSS, tab bar, bottom sheets, touch interactions, attachment button |
| `static/manifest.json` | Create | PWA manifest for Add to Home Screen |
| `static/icon-192.png` | Create | PWA icon (192x192) |
| `static/icon-512.png` | Create | PWA icon (512x512) |
| `tests/test_api.py` | Modify | Upload endpoint tests |

---

### Task 1: Server — Upload Endpoint + Static File Serving

**Files:**
- Modify: `~/coders-war-room/server.py`
- Modify: `~/coders-war-room/tests/test_api.py`

- [ ] **Step 1: Write failing tests**

Add to `~/coders-war-room/tests/test_api.py`:

```python
@pytest.mark.asyncio
async def test_upload_file():
    from server import app
    import io
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        file_content = b"# Test Document\nHello world"
        files = {"file": ("test-doc.md", io.BytesIO(file_content), "text/markdown")}
        resp = await client.post("/api/upload", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "uploaded"
        assert "path" in data
        assert data["filename"] == "test-doc.md"


@pytest.mark.asyncio
async def test_upload_too_large():
    from server import app
    import io
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 11MB file — over the 10MB limit
        file_content = b"x" * (11 * 1024 * 1024)
        files = {"file": ("huge.bin", io.BytesIO(file_content), "application/octet-stream")}
        resp = await client.post("/api/upload", files=files)
        assert resp.status_code == 413
```

- [ ] **Step 2: Add upload endpoint to server.py**

Add `from fastapi import UploadFile, File as FastAPIFile` to the imports.

Add the upload endpoint and uploaded file serving before the WebSocket endpoint:

```python
UPLOAD_DIR = Path(PROJECT_PATH) / "docs" / "warroom-uploads"
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB


@app.post("/api/upload")
async def upload_file(file: UploadFile = FastAPIFile(...)):
    """Upload a file (image, doc) to the project directory."""
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        return JSONResponse({"error": "File too large (max 10MB)"}, status_code=413)

    # Create date-based directory
    from datetime import date
    date_dir = UPLOAD_DIR / date.today().isoformat()
    date_dir.mkdir(parents=True, exist_ok=True)

    # Save file
    dest = date_dir / file.filename
    dest.write_bytes(content)

    rel_path = str(dest.relative_to(Path(PROJECT_PATH)))
    return {"status": "uploaded", "path": rel_path, "filename": file.filename, "size": len(content)}


@app.get("/uploads/{file_path:path}")
async def serve_upload(file_path: str):
    """Serve an uploaded file."""
    full_path = UPLOAD_DIR / file_path
    if not full_path.is_file():
        return PlainTextResponse("Not found", status_code=404)
    # Determine content type
    suffix = full_path.suffix.lower()
    content_types = {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml",
        ".pdf": "application/pdf", ".md": "text/markdown", ".txt": "text/plain",
    }
    ct = content_types.get(suffix, "application/octet-stream")
    from fastapi.responses import Response
    return Response(content=full_path.read_bytes(), media_type=ct)
```

- [ ] **Step 3: Add static file serving for PWA assets**

Add routes to serve manifest.json and icons:

```python
@app.get("/manifest.json")
async def manifest():
    manifest_path = Path(__file__).parent / "static" / "manifest.json"
    if manifest_path.exists():
        return JSONResponse(json.loads(manifest_path.read_text()))
    return JSONResponse({"name": "War Room"})


@app.get("/icon-{size}.png")
async def icon(size: str):
    icon_path = Path(__file__).parent / "static" / f"icon-{size}.png"
    if icon_path.exists():
        from fastapi.responses import Response
        return Response(content=icon_path.read_bytes(), media_type="image/png")
    return PlainTextResponse("Not found", status_code=404)
```

- [ ] **Step 4: Run tests**

```bash
cd ~/coders-war-room
python3 -m pytest tests/test_api.py -v
```

- [ ] **Step 5: Commit**

```bash
cd ~/coders-war-room
git add server.py tests/test_api.py
git commit -m "feat: add file upload endpoint and static PWA asset serving"
```

---

### Task 2: PWA Manifest + Icons

**Files:**
- Create: `~/coders-war-room/static/manifest.json`
- Create: `~/coders-war-room/static/icon-192.png`
- Create: `~/coders-war-room/static/icon-512.png`
- Modify: `~/coders-war-room/static/index.html` (add manifest link + meta tags)

- [ ] **Step 1: Create manifest.json**

Create `~/coders-war-room/static/manifest.json`:

```json
{
  "name": "Coder's War Room",
  "short_name": "War Room",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#060810",
  "theme_color": "#060810",
  "orientation": "portrait",
  "icons": [
    {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
    {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"}
  ]
}
```

- [ ] **Step 2: Generate PWA icons**

Create simple SVG-based icons using Python (green dot on dark background):

```bash
cd ~/coders-war-room/static
python3 -c "
from PIL import Image, ImageDraw
for size in [192, 512]:
    img = Image.new('RGBA', (size, size), (6, 8, 16, 255))
    draw = ImageDraw.Draw(img)
    # Green circle in the center
    r = size // 4
    cx, cy = size // 2, size // 2
    draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(0, 230, 118, 255))
    img.save(f'icon-{size}.png')
    print(f'Created icon-{size}.png')
"
```

If Pillow is not installed, create them with a simpler method or use placeholder solid-color PNGs.

- [ ] **Step 3: Add manifest link and mobile meta tags to index.html**

In the `<head>` section of `static/index.html`, after the Google Fonts link, add:

```html
<link rel="manifest" href="/manifest.json">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="#060810">
<link rel="apple-touch-icon" href="/icon-192.png">
```

- [ ] **Step 4: Commit**

```bash
cd ~/coders-war-room
git add static/manifest.json static/icon-192.png static/icon-512.png static/index.html
git commit -m "feat: add PWA manifest and icons for Add to Home Screen"
```

---

### Task 3: Mobile CSS — Tab Bar + Responsive Layout

**Files:**
- Modify: `~/coders-war-room/static/index.html`

**IMPORTANT: Use the `frontend-design:frontend-design` skill for this task. The mobile UI must be production-grade and polished.**

- [ ] **Step 1: Add the tab bar HTML**

After the closing `</div>` of `.main` and before the drawer, add:

```html
<!-- Mobile Tab Bar -->
<nav class="tab-bar" id="tabBar">
  <button class="tab active" data-tab="chat">
    <span class="tab-icon">💬</span>
    <span class="tab-label">Chat</span>
  </button>
  <button class="tab" data-tab="agents">
    <span class="tab-icon">👥</span>
    <span class="tab-label">Agents</span>
  </button>
  <button class="tab" data-tab="files">
    <span class="tab-icon">📁</span>
    <span class="tab-label">Files</span>
  </button>
</nav>
```

- [ ] **Step 2: Add mobile CSS**

Add a comprehensive `@media (max-width: 767px)` block at the end of the `<style>` section. This is the core of the mobile experience. Key rules:

```css
@media (max-width: 767px) {
  /* Tab bar */
  .tab-bar {
    display: flex;
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: var(--bg-panel);
    border-top: 1px solid var(--border);
    padding: 6px 0;
    padding-bottom: env(safe-area-inset-bottom, 8px); /* iPhone home indicator */
    z-index: 200;
  }

  .tab {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    background: none;
    border: none;
    color: var(--text-dim);
    font-family: 'JetBrains Mono', monospace;
    font-size: 9px;
    padding: 4px 0;
    cursor: pointer;
  }

  .tab.active { color: var(--green); }
  .tab-icon { font-size: 20px; }

  /* Hide tab bar on desktop */
  /* (moved outside media query as display:none default) */

  /* Layout: single column */
  .main {
    flex-direction: column;
  }

  .sidebar, .file-panel {
    display: none;
    width: 100%;
    height: calc(100vh - 50px - env(safe-area-inset-bottom, 8px));
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    z-index: 50;
  }

  .sidebar.mobile-active, .file-panel.mobile-active {
    display: flex;
  }

  .chat {
    width: 100%;
    height: calc(100vh - 50px - env(safe-area-inset-bottom, 8px));
  }

  .chat.mobile-hidden { display: none; }

  /* Header compact */
  header {
    padding: 8px 16px;
  }

  .server-bar {
    gap: 6px;
  }

  .server-stat { display: none; } /* Hide uptime/LaunchAgent on mobile */

  /* Input area above tab bar */
  .input-bar {
    padding-bottom: calc(58px + env(safe-area-inset-bottom, 8px));
  }

  /* Messages: slightly larger font for mobile readability */
  .msg-body {
    font-size: 15px;
  }

  /* Agent cards: full width, larger touch targets */
  .ac {
    padding: 12px 14px;
  }

  .abtn {
    padding: 6px 12px;
    font-size: 10px;
    min-height: 32px;
  }

  /* Drawer: full screen on mobile */
  .drawer {
    width: 100%;
    right: -100%;
  }

  .drawer.open { right: 0; }

  /* File browser: larger tap targets */
  .fp-item {
    padding: 8px 12px;
    font-size: 13px;
    min-height: 40px;
  }

  /* Bottom sheets */
  .bottom-sheet {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: var(--bg-panel);
    border-top: 1px solid var(--border);
    border-radius: 16px 16px 0 0;
    padding: 16px;
    padding-bottom: calc(16px + env(safe-area-inset-bottom, 8px));
    z-index: 300;
    transform: translateY(100%);
    transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 0 -8px 24px rgba(0,0,0,0.4);
  }

  .bottom-sheet.open { transform: translateY(0); }

  .bottom-sheet-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.5);
    z-index: 299;
    display: none;
  }

  .bottom-sheet-overlay.open { display: block; }

  .bs-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 14px 8px;
    font-family: 'Source Sans 3', sans-serif;
    font-size: 16px;
    color: var(--text-primary);
    border-bottom: 1px solid var(--border);
    cursor: pointer;
  }

  .bs-item:last-child { border-bottom: none; }
  .bs-item:active { background: var(--bg-card-hover); }

  .bs-title {
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: var(--text-dim);
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-bottom: 8px;
  }

  .bs-cancel {
    text-align: center;
    padding: 14px;
    color: var(--red);
    font-weight: 500;
    cursor: pointer;
    margin-top: 8px;
  }
}

/* Hide tab bar on desktop */
@media (min-width: 768px) {
  .tab-bar { display: none; }
}
```

- [ ] **Step 3: Add tab switching JavaScript**

Add to the `<script>` section before the Init block:

```javascript
// ═══════════ Mobile Tab Navigation ═══════════
const $tabBar = $('tabBar');
let activeTab = 'chat';

function switchTab(tab) {
  activeTab = tab;
  // Update tab bar
  document.querySelectorAll('.tab').forEach(t => {
    t.classList.toggle('active', t.dataset.tab === tab);
  });
  // Show/hide panels
  const sidebar = document.querySelector('.sidebar');
  const chat = document.querySelector('.chat');
  const filePanel = document.querySelector('.file-panel');

  sidebar.classList.remove('mobile-active');
  chat.classList.remove('mobile-hidden');
  filePanel.classList.remove('mobile-active');

  if (tab === 'agents') {
    sidebar.classList.add('mobile-active');
    chat.classList.add('mobile-hidden');
  } else if (tab === 'files') {
    filePanel.classList.add('mobile-active');
    chat.classList.add('mobile-hidden');
  }
  // Chat tab: both panels hidden, chat visible (default)
}

if ($tabBar) {
  $tabBar.querySelectorAll('.tab').forEach(tab => {
    tab.onclick = () => switchTab(tab.dataset.tab);
  });
}
```

- [ ] **Step 4: Add bottom sheet utility functions**

```javascript
// ═══════════ Bottom Sheets (mobile) ═══════════
function showBottomSheet(title, items, onSelect) {
  // Remove existing
  document.querySelectorAll('.bottom-sheet, .bottom-sheet-overlay').forEach(el => el.remove());

  const overlay = document.createElement('div');
  overlay.className = 'bottom-sheet-overlay open';

  const sheet = document.createElement('div');
  sheet.className = 'bottom-sheet';

  let html = `<div class="bs-title">${title}</div>`;
  items.forEach((item, i) => {
    html += `<div class="bs-item" data-index="${i}">${item.icon ? item.icon + ' ' : ''}${item.label}</div>`;
  });
  html += `<div class="bs-cancel">Cancel</div>`;
  sheet.innerHTML = html;

  document.body.appendChild(overlay);
  document.body.appendChild(sheet);

  // Animate in
  requestAnimationFrame(() => sheet.classList.add('open'));

  const close = () => {
    sheet.classList.remove('open');
    overlay.classList.remove('open');
    setTimeout(() => { sheet.remove(); overlay.remove(); }, 250);
  };

  overlay.onclick = close;
  sheet.querySelector('.bs-cancel').onclick = close;
  sheet.querySelectorAll('.bs-item').forEach(el => {
    el.onclick = () => {
      const idx = parseInt(el.dataset.index);
      close();
      if (onSelect) onSelect(items[idx], idx);
    };
  });
}
```

- [ ] **Step 5: Test on Chrome DevTools iPhone simulator**

```bash
cd ~/coders-war-room
pkill -f "python3.*server.py"; sleep 1
python3 server.py &
sleep 2
open http://localhost:5680
```

Open Chrome DevTools (Cmd+Option+I) → Device toggle (Cmd+Shift+M) → iPhone 14 Pro.
Verify: tab bar visible, tabs switch panels, chat is default.

- [ ] **Step 6: Commit**

```bash
cd ~/coders-war-room
git add static/index.html
git commit -m "feat: mobile three-tab layout with bottom navigation and responsive CSS"
```

---

### Task 4: Mobile Chat Interactions — Attachment + Agent Picker + File Reference

**Files:**
- Modify: `~/coders-war-room/static/index.html`

**IMPORTANT: Use the `frontend-design:frontend-design` skill for this task.**

- [ ] **Step 1: Add attachment button to input area**

Update the input bar HTML. Find the existing input-bar div and add a mobile-friendly layout:

```html
<div class="input-bar">
  <div class="input-target" id="inputTarget">@all ▼</div>
  <div class="input-row">
    <button class="input-attach" id="attachBtn" title="Attach">📎</button>
    <textarea id="msgInput" class="msg-input" placeholder="Message the war room..." rows="1"></textarea>
    <button id="sendBtn" class="send-btn" disabled>➤</button>
  </div>
</div>
```

On mobile, the `@target` dropdown becomes a tappable label above the input that opens an agent picker bottom sheet. The `📎` button opens an attachment action sheet. On desktop, the existing `<select>` behavior is preserved.

- [ ] **Step 2: Add CSS for the mobile input area**

```css
@media (max-width: 767px) {
  .input-bar {
    flex-direction: column;
    gap: 6px;
  }

  .input-target {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    color: var(--green);
    padding: 4px 0;
    cursor: pointer;
  }

  .input-row {
    display: flex;
    gap: 8px;
    align-items: flex-end;
  }

  .input-attach {
    background: none;
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 8px;
    font-size: 18px;
    cursor: pointer;
    min-width: 40px;
    min-height: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .target-sel { display: none; } /* Hide desktop dropdown on mobile */
}

@media (min-width: 768px) {
  .input-target { display: none; } /* Hide mobile target label on desktop */
  .input-attach { display: none; } /* Hide attach button on desktop */
}
```

- [ ] **Step 3: Add agent picker bottom sheet handler**

```javascript
// Mobile: tap @target to pick agent
const $inputTarget = $('inputTarget');
if ($inputTarget) {
  $inputTarget.onclick = () => {
    if (window.innerWidth >= 768) return; // Desktop uses dropdown
    const items = [{ label: '@all', value: 'all' }];
    agentRoster.forEach(a => items.push({ label: `@${a.name}`, value: a.name }));
    showBottomSheet('Send to...', items, (item) => {
      $target.value = item.value;
      $inputTarget.textContent = `${item.label} ▼`;
      $input.focus();
    });
  };
}
```

- [ ] **Step 4: Add attachment button handler**

```javascript
// Mobile: attachment button
const $attachBtn = $('attachBtn');
if ($attachBtn) {
  $attachBtn.onclick = () => {
    showBottomSheet('Attach', [
      { icon: '📷', label: 'Photo', action: 'photo' },
      { icon: '📄', label: 'Upload File', action: 'file' },
      { icon: '📂', label: 'Project File', action: 'project' },
    ], (item) => {
      if (item.action === 'photo' || item.action === 'file') {
        // Create hidden file input and trigger it
        const input = document.createElement('input');
        input.type = 'file';
        if (item.action === 'photo') input.accept = 'image/*';
        input.onchange = async () => {
          const file = input.files[0];
          if (!file) return;
          const formData = new FormData();
          formData.append('file', file);
          try {
            const resp = await fetch('/api/upload', { method: 'POST', body: formData });
            const data = await resp.json();
            if (data.path) {
              $input.value += `[uploaded: ${data.path}] `;
              $input.focus();
            }
          } catch (e) {
            alert('Upload failed');
          }
        };
        input.click();
      } else if (item.action === 'project') {
        // Show file tree as bottom sheet
        showProjectFilePicker();
      }
    });
  };
}

async function showProjectFilePicker(path = '.') {
  try {
    const resp = await fetch(`/api/files?path=${encodeURIComponent(path)}`);
    const data = await resp.json();
    const items = [];
    if (data.parent) {
      items.push({ icon: '⬆️', label: '.. (up)', action: 'navigate', path: data.parent });
    }
    data.entries.forEach(e => {
      if (e.type === 'dir') {
        items.push({ icon: '📁', label: e.name, action: 'navigate', path: e.path });
      } else {
        items.push({ icon: '📄', label: e.name, action: 'select', path: e.path });
      }
    });
    showBottomSheet(`📂 ${data.current}`, items, (item) => {
      if (item.action === 'navigate') {
        showProjectFilePicker(item.path);
      } else if (item.action === 'select') {
        $input.value += `[file: ${item.path}] `;
        $input.focus();
        switchTab('chat');
      }
    });
  } catch (e) {
    alert('Failed to load files');
  }
}
```

- [ ] **Step 5: Add image preview in chat messages**

In the `renderMsg` function, after setting `el.innerHTML`, add image preview for uploaded files:

```javascript
// Image preview for uploaded files
if (m.content && m.content.includes('[uploaded:')) {
  const match = m.content.match(/\[uploaded:\s*([^\]]+)\]/);
  if (match) {
    const filePath = match[1].trim();
    const ext = filePath.split('.').pop().toLowerCase();
    if (['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(ext)) {
      const img = document.createElement('img');
      img.src = `/uploads/${filePath.replace('docs/warroom-uploads/', '')}`;
      img.style.cssText = 'max-width:100%;max-height:300px;border-radius:8px;margin-top:8px;cursor:pointer';
      img.onclick = () => window.open(img.src, '_blank');
      const body = el.querySelector('.msg-body');
      if (body) body.appendChild(img);
    }
  }
}
```

- [ ] **Step 6: Update the Agents tab [@] button to switch to chat**

In `renderAgents()`, update the `msg` action handler:

```javascript
else if (action === 'msg') {
  $target.value = agent;
  if ($inputTarget) $inputTarget.textContent = `@${agent} ▼`;
  $input.focus();
  if (window.innerWidth < 768) switchTab('chat');
}
```

- [ ] **Step 7: Test on Chrome DevTools + real iPhone**

Test all flows:
1. Tab switching works
2. Agent picker bottom sheet opens from @target tap
3. Attachment button shows 3 options
4. Photo upload works (select image, uploads, path inserted)
5. Project file picker navigates and inserts file path
6. Agent [@] button switches to chat with target set
7. Image previews render in chat

- [ ] **Step 8: Commit**

```bash
cd ~/coders-war-room
git add static/index.html
git commit -m "feat: mobile chat interactions — attachment, agent picker, file reference, image preview"
```

---

### Task 5: Final Polish + Files Tab Mobile Actions + Push to GitHub

**Files:**
- Modify: `~/coders-war-room/static/index.html`

- [ ] **Step 1: Add file action menu for Files tab on mobile**

In the `loadDir()` function, update the file click handler to show a bottom sheet on mobile instead of opening directly:

```javascript
item.onclick = (e) => {
  e.stopPropagation();
  if (window.innerWidth < 768) {
    // Mobile: show action menu
    const actions = [
      { icon: '📋', label: 'Copy path', action: 'copy' },
      { icon: '💬', label: 'Send to chat', action: 'chat' },
      { icon: '👤', label: 'Assign to agent...', action: 'assign' },
    ];
    if (entry.name.endsWith('.md')) {
      actions.push({ icon: '👁', label: 'Preview', action: 'preview' });
    }
    showBottomSheet(entry.name, actions, (item) => {
      if (item.action === 'copy') {
        navigator.clipboard.writeText(entry.path);
      } else if (item.action === 'chat') {
        $input.value += entry.path + ' ';
        switchTab('chat');
        $input.focus();
      } else if (item.action === 'assign') {
        // Show agent picker, then switch to chat
        const agents = agentRoster.map(a => ({ label: `@${a.name}`, value: a.name }));
        showBottomSheet('Assign to...', agents, (agent) => {
          $target.value = agent.value;
          if ($inputTarget) $inputTarget.textContent = `@${agent.value} ▼`;
          $input.value = `[file: ${entry.path}] `;
          switchTab('chat');
          $input.focus();
        });
      } else if (item.action === 'preview') {
        fetch('/api/files/open', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({path: entry.path}),
        }).then(r => r.json()).then(d => {
          if (d.url) window.open(d.url, '_blank');
        });
      }
    });
  } else {
    // Desktop: open directly
    fetch('/api/files/open', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({path: entry.path}),
    }).then(r => r.json()).then(d => {
      if (d.status === 'preview' && d.url) window.open(d.url, '_blank');
    }).catch(() => {});
  }
};
```

- [ ] **Step 2: Add settings gear icon for mobile header**

In the mobile header, add a gear icon that opens server management as a bottom sheet:

```javascript
// Settings gear (mobile only) — add after Roll Call handler
const settingsGear = document.createElement('button');
settingsGear.className = 'server-btn';
settingsGear.id = 'mobileSettings';
settingsGear.textContent = '⚙';
settingsGear.style.display = 'none'; // shown via media query
settingsGear.onclick = () => {
  fetch('/api/server/health').then(r => r.json()).then(d => {
    showBottomSheet('Server', [
      { icon: '⏱', label: `Uptime: ${d.uptime_human}` },
      { icon: d.launchagent_active ? '🟢' : '⚪', label: `LaunchAgent: ${d.launchagent_active ? 'active' : 'not installed'}` },
      { icon: '🔄', label: 'Restart Server', action: 'restart' },
      { icon: '📋', label: 'View Logs', action: 'logs' },
    ], (item) => {
      if (item.action === 'restart') {
        if (confirm('Restart server?')) fetch('/api/server/restart', { method: 'POST' });
      } else if (item.action === 'logs') {
        window.open('/api/server/logs', '_blank');
      }
    });
  });
};
// Insert into header
document.querySelector('.server-bar').appendChild(settingsGear);
```

CSS to show gear only on mobile:
```css
@media (max-width: 767px) {
  #mobileSettings { display: block !important; }
}
```

- [ ] **Step 3: Final responsive tweaks**

Test and fix any remaining issues:
- Ensure onboarding drawer is full-screen on mobile
- Ensure recovery button works on mobile
- Ensure de-board section scrolls properly
- Ensure bottom sheets dismiss properly
- Test WebSocket reconnection on mobile (Safari can be aggressive about dropping connections)

- [ ] **Step 4: Run all tests**

```bash
cd ~/coders-war-room
python3 -m pytest tests/ -v
```

- [ ] **Step 5: Commit and push**

```bash
cd ~/coders-war-room
git add -A
git commit -m "feat: Package F complete — full mobile War Room with upload, PWA, touch interactions"
git push origin main
```

- [ ] **Step 6: Test on actual iPhone**

Open `http://100.119.47.67:5680` on iPhone Safari:
1. Tab bar visible at bottom
2. Chat loads with messages
3. Can send messages
4. Agent picker works
5. Can upload photo from camera roll
6. Can browse project files
7. Can assign file to agent
8. Add to Home Screen → opens as standalone app
