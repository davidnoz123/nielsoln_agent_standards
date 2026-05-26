# Profile: website-fe-be-component

Repos that implement one focused product unit: a self-contained frontend widget and the
backend API it needs. The widget can be embedded in any website (Wix, plain HTML, React app).

**Repos using this profile:** `wsc_address_lookup`

---

## Purpose

A single widget repo stays intentionally small. It has a frontend widget, a backend API, a
test/dev area, and planning markdown. It is not a general monorepo, component library, or
full application platform.

---

## Canonical Directory Shape

```
repo/
  fe/                   # Vite + React + TypeScript widget
  be/                   # FastAPI + Python backend
  test/                 # dev harnesses, test pages, smoke tests
  subprojects/          # one .md per implementation phase
  widget-contract.md    # stable config/API reference (see below)
  README.md
```

**Tracked:** `fe/`, `be/`, `test/`, `subprojects/`, `widget-contract.md`, `README.md`

**Always gitignored:**
- `temp/` — raw/scratch files not yet structured into the repo
- `be/.env` — local and production environment variables (API keys, CORS origins)
- `tokens.json` — machine-local API key store (legacy; prefer env vars in new code)
- `fe/node_modules/`
- `repl_logs/`, `.repl_terminal_id_*`
- `__pycache__/`, `*.pyc`, `.pytest_cache/`
- `dist/`

---

## Backend Rules

### Stack

FastAPI + Python. Use the Python interpreter from `locals.txt`.

### File layout

Start with a single `be/app.py`. Split only when the file becomes genuinely awkward:

```
be/
  app.py          # all routes, settings, startup — single file initially
  .env.example    # tracked; documents required env vars with placeholder values
  .env            # gitignored; real local/production values
```

Later, if app.py grows:
```
be/
  app.py
  models.py
  service.py
```

### API key management

Read API keys from environment variables set in `be/.env`. The `.env.example` file is
tracked and documents all required keys with placeholder values.

```env
# be/.env.example
IDEAL_POSTCODES_API_KEY=ak_your_key_here
ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

Do not read keys from `tokens.json` in new code. The `tokens.json` fallback pattern from
`ws_avenrose` is for legacy use only.

### CORS

The backend reads `ALLOWED_ORIGINS` from the environment and configures FastAPI
`CORSMiddleware` at startup:

```python
import os
from fastapi.middleware.cors import CORSMiddleware

origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"],
                   allow_headers=["*"])
```

**Never use `allow_origins=["*"]` in production.** CORS is browser-facing permission only —
it is not a substitute for validation, rate limiting, widget keys, or spam protection.

For multi-tenant use (widget embedded on many customer sites), pair each widget key with an
allowed origins list stored server-side. The backend checks both key and origin.

### REPL development

Backend development uses the `python-repl-driven-dev` pattern. This profile always pairs
with `profiles/python-repl-driven-dev` in `AGENTS.project.json`.

### Minimal endpoints

Every backend starts with at minimum:

```
GET  /health                         — liveness probe; returns {"status": "ok"}
GET  /api/<domain>/autocomplete?q=   — main widget lookup
GET  /api/<domain>/resolve/{id}      — fetch full record by ID
```

Add endpoints only when the widget needs them.

---

## Frontend Rules

### Stack

Vite + React + TypeScript.

### Build target: embeddable bundle + dev page

The widget builds as a single self-contained JavaScript bundle (IIFE format) with React
bundled inline. The host page does not provide React.

```ts
// vite.config.ts (build section)
build: {
  lib: {
    entry: 'src/custom-element.tsx',
    name: 'NielsolnWidget',
    formats: ['iife'],
    fileName: () => 'widget.js',
  },
  rollupOptions: {
    external: [],   // bundle React inline — host page does not provide it
  },
}
```

The `index.html` at `fe/` root serves as a standalone dev/demo page for local iteration.

### File layout

```
fe/
  package.json
  vite.config.ts
  index.html
  .env.example    # VITE_API_BASE_URL=http://127.0.0.1:8000
  src/
    Widget.tsx          # the real React widget — normal typed component
    custom-element.tsx  # thin wrapper: registers <nielsoln-widget>; reads HTML
                        # attributes, builds WidgetConfig, renders Widget
    api.ts              # only file that calls the backend
    style.css
```

Do not add `src/components/`, `src/hooks/`, `src/utils/` until there are multiple files
that genuinely belong together.

### Embedding model

The public embedding surface is a Web Component / Custom Element:

```html
<script src="https://cdn.example.com/widget.js"></script>
<nielsoln-widget
  api-base-url="https://api.example.com"
  widget-key="customer_abc123"
  title="Find your address">
