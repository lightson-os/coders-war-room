# React Native War Room — Phase 1: Expo Shell + WebView Design Spec

**Date:** 2026-04-03
**Phase:** 1 of 3 (WebView shell → Native screens → Push + background)
**Project:** ~/warroom-mobile/ (new repo, separate from server)
**Approach:** WebView-first — wrap existing web UI in a native Expo shell

---

## Context

The War Room web UI at `http://100.119.47.67:5680` is a fully functional mobile-optimized PWA (M1-M3 polish complete). It works in Safari but has limitations: no proper app icon, Safari chrome visible, WebSocket drops on background, no push notifications.

Phase 1 wraps this web UI in a React Native WebView. The result is a real iOS app that looks native (app icon, splash screen, full-screen) while reusing 100% of the existing web frontend. No UI rewrite.

---

## 1. Project Structure

```
~/warroom-mobile/
├── App.js                  # Root component — WebView + connectivity handling
├── app.json                # Expo config: name, icon, splash, orientation
├── package.json            # Dependencies (6 packages)
├── babel.config.js         # Expo default babel config
├── .gitignore              # Node modules, Expo cache
├── assets/
│   ├── icon.png            # App icon 1024x1024 (green circle, dark bg)
│   ├── splash.png          # Launch screen 1284x2778 (dark bg, "WAR ROOM" text)
│   └── adaptive-icon.png   # Android adaptive icon (future use)
└── README.md               # Setup instructions
```

**Total custom code:** ~80 lines in App.js. Everything else is config.

---

## 2. App.js — The Single Component

### Responsibilities

1. **Full-screen WebView** pointing at `http://100.119.47.67:5680`
2. **Status bar** — light text on dark background (`#060810`)
3. **Safe area** — respects iPhone notch (top) and home indicator (bottom)
4. **Connectivity overlay** — when server is unreachable, shows centered "Connecting to War Room..." text with auto-retry every 3 seconds
5. **Pull-to-refresh** — pull down to reload the page
6. **Error handling** — WebView load errors show the connectivity overlay, not a blank screen

### WebView Configuration

| Setting | Value | Reason |
|---------|-------|--------|
| `source.uri` | `http://100.119.47.67:5680` | Tailscale IP, stable |
| `javaScriptEnabled` | `true` | Required for the app to function |
| `domStorageEnabled` | `true` | localStorage for agent order, etc. |
| `allowsBackForwardNavigationGestures` | `false` | Prevent accidental back nav |
| `pullToRefreshEnabled` | `true` | Reload on pull-down |
| `mediaPlaybackRequiresUserAction` | `false` | Future: audio notifications |
| `startInLoadingState` | `true` | Show activity indicator while loading |
| `backgroundColor` | `#060810` | Match War Room theme during load |
| `contentMode` | `mobile` | Force mobile viewport |
| `allowsInlineMediaPlayback` | `true` | Standard iOS behavior |
| `userAgent` | Append `WarRoomMobile/1.0` | Server can identify app vs browser requests |
| `keyboardDisplayRequiresUserAction` | `false` | Allow programmatic keyboard focus |
| `hideKeyboardAccessoryView` | `true` | Remove iOS "Done" bar above keyboard — cleaner chat input |
| `cacheEnabled` | `true` | Keep cache for Phase 1; clear via URL version param if needed |

### External Link Handling

Links to external sites (GitHub, docs) must NOT open inside the WebView — there's no back button to return. Use `onShouldStartLoadWithRequest` to intercept any URL that doesn't match the Tailscale IP (`100.119.47.67:5680`) and open it in the system browser via Expo's `Linking.openURL()`.

### White Flash Prevention

The WebView defaults to white background during initialization even with dark app.json settings. Explicitly set `style={{ backgroundColor: '#060810' }}` on BOTH the WebView component AND its parent View container.

### Connectivity Detection

```
App starts
  → WebView loads URL
  → onError or onHttpError?
    YES → Show overlay: "Connecting to War Room..."
          → Retry every 3 seconds
          → onLoad success → Hide overlay
    NO  → App is live, hide loading indicator
```

The overlay is a simple View with centered text, matching the War Room dark theme. It covers the WebView until a successful load.

### Safe Area Layout

