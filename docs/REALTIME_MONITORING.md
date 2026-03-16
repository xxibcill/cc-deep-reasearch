# Real-Time Monitoring Dashboard - Implementation Summary

## Overview

This document summarizes the implementation of an interactive real-time monitoring dashboard for CC Deep Research. The dashboard provides live visibility into agent workflow execution with WebSocket-based streaming and visualization components.

## What Was Built

### Backend (Python)

#### 1. EventRouter Module ([`event_router.py`](src/cc_deep_research/event_router.py))
- In-memory pub/sub system for real-time event distribution
- Session-based routing (events go only to subscribed clients)
- Connection lifecycle management with WebSocket wrappers
- Async-friendly implementation using `asyncio.Queue` and `asyncio.Lock`

**Key Classes:**
- `EventRouter`: Manages subscriptions and event broadcasting
- `WebSocketConnection`: Wrapper for WebSocket connections with metadata

#### 2. Enhanced ResearchMonitor ([`monitoring.py`](src/cc_deep_research/monitoring.py))
- Added `event_router` parameter to `__init__()`
- Modified `emit_event()` to publish to EventRouter after persisting
- Added `real_time_enabled` property to check if real-time streaming is active
- Maintains backward compatibility (router=None for existing behavior)

#### 3. FastAPI Web Server ([`web_server.py`](src/cc_deep_research/web_server.py))
- WebSocket endpoint: `/ws/session/{session_id}` - Real-time event streaming
- REST endpoints:
  - `GET /api/sessions` - List available sessions
  - `GET /api/sessions/{session_id}` - Session details
  - `GET /api/sessions/{session_id}/events` - Event history
- CORS support for browser access
- Integrated EventRouter for WebSocket broadcasting

#### 4. CLI Updates ([`cli.py`](src/cc_deep_research/cli.py))
- Added `cc-deep-research dashboard` command
- Added flags:
  - `--enable-realtime` - Enable WebSocket server
  - `--dashboard-port` - Port for dashboard (default: 8000)
  - `--dashboard-host` - Host for dashboard (default: localhost)
- Added `--enable-realtime` flag to `research` command
- Passes EventRouter to orchestrator when real-time is enabled

#### 5. Configuration Updates ([`config.py`](src/cc_deep_research/config.py))
- Added `DashboardConfig` Pydantic model with enabled, host, port fields
- Added environment variable support in Settings class:
  - `DASHBOARD_ENABLED`
  - `DASHBOARD_HOST`
  - `DASHBOARD_PORT`

#### 6. Dependencies ([`pyproject.toml`](pyproject.toml))
Added to `[project.dependencies]`:
- `fastapi>=0.104.0`
- `uvicorn[standard]>=0.24.0`
- `websockets>=12.0`

### Frontend (Next.js + TypeScript)

#### 1. Project Structure ([`dashboard/`](dashboard/))
Created Next.js 14 project with:
- TypeScript configuration
- Tailwind CSS with custom theme
- App Router structure
- Component, hooks, lib, and types directories

#### 2. Type Definitions ([`src/types/telemetry.ts`](dashboard/src/types/telemetry.ts))
Comprehensive TypeScript interfaces for:
- `TelemetryEvent`: Event structure
- `Session`: Session metadata
- `ServerMessage`/`ClientMessage`: WebSocket protocol
- `WorkflowNode`/`WorkflowEdge`: Workflow graph types
- `AgentExecution`: Agent execution tracking
- `ToolExecution`: Tool call details
- `LLMReasoning`: LLM call details
- `EventFilter`: Event filtering options
- `ViewMode`: Visualization mode types

#### 3. WebSocket Client ([`src/lib/websocket.ts`](dashboard/src/lib/websocket.ts))
Custom React hook `useWebSocket(sessionId)`:
- Connection management with auto-reconnect and exponential backoff
- Message parsing and type safety
- Error handling and connection status
- Ping/pong for keepalive
- Automatic subscription and history request on connect

