import argparse
import os
import sys
from pathlib import Path

import mlflow
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException

ROOT = Path(__file__).resolve().parents[1]
NAME = os.environ.get("MODEL_NAME", "airbnb-superhost")


def alias(client: MlflowClient, name: str) -> str | None:
    try:
        return client.get_model_version_by_alias(NAME, name).version
    except MlflowException:
        return None

# One version per run: a rerun of the same run_id registers nothing new
def register(client: MlflowClient, run_id: str) -> tuple[str, bool]:
    existing = client.search_model_versions(f"name = '{NAME}' and run_id = '{run_id}'")
    if existing:
        return existing[0].version, False
    run = client.get_run(run_id)
    version = mlflow.register_model(f"models:/{run.data.tags['model_id']}", NAME).version
    for key in ("git_commit", "dvc_raw_md5"):
        client.set_model_version_tag(NAME, version, key, run.data.tags.get(key, "unknown"))
    for key in ("accuracy", "f1"):
        client.set_model_version_tag(NAME, version, key, f"{run.data.metrics[key]:.4f}")
    client.set_model_version_tag(NAME, version, "gate", "passed")
    return version, True

# @previous keeps the old champion, so a rollback has a target
def promote(client: MlflowClient, version: str) -> None:
    champion = alias(client, "champion")
    if champion == version:
        return
    if champion:
        client.set_registered_model_alias(NAME, "previous", champion)
    client.set_registered_model_alias(NAME, "champion", version)

def rollback(client: MlflowClient, version: str | None) -> str:
    champion, target = alias(client, "champion"), version or alias(client, "previous")
    if not target:
        sys.exit("no rollback target: pass --version or set @previous first")
    client.set_registered_model_alias(NAME, "champion", target)
    if champion and champion != target:
        client.set_registered_model_alias(NAME, "previous", champion)
    return target

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["register", "promote", "rollback", "current"])
    parser.add_argument("--run-id")
    parser.add_argument("--version")
    args = parser.parse_args()
    client = MlflowClient()

    if args.action == "register":
        run_id = args.run_id or (ROOT / "models/run_id.txt").read_text().strip()
        version, new = register(client, run_id)
        print(f"version={version}\nnew={str(new).lower()}")
    elif args.action == "promote":
        promote(client, args.version)
        print(f"version={alias(client, 'champion')}")
    elif args.action == "rollback":
        print(f"version={rollback(client, args.version)}")
    else:
        print(f"version={alias(client, 'champion')}")

if __name__ == "__main__":
    main()
