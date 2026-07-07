# T4.5 — Resend Domain Verification Runbook

Verify the `wishly.dev` sending domain in Resend and configure the required SPF, DKIM, and DMARC
DNS records in Cloudflare. This must be completed before the application can send any email.

---

## Why this is a hard prerequisite

Resend will not deliver mail from an unverified domain. ISPs (Gmail, Outlook, etc.) use SPF and
DKIM to authenticate that mail claiming to come from `wishly.dev` was actually sent by an
authorised system. DMARC tells ISPs what to do when authentication fails. Without these records:

- Resend rejects send requests with an API error
- Even if mail is delivered, it will be flagged as spam or rejected
- Bounce feedback loop (required for the `suppressions` table) does not work

Complete this runbook before wiring up `RESEND_API_KEY` in the backend or running the Dagster
send pipeline.

---

## Prerequisites

- A Resend account at resend.com (sign up if needed — free tier is sufficient for dev)
- `wishly.dev` must be in your Cloudflare account as an active zone (DNS managed by Cloudflare)
- You must have permission to add DNS records in the `wishly.dev` Cloudflare zone

---

## Step 1 — Add the domain in Resend

1. Log in to **resend.com/domains**
2. Click **Add Domain**
3. Enter `wishly.dev` as the domain name
4. Select your preferred region (US East is the default; match your AWS region if you care about
   latency to SES — the MX/SPF values will reflect the region you choose)
5. Click **Add**

Resend now shows a **Records** tab with the exact DNS records you need to add. Keep this tab
open; you will copy values from it in the next steps.

> **Shortcut:** Resend offers a **"Sign in to Cloudflare"** button that uses Domain Connect to
> auto-configure all required DNS records. If you use this, Resend handles steps 2–5 for you.
> You still need to add the DMARC record in step 6 manually (Resend does not create it).

---

## Step 2 — Add the MX record (bounce feedback)

In **Cloudflare DNS** (dash.cloudflare.com → wishly.dev → DNS → Records):

| Field | Value |
|---|---|
| Type | `MX` |
| Name | `send` |
| Mail server | Shown in Resend dashboard (e.g. `feedback-smtp.us-east-1.amazonses.com`) |
| Priority | `10` |
| TTL | Auto |
| Proxy status | DNS Only (grey cloud) |

Cloudflare appends `.wishly.dev` automatically — enter `send`, not `send.wishly.dev`.

If Cloudflare auto-appends your domain to the mail server value, add a trailing period to mark it
as fully qualified: `feedback-smtp.us-east-1.amazonses.com.`

---

## Step 3 — Add the SPF record

| Field | Value |
|---|---|
| Type | `TXT` |
| Name | `send` |
| Content | `v=spf1 include:amazonses.com ~all` |
| TTL | Auto |
| Proxy status | DNS Only (grey cloud) |

Resend sends through Amazon SES infrastructure; `include:amazonses.com` authorises it. The
`~all` is a softfail; you can tighten to `-all` after confirming deliverability.

---

## Step 4 — Add the DKIM record

Resend's dashboard shows the exact DKIM record. The format may be a TXT record named
`resend._domainkey` or a CNAME with a randomised token name — **copy exactly what the
dashboard shows; do not guess from this document**.

General guidance:

| Field | Value |
|---|---|
| Type | `TXT` or `CNAME` (dashboard-specified) |
| Name | Shown in dashboard (e.g. `resend._domainkey` or `<token>._domainkey`) |
| Content/Target | Long key starting with `p=...` (TXT) or a CNAME target (CNAME) |
| TTL | Auto |
| Proxy status | **DNS Only (grey cloud)** — proxying DKIM breaks email authentication |

---

## Step 5 — Verify in Resend

1. Return to the Resend domain page (resend.com/domains → wishly.dev)
2. Click **Verify DNS Records**
3. Resend checks propagation in real time. Errors appear with red wavy underlines on the
   affected record
4. DNS propagation typically completes within **15 minutes** when Cloudflare is the authoritative
   nameserver; allow up to **72 hours** in the worst case
