# React Native Phase 1: Expo WebView Shell — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a React Native Expo app at `~/warroom-mobile/` that wraps the existing War Room web UI in a native WebView shell, installable via Expo Go on iPhone.

**Architecture:** Minimal Expo project — one App.js component containing a full-screen WebView pointing at the Tailscale server IP, with connectivity overlay, external link handling, safe area support, and dark theme throughout. No web UI modifications.

**Tech Stack:** Expo SDK 52, React Native, react-native-webview, expo-status-bar, expo-linking

---

## File Map

| File | Action | What it does |
|------|--------|-------------|
| `~/warroom-mobile/` | Create | New Expo project directory |
| `~/warroom-mobile/App.js` | Create | Root component — WebView + overlay + link handler |
| `~/warroom-mobile/app.json` | Modify | Expo config — name, icon, splash, iOS settings |
| `~/warroom-mobile/assets/icon.png` | Create | App icon 1024x1024 |
| `~/warroom-mobile/assets/splash.png` | Create | Launch screen 1284x2778 |
| `~/warroom-mobile/.gitignore` | Verify | Ensure node_modules, .expo excluded |

---

### Task 1: Environment Setup + Expo Project Scaffold

**Files:**
- Create: `~/warroom-mobile/` (entire project scaffold)

This task sets up Node.js, creates the Expo project, and installs dependencies.

- [ ] **Step 1: Ensure Node.js is available via nvm**

```bash
source ~/.nvm/nvm.sh
nvm use node
node -v
npm -v
```

Expected: Node 20+ and npm 10+ (nvm 0.40.3 is already installed)

If no Node version is installed:
```bash
source ~/.nvm/nvm.sh
nvm install --lts
nvm use --lts
```

- [ ] **Step 2: Create the Expo project**

```bash
source ~/.nvm/nvm.sh && nvm use node
mkdir -p ~/warroom-mobile
cd ~/warroom-mobile
npx create-expo-app@latest . --template blank
```

Expected: project scaffold created with App.js, app.json, package.json, node_modules/, assets/

- [ ] **Step 3: Install additional dependencies**

```bash
cd ~/warroom-mobile
npx expo install react-native-webview expo-linking
```

Note: `expo-status-bar` and `react-native-safe-area-context` are already included in the blank template.

- [ ] **Step 4: Verify the project starts**

```bash
cd ~/warroom-mobile
npx expo start --no-dev --minify 2>&1 | head -20
```

Expected: "Metro waiting on..." with a QR code URL. Press Ctrl+C to stop.

- [ ] **Step 5: Initialize git repo**

```bash
cd ~/warroom-mobile
git init
git add -A
git commit -m "init: Expo blank project scaffold with webview dependency"
```

- [ ] **Step 6: Commit**

Already done in step 5.

---

### Task 2: App Configuration (app.json)

**Files:**
- Modify: `~/warroom-mobile/app.json`

This task configures the Expo app identity, iOS settings, and splash screen.

- [ ] **Step 1: Replace app.json with War Room config**

Replace the entire contents of `~/warroom-mobile/app.json` with:

```json
{
  "expo": {
    "name": "War Room",
    "slug": "warroom-mobile",
    "version": "1.0.0",
    "orientation": "portrait",
    "icon": "./assets/icon.png",
    "userInterfaceStyle": "dark",
    "splash": {
      "image": "./assets/splash.png",
      "resizeMode": "cover",
      "backgroundColor": "#060810"
    },
    "ios": {
      "supportsTablet": false,
      "bundleIdentifier": "com.gurvindersingh.warroom",
      "infoPlist": {
        "NSAppTransportSecurity": {
          "NSAllowsArbitraryLoads": true
        }
      }
    },
    "android": {
      "adaptiveIcon": {
        "foregroundImage": "./assets/adaptive-icon.png",
        "backgroundColor": "#060810"
      }
    },
    "scheme": "warroom",
    "plugins": [
      "expo-linking"
    ]
  }
}
```

- [ ] **Step 2: Verify config is valid**

```bash
cd ~/warroom-mobile
npx expo config --type public 2>&1 | head -5
```

