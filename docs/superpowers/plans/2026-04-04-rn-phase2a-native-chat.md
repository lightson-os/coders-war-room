# React Native Phase 2a: Native Chat Screen — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Chat tab's WebView with a fully native React Native chat screen featuring FlashList, iMessage-style input bar, and legibility-optimized typography — while keeping Agents and Files as WebView tabs.

**Architecture:** Bottom-up build: constants → WebSocket hook → message components → input bar → chat screen → WebView wrapper screens → App.js with React Navigation tabs. Each task produces a testable file. The native Chat connects to the server via its own WebSocket; WebView tabs keep their existing HTML-based connections.

**Tech Stack:** React Native 0.81, Expo SDK 54, React Navigation bottom-tabs, @shopify/flash-list, expo-font, react-native-svg, react-native-webview.

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `src/constants/colors.js` | Create | All color values, role→color map, resolution function |
| `src/constants/icons.js` | Create | SVG icon components for tab bar and input |
| `src/hooks/useWebSocket.js` | Create | WebSocket connection, messages state, send function |
| `src/components/MessageBubble.js` | Create | Single message render — agent card or user bubble |
| `src/components/TimeDivider.js` | Create | Time/day divider separator |
| `src/components/ChatInputBar.js` | Create | iMessage-style input: + button, pill, send |
| `src/screens/ChatScreen.js` | Create | FlashList + input bar + keyboard handling |
| `src/screens/AgentsScreen.js` | Create | WebView wrapper, injects switchTab('agents') |
| `src/screens/FilesScreen.js` | Create | WebView wrapper, injects switchTab('files') |
| `App.js` | Modify | React Navigation tabs + font loading |

---

### Task 1: Install Dependencies + Download Fonts

**Files:**
- Modify: `~/warroom-mobile/package.json` (via npm)
- Create: `~/warroom-mobile/assets/fonts/` directory with font files

- [ ] **Step 1: Install all new dependencies**

```bash
export NVM_DIR="$HOME/.nvm" && [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh" && nvm use node
cd ~/warroom-mobile
npx expo install @react-navigation/native @react-navigation/bottom-tabs react-native-screens @shopify/flash-list expo-font expo-splash-screen react-native-svg
```

- [ ] **Step 2: Download Source Sans 3 and JetBrains Mono fonts**

```bash
cd ~/warroom-mobile
mkdir -p assets/fonts

# Source Sans 3
curl -L -o /tmp/source-sans-3.zip "https://fonts.google.com/download?family=Source+Sans+3"
unzip -o /tmp/source-sans-3.zip -d /tmp/source-sans-3/
cp /tmp/source-sans-3/static/SourceSans3-Regular.ttf assets/fonts/
cp /tmp/source-sans-3/static/SourceSans3-SemiBold.ttf assets/fonts/

# JetBrains Mono
curl -L -o /tmp/jetbrains-mono.zip "https://fonts.google.com/download?family=JetBrains+Mono"
unzip -o /tmp/jetbrains-mono.zip -d /tmp/jetbrains-mono/
cp /tmp/jetbrains-mono/static/JetBrainsMono-Regular.ttf assets/fonts/
cp /tmp/jetbrains-mono/static/JetBrainsMono-Bold.ttf assets/fonts/

ls -la assets/fonts/
```

Expected: 4 .ttf files in assets/fonts/

- [ ] **Step 3: Create src directory structure**

```bash
cd ~/warroom-mobile
mkdir -p src/constants src/hooks src/components src/screens
```

- [ ] **Step 4: Commit**

```bash
cd ~/warroom-mobile
git add -A
git commit -m "feat(2a): step 1 — install dependencies + download fonts"
```

---

### Task 2: Constants — Colors + Icons

**Files:**
- Create: `~/warroom-mobile/src/constants/colors.js`
- Create: `~/warroom-mobile/src/constants/icons.js`

- [ ] **Step 1: Create colors.js**

Write `~/warroom-mobile/src/constants/colors.js`:

