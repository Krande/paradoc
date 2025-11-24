Paradoc Frontend

Tech stack
- React + TypeScript
- Vite
- TailwindCSS v4
- In-app WebSocket listener (dev)

Development
- Install deps once: cd frontend && npm install
- Start the dev environment: pixi run -e frontend wdev
- Open http://localhost:5173 in your browser.

WebSocket (dev)
- The frontend initializes an in-app WebSocket listener at ws://localhost:13579 during development.
- It is implemented inside the browser using mock-socket and is started from src/main.tsx (see src/ws/listener.ts).
- The app connects to ws://localhost:13579 and renders any HTML text message it receives.
- Use the "Send Mock" button to broadcast a sample HTML to all connected clients.

Notes
- The document reader displays HTML payloads it receives and builds a professional sidebar TOC (with appendix logic) from headings h1–h6.
- The Appendix start marker is read from a meta tag named data-appendix-start in index.html. Adjust as needed based on your backend output.
- The default document styling includes Paradoc's default CSS (see src/paradoc/resources/default_style.css) for consistent local viewing.
