# War Room Evolution Tab — Clean-Sheet UI Rebuild

## Context

The War Room UI (`static/index.html`) is the live Evolution tab in the North Star app, served at `localhost:5680` and loaded via WKWebView. The hardening work added functional improvements (gate status dots, Gates dashboard, role dropdown hints, drag-drop upload, hook event APIs) but the visual skin is still the pre-hardening dark green/blue theme. The user wants a clean-sheet rebuild that fully implements the North Star Design System v4.4 while preserving all JS functionality. This is the active tool — the user needs it tomorrow. A subagent will build it; this session's author will review it.

## Safety Constraints

1. **The server must keep running** — the rebuild is HTML/CSS/JS only in `static/index.html`. No server.py changes.
2. **All 18 API endpoints must work** — the JS must call every endpoint listed in the UI map.
3. **All 7 WebSocket message types must be handled** — history, message, agent_status, membership, agent_created, agent_removed, hook_event.
4. **All global state variables preserved** — agentRoster, agentData, agentHookEvents, ws, rolesRegistry, etc.
5. **localStorage key `warroom-agent-order`** — exact string, must persist.
6. **MIME types for drag-drop** — `application/x-warroom-reorder` and `application/x-warroom-file` — exact strings.
7. **Build on a feature branch with worktree** — never touch main directly.

## Approach: Rebuild in Layers

The 4000-line single-file HTML is rebuilt as a fresh file with four layers:

### Layer 1: CSS Foundation (~400 lines)
All Design System v4.4 tokens as CSS custom properties. Reset, typography, grid, elevation, animations. Zero HTML or JS — pure CSS.

**Source of truth:** `~/contextualise/docs/ux/Stich/DESIGN.md` v4.4

Key tokens:
- `--color-surface: #000000` (Void — pure OLED black)
- `--color-container-low: #131313`
- `--color-container-high: #1B1B1B`
- `--color-text-primary: #F2F2F7` (Ivory)
- `--color-text-secondary: rgba(242,242,247,0.6)` (Dimmed)
- `--color-text-faint: rgba(242,242,247,0.3)`
- `--color-evolution: #AF82FF` (Violet — War Room domain)
- `--color-approve: #32D74B` (gate pass ONLY)
- `--color-deny: #FF453A` (gate fail ONLY)
- `--color-modify: #FBBC05` (gate warn ONLY)
- `--radius-card: 14px`, `--radius-pill: 9999px`
- `--padding-card: 24px`, `--gap-items: 16px`, `--grid: 8px`
- Fonts: Inter (system voice fallback for SF Pro), Source Sans 3 (body), JetBrains Mono (technical), Instrument Serif (brand)
- Elevation shadows: 5 levels with exact Y-offset, blur, opacity, tint from §4.1
- Animations: skeleton shimmer, urgency beacon pulse, breathing glow
- `@media (prefers-reduced-motion: reduce)` — disable all animations
- `max-width: 1200px` on outer container (§12 web rule)

### Layer 2: Layout Shell (~200 lines)
The structural HTML: nav bar, three-panel layout (sidebar + main + file panel), bottom pill tab bar, drawer overlay.

**Layout:**
```
┌─────────────────────────────────────────────────────┐
│ NAV BAR — backdrop-filter blur, Container-High      │
│ "Coders War Room" + server stats + connection badge │
├──────────────┬──────────────────────────────────────┤
│ SIDEBAR      │ MAIN PANEL                           │
│ 320px        │                                      │
│              │ Sub-tabs: War Room | Gates            │
│ Agent cards  │                                      │
│ + operator   │ Messages / Gates dashboard            │
│              │                                      │
│              │                                      │
├──────────────┴──────────────────────────────────────┤
│ INPUT BAR — fixed bottom, above tab bar             │
│ @target ▾ | [textarea] | Send                       │
├─────────────────────────────────────────────────────┤
│ TAB BAR — floating pill, backdrop-filter blur        │
│ [ Chat ] [ Agents ] [ Files ] [ Gates ]             │
└─────────────────────────────────────────────────────┘
```

- Sidebar: 320px fixed, scrollable agent list
- Main: flex-grow, contains messages OR Gates dashboard
- File panel: 280px, hidden on mobile, toggled via tab
- Gates panel: hidden by default, shown via Gates tab
- Mobile breakpoint: 768px — single-view with tab switching
- No Liquid Glass on cards/content — only on nav bar, tab bar, toolbar (§14)
- Boundaries are tonal shifts, never 1px solid lines (§4 "No-Line Rule")