```javascript
// War Room color palette
export const COLORS = {
  bgVoid: '#060810',
  bgDeep: '#0a0d14',
  bgPanel: '#0e1119',
  bgCard: '#121620',
  bgCardHover: '#171c28',
  bgElevated: '#1a2030',
  border: '#1a2030',
  borderBright: '#243044',
  textPrimary: '#d8dee8',
  textSecondary: '#7a8a9e',
  textDim: '#3e4e64',
  green: '#00e676',
  greenDim: 'rgba(0,230,118,0.12)',
  greenBubble: 'rgba(0,230,118,0.08)',
  yellow: '#ffd740',
  cyan: '#18ffff',
  orange: '#ff9100',
  red: '#ff5252',
  blue: '#448aff',
  purple: '#b388ff',
  pink: '#ff80ab',
};

// Role → color defaults
const ROLE_COLOR_MAP = {
  supervisor: COLORS.purple, lead: COLORS.purple, director: COLORS.purple,
  engineer: COLORS.blue, builder: COLORS.blue, developer: COLORS.blue, coder: COLORS.blue,
  scout: COLORS.cyan, researcher: COLORS.cyan, investigator: COLORS.cyan,
  qa: COLORS.red, 'q-a': COLORS.red, quality: COLORS.red, tester: COLORS.red,
  git: COLORS.yellow, 'git-agent': COLORS.yellow, vcs: COLORS.yellow,
  chronicler: COLORS.pink, observer: COLORS.pink, logger: COLORS.pink,
  gurvinder: COLORS.orange, operator: COLORS.orange,
};

const EXTRA_SWATCHES = ['#64ffda', '#b9f6ca', '#ff6e40', '#8c9eff', '#ffcc80', '#84ffff', '#f48fb1', '#ce93d8'];

export function resolveAgentColor(agent) {
  if (agent && agent.color) return agent.color;
  const name = (agent?.name || '').toLowerCase();
  for (const [kw, c] of Object.entries(ROLE_COLOR_MAP)) {
    if (name.includes(kw)) return c;
  }
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = ((hash << 5) - hash + name.charCodeAt(i)) | 0;
  return EXTRA_SWATCHES[Math.abs(hash) % EXTRA_SWATCHES.length];
}

// Presence → color mapping
export const PRESENCE_COLORS = {
  active: COLORS.green,
  busy: COLORS.yellow,
  typing: COLORS.cyan,
  session: COLORS.textDim,
  offline: '#555555',
};
```

- [ ] **Step 2: Create icons.js**

Write `~/warroom-mobile/src/constants/icons.js`:

```javascript
import React from 'react';
import Svg, { Path, Line, Circle, Polyline, Rect } from 'react-native-svg';

export function ChatIcon({ size = 22, color = '#3e4e64' }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
      <Path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </Svg>
  );
}

export function UsersIcon({ size = 22, color = '#3e4e64' }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
      <Path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <Circle cx="9" cy="7" r="4" />
      <Path d="M23 21v-2a4 4 0 0 0-3-3.87" />
      <Path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </Svg>
  );
}

export function FolderIcon({ size = 22, color = '#3e4e64' }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
      <Path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
    </Svg>
  );
}

export function PlusIcon({ size = 16, color = 'white' }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2.5} strokeLinecap="round">
      <Line x1="12" y1="5" x2="12" y2="19" />
      <Line x1="5" y1="12" x2="19" y2="12" />
    </Svg>
  );
}

export function SendIcon({ size = 14, color = 'white' }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill={color}>
      <Path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
    </Svg>
  );
}
```

- [ ] **Step 3: Commit**

```bash
cd ~/warroom-mobile
git add src/constants/
git commit -m "feat(2a): step 2 — color palette, role color resolution, SVG icon components"
```

---

### Task 3: WebSocket Hook

**Files:**
- Create: `~/warroom-mobile/src/hooks/useWebSocket.js`

- [ ] **Step 1: Create useWebSocket.js**

Write `~/warroom-mobile/src/hooks/useWebSocket.js`:

```javascript
import { useState, useEffect, useRef, useCallback } from 'react';
import { AppState } from 'react-native';

const WS_URL = 'ws://100.119.47.67:5680/ws';
const RECONNECT_BASE = 2000;
const RECONNECT_MAX = 10000;

export default function useWebSocket() {
  const [messages, setMessages] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const agentRoster = useRef([]);
  const agentData = useRef({});
  const ws = useRef(null);
  const reconnectDelay = useRef(RECONNECT_BASE);
  const reconnectTimer = useRef(null);
  const appState = useRef(AppState.currentState);

  const connect = useCallback(() => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) return;

    try {
      ws.current = new WebSocket(WS_URL);

      ws.current.onopen = () => {
        setIsConnected(true);
        reconnectDelay.current = RECONNECT_BASE;
      };

      ws.current.onmessage = (event) => {
        try {
          const d = JSON.parse(event.data);

          if (d.type === 'history') {
            setMessages(d.messages || []);
          } else if (d.type === 'message') {
            setMessages(prev => [...prev, d.message]);
          } else if (d.type === 'agent_status') {
            agentData.current = d.agents || {};
            if (d.roster) agentRoster.current = d.roster;
          } else if (d.type === 'agent_created') {
            const a = d.agent;
            if (!agentRoster.current.find(x => x.name === a.name)) {
              agentRoster.current = [...agentRoster.current, { name: a.name, role: a.role }];
            }
          } else if (d.type === 'agent_removed') {
            agentRoster.current = agentRoster.current.filter(x => x.name !== d.agent);
          } else if (d.type === 'membership') {
            if (agentData.current[d.agent]) {
              agentData.current[d.agent].in_room = d.in_room;
            }
          }
        } catch (e) {
          // Ignore malformed messages
        }
      };

      ws.current.onclose = () => {
        setIsConnected(false);
        // Auto-reconnect with exponential backoff
        if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
        reconnectTimer.current = setTimeout(() => {
          reconnectDelay.current = Math.min(reconnectDelay.current * 1.5, RECONNECT_MAX);
          connect();
        }, reconnectDelay.current);
      };

      ws.current.onerror = () => {
        ws.current?.close();
      };
    } catch (e) {
      // Connection failed, will retry via onclose
    }
  }, []);

  const send = useCallback((payload) => {
    const msg = {
      sender: 'gurvinder',
      type: 'message',
      ...payload,
    };

    // Optimistic render
    const localMsg = { ...msg, timestamp: new Date().toISOString() };
    setMessages(prev => [...prev, localMsg]);

    // Send via WebSocket
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(msg));
    }
  }, []);

  // Connect on mount
  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (ws.current) ws.current.close();
    };
  }, [connect]);

  // Reconnect on foreground
  useEffect(() => {
    const sub = AppState.addEventListener('change', (nextState) => {
      if (appState.current.match(/inactive|background/) && nextState === 'active') {
        if (!ws.current || ws.current.readyState !== WebSocket.OPEN) {
          connect();
        }
      }
      appState.current = nextState;
    });
    return () => sub?.remove();
  }, [connect]);

  return { messages, isConnected, send, agentRoster, agentData };
}
```

