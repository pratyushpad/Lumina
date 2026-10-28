# Deploy runbook

The stack: **Vercel** (SPA) → **Hugging Face Space** `prat20/lumina-api` (FastAPI in
Docker) → **Neon** Postgres. Free tier throughout. Database migrations run
automatically at API startup, so Neon upgrades itself on each deploy; there is no
separate migration step.

Do these in order. Steps 1 and 2 are one-time setup; 3 to 6 are the deploy.

## 1. Rotate the secrets that were shared in chat (do this first)

Anything pasted into a chat should be considered burned. Rotate and re-set:

- **Neon**: reset the database password → new pooled connection string.
- **Groq**: revoke the old `gsk_…` key, mint a new one.
- **Hugging Face**: rotate the Space access token if one was shared.

## 2. (Optional) Google sign-in

Skip to leave sign-in off: the app is fully usable anonymously and every auth
endpoint 404s while unconfigured.

1. Google Cloud Console → APIs & Services → Credentials → **Create OAuth client ID**
   → type **Web application**.
2. Authorised redirect URI: `https://luminarag.vercel.app/auth/callback`
   (add `http://localhost:5173/auth/callback` too for local testing).
3. Note the client id and secret.
4. Generate a signing secret: `openssl rand -hex 32`.

## 3. Set Space secrets (HF → Space → Settings → Variables and secrets)

| Key | Value |
|---|---|
| `DATABASE_URL` | new Neon pooled string, `postgresql+asyncpg://…-pooler.…` |
| `GEMINI_API_KEY` | Gemini key (default generator + vision) |
| `LLM_PROVIDER_ORDER` | `gemini` (Gemini only), or `local,gemini` with the three Groq rows below |
| `LOCAL_LLM_BASE_URL` | `https://api.groq.com/openai/v1` (only with `local` in the order) |
| `LOCAL_LLM_MODEL` | `openai/gpt-oss-120b` (Groq retired `llama-3.3-70b-versatile` on Aug 16, 2026; not yet evaluated in Lumina) |
| `LOCAL_LLM_API_KEY` | new Groq `gsk_…` key (only with `local` in the order) |
| `CORS_ORIGINS` | `https://luminarag.vercel.app` |
| `SEED_DEMO_ON_STARTUP` | `true` |
| `TRUSTED_PROXY_HOPS` | `1` (HF adds exactly one proxy hop) |
| `BUDGET_LOCAL_TOKENS_PER_DAY` | Groq free-tier daily token budget (e.g. `90000`) |
| `BUDGET_GEMINI_REQUESTS_PER_DAY` | Gemini free-tier daily request budget (e.g. `18`) |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | from step 2 (omit to keep sign-in off) |
| `JWT_SECRET` | from step 2 (omit to keep sign-in off) |
| `OAUTH_REDIRECT_URI` | `https://luminarag.vercel.app/auth/callback` |

`TRUSTED_PROXY_HOPS=1` is important: it is what makes per-client rate limiting
un-spoofable behind the HF proxy. Getting it wrong (leaving it 0, or setting it too
high) lets a client forge its rate-limit key.

## 4. Ship the code

```bash
git push origin main            # runs CI (ruff, pytest incl. pgvector, eslint, prettier, build)
```

Then rebuild the HF Space from this commit as a single clean commit by `prat20`
(keeps Space history tidy), with the secrets from step 3.

## 5. Vercel

- Env: `VITE_API_URL=https://prat20-lumina-api.hf.space` (unchanged).
- Deploy the SPA (CLI-driven, not GitHub-integrated).
- **`luminarag.vercel.app`** is the canonical domain; a host-based redirect in
  `frontend/vercel.json` 308s the old `lumina-rag-two` URL to it.

## 6. Post-deploy smoke test (live)

- `GET /health/ready` → `db: ok`.
- `GET /api/sessions/` → 200, demo present.
- Demo chat streams a cited answer; an off-topic question refuses.
- Two browsers: neither sees the other's sessions; demo is read-only.
- If sign-in is on: Google round-trip on Chrome **and** Safari; after sign-in your
  anonymous sessions are adopted (claim).