Expected: JSON output showing "name": "War Room"

- [ ] **Step 3: Commit**

```bash
cd ~/warroom-mobile
git add app.json
git commit -m "feat: configure app.json — War Room identity, iOS settings, dark theme"
```

---

### Task 3: Generate App Icon + Splash Screen

**Files:**
- Create: `~/warroom-mobile/assets/icon.png` (1024x1024)
- Create: `~/warroom-mobile/assets/splash.png` (1284x2778)

This task generates the app assets programmatically using Python + Pillow.

- [ ] **Step 1: Check if Pillow is available**

```bash
python3 -c "from PIL import Image, ImageDraw, ImageFont; print('Pillow OK')"
```

If not installed:
```bash
pip3 install Pillow
```

- [ ] **Step 2: Generate the app icon**

```bash
cd ~/warroom-mobile
python3 << 'PYEOF'
from PIL import Image, ImageDraw, ImageFont
import struct, zlib

size = 1024
img = Image.new('RGBA', (size, size), (6, 8, 16, 255))
draw = ImageDraw.Draw(img)

# Green circle
cx, cy = size // 2, size // 2
r = size // 3
draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(0, 230, 118, 255))

# "WR" text — try to use a bold font, fallback to default
try:
    font = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", size=220)
except:
    font = ImageFont.load_default()

# Draw "WR" centered in the circle
text = "WR"
bbox = draw.textbbox((0, 0), text, font=font)
tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
tx = cx - tw // 2 - bbox[0]
ty = cy - th // 2 - bbox[1]
draw.text((tx, ty), text, fill=(6, 8, 16, 255), font=font)

img.save('assets/icon.png')
print(f"Icon saved: {img.size}")
PYEOF
```

Expected: `Icon saved: (1024, 1024)`

- [ ] **Step 3: Generate the splash screen**

```bash
cd ~/warroom-mobile
python3 << 'PYEOF'
from PIL import Image, ImageDraw, ImageFont

width, height = 1284, 2778
img = Image.new('RGBA', (width, height), (6, 8, 16, 255))
draw = ImageDraw.Draw(img)

# "WAR ROOM" text centered
try:
    font = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", size=72)
except:
    font = ImageFont.load_default()

text = "WAR  ROOM"
bbox = draw.textbbox((0, 0), text, font=font)
tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
tx = (width - tw) // 2 - bbox[0]
ty = (height - th) // 2 - bbox[1]
draw.text((tx, ty), text, fill=(0, 230, 118, 255), font=font)

img.save('assets/splash.png')
print(f"Splash saved: {img.size}")
PYEOF
```

Expected: `Splash saved: (1284, 2778)`

- [ ] **Step 4: Also create adaptive-icon.png for Android (same as icon)**

```bash
cd ~/warroom-mobile
cp assets/icon.png assets/adaptive-icon.png
```

- [ ] **Step 5: Verify assets exist and are correct sizes**

```bash
cd ~/warroom-mobile
python3 -c "
from PIL import Image
icon = Image.open('assets/icon.png')
splash = Image.open('assets/splash.png')
print(f'icon: {icon.size}')
print(f'splash: {splash.size}')
assert icon.size == (1024, 1024), 'Icon wrong size'
assert splash.size == (1284, 2778), 'Splash wrong size'
print('All assets OK')
"
```

- [ ] **Step 6: Commit**

```bash
cd ~/warroom-mobile
git add assets/
git commit -m "feat: add app icon and splash screen — dark theme, green WR monogram"
```

---

### Task 4: Write App.js — The WebView Shell

**Files:**
- Create: `~/warroom-mobile/App.js` (replace the default)

This is the core task — the entire app in one file.

- [ ] **Step 1: Replace App.js with the WebView shell**

Replace the entire contents of `~/warroom-mobile/App.js` with:

```javascript
import React, { useState, useRef, useCallback } from 'react';
import { View, Text, StyleSheet, ActivityIndicator, Platform } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { WebView } from 'react-native-webview';
import * as Linking from 'expo-linking';

const SERVER_URL = 'http://100.119.47.67:5680';
const BG_COLOR = '#060810';

export default function App() {
  const [isError, setIsError] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const webviewRef = useRef(null);
  const retryTimer = useRef(null);

  const handleLoad = useCallback(() => {
    setIsLoading(false);
    setIsError(false);
    if (retryTimer.current) {
      clearInterval(retryTimer.current);
      retryTimer.current = null;
    }
  }, []);

  const handleError = useCallback(() => {
    setIsError(true);
    setIsLoading(false);
    // Auto-retry every 3 seconds
    if (!retryTimer.current) {
      retryTimer.current = setInterval(() => {
        if (webviewRef.current) {
          webviewRef.current.reload();
        }
      }, 3000);
    }
  }, []);

  const handleNavigationRequest = useCallback((request) => {
    const { url } = request;
    // Allow the War Room URL and WebSocket connections
    if (url.startsWith(SERVER_URL) || url.startsWith('ws://') || url.startsWith('wss://')) {
      return true;
    }
    // Open everything else in the system browser
    Linking.openURL(url).catch(() => {});
    return false;
  }, []);

  return (
    <SafeAreaProvider>
      <View style={styles.container}>
        <StatusBar style="light" backgroundColor={BG_COLOR} />
        <SafeAreaView style={styles.safeArea} edges={['top']}>
          <WebView
            ref={webviewRef}
            source={{ uri: SERVER_URL }}
            style={styles.webview}
            javaScriptEnabled={true}
            domStorageEnabled={true}
            allowsBackForwardNavigationGestures={false}
            pullToRefreshEnabled={true}
            mediaPlaybackRequiresUserAction={false}
            startInLoadingState={true}
            allowsInlineMediaPlayback={true}
            cacheEnabled={true}
            contentMode="mobile"
            keyboardDisplayRequiresUserAction={false}
            hideKeyboardAccessoryView={true}
            userAgent="Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) WarRoomMobile/1.0"
            onLoad={handleLoad}
            onError={handleError}
            onHttpError={handleError}
            onShouldStartLoadWithRequest={handleNavigationRequest}
            renderLoading={() => (
              <View style={styles.loadingContainer}>
                <ActivityIndicator size="large" color="#00e676" />
              </View>
            )}
          />
        </SafeAreaView>

        {/* Connectivity overlay */}
        {isError && (
          <View style={styles.overlay}>
            <ActivityIndicator size="large" color="#00e676" style={{ marginBottom: 16 }} />
            <Text style={styles.overlayTitle}>Connecting to War Room</Text>
            <Text style={styles.overlaySubtext}>Retrying every 3 seconds...</Text>
          </View>
        )}
      </View>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: BG_COLOR,
  },
  safeArea: {
    flex: 1,
    backgroundColor: BG_COLOR,
  },
  webview: {
    flex: 1,
    backgroundColor: BG_COLOR,
  },
  loadingContainer: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: BG_COLOR,
    justifyContent: 'center',
    alignItems: 'center',
  },
  overlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: BG_COLOR,
    justifyContent: 'center',
    alignItems: 'center',
    zIndex: 100,
  },
  overlayTitle: {
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    fontSize: 16,
    color: '#d8dee8',
    letterSpacing: 1,
  },
  overlaySubtext: {
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    fontSize: 12,
    color: '#3e4e64',
    marginTop: 8,
  },
});
```

- [ ] **Step 2: Verify the file is syntactically correct**

```bash
cd ~/warroom-mobile
source ~/.nvm/nvm.sh && nvm use node
node -e "require('./App.js')" 2>&1 || echo "Syntax check: may show JSX error (expected — Node can't parse JSX). If error is about imports/require, there's a real issue."
```

Note: Node can't parse JSX directly, so a "SyntaxError: Cannot use import statement" is expected and fine. A different error (like "Unexpected token") would indicate a real syntax problem.

- [ ] **Step 3: Commit**

```bash
cd ~/warroom-mobile
git add App.js
git commit -m "feat: App.js — WebView shell with connectivity overlay, external link handling"
```

---

### Task 5: Add README + Final Verification

**Files:**
- Create: `~/warroom-mobile/README.md`