- [ ] **Step 2: Commit**

```bash
cd ~/warroom-mobile
git add src/hooks/
git commit -m "feat(2a): step 3 — useWebSocket hook with reconnect and AppState"
```

---

### Task 4: Message Components — MessageBubble + TimeDivider

**Files:**
- Create: `~/warroom-mobile/src/components/MessageBubble.js`
- Create: `~/warroom-mobile/src/components/TimeDivider.js`

- [ ] **Step 1: Create TimeDivider.js**

Write `~/warroom-mobile/src/components/TimeDivider.js`:

```javascript
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { COLORS } from '../constants/colors';

export default function TimeDivider({ text }) {
  return (
    <View style={styles.container}>
      <View style={styles.line} />
      <Text style={styles.text}>{text}</Text>
      <View style={styles.line} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    marginVertical: 16,
    paddingHorizontal: 12,
  },
  line: {
    flex: 1,
    height: 1,
    backgroundColor: COLORS.border,
  },
  text: {
    fontFamily: 'JetBrainsMono-Regular',
    fontSize: 10,
    color: COLORS.textDim,
    marginHorizontal: 8,
  },
});
```

- [ ] **Step 2: Create MessageBubble.js**

Write `~/warroom-mobile/src/components/MessageBubble.js`:

```javascript
import React, { memo } from 'react';
import { View, Text, StyleSheet, Dimensions } from 'react-native';
import { COLORS, resolveAgentColor } from '../constants/colors';

const SCREEN_WIDTH = Dimensions.get('window').width;

function MessageBubble({ message, isGrouped }) {
  const { sender, content, timestamp, type, target } = message;
  const isSystem = type === 'system';
  const isUser = sender === 'gurvinder';
  const isDirect = !isSystem && target && target !== 'all';

  if (isSystem) {
    return (
      <View style={styles.systemContainer}>
        <Text style={styles.systemText}>{content}</Text>
      </View>
    );
  }

  const agentColor = isUser ? COLORS.green : resolveAgentColor(message);
  const borderColor = isDirect && !isUser ? COLORS.orange : agentColor;

  // Format timestamp
  const ts = timestamp ? formatTime(timestamp) : '';

  if (isUser) {
    return (
      <View style={[styles.userContainer, isGrouped && styles.groupedMargin]}>
        <View style={styles.userBubble}>
          <Text style={styles.bodyText}>{content}</Text>
        </View>
        {!isGrouped && ts ? (
          <Text style={styles.userTimestamp}>{ts}</Text>
        ) : null}
      </View>
    );
  }

  // Agent message
  return (
    <View style={[styles.agentContainer, isGrouped && styles.groupedMargin]}>
      <View style={[styles.agentMessage, { borderLeftColor: borderColor }]}>
        {!isGrouped && (
          <View style={styles.header}>
            <Text style={[styles.senderName, { color: agentColor }]}>{sender}</Text>
            {isDirect && <Text style={styles.targetTag}>@{target}</Text>}
            <Text style={styles.timestamp}>{ts}</Text>
          </View>
        )}
        <Text style={styles.bodyText}>{content}</Text>
      </View>
    </View>
  );
}

function formatTime(isoString) {
  try {
    const d = new Date(isoString);
    let h = d.getHours();
    const m = String(d.getMinutes()).padStart(2, '0');
    const ampm = h >= 12 ? 'PM' : 'AM';
    h = h % 12 || 12;
    return `${h}:${m} ${ampm}`;
  } catch {
    return '';
  }
}

export default memo(MessageBubble);

const styles = StyleSheet.create({
  // Agent message
  agentContainer: {
    alignSelf: 'flex-start',
    maxWidth: SCREEN_WIDTH * 0.95,
    marginTop: 12,
    paddingHorizontal: 8,
  },
  agentMessage: {
    borderLeftWidth: 3,
    paddingVertical: 8,
    paddingHorizontal: 10,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'baseline',
    marginBottom: 3,
    gap: 6,
  },
  senderName: {
    fontFamily: 'JetBrainsMono-Bold',
    fontSize: 12,
  },
  targetTag: {
    fontFamily: 'JetBrainsMono-Regular',
    fontSize: 10,
    color: COLORS.orange,
    backgroundColor: 'rgba(255,145,0,0.08)',
    paddingHorizontal: 4,
    paddingVertical: 1,
    borderRadius: 3,
    overflow: 'hidden',
  },
  timestamp: {
    fontFamily: 'JetBrainsMono-Regular',
    fontSize: 11,
    color: COLORS.textDim,
  },
  bodyText: {
    fontFamily: 'SourceSans3-Regular',
    fontSize: 16,
    lineHeight: 24,
    letterSpacing: 0.2,
    color: COLORS.textPrimary,
  },

  // User message
  userContainer: {
    alignSelf: 'flex-end',
    maxWidth: SCREEN_WIDTH * 0.92,
    marginTop: 12,
    paddingHorizontal: 8,
  },
  userBubble: {
    backgroundColor: COLORS.greenBubble,
    borderRadius: 16,
    borderBottomRightRadius: 4,
    paddingVertical: 10,
    paddingHorizontal: 12,
  },
  userTimestamp: {
    fontFamily: 'JetBrainsMono-Regular',
    fontSize: 11,
    color: COLORS.textDim,
    textAlign: 'right',
    marginTop: 4,
    marginRight: 4,
  },

  // System message
  systemContainer: {
    alignSelf: 'center',
    maxWidth: SCREEN_WIDTH * 0.9,
    marginVertical: 4,
    paddingHorizontal: 12,
  },
  systemText: {
    fontFamily: 'SourceSans3-Regular',
    fontSize: 12,
    fontStyle: 'italic',
    color: COLORS.textDim,
    textAlign: 'center',
  },

  // Grouping
  groupedMargin: {
    marginTop: 4,
  },
});
```