```
┌──────────────────────────┐
│ Status Bar (dark, #060810)│ ← expo-status-bar
├──────────────────────────┤
│                          │
│      WebView             │ ← flex: 1, fills available space
│      (full screen)       │
│                          │
│                          │
├──────────────────────────┤
│ Home Indicator (safe)    │ ← SafeAreaView bottom inset
└──────────────────────────┘
```

The WebView fills the entire screen between the status bar and the home indicator. The War Room's own tab bar sits inside the WebView, above the safe area bottom inset.

---

## 3. App Configuration (app.json)

```json
{
  "expo": {
    "name": "War Room",
    "slug": "warroom-mobile",
    "version": "1.0.0",
    "orientation": "portrait",
    "icon": "./assets/icon.png",
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
    "scheme": "warroom"
  }
}
```

Key settings:
- **NSAllowsArbitraryLoads: true** — required because the server is HTTP (not HTTPS) over Tailscale. This is safe for an internal tool.
- **orientation: portrait** — matches the mobile-optimized web UI
- **bundleIdentifier** — `com.gurvindersingh.warroom` (needed for future TestFlight)
- **supportsTablet: false** — iPhone only

---

## 4. Assets

### App Icon (icon.png)

- Size: 1024x1024 px
- Design: Dark background (#060810), centered green circle with "WR" monogram in JetBrains Mono
- Generated programmatically using the same style as the PWA icons

### Splash Screen (splash.png)

- Size: 1284x2778 px (iPhone 14 Pro Max resolution)
- Design: Full dark background (#060810), "WAR ROOM" text centered in green (#00e676), JetBrains Mono uppercase letterspaced
- Matches the header style of the web UI

---

## 5. Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `expo` | ~52.0.0 | Framework + CLI |
| `react` | 18.3.1 | React core |
| `react-native` | 0.76.x | React Native core |
| `react-native-webview` | 13.x | WebView component |
| `expo-status-bar` | ~2.0.0 | Status bar styling |
| `react-native-safe-area-context` | 4.x | Safe area insets |

All from Expo SDK 52 compatibility matrix. No custom native modules — works with Expo Go.

---

## 6. Development Workflow

### Setup (one-time)

```bash
cd ~/warroom-mobile
npx create-expo-app@latest . --template blank
npx expo install react-native-webview react-native-safe-area-context
```

### Development

```bash
npx expo start
# Scan QR code with Expo Go on iPhone
# Live reload as you edit App.js
```

### Testing

1. Ensure War Room server is running: `http://100.119.47.67:5680`
2. Ensure iPhone is on Tailscale
3. Open Expo Go, scan QR code
4. War Room loads as a native app

### Future: TestFlight build (after $99 enrollment)

```bash
npx eas build --platform ios --profile preview
npx eas submit --platform ios
```

---

## 7. What Improves Over PWA

| PWA (current) | Native WebView (Phase 1) |
|--------------|--------------------------|
| Safari chrome visible (address bar, tabs) | Full screen, no browser UI |
| Generic Safari icon in app switcher | Custom "War Room" icon + name |
| White flash on launch | Dark themed splash screen |
| Safari back/forward gestures interfere | Disabled, clean scrolling |
| "Add to Home Screen" prompt | Real app, installed via Expo Go |
| WebSocket recovery via Safari's logic | WebView's more reliable recovery |
| No connectivity indicator | Dark overlay with retry on disconnect |

---

## 8. What Does NOT Change

- The web UI (static/index.html) — zero modifications
- The server (server.py) — zero modifications
- WebSocket protocol, API endpoints
- All M1/M2/M3 mobile CSS polish
- Desktop web UI

---

## 9. What Phase 1 Does NOT Include

- Native Chat/Agents/Files screens (Phase 2)
- Push notifications (Phase 3)
- Background WebSocket keep-alive (Phase 3)
- Offline message queuing (Phase 3)
- Badge count on app icon (Phase 3)

---

## 10. Success Criteria

1. `npx expo start` runs without errors
2. Scanning QR code in Expo Go loads the War Room
3. Full-screen — no Safari chrome, no address bar
4. Status bar matches War Room theme (light text, dark bg)
5. Safe area respected — no content under notch or home indicator
6. Chat tab works — can read and send messages
7. Agents tab works — can see agent cards, tap for actions
8. Files tab works — can browse project files
9. Tab bar and pill input function correctly
10. Connectivity overlay appears when server is unreachable, auto-retries
11. Pull-to-refresh reloads the page