</nielsoln-widget>
```

The custom element wrapper (`custom-element.tsx`) is thin:

```
HTML attributes → Custom Element wrapper → WidgetConfig → React Widget
```

The wrapper must not contain business logic.

### Wix embedding

For Wix sites, use the Wix Editor's Custom Element feature (Add Elements → Embed Code →
Custom Element). Wix Velo page code sets attributes via `setAttribute()`:

```js
// in Velo page code (ws_avenrose)
$w('#addressWidget').setAttribute('api-base-url', 'https://api.example.com');
$w('#addressWidget').setAttribute('widget-key', 'customer_abc123');
```

**Do not rely on the Wix Editor UI attribute panel** — it is in limited rollout as of 2026.
`setAttribute()` via Velo is the confirmed mechanism.

**Wix constraints (confirmed from Wix docs):**
- Premium plan + connected domain + Wix ads removed required for custom elements on live site
- Custom elements render inside an iframe in Editor/preview mode — layout testing must be
  done on the published site or a test site, not in Editor/preview
- Bundle must be served over HTTPS on a live site; HTTP is only acceptable for local dev
- Early development: bundle can be hosted as a Velo file at `Public/custom-elements/widget.js`
  inside the Wix project — Wix serves it over HTTPS automatically. Switch to an external
  CDN/server for production deployment.

---

## Widget Contract

Every repo using this profile must have a `widget-contract.md` at the repo root. This is a
stable reference document consulted by both `be/` and `fe/`. It is NOT a phase plan — do
not put it in `subprojects/`.

Minimum contents:

1. **`WidgetConfig` TypeScript interface** — the typed config object passed as React props
   and mirrored as HTML attributes on the custom element
2. **Configurable items** — what the host page can control
3. **Deferred items** — what is explicitly not configurable yet
4. **HTML attribute mapping** — how camelCase props map to kebab-case HTML attributes

### Standard configurable items (configure early)

```ts
type WidgetConfig = {
  apiBaseUrl: string;          // required
  widgetKey?: string;          // site/customer key sent with requests
  title?: string;
  theme?: {
    primaryColor?: string;
    borderRadius?: string;
    fontFamily?: string;
  };
  labels?: {
    placeholder?: string;
    submitButton?: string;
    successMessage?: string;
    errorMessage?: string;
  };
  initialValues?: Record<string, unknown>;
  onSuccess?: (result: unknown) => void;
  onError?: (error: unknown) => void;
};
```

### Standard deferred items (do not build until there is real pressure)

- Arbitrary component slot overrides
- Custom render functions / render props
- Complex validation DSLs
- Full layout engines
- Every CSS spacing/colour value
- Multi-step workflow engines

---

## Subprojects Convention

`subprojects/` at the repo root holds one `.md` per implementation phase.

**Rules:**
- Only create a file when it contains real decisions, not vague future work
- Each file covers one concrete phase: goal, specific technical decisions, deferred list
- Free-form markdown — no required template
- Do NOT create `phase-N-fe-widget.md` until there are actual widget implementation decisions

---

## Test and Dev Area

```
test/
  host-page.html    # simulates a real host website embedding the widget bundle
  test_api.py       # pytest smoke tests for be/
  sample_payloads/  # example request/response JSON (add when useful)
```

`test/host-page.html` loads the built `dist/widget.js` and embeds the custom element. This
is the only realistic way to test the widget outside a Velo environment.

Start with pytest for backend smoke tests (`/health`, primary autocomplete endpoint).
Add Playwright only when the widget has enough browser behaviour to justify it.

---

## Local Development Flow

```powershell
# Backend
cd be
& "C:\...\venv\Scripts\python.exe" -m uvicorn app:app --reload --port 8000

# Frontend
cd fe
npm install
npm run dev    # Vite dev server on :5173

# Tests
& "C:\...\venv\Scripts\python.exe" -m pytest test/
```

---

## Patterns

- Single `be/app.py` until splitting is genuinely needed
- `ALLOWED_ORIGINS` from env, never hardcoded
- IIFE bundle with React inline — no external deps expected from host
- Custom element wrapper reads HTML attributes → WidgetConfig → React component
- Velo `setAttribute()` for Wix integration
- `subprojects/` for phase plans; `widget-contract.md` for stable design reference
- `be/.env.example` tracked; `be/.env` gitignored

---

## Anti-patterns

- `allow_origins=["*"]` in production CORS config
- Business logic in the custom element wrapper
- Hardcoding customer-specific text, colours, or endpoints in the widget
- Creating `subprojects/phase-N-*.md` files with only vague future intentions
- Adding `src/components/`, `src/hooks/` before there are multiple files that need grouping
- Importing React in the host page instead of bundling it into the widget IIFE
- Using the Wix Editor UI attribute panel for attribute config (limited rollout — use Velo `setAttribute()`)