- [ ] **Step 3: Commit**

```bash
cd ~/warroom-mobile
git add src/components/
git commit -m "feat(2a): step 4 — MessageBubble + TimeDivider components"
```

---

### Task 5: Chat Input Bar

**Files:**
- Create: `~/warroom-mobile/src/components/ChatInputBar.js`

- [ ] **Step 1: Create ChatInputBar.js**

Write `~/warroom-mobile/src/components/ChatInputBar.js`:

```javascript
import React, { useState, useRef } from 'react';
import {
  View, TextInput, TouchableOpacity, Text, StyleSheet, Animated,
  ActionSheetIOS, Platform,
} from 'react-native';
import { COLORS } from '../constants/colors';
import { PlusIcon, SendIcon } from '../constants/icons';

export default function ChatInputBar({ onSend, target, onTargetPress }) {
  const [text, setText] = useState('');
  const [inputHeight, setInputHeight] = useState(36);
  const sendScale = useRef(new Animated.Value(1)).current;
  const inputRef = useRef(null);

  const hasContent = text.trim().length > 0;

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setText('');
    setInputHeight(36);
  };

  const handleSendPressIn = () => {
    Animated.spring(sendScale, {
      toValue: 0.88,
      useNativeDriver: true,
      speed: 50,
      bounciness: 4,
    }).start();
  };

  const handleSendPressOut = () => {
    Animated.spring(sendScale, {
      toValue: 1,
      useNativeDriver: true,
      speed: 50,
      bounciness: 4,
    }).start();
  };

  const handlePlus = () => {
    if (Platform.OS === 'ios') {
      ActionSheetIOS.showActionSheetWithOptions(
        {
          options: ['Cancel', 'Photo', 'Upload File', 'Project File'],
          cancelButtonIndex: 0,
        },
        (buttonIndex) => {
          // Phase 2a: attachment handling placeholder — will wire in Phase 2b
          if (buttonIndex === 1) { /* Photo */ }
          else if (buttonIndex === 2) { /* File */ }
          else if (buttonIndex === 3) { /* Project file */ }
        },
      );
    }
  };

  const handleContentSizeChange = (e) => {
    const h = e.nativeEvent.contentSize.height;
    setInputHeight(Math.min(Math.max(36, h), 84));
  };

  return (
    <View style={styles.container}>
      {/* Target selector */}
      <TouchableOpacity onPress={onTargetPress} activeOpacity={0.7}>
        <Text style={styles.targetLabel}>@{target || 'all'} ▼</Text>
      </TouchableOpacity>

      {/* Input row */}
      <View style={styles.inputRow}>
        {/* Plus button */}
        <TouchableOpacity style={styles.plusButton} onPress={handlePlus} activeOpacity={0.7}>
          <PlusIcon size={16} color="white" />
        </TouchableOpacity>

        {/* Text input pill */}
        <View style={styles.pillContainer}>
          <TextInput
            ref={inputRef}
            style={[styles.textInput, { height: inputHeight }]}
            value={text}
            onChangeText={setText}
            onContentSizeChange={handleContentSizeChange}
            placeholder="Message the war room..."
            placeholderTextColor={COLORS.textDim}
            multiline
            maxLength={4000}
            returnKeyType="default"
            blurOnSubmit={false}
          />
        </View>

        {/* Send button */}
        {hasContent && (
          <TouchableOpacity
            onPress={handleSend}
            onPressIn={handleSendPressIn}
            onPressOut={handleSendPressOut}
            activeOpacity={1}
          >
            <Animated.View style={[styles.sendButton, { transform: [{ scale: sendScale }] }]}>
              <SendIcon size={14} color={COLORS.bgVoid} />
            </Animated.View>
          </TouchableOpacity>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: COLORS.bgPanel,
    borderTopWidth: 1,
    borderTopColor: COLORS.border,
    paddingHorizontal: 12,
    paddingTop: 6,
    paddingBottom: 6,
  },
  targetLabel: {
    fontFamily: 'JetBrainsMono-Regular',
    fontSize: 11,
    color: COLORS.green,
    marginBottom: 4,
    paddingLeft: 44,
  },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 8,
  },
  plusButton: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: COLORS.bgElevated,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 2,
  },
  pillContainer: {
    flex: 1,
    backgroundColor: COLORS.bgDeep,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: COLORS.border,
    paddingHorizontal: 14,
    paddingVertical: 2,
    justifyContent: 'center',
  },
  textInput: {
    fontFamily: 'SourceSans3-Regular',
    fontSize: 16,
    color: COLORS.textPrimary,
    lineHeight: 22,
    minHeight: 36,
    maxHeight: 84,
    paddingTop: 8,
    paddingBottom: 8,
  },
  sendButton: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: COLORS.green,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 2,
  },
});
```

