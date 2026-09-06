"""Load config from AWS Secrets Manager into the environment, then exec the app.

The container entrypoint::

    python -m wishly.bootstrap uvicorn wishly.api.main:app --host 0.0.0.0

Credentials are never configured. boto3 finds them from the task role on ECS and
from ~/.aws locally — there is no access key in the image, the environment, or
this file. All that is set is WISHLY_SECRETS_ID, naming which secret to read.

``setdefault`` means anything already in the environment wins, so a rendered
``infra/.env`` or a compose override takes precedence and no AWS call is needed.
Unset WISHLY_SECRETS_ID and this is a no-op that just execs.
"""

from __future__ import annotations

import json
import os
import sys


def main() -> None:
    if not sys.argv[1:]:
        raise SystemExit("usage: python -m wishly.bootstrap <command> [args...]")

    secret_id = os.environ.get("WISHLY_SECRETS_ID")
    if secret_id:
        import boto3  # imported here so the no-op path costs nothing

        raw = boto3.client("secretsmanager").get_secret_value(SecretId=secret_id)
        for key, value in json.loads(raw["SecretString"]).items():
            if value is not None:
                os.environ.setdefault(key, str(value))

    # execvp, not subprocess: the real process must inherit PID 1 or a SIGTERM
    # from ECS never reaches uvicorn and every stop becomes a 30-second kill.
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    main()
