import os

from dotenv import load_dotenv
from infisical_sdk import InfisicalSDKClient

load_dotenv()

project_id = os.environ["INFISICAL_PROJECT_ID"]
environment_slug = os.environ["INFISICAL_ENV"]
client_id = os.environ["INFISICAL_CLIENT_ID"]
client_secret = os.environ["INFISICAL_CLIENT_SECRET"]

client = InfisicalSDKClient(host="https://app.infisical.com")

client.auth.universal_auth.login(
    client_id=client_id,
    client_secret=client_secret,
)

aws_access_key = client.secrets.get_secret_by_name(
    secret_name="aws-iam-pg-backup-service-access-key",
    project_id=project_id,
    environment_slug=environment_slug,
    secret_path="/",
).secretValue

aws_secret_key = client.secrets.get_secret_by_name(
    secret_name="aws-iam-pg-backup-service-secret-key",
    project_id=project_id,
    environment_slug=environment_slug,
    secret_path="/",
).secretValue