- [ ] **Step 2: Commit**

```bash
cd ~/warroom-mobile
git add src/components/ChatInputBar.js
git commit -m "feat(2a): step 5 — iMessage-style ChatInputBar with + button and send"
```

---

### Task 6: Chat Screen — FlashList + Keyboard Handling

**Files:**
- Create: `~/warroom-mobile/src/screens/ChatScreen.js`

- [ ] **Step 1: Create ChatScreen.js**

Write `~/warroom-mobile/src/screens/ChatScreen.js`:

```javascript
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { View, StyleSheet, Keyboard, Animated, ActionSheetIOS, Platform } from 'react-native';
import { FlashList } from '@shopify/flash-list';
import { COLORS } from '../constants/colors';
import useWebSocket from '../hooks/useWebSocket';
import MessageBubble from '../components/MessageBubble';
import TimeDivider from '../components/TimeDivider';
import ChatInputBar from '../components/ChatInputBar';

const GROUPING_WINDOW = 20000; // 20 seconds
const DIVIDER_GAP = 300000; // 5 minutes

export default function ChatScreen() {
  const { messages, isConnected, send, agentRoster } = useWebSocket();
  const [target, setTarget] = useState('all');
  const [keyboardOffset, setKeyboardOffset] = useState(0);
  const keyboardAnim = useRef(new Animated.Value(0)).current;
  const listRef = useRef(null);

  // Keyboard animation
  useEffect(() => {
    const showSub = Keyboard.addListener('keyboardWillShow', (e) => {
      const height = e.endCoordinates.height;
      setKeyboardOffset(height);
      Animated.timing(keyboardAnim, {
        toValue: height,
        duration: e.duration || 250,
        useNativeDriver: false,
      }).start();
    });

    const hideSub = Keyboard.addListener('keyboardWillHide', (e) => {
      setKeyboardOffset(0);
      Animated.timing(keyboardAnim, {
        toValue: 0,
        duration: e.duration || 250,
        useNativeDriver: false,
      }).start();
    });

    return () => {
      showSub.remove();
      hideSub.remove();
    };
  }, [keyboardAnim]);

  // Process messages into list items with dividers and grouping
  const listData = useCallback(() => {
    const items = [];
    let prevSender = null;
    let prevTimestamp = null;

    messages.forEach((msg, i) => {
      // Time divider check
      if (msg.type !== 'system' && msg.timestamp && prevTimestamp) {
        const prev = new Date(prevTimestamp);
        const curr = new Date(msg.timestamp);
        const gap = curr - prev;

        if (prev.toDateString() !== curr.toDateString()) {
          // Day divider
          items.push({ type: 'divider', id: `div-${i}`, text: formatDayDivider(msg.timestamp) });
        } else if (gap > DIVIDER_GAP) {
          // Time divider
          items.push({ type: 'divider', id: `div-${i}`, text: formatTimeShort(msg.timestamp) });
        }
      }

      // Grouping
      const isGrouped = msg.type !== 'system'
        && msg.sender === prevSender
        && prevTimestamp
        && msg.timestamp
        && (new Date(msg.timestamp) - new Date(prevTimestamp)) < GROUPING_WINDOW;

      items.push({
        type: 'message',
        id: msg.id || `msg-${i}`,
        message: msg,
        isGrouped,
      });

      if (msg.type !== 'system') {
        prevSender = msg.sender;
        prevTimestamp = msg.timestamp;
      } else {
        prevSender = null;
      }
    });

    return items;
  }, [messages]);

  const handleSend = useCallback((text) => {
    send({ target, content: text });
    // Scroll to bottom after sending
    setTimeout(() => {
      listRef.current?.scrollToEnd({ animated: true });
    }, 100);
  }, [target, send]);

  const handleTargetPress = useCallback(() => {
    const agents = agentRoster.current || [];
    const options = ['Cancel', '@all', ...agents.map(a => `@${a.name}`)];

    if (Platform.OS === 'ios') {
      ActionSheetIOS.showActionSheetWithOptions(
        { options, cancelButtonIndex: 0, title: 'Send to...' },
        (idx) => {
          if (idx === 1) setTarget('all');
          else if (idx > 1) setTarget(agents[idx - 2].name);
        },
      );
    }
  }, [agentRoster]);

  const renderItem = useCallback(({ item }) => {
    if (item.type === 'divider') {
      return <TimeDivider text={item.text} />;
    }
    return <MessageBubble message={item.message} isGrouped={item.isGrouped} />;
  }, []);

  const data = listData();

  return (
    <View style={styles.container}>
      <Animated.View style={[styles.content, { marginBottom: keyboardAnim }]}>
        <FlashList
          ref={listRef}
          data={data}
          renderItem={renderItem}
          estimatedItemSize={80}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.listContent}
          showsVerticalScrollIndicator={false}
          onContentSizeChange={() => {
            listRef.current?.scrollToEnd({ animated: false });
          }}
        />
        <ChatInputBar
          onSend={handleSend}
          target={target}
          onTargetPress={handleTargetPress}
        />
      </Animated.View>
    </View>
  );
}

function formatTimeShort(isoString) {
  try {
    const d = new Date(isoString);
    let h = d.getHours();
    const m = String(d.getMinutes()).padStart(2, '0');
    const ampm = h >= 12 ? 'PM' : 'AM';
    h = h % 12 || 12;
    return `${h}:${m} ${ampm}`;
  } catch {
    return '';
  }
}

function formatDayDivider(isoString) {
  try {
    const d = new Date(isoString);
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const msgDay = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    const diff = Math.floor((today - msgDay) / 86400000);
    if (diff === 0) return 'Today';
    if (diff === 1) return 'Yesterday';
    const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return `${days[d.getDay()]}, ${d.getDate()} ${months[d.getMonth()]}`;
  } catch {
    return '';
  }
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.bgVoid,
  },
  content: {
    flex: 1,
  },
  listContent: {
    paddingTop: 8,
    paddingBottom: 8,
  },
});
```

