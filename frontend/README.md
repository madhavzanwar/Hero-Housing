# FinPilot HomeLoan — frontend

Vite 6 + React 19 + TypeScript (strict) + Tailwind v4. Design system: `../DESIGN.md`.

```bash
npm install
npm run dev            # http://localhost:5173, proxies /api to http://127.0.0.1:8000 (BACKEND_URL overrides)
npm run build          # tsc -b && vite build
npm run lint
```

- `VITE_API_URL` — backend origin for a split deployment (default: same origin, `/api`).
- `VITE_DEMO=1` — force offline demo mode. Demo mode also switches on automatically when `/api/health` is unreachable.
- `npm run export:snapshot` — with the backend running, writes `src/demo/snapshot.json` (all persona cases, memos,
  letters, portfolio, policy, model card) and `public/demo-docs/` (document files for the viewer). Re-run after engine changes.

Routes: `/` landing · `/pipeline` · `/cases/new` · `/cases/:id` (10 tabs) · `/copilot` · `/portfolio` · `/policy` · `/model`.
