# CC Deep Research Monitoring Dashboard

Real-time interactive monitoring dashboard for CC Deep Research with workflow visualization, agent tracking, and detailed event inspection.

## Features

- **Real-time Event Streaming**: WebSocket-based live updates without manual refresh
- **Multiple View Modes**: Switch between Workflow Graph, Agent Timeline, and Event Table
- **Session Management**: View and manage all research sessions
- **Event Filtering**: Filter events by phase, agent, status, and event type
- **Detailed Inspection**: Click any event to see full details including metadata
- **Live Status Indicators**: See connection status and event counts in real-time

## Installation

\`\`\`bash
npm install
\`\`\`

## Development

\`\`\`bash
npm run dev
\`\`\`

The dashboard will be available at http://localhost:3000

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
- **Zustand**: Lightweight state management
- **D3.js**: Data visualization (planned for workflow graphs)
- **WebSocket**: Real-time event streaming
- **Lucide React**: Icon library

## Project Structure

\`\`\`
src/
├── app/               # Next.js App Router pages
├── components/        # Reusable page sections and tables
├── hooks/             # Shared dashboard state
├── lib/               # Runtime config, API, websocket, transformers
└── types/             # Frontend and API payload types
\`\`\`

## API Integration

The dashboard connects to the CC Deep Research backend:

- **WebSocket**: \`${NEXT_PUBLIC_CC_WS_BASE_URL}/session/{sessionId}\` with \`ws://localhost:8000/ws\` as the local default
- **REST API**: \`${NEXT_PUBLIC_CC_API_BASE_URL}/sessions\` with \`http://localhost:8000/api\` as the local default

## Backend Setup

To use the dashboard with real-time monitoring:

1. Start the backend server:
   \`\`\`bash
   cc-deep-research dashboard --enable-realtime --dashboard-port 8000
   \`\`\`

2. Run a research query with real-time enabled:
   \`\`\`bash
   cc-deep-research research "your query" --enable-realtime
   \`\`\`

3. Open the dashboard in a browser and select the session to monitor

## Future Enhancements

- [ ] D3.js workflow graph visualization
- [ ] Agent swimlane timeline with parallel execution
- [ ] Tool execution detail view with syntax highlighting
- [ ] LLM reasoning panel with prompt/response display
- [ ] Advanced filtering and search
- [ ] Export functionality (JSON, CSV)
- [ ] Dark mode toggle