- [ ] **Step 2: Commit**

```bash
cd ~/warroom-mobile
git add src/screens/ChatScreen.js
git commit -m "feat(2a): step 6 — ChatScreen with FlashList, grouping, keyboard animation"
```

---

### Task 7: WebView Wrapper Screens (Agents + Files)

**Files:**
- Create: `~/warroom-mobile/src/screens/AgentsScreen.js`
- Create: `~/warroom-mobile/src/screens/FilesScreen.js`

- [ ] **Step 1: Create AgentsScreen.js**

Write `~/warroom-mobile/src/screens/AgentsScreen.js`:

```javascript
import React, { useRef, useCallback } from 'react';
import { View, StyleSheet } from 'react-native';
import { WebView } from 'react-native-webview';
import * as Linking from 'expo-linking';
import { COLORS } from '../constants/colors';

const SERVER_URL = 'http://100.119.47.67:5680';

const INJECT_JS = `
(function() {
  // Hide the web tab bar — native tabs replace it
  const style = document.createElement('style');
  style.textContent = '.tab-bar { display: none !important; } .input-bar { bottom: 0 !important; } .chat .messages { padding-bottom: 80px !important; }';
  document.head.appendChild(style);

  // Switch to Agents tab
  function waitAndSwitch() {
    if (typeof switchTab === 'function') {
      switchTab('agents');
    } else {
      setTimeout(waitAndSwitch, 200);
    }
  }
  if (document.readyState === 'complete') waitAndSwitch();
  else window.addEventListener('load', waitAndSwitch);
})();
true;
`;

export default function AgentsScreen() {
  const webviewRef = useRef(null);

  const handleNavRequest = useCallback((request) => {
    if (request.url.startsWith(SERVER_URL) || request.url.startsWith('ws://')) return true;
    Linking.openURL(request.url).catch(() => {});
    return false;
  }, []);

  return (
    <View style={styles.container}>
      <WebView
        ref={webviewRef}
        source={{ uri: SERVER_URL }}
        style={styles.webview}
        injectedJavaScript={INJECT_JS}
        javaScriptEnabled={true}
        domStorageEnabled={true}
        allowsBackForwardNavigationGestures={false}
        cacheEnabled={true}
        contentMode="mobile"
        keyboardDisplayRequiresUserAction={false}
        hideKeyboardAccessoryView={true}
        onShouldStartLoadWithRequest={handleNavRequest}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bgVoid },
  webview: { flex: 1, backgroundColor: COLORS.bgVoid },
});
```