### Layer 3: Components (~800 lines HTML + CSS)
Each component is a self-contained atom from DESIGN.md §9.

**Agent Card (Card Shell):**
```
┌─────────────────────────────────────────────┐
│ ◉ Agent Name                    MODEL PILL  │  Card Shell: 14px radius
│                                             │  Container-Low #131313
│ ● Status: NS-108                ⏱ 12m      │  24px padding
│                                             │  Top-left Violet radial glow 8%
│ GATE 1 ─────────────────────────────        │
│  ● pytest   ● flake8   ● mypy             │  Gate dots: green/red/grey
│  ● bandit   ● coverage                     │
│                                             │
│ Last: flake8 clean · 2m ago                 │  JetBrains Mono, text-secondary
└─────────────────────────────────────────────┘
```

- Domain badge: 40×40px circle, Violet 15% bg, icon 100% opacity
- Model pill: 9999px radius, Violet neon glass bg
- Status pill: domain color dot + text
- Gate dots: `--color-approve` (pass), `--color-deny` (fail), `rgba(255,255,255,0.2)` (not run)
- States: idle (Container-Low), working (Container-High), stalled (amber beacon pulse), offline (40% opacity), error (red beacon)
- Compression at 6+ agents: single-row summary (§17)

**Message Bubble:**
- Sender name in Source Sans 3, colored by agent role
- Body in Source Sans 3, 17px, Ivory
- Timestamp in JetBrains Mono, text-faint
- System messages: no avatar, centered, text-secondary
- Grouping: same sender within 20s = continuation (no repeated header)
- Direct messages: subtle Container-High background

**Gates Dashboard:**
- Each gate is a Card Shell with conditional glow (green pass, red fail, violet pending)
- Tool rows: JetBrains Mono, with PASS/FAIL/— status
- Refresh button

**Agent Creation Drawer:**
- Slides from right, Container-High background
- Form fields: Input with Container-Low bg, 14px radius
- Color picker: circular swatches
- Icon picker: grid of SVG icons
- Model hint: appears below model dropdown when QA selected
- Directory browser: tree navigation with Container-Low items

**Input Bar:**
- Container-High background, backdrop blur
- Textarea: Container-Low background, 14px radius
- Send button: Violet accent
- Drag-drop zone: Violet neon glass glow on dragover
- Target selector: pill-shaped dropdown

**Bottom Tab Bar (Mobile):**
- Fixed bottom, full width
- backdrop-filter: blur(20px) + Container-High at 80% opacity
- 4 tabs: Chat, Agents, Files, Gates
- Active tab: Violet color, others dimmed
- Safe area padding for notch devices

### Layer 4: JavaScript (~1500 lines)
All JS functions from the current implementation, preserved exactly. The only changes are:
- DOM element creation in `renderAgents()`, `renderMsg()`, etc. uses new CSS classes
- Color/icon maps updated to DESIGN.md values
- Same API calls, same WebSocket handling, same state management

**Critical functions that MUST survive unchanged in behavior:**
- `connect()` — WebSocket with all 7 message types
- `renderAgents()` — full agent card rendering with drag-drop reorder
- `renderMsg(m)` — message rendering with grouping logic
- `updateAgentGateStatus(agentName)` — gate dot rendering from hook events
- `loadGatesDashboard()` — Gates dashboard from /api/hooks/events/all
- `loadHistoricalHookEvents()` — initial fetch on page load
- `send()` — message sending with debounce
- `scrollEnd()` / `scrollForce()` — scroll behavior
- `openDrawer()` / `closeDrawer()` — agent creation
- `loadDirectory(path)` — directory browser
- `loadRolesRegistry()` / `onRoleChange()` — model hints
- `switchTab(tab)` — mobile tab switching
- `showBottomSheet()` — mobile menus
- `initDragDrop()` — file upload drag-drop
- All event listeners on all elements

**Font loading:**
```html
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@300;400;500;600;700&family=Source+Sans+3:wght@300;400;500;600&family=Instrument+Serif&display=swap" rel="stylesheet">
```

SF Pro available on Apple via `-apple-system`. Inter is the cross-platform fallback.

