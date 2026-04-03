# React Native Phase 2a: Native Chat Screen — Design Spec

**Date:** 2026-04-04
**Phase:** 2a of 3 (native Chat screen, Agents/Files stay WebView)
**Project:** ~/warroom-mobile/
**Approach:** Replace Chat tab WebView with native React Native components. Agents and Files tabs remain as WebView wrappers.

---

## Context

Phase 1 delivered an Expo WebView shell that wraps the existing War Room web UI. It works but the entire UI runs inside a WebView — no native rendering, no native scroll, no native text. Phase 2a replaces the Chat tab (80% of usage) with a fully native React Native implementation, applying the legibility research findings for maximum readability on iPhone.

Agents and Files tabs remain as WebView wrappers until Phase 2b/2c.

---

## 1. Architecture

```
App.js
├── SafeAreaProvider
├── React Navigation BottomTabNavigator
│   ├── ChatScreen (NATIVE)
│   │   ├── useWebSocket hook → ws://100.119.47.67:5680/ws
│   │   ├── FlashList (message list, inverted)
│   │   ├── MessageBubble component
│   │   ├── TimeDivider component
│   │   ├── ChatInputBar component (iMessage-style)
│   │   └── Keyboard offset (custom animation)
│   ├── AgentsScreen → WebView (auto-selects Agents tab, hides web tab bar)
│   └── FilesScreen → WebView (auto-selects Files tab, hides web tab bar)
└── StatusBar (dark)
```

Two independent WebSocket connections: native Chat has its own via `useWebSocket` hook. WebView tabs keep their existing connection inside the HTML.

---

## 2. File Structure

```
~/warroom-mobile/
├── App.js                          # Tab navigator setup + font loading
├── src/
│   ├── screens/
│   │   ├── ChatScreen.js           # Native chat — list + input + keyboard
│   │   ├── AgentsScreen.js         # WebView wrapper, injects switchTab('agents')
│   │   └── FilesScreen.js          # WebView wrapper, injects switchTab('files')
│   ├── components/
│   │   ├── MessageBubble.js        # Single message — user bubble or agent card
│   │   ├── TimeDivider.js          # "── 12:45 PM ──" centered separator
│   │   └── ChatInputBar.js         # iMessage-style: + button, pill input, send button
│   ├── hooks/
│   │   └── useWebSocket.js         # Connect, reconnect, message state, send
│   └── constants/
│       ├── colors.js               # War Room palette + role color map + swatches
│       └── icons.js                # SVG icon components (send arrow, plus, chat, users, folder)
├── app.json
└── package.json
```

Each file has one responsibility. No file exceeds ~150 lines.

---

## 3. Legibility — Research Applied to Native

All findings from the contrast/density research, implemented with native React Native text rendering:

| Setting | Value | Rationale |
|---------|-------|-----------|
| Screen background | `#060810` | 17.2:1 contrast ratio with text (vs 13.5:1 with card bg) |
| Message body text | 16px Source Sans 3, weight 400 | Optimal density + legibility per research |
| Letter spacing | 0.2 (RN units) | ~0.01em micro word separation |
| Line height | 24 (1.5x) | Minimum recommended for sustained reading |
| Agent message width | 95% of screen width | +6 chars per line vs current 85% |
| User message width | 92% of screen width | Right-aligned with slight margin |
| Agent card background | None — text on `#060810` | Maximum contrast, no card bg layer |
| Agent identity | 3px left border in agent's color | Visual anchor without contrast reduction |
| Message separation | 12px gap between different senders | Clean separation via spacing, not boxes |
| User bubble bg | `rgba(0, 230, 118, 0.08)` | Subtle green tint on dark background |
| Sender name | 12px JetBrains Mono, bold, agent color | Monospace for alignment, colored for identity |
| Timestamp | 11px JetBrains Mono, `#3e4e64` | Dim, doesn't compete with content |
| System messages | 12px Source Sans 3, italic, centered, `#3e4e64` | Clearly distinct from user/agent messages |

---

## 4. Message Types

### Agent messages (left-aligned, no card background)

- Left border: 3px solid, agent's resolved color
- Sender name: 12px JetBrains Mono, bold, agent color + timestamp 11px dim inline
- Body: 16px Source Sans 3, `#d8dee8`, letter-spacing 0.2
- Max width: 95% of screen
- Padding: 8px vertical, 10px horizontal (after the border)
- Bottom margin: 4px (same sender within 20s), 12px (different sender)

### User messages (right-aligned, green tint)

