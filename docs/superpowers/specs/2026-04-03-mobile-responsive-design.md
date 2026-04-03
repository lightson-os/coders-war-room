# Package F: Mobile-Responsive War Room — Design Spec

**Date:** 2026-04-03
**Goal:** Full-functionality War Room on iPhone via Tailscale, with responsive three-tab layout, touch-optimized interactions, file/image upload, and PWA support.
**Access:** `http://100.119.47.67:5680` via Tailscale (private network, no auth needed)
**Principle:** Not a "mobile view" — a complete command center on the phone. Every action available on desktop must be possible on mobile.

---

## Layout Strategy

**Breakpoint:** 768px

- **< 768px (mobile):** Three-tab bottom navigation. One panel at a time. Full-width.
- **>= 768px (desktop):** Existing three-column layout. Tab bar hidden. Zero changes.

CSS media queries only. No separate mobile page. Same HTML, different layout.

---

## Tab Bar

Fixed at the bottom of the viewport. Three tabs:

```
  💬 Chat        👥 Agents        📁 Files
```

- Chat is the default active tab
- Active tab: green accent color highlight
- Inactive tabs: dim text
- Tab bar sits above the safe area (iPhone notch/home indicator)
- Hidden on desktop (display: none above 768px)

---

## Tab 1: Chat

Full-width message feed with the same styling as desktop (sender colors, dynamic border, message grouping).

### Header (compact)
```
WAR ROOM                                    ● LIVE
```
No uptime, no LaunchAgent status, no Restart/Logs on mobile. Those move to a gear icon that opens a settings bottom sheet.

### Message Feed
- Same `msg` styling: sender color name, dynamic left border, timestamp, grouping
- Font: Source Sans 3 at 15px (slightly larger for mobile readability)
- Full-width messages with appropriate padding

### Input Area (above tab bar)
```
┌──────────────────────────────────────────────┐
│ @engineer ▼                                  │
│ [📎] [Type a message...              ] [➤]  │
└──────────────────────────────────────────────┘
```

- `@engineer ▼` — tappable target label. Opens agent picker bottom sheet.
- `📎` — attachment button. Opens action sheet: Photo / File Upload / Project File
- Text input — full width, auto-expanding
- `➤` — send button (green)

### Agent Picker (bottom sheet)
Triggered by tapping the @target label:
```
┌─────────────────────────────────────┐
│  Send to...                         │
│                                     │
│  ● @all                             │
│  ● @supervisor                      │
│  ● @mr-scout                        │
│  ● @engineer                        │
│  ● @q-a                             │
│  ● @mr-git                          │
│  ● @mr-chronicler                   │
└─────────────────────────────────────┘
```

### Attachment Action Sheet
Triggered by tapping 📎:
```
┌─────────────────────────────────────┐
│  📷 Photo (Camera Roll)             │
│  📄 Upload File                     │
│  📂 Project File (browse tree)      │
│  ─────────────────────              │
│  Cancel                             │
└─────────────────────────────────────┘
```

- **Photo / Upload File** — native file picker → upload to server → path inserted in message
- **Project File** — opens a bottom sheet with the file tree. Tap a file → inserts `[file: path]` in input.

---

## Tab 2: Agents

Full-width agent cards with all desktop functionality.

### Top Bar
```
AGENTS  6/6          [+ New Agent]  [Roll Call]
```

### Agent Cards
Same progressive disclosure as desktop, full-width:
```
● supervisor                          [@] [x]
  Coordinator
  Decomposing CTX-001
  ████████░░ 60% · ~5m
```

- `[@]` — tap → switches to Chat tab with @target pre-set to this agent
- `[x]` — deboard with confirmation dialog
- `[Recover]` — on dead session cards (pulsing red)
- **No `[cli]` button** — can't open Warp from iPhone
- Long-press to reorder (native mobile gesture, replaces drag handle)

### De-boarded Section
Same as desktop — bottom of the list with `[+ rejoin]` and `[remove]` buttons.