## Files

| File | Action |
|------|--------|
| `static/index.html` | **REWRITE** — clean-sheet rebuild |
| `static/index.html.bak` | **CREATE** — backup of current file before rebuild |
| `server.py` | **NO CHANGES** |
| `registries/*.yaml` | **NO CHANGES** |
| `hooks/*.sh` | **NO CHANGES** |

## Task Breakdown

### Task 1: Setup & Backup
- Create feature branch `feature/evolution-ui-rebuild`
- Copy `static/index.html` to `static/index.html.bak`
- Verify server is running and serving the current UI

### Task 2: CSS Foundation
- Write the complete `:root` CSS custom properties block
- Reset styles (box-sizing, margin, padding)
- Typography classes for each role (hero, body, system-voice, technical, brand)
- Elevation shadow classes (level-0 through level-5)
- Animation keyframes (skeleton-shimmer, beacon-pulse, breathing-glow)
- Neon Glass Protocol utility class
- Card Shell base class
- Status Pill, Domain Badge, Gate Dot classes
- `@media (prefers-reduced-motion: reduce)` overrides
- `@media (max-width: 768px)` responsive foundation

### Task 3: Layout Shell HTML
- DOCTYPE, head, meta tags, font loading
- Nav bar with server stats and connection badge
- Three-panel layout (sidebar + main + file panel)
- Gates panel (hidden by default)
- Input bar (fixed bottom)
- Tab bar (mobile, floating pill)
- Drawer overlay and form structure
- All DOM IDs preserved exactly as listed in the UI map

### Task 4: Component Rendering
- Agent card HTML/CSS matching the Card Shell wireframe
- Message bubble HTML/CSS
- Gates dashboard cards with conditional glow
- Drawer form with directory browser, color/icon pickers, model hint
- File tree panel
- Bottom sheet (mobile)

### Task 5: JavaScript — State & WebSocket
- All global state variables (exact names)
- WebSocket connect() with all 7 message type handlers
- Message rendering with grouping logic
- Agent rendering with drag-drop reorder
- Gate status dots and historical event loading

### Task 6: JavaScript — Interactions
- Agent creation (drawer open/close, form validation, API call)
- Directory browser navigation
- Role presets and model hint logic
- File tree with drag-to-chat
- Drag-drop file upload on compose area
- Tab switching (mobile)
- Bottom sheet menus (mobile)
- Keyboard shortcuts (Enter to send, Escape to close drawer)
- localStorage persistence for agent order

### Task 7: Verification
- Start server, load UI at localhost:5680
- Verify: Void black background, Container-Low cards, Violet domain glow
- Verify: All fonts loading (Inter, Source Sans 3, JetBrains Mono)
- Verify: Agent creation works (role dropdown, model hint, directory browser)
- Verify: Messages send and receive via WebSocket
- Verify: Gate dots appear from hook events
- Verify: Gates dashboard loads and renders
- Verify: Mobile responsive at 768px
- Verify: Drag-drop file upload works
- Verify: Agent reorder persists in localStorage
- Verify: No Liquid Glass on cards (only nav/tab bar)
- Verify: Forensic Empathy labels (terse, fact-first)
- Verify: 14px card radius, 24px padding, 8px grid
- Verify: Touch targets minimum 44×44px
- Verify: No 1px solid borders (tonal shifts only)

## Reference Files

The implementing agent MUST read these before starting:

1. **DESIGN.md** — `~/contextualise/docs/ux/Stich/DESIGN.md` — the constitution for all visual decisions
2. **Current index.html** — `~/coders-war-room/static/index.html` — the JS that must be preserved
3. **Hardening spec** — `~/coders-war-room/docs/superpowers/specs/2026-04-12-war-room-hardening-design.md` — the gate/hook architecture the UI visualizes
4. **Role registry** — `~/coders-war-room/registries/role-registry.yaml` — agent icons, colors, model hints
5. **Gate registry** — `~/coders-war-room/registries/gate-registry.yaml` — gate tool lists for dashboard

## Rollback Plan

If the rebuild breaks the live tool:
```bash
cd ~/coders-war-room
cp static/index.html.bak static/index.html
# Server auto-serves the restored file — no restart needed
```

The backup is created in Task 1 before any changes. Recovery takes 5 seconds.