- [ ] **Step 1: Create README**

```bash
cat > ~/warroom-mobile/README.md << 'EOF'
# War Room Mobile

React Native (Expo) shell for the Coder's War Room.

## Phase 1: WebView Shell

Wraps the existing web UI at `http://100.119.47.67:5680` in a native iOS app.

## Setup

```bash
# Ensure Node.js is available
source ~/.nvm/nvm.sh && nvm use node

# Install dependencies
npm install

# Start development server
npx expo start
```

## Testing on iPhone

1. Install "Expo Go" from the App Store
2. Ensure iPhone is connected to Tailscale
3. Scan the QR code from `npx expo start`
4. War Room loads as a native app

## Requirements

- Node.js 20+ (via nvm)
- Expo Go on iPhone
- War Room server running at 100.119.47.67:5680
- iPhone on Tailscale network
EOF
```

- [ ] **Step 2: Start Expo and verify QR code appears**

```bash
cd ~/warroom-mobile
source ~/.nvm/nvm.sh && nvm use node
npx expo start 2>&1 | head -30
```

Expected: Metro bundler starts, QR code displayed. The URL should be something like `exp://192.168.x.x:8081`.

Press Ctrl+C to stop after verifying.

- [ ] **Step 3: Final commit and push**

```bash
cd ~/warroom-mobile
git add -A
git commit -m "feat: Phase 1 complete — Expo WebView shell for War Room

- Full-screen WebView pointing at Tailscale server
- Dark themed splash screen and app icon
- Connectivity overlay with auto-retry
- External links open in system browser
- Safe area + status bar handling
- Pull-to-refresh support
- Hidden keyboard accessory bar
- Custom user agent for server identification

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 4: Create GitHub repo and push (optional)**

```bash
cd ~/warroom-mobile
gh repo create gurvindernitb/warroom-mobile --private --source=. --push
```

---

### Task 6: Test on iPhone via Expo Go

**Files:**
- No modifications — testing only

This task requires Gurvinder's iPhone.

- [ ] **Step 1: Ensure prerequisites**

Verify:
1. War Room server is running: `curl -s http://100.119.47.67:5680/api/server/health`
2. iPhone has "Expo Go" installed from App Store
3. iPhone is connected to Tailscale
4. Mac and iPhone are on the same Tailscale network

- [ ] **Step 2: Start Expo dev server**

```bash
cd ~/warroom-mobile
source ~/.nvm/nvm.sh && nvm use node
npx expo start
```

A QR code will appear in the terminal.

- [ ] **Step 3: Scan QR code on iPhone**

1. Open Expo Go app on iPhone
2. Tap "Scan QR Code"
3. Point camera at the terminal QR code
4. App should load and show the War Room

- [ ] **Step 4: Verify success criteria**

Check each item:
- [ ] Full-screen — no Safari chrome or address bar
- [ ] Status bar shows light text on dark background
- [ ] No white flash on load (dark theme throughout)
- [ ] Chat tab — can read messages, scroll, send a message
- [ ] Agents tab — agent cards visible with avatars
- [ ] Files tab — file tree browsable
- [ ] Tab bar functions (Chat/Agents/Files switching)
- [ ] Pill input works — can type and send
- [ ] Pull down to refresh works
- [ ] External link (if any) opens in Safari, not inside the app

- [ ] **Step 5: Report results**

Ask Gurvinder to screenshot the app and report any issues.

---

## Success Criteria Checklist

| # | Criterion | Task |
|---|-----------|------|
| 1 | `npx expo start` runs without errors | Task 1, 5 |
| 2 | QR code scan loads War Room in Expo Go | Task 6 |
| 3 | Full-screen, no Safari chrome | Task 4 |
| 4 | Status bar dark themed | Task 4 |
| 5 | Safe area respected (notch + home indicator) | Task 4 |
| 6 | Chat/Agents/Files all functional | Task 6 |
| 7 | Connectivity overlay on server unreachable | Task 4 |
| 8 | Pull-to-refresh works | Task 4 |
| 9 | External links open in Safari | Task 4 |
| 10 | App icon and splash screen display | Task 2, 3 |