#### 4. API Client ([`src/lib/api.ts`](dashboard/src/lib/api.ts))
HTTP client functions:
- `getSessions(activeOnly, limit)`: List sessions
- `getSession(sessionId)`: Get session details
- `getSessionEvents(sessionId, limit, offset)`: Get event history

#### 5. State Management ([`src/hooks/useDashboard.ts`](dashboard/src/hooks/useDashboard.ts))
Zustand store with:
- Session selection management
- Event storage (keeps last 1000 events)
- Filtering controls (phase, agent, status, event types, time range)
- View mode switching (graph/timeline/table)
- Auto-scroll toggle

#### 6. Application Pages

**Home Page ([`src/app/page.tsx`](dashboard/src/app/page.tsx))**
- Session list with live status indicators
- Loading states and error handling
- Links to session detail pages
- Stats cards (total sessions, active sessions)

**Session Detail Page ([`src/app/session/[id]/page.tsx`](dashboard/src/app/session/[id]/page.tsx))**
- Three view modes with switcher buttons:
  - Workflow Graph (placeholder - coming soon)
  - Agent Timeline (placeholder - coming soon)
  - Event Table (fully implemented)
- Stats cards showing:
  - Agent count
  - Tool call count
  - LLM call count
  - Total event count
- Event table with sorting and filtering
- Event detail modal with JSON inspection
- Live connection status indicator

**Root Layout ([`src/app/layout.tsx`](dashboard/src/app/layout.tsx))**
- Global CSS with theme variables
- Dark/light mode support
- Responsive layout structure

#### 7. Styling ([`src/app/globals.css`](dashboard/src/app/globals.css))
- Tailwind CSS integration
- Custom CSS variables for theming
- Responsive design classes

## How to Use

### 1. Start the Backend Server

```bash
cd /Users/jjae/Documents/guthib/cc-deep-research
uv run cc-deep-research dashboard --enable-realtime --dashboard-port 8000
```

The server will start on http://localhost:8000

### 2. Run Research with Real-Time Monitoring

```bash
uv run cc-deep-research research "your research query" --enable-realtime
```

This will:
- Create an EventRouter for real-time event distribution
- Pass it to ResearchMonitor
- Stream events to connected WebSocket clients

### 3. Open the Dashboard

```bash
cd /Users/jjae/Documents/guthib/cc-deep-research/dashboard
npm install
npm run dev
```

The dashboard will be available at http://localhost:3000

### 4. Monitor Research in Real-Time

1. Open the dashboard in a browser
2. View the list of available sessions
3. Click on a session to enter the monitoring view
4. Switch between view modes (Graph/Timeline/Table)
5. Watch events stream in real-time without manual refresh
6. Click on any event to see full details

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│           CC Deep Research Research Process                  │
│              (Orchestrator + Agents)                   │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     │ emit_event()
                     │
                     ▼
         ┌───────────────────────┐
         │  ResearchMonitor      │
         │  (enhanced)         │
         └──────┬─────────────┘
                │
                │ 1. Persist to JSONL
                │ 2. Publish to EventRouter
                │
        ┌───────┴───────┐
        │               │
        ▼               ▼
┌──────────────┐  ┌───────────────────┐
│  JSONL File  │  │  EventRouter     │
│  (existing)  │  │  (pub/sub)       │
└──────────────┘  └──────┬───────────┘
                         │
                         │ broadcast()
                         │
                ┌──────────┴──────────┐
                │                     │
                ▼                     ▼
        ┌──────────────┐    ┌───────────────────┐
        │  FastAPI     │    │  FastAPI          │
        │  HTTP Server  │    │  WebSocket        │
        │  (REST API)  │    │  Server           │
        └──────┬───────┘    └──────┬───────────┘
               │                    │
               │ REST API           │ WebSocket
               │                    │
               ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│              Next.js Dashboard                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │  WebSocket Client  │  API Client            │    │
