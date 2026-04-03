# React Native Phase 2a v2: Home Screen + Native Chat — Design Spec

**Date:** 2026-04-04
**Phase:** 2a of 3
**Project:** ~/warroom-mobile/
**Approach:** WhatsApp-style stack navigation — Home screen with War Room card, tap to push into full-screen native Chat (tab bar hidden). Agents/Files remain WebView tabs.

---

## Context

Phase 1 delivered an Expo WebView shell. Phase 2a replaces the Chat tab with a native implementation. During brainstorming, we identified that WhatsApp hides the tab bar inside conversations, gaining ~50px of vertical space. The design now uses a Home screen with a War Room card as the entry point — tapping it pushes into a full-screen Chat with no tab bar.

The legibility research from our deep dive session (contrast, width, font density) is applied throughout the native Chat screen.

---

## 1. Navigation Architecture

```
App.js
├── SafeAreaProvider + Font Loading
├── React Navigation
│   ├── BottomTabNavigator
│   │   ├── HomeTab → StackNavigator
│   │   │   ├── HomeScreen (War Room card — tab bar visible)
│   │   │   └── ChatScreen (full screen — tab bar HIDDEN)
│   │   ├── AgentsTab → AgentsScreen (WebView — tab bar visible)
│   │   └── FilesTab → FilesScreen (WebView — tab bar visible)
```

- HomeScreen shows the tab bar (Chat, Agents, Files)
- ChatScreen hides the tab bar via `tabBarStyle: { display: 'none' }` on navigation
- Back button in ChatScreen returns to HomeScreen, tab bar reappears
- Agents and Files tabs always show the tab bar

---

## 2. Home Screen

Dark background (`#060810`). One hero card in the upper third. Rest is empty space (future widgets).

### War Room Card

```
┌─────────────────────────────────────────┐
│                                         │
│  ● WAR ROOM                    ONLINE   │
│                                LIVE     │
│  8 agents · 2 working                  │
│  1 blocked · 5 idle                    │
│                                         │
└─────────────────────────────────────────┘
```

**Card styling:**
- Full width minus 16px margins each side
- Border-radius: 16px
- Background: `#0e1119` (bgPanel)
- Border: 1px `#1a2030`
- Padding: 20px
- Tap: navigates to ChatScreen (stack push)
- Active opacity: 0.85 on press

**Green breathing dot:**
- Size: 10px circle
- Color: `#00e676`
- Animation: box-shadow pulses `rgba(0,230,118,0.5)` spread 4px → 12px → 4px over 2 seconds, infinite repeat
- When disconnected: grey `#555`, no animation

**"WAR ROOM" title:**
- 18px JetBrains Mono, bold
- Color: `#00e676`
- Letter-spacing: 3

**Status labels (right side):**
- "ONLINE" / "OFFLINE": 11px JetBrains Mono, green when connected, `#ff5252` when not
- "LIVE": 11px JetBrains Mono, green — shown only when connected

**Agent health (below title):**
- Line 1: 14px Source Sans 3, `#d8dee8` — "8 agents · 2 working"
- Line 2: 13px Source Sans 3, `#7a8a9e` — "1 blocked · 5 idle"
- Counts derived from WebSocket `agent_status` data

### Data source

The HomeScreen connects to the same WebSocket as ChatScreen. The `agent_status` message provides all the data needed:
- `agent_count` — total agents
- `agents_alive` — agents with active tmux sessions
- Per-agent presence data → count working/blocked/idle

---

## 3. Chat Screen (Full Screen, No Tab Bar)

### Header (44px height)

```
  ←  WAR ROOM      LIVE   ROLL CALL   ⚙
```

