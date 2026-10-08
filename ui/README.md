# Auckland Hospital Health Assistant — Web UI

React and TypeScript client for the Auckland Hospital Health Assistant API. The UI provides authenticated patient access, text chat, voice sessions, session history, profile management, service readiness indicators, and live pipeline progress from the backend.

## Stack

- **Vite 5** + **React 18** + **TypeScript**
- **Tailwind CSS** for styling
- **Framer Motion** for interface transitions
- **LiveKit Client** for browser voice sessions
- **react-markdown** + **remark-gfm** for assistant responses

Application state is handled with focused React hooks rather than a global state library.

## Run locally

Start the API from the repository root:

```bash
cd src
uvicorn api.main:app --reload --port 8000
```

Start the UI:

```bash
cd ui
npm ci
npm run dev
```

The development server proxies `/api/*` to `VITE_API_URL`, which defaults to `http://localhost:8000`. Copy `.env.example` to `.env` to override the backend address.

## Client responsibilities

| Area | Responsibility |
|---|---|
| Authentication | Stores the short-lived bearer token in `sessionStorage` and restores the signed-in patient through `/auth/me` and `/patients/me`. |
| Chat | Sends authenticated chat requests and renders backend pipeline progress delivered through Server-Sent Events. |
| Sessions | Loads, creates, selects, and removes patient-scoped conversation sessions. |
| Voice | Requests a server-signed LiveKit token and connects the browser to the voice worker. |
| Profile | Displays the authenticated patient profile and submits permitted profile updates. |
| Service status | Surfaces API readiness, configured models, and dependency health. |

## Structure

```text
ui/
├── index.html
├── vite.config.ts
├── tailwind.config.ts
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── types.ts
│   ├── api/client.ts
│   ├── hooks/
│   │   ├── useChatStream.ts
│   │   ├── useHealth.ts
│   │   ├── usePatient.ts
│   │   └── useSessions.ts
│   └── components/
│       ├── ChatWindow.tsx
│       ├── PatientGate.tsx
│       ├── ProfileSheet.tsx
│       ├── Sidebar.tsx
│       ├── StatusBar.tsx
│       └── VoiceRoom.tsx
└── tests/
```

## Commands

```bash
npm run dev      # development server
npm run build    # type-check and production build
npm run lint     # TypeScript validation
npm test         # UI access-control tests
npm run preview  # preview the production build
```

The production API image builds the UI and serves the compiled SPA from FastAPI, so the browser and API share the same origin.
