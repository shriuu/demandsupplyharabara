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

## Response shapes the contract file does not define (assumed; API session please match)
| Endpoint | Assumed shape |
|---|---|
| `GET /dc/totals` | `{date, totals: [{sku_id, total: Range}], trimming: [{suggestion_id, sku_id, reduce_spot_units, reason}]}` |
| `POST /admin/kill-switch` | request `{active: true}`; response `{status, kill_switch}` |
| `POST /assistant/ask` | response `{answer: string \| null}`; null/empty or any error shows "I don't have that." |
| `POST /suggestions/{id}/decision` | request is an `Approval`; response is the updated `Suggestion` |
| Price shock | `PriceQuote` has no shock field, so no shock flag is shown yet |

Sign-in, voice, translations and offline mode are deferred; actors are recorded as
`screen-<role>` and the store manager screens use a demo store id (`S01`) until sign-in sets it.
