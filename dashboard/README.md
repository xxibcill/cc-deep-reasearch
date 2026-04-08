# CC Deep Research Monitoring Dashboard

Real-time interactive monitoring dashboard for CC Deep Research with workflow visualization, agent tracking, and detailed event inspection.

## Features

- **Real-time Event Streaming**: WebSocket-based live updates without manual refresh
- **Multiple View Modes**: Switch between a D3 workflow graph, an agent swimlane timeline, and a virtualized event table
- **Session Management**: View and manage all research sessions
- **Event Filtering**: Filter by phase, agent, tool, provider, status, and event type
- **Detailed Inspection**: Dedicated tool execution and LLM reasoning panels plus raw event inspection
- **Live Status Indicators**: See connection status and event counts in real-time
- **Live Performance Guardrails**: WebSocket batching, virtualized event rendering, and lazy-loaded heavy panels

## Installation

\`\`\`bash
npm install
\`\`\`

## Development

### Quick Start (Recommended)

Start both the backend API and frontend dashboard together:

\`\`\`bash
../scripts/dashboard-dev
\`\`\`

This starts:
- **Backend API**: http://localhost:8000
- **Frontend Dashboard**: http://localhost:3000

The combined launcher handles graceful shutdown with Ctrl+C and labels logs clearly.

If you prefer running from inside the dashboard directory, use:

\`\`\`bash
npm run dev
\`\`\`

### Frontend-Only Development

For frontend-only debugging without the backend:

\`\`\`bash
npm run dev:frontend
\`\`\`

To point the dashboard at a different backend without code edits, create `.env.local` or export runtime variables before starting Next.js:

\`\`\`bash
NEXT_PUBLIC_CC_BACKEND_ORIGIN=http://localhost:8000
# optional explicit overrides
NEXT_PUBLIC_CC_API_BASE_URL=http://localhost:8000/api
NEXT_PUBLIC_CC_WS_BASE_URL=ws://localhost:8000/ws
\`\`\`

## Build

\`\`\`bash
npm run build
\`\`\`

## Technology Stack

- **Next.js 14**: React framework with App Router
- **TypeScript**: Type-safe development
- **Tailwind CSS**: Utility-first styling
- **shadcn/ui conventions**: shared UI primitives in `src/components/ui/` backed by `components.json`
- **Zustand**: Lightweight state management
- **D3.js**: Workflow graph visualization
- **WebSocket**: Real-time event streaming
- **Lucide React**: Icon library

## Project Structure

\`\`\`
src/
├── app/               # Next.js App Router pages
├── components/        # Reusable page sections, visualizations, and ui primitives
├── hooks/             # Shared dashboard state
├── lib/               # Runtime config, API, websocket, transformers
└── types/             # Frontend and API payload types
\`\`\`

## API Integration

The dashboard connects to the CC Deep Research backend:

- **WebSocket**: \`${NEXT_PUBLIC_CC_WS_BASE_URL}/session/{sessionId}\` with \`ws://localhost:8000/ws\` as the local default
- **REST API**: \`${NEXT_PUBLIC_CC_API_BASE_URL}/sessions\` with \`http://localhost:8000/api\` as the local default

## Backend Setup

`npm run dev` already starts both the backend API and the frontend dashboard. If you want to run the backend separately, use the real CLI command and current flags:

1. Start the backend server:
   \`\`\`bash
   cc-deep-research dashboard --host localhost --port 8000
   \`\`\`

2. Run a research query with real-time enabled:
   \`\`\`bash
   cc-deep-research research "your query" --enable-realtime
   \`\`\`

3. Open the dashboard in a browser and select the session to monitor

## Component Foundation

The dashboard now uses shared `shadcn/ui`-style primitives from [`src/components/ui/`](src/components/ui) with class merging from [`src/lib/utils.ts`](src/lib/utils.ts). The local setup is declared in [`components.json`](components.json) so dashboard surfaces can reuse the same vocabulary for:

- dialogs and confirmation flows
- buttons, badges, tabs, and cards
- text inputs, textareas, labels, native selects, and field messaging
- alerts, tables, separators, and collapsible content panels

Intentionally custom surfaces still keep bespoke rendering logic and only reuse the shared shell around them:

- workflow graphs
- decision graphs
- agent timelines
- pipeline progress visualization
- rich script and report viewers

## Performance Notes

- WebSocket updates are buffered briefly before they hit React state.
- The event table renders a moving window instead of the full list.
- Graph, timeline, tool, and LLM detail panels are lazy-loaded on the session page.