5. If a record still fails after 24 hours, use `dig TXT send.wishly.dev` or `dig MX send.wishly.dev`
   to confirm what is actually in DNS

Once all records show green, the domain status changes to **Verified**.

---

## Step 6 — Add a DMARC record

Resend does not create this for you. Add it manually in Cloudflare DNS:

| Field | Value |
|---|---|
| Type | `TXT` |
| Name | `_dmarc` |
| Content | `v=DMARC1; p=none; rua=mailto:dmarc-reports@wishly.dev;` |
| TTL | Auto |
| Proxy status | DNS Only (grey cloud) |

Start with `p=none` (monitoring only). After confirming reminders land in inboxes and the
DMARC report aggregate shows only legitimate senders, advance to `p=quarantine`, then
optionally `p=reject`.

The `rua=` address receives aggregate XML reports from ISPs. If you do not want to process
these, you can omit `rua=` entirely or use a free DMARC report analyser (Resend offers one
at resend.com/dmarc-analyzer).

---

## Step 7 — Obtain and store the API key

1. In the Resend dashboard, go to **API Keys → Create API Key**
2. Name it (e.g. `wishly-prod`), grant **Full access** (or Send access only)
3. Copy the key — it is shown only once

Store it as:

```
RESEND_API_KEY=re_...
```

in `infra/.env` (the production `.env` that is never committed to git). The backend reads this
via `wishly.core.settings.Settings.resend_api_key`.

---

## Step 8 — Set EMAIL_FROM

Set the following in `infra/.env`:

```
EMAIL_FROM=reminders@wishly.dev
```

The `EMAIL_FROM` variable is used by `wishly.email.resend_client` as the `from` address on
every outbound email. The `reminders@wishly.dev` address:

- Uses the `wishly.dev` domain you just verified
- Makes the sender clearly identifiable to recipients
- Routes bounce feedback through the `send.wishly.dev` MX record you added above (Resend
  handles the return-path alignment transparently)

Do not use an address at a subdomain you have not verified (e.g. `reminders@send.wishly.dev`
is unnecessary — `@wishly.dev` is correct).

---

## Step 9 — Configure the Resend webhook for bounce/complaint handling

This is the hook that feeds the `suppressions` table (task T4.4). It requires a reachable API
URL, so complete T7.3 (Cloudflare Tunnel) first.

1. In Resend dashboard → **Webhooks → Add Endpoint**
2. Endpoint URL: `https://api.wishly.dev/webhooks/resend`
3. Events to subscribe: `email.bounced`, `email.complained`
4. After saving, copy the **Signing Secret**
5. Store it as:
   ```
   RESEND_WEBHOOK_SIGNING_SECRET=whsec_...
   ```
   in `infra/.env`

---

## Smoke test

Once the domain is verified and the API key is set, send a one-off test using the Resend Python SDK:

```python
import resend
resend.api_key = "re_..."
resend.Emails.send({
    "from": "reminders@wishly.dev",
    "to": ["you@yourdomain.com"],
    "subject": "Wishly smoke test",
    "html": "<p>Domain verification worked.</p>",
})
```

Or use the **Send test email** button in the Resend domain UI.

Check your inbox. If the email arrives and shows as authenticated (check headers:
`Authentication-Results: dkim=pass; spf=pass`), the domain is fully operational.

---

## Summary of DNS records added

| Type | Name | Purpose |
|---|---|---|
| `MX` | `send` | Bounce feedback loop (SES) |
| `TXT` | `send` | SPF authorisation |
| `TXT` or `CNAME` | `resend._domainkey` (or token) | DKIM signing key |
| `TXT` | `_dmarc` | DMARC policy |

All records must be **DNS Only** (grey cloud) in Cloudflare — never proxied.

---

## QUESTIONS

None — the domain (`wishly.dev`) and email address convention (`reminders@wishly.dev`) are
established. The Resend webhook setup (step 9) depends on T7.3 being complete first.
