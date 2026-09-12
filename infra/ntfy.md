# Push notifications (ntfy)

Evaluated 2026-09-12 as a way to get alerts on a phone without building an app,
running a notification service, or paying anyone. **Status: proven, wired to
nothing.** The send path is tested end to end; no part of Wishly calls it yet.

[ntfy](https://ntfy.sh) is pub/sub over HTTP. A *topic* is just a string. You
publish to it with a POST and subscribe to it from the phone app, which holds
the push connection for you.

```
   curl -d "..."  ──POST──▶  ntfy.sh/<topic>  ──push──▶  iPhone (ntfy app)
   (any host, no auth)       (broker, 12h cache)         (subscribed)
```

There is no account, no API key, and no SDK. That is the appeal — any shell
script, Lambda, or CI job that has outbound HTTPS can page you in one line.

## Sending

```bash
curl \
  -H "Title: Home cluster is down" \
  -H "Priority: high" \
  -H "Tags: rotating_light,warning" \
  -d "No response from the home cluster. Check power and network." \
  "https://ntfy.sh/$NTFY_TOPIC"
```

The body is the message. Everything else is a header:

| Header     | Notes                                                        |
|------------|--------------------------------------------------------------|
| `Title`    | Bold first line. Falls back to the topic name.               |
| `Priority` | `min`, `low`, `default`, `high`, `urgent` (1–5).             |
| `Tags`     | Comma-separated. Emoji shortcodes render as emoji.           |

`Priority: urgent` bypasses Do Not Disturb and vibrates insistently — that is
the level a real outage page wants, and the level that will make you hate it if
anything noisy ever gets pointed at it.

`Tags` uses GitHub-style shortcodes: `warning` becomes ⚠️, `rotating_light`
becomes 🚨, `white_check_mark` becomes ✅. A tag ntfy does not recognize as an
emoji is displayed as plain text beneath the message, which makes it a decent
place to put a hostname or an environment name.

A successful publish returns `200` and a JSON echo of the stored message.
Messages persist on ntfy.sh for 12 hours, so a phone that subscribes late still
sees recent history — but only messages sent *after* subscribing arrive as an
actual push.

## Subscribing

Install ntfy from the App Store, tap **+**, enter the topic name, leave the
server as the default `ntfy.sh`. The web interface at `https://ntfy.sh/<topic>`
works too and needs nothing installed, but it only notifies while the tab is
open.

## Why the topic name is not in this file

**This repository is public.** A topic on the shared `ntfy.sh` server is
completely unauthenticated: anyone who knows the string can read every message
sent to it and publish anything they like to it. Committing the name here would
hand strangers both a feed of our alerts and the ability to forge them.

So the live topic is a random string kept out of the repo — it lives in the
phone app and in the operator's notes. Scripts read it from `NTFY_TOPIC`, the
same way everything else here reads config, and it belongs in `infra/.env`
alongside the AWS reachability settings described in [secrets.md](secrets.md).
A random name is obscurity, not security; it is adequate for a test and not for
anything that matters.

Before this carries real alerts, one of:

- **Reserve the topic.** An ntfy.sh account (paid tier) can claim a topic name
  and restrict publish/subscribe to access tokens. The token then becomes a
  normal secret and goes into `wishly/prod` in Secrets Manager.
- **Self-host.** `binwiederhier/ntfy` is a single Go binary with a config file.
  It would sit behind the existing Cloudflare tunnel, which means the phone can
  reach it without opening a port at home. Access control comes built in.

## What was actually tested

Three publishes to the live topic, all returning `200`, all delivered:

1. A default-priority smoke test with a ✅ tag, to confirm the endpoint accepts
   writes at all.
2. A second default-priority message, to confirm live push delivery to a phone
   that was already subscribed rather than cache replay.
3. A `high` priority "Home cluster is down" with 🚨⚠️, to see what an outage
   alert actually looks and feels like on the lock screen.

## If we go further

Nothing is wired up on purpose — the point was to find out whether the
experience is good enough to build on. The candidates, in rough order of how
much they would benefit:

- **The failover watchdog.** The Lambda in `infra/lambda/` already detects when
  the home cluster stops answering and flips traffic to the zero-count Fargate
  task. It currently tells no one. A publish there is the single highest-value
  place this could go, and it is about five lines.
- **Deploys.** `deploy-vm.sh` and the GitHub Actions workflow could announce
  success or failure, so a push to `main` reports back without watching a log.
- **Claude Code hooks.** A `Stop` or `Notification` hook in `~/.claude` can ping
  when a long agent session finishes or needs input. Unrelated to Wishly, but
  the same topic works.