- Background: `rgba(0, 230, 118, 0.08)`
- Border radius: 16px 16px 4px 16px (flat bottom-right, like iMessage)
- No sender name (it's you)
- Body: 16px Source Sans 3, `#d8dee8`
- Timestamp: 11px, dim, below bubble, right-aligned
- Max width: 92% of screen
- Padding: 10px 12px

### System messages (centered)

- No bubble, no border
- Text: 12px Source Sans 3, italic, `#3e4e64`
- Centered horizontally
- Margin: 4px vertical

### Direct messages (@you specifically)

- Same as agent message but left border color is `#ff9100` (orange)

---

## 5. Grouping Rules

Same as M1 web implementation:

1. **Never group across different senders** — every sender change shows full header
2. **Same sender, consecutive, within 20 seconds** — stack tight (4px gap), header on first only
3. **Same sender, 20+ seconds apart** — show full header again
4. **Time dividers** — after 5+ minute gap: centered `── 12:45 PM ──` with horizontal rules
5. **Day dividers** — midnight crossings: `── Today ──`, `── Yesterday ──`, `── Mon, 31 Mar ──`

---

## 6. Input Bar (iMessage-style)

```
  ┌───┐ ┌─────────────────────────────┐ ┌───┐
  │ + │ │ Message the war room...     │ │ ▶ │
  └───┘ └─────────────────────────────┘ └───┘
```

### Plus button (left)

- 32px circle, background `#1a2030`
- White `+` icon (16px)
- Always visible
- Tap: opens native ActionSheet with options:
  - Photo (launches image picker)
  - Upload File (launches document picker)
  - Project File (API call to /api/files, presented in a modal list)
- After selection: attachment chip appears above input bar

### Text input (center)

- Pill shape: borderRadius 20, background `#0a0d14`, border 1px `#1a2030`
- Font: 16px Source Sans 3 (prevents iOS zoom)
- Placeholder: "Message the war room..." in `#3e4e64`
- Expands from 1 line (36px) to max 3 lines (~84px)
- Focus: border color changes to `#448aff`

### Send button (right)

- 32px circle, background `#00e676` (green)
- White send arrow SVG (14px)
- Hidden when input is empty AND no attachment
- Visible when text present OR attachment present
- Press animation: scales to 0.88 with spring effect
- Tap: sends message via WebSocket, clears input

### Target selector

- Above the input bar: `@all ▼` in 11px JetBrains Mono, green
- Tap: opens native ActionSheet listing all agents
- Selecting an agent changes the target

### Attachment chip

- Between target and input bar when a file is attached
- Pill shape: borderRadius 12, background `#121620`, border `#1a2030`
- File icon + name (truncated 25 chars) + ✕ remove
- Tap ✕: removes attachment

### Keyboard handling

- Custom keyboard offset via `Keyboard.addListener('keyboardWillShow')` and `Keyboard.addListener('keyboardWillHide')`
- Animate input bar position with `Animated.timing`, duration 250ms, matching iOS keyboard curve
- FlashList adjusts content inset automatically

---

## 7. WebSocket Hook (useWebSocket.js)

### Connection

- URL: `ws://100.119.47.67:5680/ws`
- Connect on mount, disconnect on unmount
- Auto-reconnect on close: 2 second delay, exponential backoff up to 10 seconds

### Message handling

| Server message type | Action |
|-------------------|--------|
| `history` | Replace message list with received messages |
| `message` | Append to message list |
| `agent_status` | Store in agentData ref (used for color resolution, not rendered) |
| `agent_created` | Add to agent roster |
| `agent_removed` | Remove from agent roster |
| `membership` | Update agent membership |

### Sending

```javascript
send({ sender: 'gurvinder', target, content, type: 'message' })
```

Optimistic rendering: message added to local list immediately. Server broadcast excluded (server uses `exclude=ws` for the sender).

### AppState reconnection

- Listen for `AppState` changes
- When app returns to foreground and WebSocket is not OPEN: reconnect
- Handles iOS backgrounding gracefully

### State exposed

```javascript
const { messages, agentRoster, agentData, isConnected, send } = useWebSocket();
```

---

## 8. Tab Navigator (App.js)

### React Navigation bottom tabs

- `@react-navigation/bottom-tabs` with custom tab bar styling
- Three tabs: Chat, Agents, Files

### Tab bar styling

- Background: `#0e1119`
- Border top: 1px `#1a2030`
- Active color: `#00e676`
- Inactive color: `#3e4e64`
- Icons: SVG components (chat bubble, users group, folder)
- Labels: 9px JetBrains Mono, letterspaced
- Safe area bottom padding (home indicator)
- Height: ~50px + safe area

### WebView tab screens

AgentsScreen and FilesScreen load `http://100.119.47.67:5680` and inject JavaScript to:
1. Auto-switch to the correct tab: `switchTab('agents')` or `switchTab('files')`
2. Hide the web tab bar via injected CSS: `.tab-bar { display: none !important; }`
3. Adjust input bar bottom position: `.input-bar { bottom: 0 !important; }`

---

## 9. Font Loading

Load custom fonts via `expo-font`:
- Source Sans 3 (400, 600 weights) — from Google Fonts
- JetBrains Mono (400, 700 weights) — from Google Fonts

Loaded in App.js before rendering. Show splash screen until fonts ready via `expo-splash-screen`.

---

## 10. New Dependencies

| Package | Purpose |
|---------|---------|
| `@react-navigation/native` | Navigation framework core |
| `@react-navigation/bottom-tabs` | Tab navigator |
| `react-native-screens` | Required by React Navigation |
| `@shopify/flash-list` | Fast virtualized message list |
| `expo-font` | Load Source Sans 3 + JetBrains Mono |
| `expo-splash-screen` | Keep splash while fonts load |
| `react-native-svg` | Render SVG icons natively |

---

## 11. What Does NOT Change

- Server (server.py) — zero modifications
- Web UI (static/index.html) — zero modifications
- WebSocket protocol — same message format
- Agents tab functionality — still WebView
- Files tab functionality — still WebView
- Desktop web UI

---

## 12. Success Criteria

1. Chat tab renders natively — not a WebView
2. Messages from server display correctly (agent left-aligned, user right-aligned)
3. Can send messages — they appear in both the native app and the web UI
4. FlashList scrolls smoothly through 200+ messages
5. Grouping: 20-second window, time dividers after 5+ min gaps
6. Input bar: + button, pill text field, circular green send
7. Keyboard pushes input up smoothly (custom animation)
8. Target selector (@all / @agent) works
9. Agents tab works via WebView (web tab bar hidden)
10. Files tab works via WebView (web tab bar hidden)
11. Tab bar matches War Room theme (dark, green active)
12. Fonts loaded: Source Sans 3 + JetBrains Mono
13. Legibility: text on #060810, 95% width, 16px, letter-spacing 0.2
14. WebSocket reconnects on foreground return