- [ ] **Step 2: Create FilesScreen.js**

Write `~/warroom-mobile/src/screens/FilesScreen.js`:

```javascript
import React, { useRef, useCallback } from 'react';
import { View, StyleSheet } from 'react-native';
import { WebView } from 'react-native-webview';
import * as Linking from 'expo-linking';
import { COLORS } from '../constants/colors';

const SERVER_URL = 'http://100.119.47.67:5680';

const INJECT_JS = `
(function() {
  const style = document.createElement('style');
  style.textContent = '.tab-bar { display: none !important; } .input-bar { display: none !important; }';
  document.head.appendChild(style);

  function waitAndSwitch() {
    if (typeof switchTab === 'function') {
      switchTab('files');
    } else {
      setTimeout(waitAndSwitch, 200);
    }
  }
  if (document.readyState === 'complete') waitAndSwitch();
  else window.addEventListener('load', waitAndSwitch);
})();
true;
`;

export default function FilesScreen() {
  const webviewRef = useRef(null);

  const handleNavRequest = useCallback((request) => {
    if (request.url.startsWith(SERVER_URL) || request.url.startsWith('ws://')) return true;
    Linking.openURL(request.url).catch(() => {});
    return false;
  }, []);

  return (
    <View style={styles.container}>
      <WebView
        ref={webviewRef}
        source={{ uri: SERVER_URL }}
        style={styles.webview}
        injectedJavaScript={INJECT_JS}
        javaScriptEnabled={true}
        domStorageEnabled={true}
        allowsBackForwardNavigationGestures={false}
        cacheEnabled={true}
        contentMode="mobile"
        keyboardDisplayRequiresUserAction={false}
        hideKeyboardAccessoryView={true}
        onShouldStartLoadWithRequest={handleNavRequest}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bgVoid },
  webview: { flex: 1, backgroundColor: COLORS.bgVoid },
});
```

- [ ] **Step 3: Commit**

```bash
cd ~/warroom-mobile
git add src/screens/
git commit -m "feat(2a): step 7 — AgentsScreen + FilesScreen WebView wrappers with tab injection"
```

---

### Task 8: App.js — Tab Navigator + Font Loading

**Files:**
- Modify: `~/warroom-mobile/App.js` (complete rewrite)

- [ ] **Step 1: Replace App.js entirely**

Replace the entire contents of `~/warroom-mobile/App.js` with:

```javascript
import React, { useCallback, useEffect, useState } from 'react';
import { View, ActivityIndicator, StyleSheet } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import * as Font from 'expo-font';
import * as SplashScreen from 'expo-splash-screen';

import ChatScreen from './src/screens/ChatScreen';
import AgentsScreen from './src/screens/AgentsScreen';
import FilesScreen from './src/screens/FilesScreen';
import { ChatIcon, UsersIcon, FolderIcon } from './src/constants/icons';
import { COLORS } from './src/constants/colors';

SplashScreen.preventAutoHideAsync();

const Tab = createBottomTabNavigator();

const navTheme = {
  dark: true,
  colors: {
    primary: COLORS.green,
    background: COLORS.bgVoid,
    card: COLORS.bgPanel,
    text: COLORS.textPrimary,
    border: COLORS.border,
    notification: COLORS.green,
  },
};

export default function App() {
  const [fontsLoaded, setFontsLoaded] = useState(false);

  useEffect(() => {
    async function loadFonts() {
      try {
        await Font.loadAsync({
          'SourceSans3-Regular': require('./assets/fonts/SourceSans3-Regular.ttf'),
          'SourceSans3-SemiBold': require('./assets/fonts/SourceSans3-SemiBold.ttf'),
          'JetBrainsMono-Regular': require('./assets/fonts/JetBrainsMono-Regular.ttf'),
          'JetBrainsMono-Bold': require('./assets/fonts/JetBrainsMono-Bold.ttf'),
        });
      } catch (e) {
        console.warn('Font loading failed:', e);
      } finally {
        setFontsLoaded(true);
      }
    }
    loadFonts();
  }, []);

  const onLayoutRootView = useCallback(async () => {
    if (fontsLoaded) {
      await SplashScreen.hideAsync();
    }
  }, [fontsLoaded]);

  if (!fontsLoaded) {
    return (
      <View style={styles.loading}>
        <ActivityIndicator size="large" color={COLORS.green} />
      </View>
    );
  }

  return (
    <SafeAreaProvider>
      <View style={styles.container} onLayout={onLayoutRootView}>
        <StatusBar style="light" backgroundColor={COLORS.bgVoid} />
        <NavigationContainer theme={navTheme}>
          <Tab.Navigator
            screenOptions={{
              headerShown: false,
              tabBarStyle: {
                backgroundColor: COLORS.bgPanel,
                borderTopColor: COLORS.border,
                borderTopWidth: 1,
                height: 50,
                paddingBottom: 4,
                paddingTop: 4,
              },
              tabBarActiveTintColor: COLORS.green,
              tabBarInactiveTintColor: COLORS.textDim,
              tabBarLabelStyle: {
                fontFamily: 'JetBrainsMono-Regular',
                fontSize: 9,
                letterSpacing: 0.5,
              },
            }}
          >
            <Tab.Screen
              name="Chat"
              component={ChatScreen}
              options={{
                tabBarIcon: ({ color }) => <ChatIcon color={color} />,
              }}
            />
            <Tab.Screen
              name="Agents"
              component={AgentsScreen}
              options={{
                tabBarIcon: ({ color }) => <UsersIcon color={color} />,
              }}
            />
            <Tab.Screen
              name="Files"
              component={FilesScreen}
              options={{
                tabBarIcon: ({ color }) => <FolderIcon color={color} />,
              }}
            />
          </Tab.Navigator>
        </NavigationContainer>
      </View>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.bgVoid,
  },
  loading: {
    flex: 1,
    backgroundColor: COLORS.bgVoid,
    justifyContent: 'center',
    alignItems: 'center',
  },
});
```

- [ ] **Step 2: Commit**

```bash
cd ~/warroom-mobile
git add App.js
git commit -m "feat(2a): step 8 — App.js with React Navigation tabs + font loading"
```

---

### Task 9: Test on iPhone via Expo Go

**Files:**
- No modifications — testing only

- [ ] **Step 1: Start Expo**

```bash
cd ~/warroom-mobile
source ~/.nvm/nvm.sh && nvm use node
npx expo start
```

- [ ] **Step 2: Ensure War Room server is running**

In another terminal:
```bash
curl -s http://100.119.47.67:5680/api/server/health | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'{d[\"status\"]} — {d[\"agent_count\"]} agents')"
```

- [ ] **Step 3: Scan QR code and test**

Verify on iPhone:
- [ ] Chat tab shows native message list (not WebView)
- [ ] Messages are legible — 16px on dark background
- [ ] Agent messages left-aligned with colored left border, no card background
- [ ] User messages right-aligned with green tint bubble
- [ ] Can type and send a message — appears in chat
- [ ] Grouping works (consecutive same-sender messages stack tight)
- [ ] Time dividers appear between gaps
- [ ] Input bar: + button (grey circle), pill text field, green send (appears on text)
- [ ] Send button has spring animation on press
- [ ] @all target selector works
- [ ] Keyboard pushes input up smoothly
- [ ] Agents tab loads WebView with agent cards (web tab bar hidden)
- [ ] Files tab loads WebView with file tree (web tab bar hidden)
- [ ] Tab bar: dark background, green active, SVG icons

- [ ] **Step 4: Commit final**

```bash
cd ~/warroom-mobile
git add -A
git commit -m "feat(2a): Phase 2a complete — native Chat screen with legibility research

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Success Criteria Checklist

| # | Criterion | Task |
|---|-----------|------|
| 1 | Chat tab renders natively | Task 6, 8 |
| 2 | Messages display correctly (agent left, user right) | Task 4 |
| 3 | Can send messages | Task 5, 6 |
| 4 | FlashList scrolls smoothly | Task 6 |
| 5 | 20-second grouping + time dividers | Task 6 |
| 6 | Input bar: + button, pill, green send | Task 5 |
| 7 | Keyboard animation smooth | Task 6 |
| 8 | Target selector works | Task 5, 6 |
| 9 | Agents tab via WebView (tab bar hidden) | Task 7 |
| 10 | Files tab via WebView (tab bar hidden) | Task 7 |
| 11 | Tab bar matches War Room theme | Task 8 |
| 12 | Fonts loaded (Source Sans 3 + JetBrains Mono) | Task 1, 8 |
| 13 | Legibility: #060810 bg, 95% width, 16px, letter-spacing 0.2 | Task 4 |
| 14 | WebSocket reconnects on foreground | Task 3 |