- **← back:** 44px tap target, returns to HomeScreen, tab bar reappears
- **WAR ROOM:** 11px JetBrains Mono, `#00e676`, letter-spacing 3
- **LIVE/OFFLINE:** badge, 9px JetBrains Mono, green bg with dark text / red bg with white text
- **ROLL CALL:** tappable text, 9px JetBrains Mono, triggers `POST /api/agents/rollcall` (or equivalent)
- **⚙:** settings icon (gear SVG), opens ActionSheet: Server Health, Restart Server, View Logs
- Background: `#0e1119`, border-bottom 1px `#1a2030`

### Messages area

Full screen minus header (44px) and input bar (~50px). No tab bar. Maximum vertical space.

Uses FlashList (inverted or scrolled to bottom) with:
- Agent messages left-aligned
- User messages right-aligned
- System messages centered
- Time dividers between gaps
- 20-second grouping window

### Input bar

iMessage-style, sits at bottom of screen:

```
  @all ▼
  (+)  Message the war room...   (▶)
```

- **+ button:** 32px grey circle (`#1a2030`), white + icon. Opens ActionSheet (Photo, Upload File, Project File)
- **Text input:** pill shape, borderRadius 20, bg `#0a0d14`, 16px Source Sans 3. Expands 1→3 lines
- **Send button:** 32px green circle, white arrow. Visible only when content present. Spring scale animation on press
- **Target selector:** `@all ▼` above input, 11px JetBrains Mono green. Tap opens agent picker ActionSheet

---

## 4. Legibility — Research Applied to Native

All findings from our deep contrast/density research session:

### Contrast

| Setting | Value | Impact |
|---------|-------|--------|
| Screen background | `#060810` (bgVoid) | 17.2:1 contrast with `#d8dee8` text |
| Message card background | None — transparent on `#060810` | Eliminates the 13.5:1 intermediate layer |
| Pure black avoided | `#060810` not `#000000` | Prevents halation and eye strain |

27% better contrast ratio than the current WebView card backgrounds.

### Text Density

| Setting | Value | Impact |
|---------|-------|--------|
| Agent message width | 95% of screen | +6 chars per line vs current 85% |
| User message width | 92% of screen | +5 chars per line vs current 80% |
| Container padding | 8px (down from 12px) | More horizontal space |
| Message padding | 8px vertical, 10px horizontal | Tighter but readable |

18% more characters per line (~39 vs ~33 on iPhone).

### Typography

| Element | Font | Size | Weight | Line-height | Letter-spacing | Color |
|---------|------|------|--------|-------------|---------------|-------|
| Message body | Source Sans 3 | 16px | 400 | 24 (1.5×) | 0.2 | `#d8dee8` |
| Sender name | JetBrains Mono | 12px | 700 | 16 | 0 | agent color |
| Timestamp | JetBrains Mono | 11px | 400 | 14 | 0 | `#3e4e64` |
| System message | Source Sans 3 | 12px | 400 italic | 18 | 0 | `#3e4e64` |
| Target tag (@name) | JetBrains Mono | 10px | 400 | 12 | 0 | `#ff9100` |
| Time divider | JetBrains Mono | 10px | 400 | 12 | 0 | `#3e4e64` |

Source Sans 3 confirmed as optimal — renders more characters per line than Inter or SF Pro at same size, best x-height ratio for small text.

### Vertical Space Gain

| Component | Before (flat tabs) | After (stack nav) |
|-----------|--------------------|--------------------|
| Tab bar | 50px always visible | Hidden in chat |
| Header | ~44px | 44px (same) |
| Input bar | ~50px + 50px tab bar below | ~50px at screen bottom |
| **Net chat area** | screen - 144px | screen - 94px |
| **Gain** | | **+50px = 3-4 more message lines** |

### Combined Impact

- 27% better contrast ratio
- 18% more characters per line
- 50px more vertical space (3-4 extra message lines)
- Native text rendering (sharper than WebView on Retina)

---

## 5. Message Types

### Agent messages (left-aligned, no card background)

