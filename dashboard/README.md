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
├── app/              # Next.js App Router pages
│   ├── layout.tsx  # Root layout
│   ├── page.tsx     # Home page (session list)
│   └── session/    # Session detail pages
├── components/      # React components
├── hooks/          # Custom React hooks
├── lib/            # Utility functions (WebSocket, API)
└── types/          # TypeScript type definitions
\`\`\`

## API Integration

The dashboard connects to the CC Deep Research backend:

- **WebSocket**: \`ws://localhost:8000/ws/session/{sessionId}\` - Real-time event streaming
- **REST API**: \`http://localhost:8000/api/sessions\` - Session management

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