### + New Agent (full-screen form)
Tapping `+ New Agent` opens a full-screen form (not a drawer — full screen on mobile):

- **Role Type** dropdown with 7 presets (auto-fill on select)
- **Agent Name** input (auto-hyphenated)
- **Working Directory** — full-screen browser with back navigation
- **Role Description** textarea (pre-filled from preset)
- **Initial Prompt** textarea (pre-filled from preset)
- **Model** dropdown (Opus/Sonnet/Haiku)
- **Permissions** toggle
- **Launch Agent** button — sticky at bottom

Close button (X) top-right returns to Agents tab.

---

## Tab 3: Files

Full-width directory tree.

### Header
```
FILES  ~/contextualise
```

### Tree
Same expand/collapse folders. Tap file → action menu (bottom sheet):

```
┌─────────────────────────────────────┐
│  state.py                           │
│                                     │
│  📋 Copy path                       │
│  💬 Send to chat                    │
│  👤 Assign to agent...              │
│  👁 Preview (markdown only)         │
│  ─────────────────────              │
│  Cancel                             │
└─────────────────────────────────────┘
```

- **Copy path** — copies to clipboard
- **Send to chat** — switches to Chat tab, inserts path in input
- **Assign to agent** — opens agent picker, then switches to Chat tab with `@agent [file: path]`
- **Preview** — only for .md files, opens rendered markdown in-app or new tab

---

## File/Image Upload

### Endpoint: `POST /api/upload`

Accepts `multipart/form-data` with a file field.

**Storage:** `~/contextualise/docs/warroom-uploads/YYYY-MM-DD/<filename>`

Creates date directories automatically. Preserves original filename.

**Response:**
```json
{
  "status": "uploaded",
  "path": "docs/warroom-uploads/2026-04-03/screenshot.png",
  "filename": "screenshot.png",
  "size": 245000
}
```

**File size limit:** 10MB

**In the chat:** After upload, the path is inserted into the message input. The user adds context and sends:
```
@engineer here's the bug screenshot [uploaded: docs/warroom-uploads/2026-04-03/screenshot.png]
```

### Image Preview in Chat
When a message contains `[uploaded: *.png]` or `[uploaded: *.jpg]`, the chat renders a thumbnail (if the server can serve the image). Endpoint:

`GET /uploads/{path}` — serves the uploaded file directly.

---

## PWA Manifest

`manifest.json` at the project root, linked in the HTML:

```json
{
  "name": "War Room",
  "short_name": "War Room",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#060810",
  "theme_color": "#060810",
  "icons": [
    {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
    {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"}
  ]
}
```

When the user taps "Add to Home Screen" in Safari, the War Room appears as a standalone app — no Safari chrome, custom splash screen, dark theme.

Icons: simple green dot on dark background (matches the LIVE badge aesthetic).

---

## Settings Bottom Sheet (mobile only)

Gear icon in the mobile header. Opens a bottom sheet with:

- Server uptime
- LaunchAgent status
- Restart button
- View Logs button
- Tailscale IP display

---

## CSS Approach

All changes via a single `@media (max-width: 767px)` block:

- `.sidebar`, `.file-panel` → `display: none` by default, shown when their tab is active
- `.chat` → `flex: 1`, full width
- `.main` → `flex-direction: column`
- Tab bar → `position: fixed; bottom: 0`
- Bottom sheets → `position: fixed; bottom: 0; border-radius: 16px 16px 0 0`
- All buttons → minimum 44px touch target (Apple HIG)
- Input area → sticky above tab bar
- Agent cards → full width with adequate padding

---

## What Does NOT Change

- **Server.py** — only new endpoint is `POST /api/upload` and `GET /uploads/{path}`
- **WebSocket** — identical protocol
- **All existing API endpoints** — unchanged
- **Desktop layout** — completely untouched (media queries only)
- **Message dispatch** — identical
- **tmux sessions** — identical
- **warroom.sh** — no changes
