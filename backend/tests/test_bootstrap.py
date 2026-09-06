"""The one property worth pinning: the environment already set always wins."""

from __future__ import annotations

import json
import os
from unittest import mock

from wishly import bootstrap


def test_existing_environment_wins_and_missing_keys_are_filled() -> None:
    secret = {"DATABASE_URL": "postgresql://prod", "EMAIL_FROM": "a@b.c", "UNSET": None}
    client = mock.Mock()
    client.get_secret_value.return_value = {"SecretString": json.dumps(secret)}

    env = {"WISHLY_SECRETS_ID": "wishly/prod", "DATABASE_URL": "postgresql://local"}
    with (
        mock.patch.dict(os.environ, env, clear=True),
        mock.patch.dict("sys.modules", {"boto3": mock.Mock(client=lambda _: client)}),
        mock.patch.object(bootstrap.sys, "argv", ["bootstrap", "true"]),
        mock.patch.object(bootstrap.os, "execvp") as execvp,
    ):
        bootstrap.main()

        assert os.environ["DATABASE_URL"] == "postgresql://local"  # not overwritten
        assert os.environ["EMAIL_FROM"] == "a@b.c"  # filled in
        assert "UNSET" not in os.environ  # null is absent, not "None"
        execvp.assert_called_once_with("true", ["true"])
