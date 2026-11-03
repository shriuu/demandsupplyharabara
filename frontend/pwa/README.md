# HaraBhara Fresh web app (PWA shell)

React + Vite + TypeScript. Built to `dist/` and served as static files by the API service;
the API base path is `/api/v1` (override with `VITE_API_BASE`). Asset paths are relative.

```bash
npm ci
npm run dev            # real API expected at /api/v1
VITE_MOCK_API=1 npm run dev   # in-memory mock API (synthetic fixtures)
npm run lint && npm run typecheck && npm test && npm run build
npm run e2e            # Playwright against the mock API (first: npx playwright install chromium)
npm run gen:types      # re-export JSON Schema from harabhara/contracts.py and regenerate types
```

- All user-visible text is in `src/i18n/strings.ts` (translation-ready; no translations yet).
- Types in `src/api/contracts.d.ts` are generated; never edit by hand.
- Interface-only settings (edit step, "big edit" share) are in `src/config.ts`; business limits
  stay in the server's `config/`.

## Types come from the API
`npm run gen:types` dumps `app.openapi()` (in-memory storage, no network) with
`scripts/export_openapi.py` into `src/api/openapi.json`, then `openapi-typescript` writes
`src/api/schema.d.ts`. Both are committed; `tests/test_openapi_file.py` fails if the JSON is stale.
The mock API (`src/mock/`) is typed from the same types, so drift is a compile error.

## Sign-in
A PIN pad calls `POST /auth/login`; the token is kept in memory and `sessionStorage` and sent as
`Authorization: Bearer`. The returned `role` picks the screen and `store_id` scopes the store
manager. 401 returns to the pad, 423 shows "suggestions are switched off", 429 shows "wait".

## End-to-end against the real API
`npm run e2e:real` builds the app and runs `scripts/serve_e2e.py` (the real FastAPI app, in-memory
storage, tiny synthetic fixture, throwaway test PINs) and drives it with Playwright.

Voice, translations and offline mode are deferred.