│  └──────────┬─────────┴──────────┬────────────┘    │
│             │                     │                  │
│             ▼                     ▼                  │
│  ┌──────────────────────────────────────────────────┐   │
│  │  React Components                           │   │
│  │  - Home Page (Session List)               │   │
│  │  - Session Detail Page                    │   │
│  │    - Workflow Graph (placeholder)          │   │
│  │    - Agent Timeline (placeholder)           │   │
│  │    - Event Table (fully implemented)        │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Key Features Implemented

### Backend
✅ **EventRouter**: In-memory pub/sub for WebSocket broadcasting
✅ **Enhanced ResearchMonitor**: Publishes events to EventRouter
✅ **FastAPI Server**: WebSocket and REST endpoints
✅ **CLI Dashboard Command**: Start monitoring server
✅ **Configuration**: Dashboard settings with env var support
✅ **Dependencies**: FastAPI, uvicorn, websockets

### Frontend
✅ **Next.js 14 Project**: TypeScript + Tailwind CSS setup
✅ **WebSocket Client**: Auto-reconnect with exponential backoff
✅ **API Client**: HTTP requests to backend
✅ **State Management**: Zustand store for global state
✅ **Home Page**: Session list with live status
✅ **Session Detail Page**: Multi-view monitoring interface
✅ **Event Table**: Sortable, filterable, clickable rows
✅ **Stats Cards**: Agent, tool, LLM, and event counts
✅ **Event Detail Modal**: JSON inspection of any event
✅ **Responsive Design**: Mobile-friendly layout
✅ **Theme Support**: Dark/light mode ready

### Future Enhancements (Not Yet Implemented)
⏳ **Workflow Graph**: D3.js force-directed graph visualization
⏳ **Agent Timeline**: Swimlane view showing parallel execution
⏳ **Tool Execution Detail**: Expandable tool call details with syntax highlighting
⏳ **LLM Reasoning Panel**: Prompt and response display with token usage
⏳ **Advanced Filtering**: Search and complex filter combinations
⏳ **Export Functionality**: Download events as JSON/CSV
⏳ **Historical Session Comparison**: Side-by-side session comparison
⏳ **Performance Metrics**: Charts and trends over time

## Performance Targets

- **Real-time latency**: <100ms from event to display (achievable with WebSocket)
- **Dashboard initial load**: <2s (Next.js optimization)
- **Frame rate**: >30fps with live updates (React efficient rendering)
- **Concurrent users**: Support 10+ users per session (EventRouter handles this)
- **Event handling**: Sessions with 10,000+ events (virtual scrolling needed)

## Testing Checklist

### End-to-End Testing

- [ ] Start monitoring server: `cc-deep-research dashboard --enable-realtime`
- [ ] Run research: `cc-deep-research research "test" --enable-realtime`
- [ ] Open dashboard: `cd dashboard && npm run dev`
- [ ] View session list on home page
- [ ] Select a session to monitor
- [ ] Verify WebSocket connection status shows "Live"
- [ ] Watch events stream in real-time
- [ ] Switch between view modes (Graph/Timeline/Table)
- [ ] Click on events to see details
- [ ] Verify stats update correctly
- [ ] Test reconnection after server restart
- [ ] Test with multiple browser tabs
- [ ] Verify historical sessions load correctly
- [ ] Test event filtering
- [ ] Verify auto-scroll behavior

## Troubleshooting

### Backend Issues

**Port already in use:**
```bash
# Use a different port
cc-deep-research dashboard --dashboard-port 8001
```

**WebSocket connection failed:**
- Check that the backend server is running
- Verify port number matches
- Check firewall settings

### Frontend Issues

**Dependencies not installing:**
```bash
# Clear npm cache
rm -rf node_modules package-lock.json
npm cache clean --force
npm install
```

**Next.js build errors:**
- Check TypeScript configuration in `tsconfig.json`
- Verify all imports have correct paths
- Check console for specific error messages