- Left border: 3px solid, agent's resolved color
- Sender name: 12px JetBrains Mono, bold, agent color + timestamp 11px dim inline
- Body: 16px Source Sans 3, `#d8dee8`, letter-spacing 0.2, line-height 24
- Max width: 95% of screen
- Padding: 8px vertical, 10px horizontal
- No background color — text on `#060810`
- Bottom margin: 4px (grouped), 12px (standalone)

### User messages (right-aligned, green tint)

- Background: `rgba(0, 230, 118, 0.08)`
- Border radius: 16px 16px 4px 16px
- No sender name
- Body: 16px Source Sans 3, `#d8dee8`, letter-spacing 0.2, line-height 24
- Timestamp: 11px, `#3e4e64`, below bubble, right-aligned
- Max width: 92% of screen
- Padding: 10px 12px

### System messages (centered)

- No bubble, no border
- 12px Source Sans 3, italic, `#3e4e64`
- Centered, margin 4px vertical

### Direct messages (@you)

- Same as agent but left border color `#ff9100` (orange)

---

## 6. Grouping Rules

1. **Never group across different senders**
2. **Same sender, within 20 seconds** — stack tight (4px gap), header on first only
3. **Same sender, 20+ seconds apart** — full header
4. **Time dividers** — 5+ minute gap: `── 12:45 PM ──`
5. **Day dividers** — midnight: `── Today ──`, `── Yesterday ──`, `── Mon, 31 Mar ──`

---

## 7. WebSocket Hook

- URL: `ws://100.119.47.67:5680/ws`
- Shared between HomeScreen and ChatScreen (single hook instance via context or prop drilling)
- Auto-reconnect: 2s delay, exponential backoff to 10s
- AppState: reconnect on foreground
- Exposes: `{ messages, isConnected, send, agentRoster, agentData }`
- `agentData` provides health counts for the home screen card

---

## 8. Tab Bar

React Navigation bottom tabs:
- Background: `#0e1119`
- Border top: 1px `#1a2030`
- Active: `#00e676`, Inactive: `#3e4e64`
- Icons: SVG (chat bubble, users, folder)
- Labels: 9px JetBrains Mono, letterspaced
- **Hidden when ChatScreen is active** via `tabBarStyle: { display: 'none' }`

---

## 9. WebView Tabs (Agents + Files)

Same as before — load `http://100.119.47.67:5680` with injected JS to:
1. Switch to correct tab: `switchTab('agents')` or `switchTab('files')`
2. Hide web tab bar: `.tab-bar { display: none !important; }`
3. Adjust layout: `.input-bar { bottom: 0 !important; }`

---

## 10. File Structure

```
~/warroom-mobile/
├── App.js                          # Tab navigator + Home stack + font loading
├── src/
│   ├── screens/
│   │   ├── HomeScreen.js           # War Room card with health summary
│   │   ├── ChatScreen.js           # Full-screen chat (tab bar hidden)
│   │   ├── AgentsScreen.js         # WebView wrapper
│   │   └── FilesScreen.js          # WebView wrapper
│   ├── components/
│   │   ├── WarRoomCard.js          # Hero card with breathing green dot
│   │   ├── ChatHeader.js           # ← WAR ROOM LIVE ROLL CALL ⚙
│   │   ├── MessageBubble.js        # Agent/user/system message
│   │   ├── TimeDivider.js          # Time separator
│   │   └── ChatInputBar.js         # iMessage-style: + pill send
│   ├── hooks/
│   │   └── useWebSocket.js         # Connection + messages + agent data
│   └── constants/
│       ├── colors.js               # Palette + role colors
│       └── icons.js                # SVG icon components
├── app.json
└── package.json
```

---

## 11. New Dependencies

| Package | Purpose |
|---------|---------|
| `@react-navigation/native` | Navigation core |
| `@react-navigation/bottom-tabs` | Tab navigator |
| `@react-navigation/native-stack` | Stack navigator (Home → Chat) |
| `react-native-screens` | Required by React Navigation |
| `@shopify/flash-list` | Fast message list |
| `expo-font` | Custom fonts |
| `expo-splash-screen` | Splash until fonts ready |
| `react-native-svg` | SVG icons |

