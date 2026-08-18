# infisical-test

Fetches and prints two secrets from Infisical Cloud.

## Setup

1. Add `INFISICAL_PROJECT_ID` and `INFISICAL_ENV` to `.env`.
2. Set `INFISICAL_TOKEN` to a machine identity access token.

```bash
uv sync
uv run get_secrets.py
```

### Getting a token

If you have a Universal Auth **client ID** and **client secret** (not a JWT):

```bash
export INFISICAL_TOKEN=$(infisical login \
  --method=universal-auth \
  --client-id=YOUR_CLIENT_ID \
  --client-secret=YOUR_CLIENT_SECRET \
  --plain --silent)
```

Put that token in `.env` as `INFISICAL_TOKEN=...`

Note: access tokens expire (often after a few hours). For long-running apps, log in with client ID + secret in code instead of storing a token.