**WebSocket not connecting:**
- Open browser DevTools Console for errors
- Verify backend is running on expected port
- Check CORS configuration

## Next Steps

To complete the full implementation as planned:

1. **Implement D3.js Workflow Graph**
   - Create `WorkflowGraph.tsx` component
   - Use force-directed layout for agent nodes
   - Add click-to-drill-down functionality
   - Show parallel execution with multiple active nodes

2. **Implement Agent Timeline**
   - Create `AgentTimeline.tsx` component
   - Use swimlane layout with time axis
   - Show parallel researcher execution
   - Add hover tooltips and click filtering

3. **Implement Tool Execution View**
   - Create `ToolTimeline.tsx` component
   - Show tool calls with duration bars
   - Expandable details with syntax highlighting
   - Add request/response inspection

4. **Implement LLM Reasoning Panel**
   - Create `LLMReasoningPanel.tsx` component
   - Display prompts and responses with markdown
   - Show token usage with progress bars
   - Add metadata display (model, provider, transport)

5. **Add shadcn/ui Components**
   - Initialize shadcn/ui for pre-built components
   - Use Dialog, Table, Select, Badge components
   - Improve accessibility and styling consistency

6. **Performance Optimization**
   - Implement virtual scrolling for long lists
   - Add event debouncing (100ms)
   - Optimize D3.js rendering with requestAnimationFrame
   - Add lazy loading for historical sessions

7. **Testing**
   - Write unit tests for components
   - Write integration tests for WebSocket + API
   - Create E2E tests with Playwright
   - Load test WebSocket server with multiple clients

## Files Created/Modified

### Backend
- **NEW**: [`src/cc_deep_research/event_router.py`](src/cc_deep_research/event_router.py)
- **NEW**: [`src/cc_deep_research/web_server.py`](src/cc_deep_research/web_server.py)
- **MODIFIED**: [`src/cc_deep_research/monitoring.py`](src/cc_deep_research/monitoring.py) - Added event_router support
- **MODIFIED**: [`src/cc_deep_research/cli.py`](src/cc_deep_research/cli.py) - Added dashboard command and --enable-realtime flag
- **MODIFIED**: [`src/cc_deep_research/config.py`](src/cc_deep_research/config.py) - Added DashboardConfig
- **MODIFIED**: [`pyproject.toml`](pyproject.toml) - Added fastapi, uvicorn, websockets dependencies

### Frontend
- **NEW**: [`dashboard/`](dashboard/) - Complete Next.js application
  - `package.json` - Dependencies and scripts
  - `tsconfig.json` - TypeScript configuration
  - `tailwind.config.ts` - Tailwind CSS configuration
  - `next.config.js` - Next.js configuration
  - `postcss.config.js` - PostCSS configuration
  - `src/app/globals.css` - Global styles
  - `src/app/layout.tsx` - Root layout
  - `src/app/page.tsx` - Home page
  - `src/app/session/[id]/page.tsx` - Session detail page
  - `src/types/telemetry.ts` - TypeScript type definitions
  - `src/lib/websocket.ts` - WebSocket client hook
  - `src/lib/api.ts` - API client functions
  - `src/hooks/useDashboard.ts` - Zustand store
  - `README.md` - Dashboard documentation

## Conclusion

The core infrastructure for real-time monitoring is now in place:
- Backend WebSocket server with event broadcasting ✅
- Frontend dashboard with WebSocket client ✅
- Session management and event streaming ✅
- Basic visualization (event table) ✅

Advanced visualizations (workflow graph, agent timeline, tool details) are scaffolded and ready for implementation with D3.js and shadcn/ui components.

The system provides a solid foundation for:
- Real-time agent visibility
- Workflow execution tracking
- Event inspection and filtering
- Multi-user concurrent monitoring

All components maintain backward compatibility and can be incrementally enhanced.