Note: `@react-navigation/native-stack` added (was not in v1 spec) — needed for Home → Chat stack push.

---

## 12. What Does NOT Change

- Server (server.py) — zero modifications
- Web UI (static/index.html) — zero modifications
- WebSocket protocol
- Desktop web UI

---

## 13. Implementation Watch Items

From code review — these must be addressed during implementation:

### Keyboard Handling
Use `Keyboard.addListener('keyboardWillShow'/'keyboardWillHide')` with `Animated.timing` and `useNativeDriver: false` (position animation can't use native driver). Ensure FlashList content inset adjusts correctly when keyboard appears. Test on physical iPhone — simulator keyboard behavior differs.

### Image Previews
Messages containing `[uploaded: path]` with image extensions need a `MessageMedia` component for inline image previews within the 95% width constraint. Use `Image` from React Native with `resizeMode="contain"`, max-height 300px, borderRadius 8px.

### WebView Synchronization
Agents/Files WebView tabs maintain their own WebSocket connections. If agent status changes while viewing the native Chat, the WebView tabs won't know until they receive their next `agent_status` broadcast (which happens every few seconds via the server's periodic push). This is acceptable — no extra sync needed since the server broadcasts to all connections.

### Breathing Dot Animation
Use `useNativeDriver: true` for the opacity animation (shadow pulse is CSS-only on web; on RN use animated opacity on an outer glow View). Keeps animation off the JS thread when WebSocket is busy processing messages.

### Haptic Feedback
Add `expo-haptics` — use `Haptics.impactAsync(ImpactFeedbackStyle.Light)` on:
- Tapping the War Room card
- Sending a message (send button press)
- Pull-to-refresh completion

### Connectivity State
When WebSocket is OFFLINE:
- Home screen card: green dot turns grey, "ONLINE" → "OFFLINE" in red
- Chat screen: show a thin red bar below header: "Reconnecting..." with activity indicator
- Input bar: greyed out, send disabled, placeholder changes to "Connecting..."

---

## 14. New Dependencies (updated)

| Package | Purpose |
|---------|---------|
| `@react-navigation/native` | Navigation core |
| `@react-navigation/bottom-tabs` | Tab navigator |
| `@react-navigation/native-stack` | Stack navigator (Home → Chat) |
| `react-native-screens` | Required by React Navigation |
| `@shopify/flash-list` | Fast message list |
| `expo-font` | Custom fonts |
| `expo-splash-screen` | Splash until fonts ready |
| `react-native-svg` | SVG icons |
| `expo-haptics` | Haptic feedback on tap/send |

---

## 15. Success Criteria

1. Home screen shows War Room card with breathing green dot and agent health
2. Tapping card pushes to full-screen Chat — tab bar disappears
3. Haptic feedback on card tap and message send
4. Chat header has: back, WAR ROOM, LIVE, ROLL CALL, ⚙
5. Back button returns to Home — tab bar reappears
6. Messages render natively (not WebView) with correct alignment
7. Legibility: text on #060810 (17.2:1 contrast), 95% width, 16px, letter-spacing 0.2
8. FlashList scrolls smoothly through 200+ messages
9. 20-second grouping + time dividers after 5+ min gaps
10. Input bar: + circle, pill, green send circle (iMessage-style)
11. Keyboard animation smooth (custom Animated.timing)
12. Target selector (@all / @agent) via ActionSheet
13. Agents tab works via WebView (web tab bar hidden)
14. Files tab works via WebView (web tab bar hidden)
15. Fonts loaded: Source Sans 3 + JetBrains Mono
16. WebSocket reconnects on foreground return
17. Home screen updates agent counts in real-time via WebSocket
18. Breathing dot uses native driver (off JS thread)
19. OFFLINE state: grey dot, red bar in chat, greyed input
20. Image previews render inline for uploaded images
