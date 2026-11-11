import mlflow
import numpy as np
import pandas as pd
import promote
import pytest
from fastapi.testclient import TestClient
from mlflow import MlflowClient
from sklearn.ensemble import RandomForestClassifier


@pytest.fixture
def registry(tmp_path, monkeypatch):
    uri = f"sqlite:///{tmp_path}/mlflow.db"
    monkeypatch.setenv("MLFLOW_TRACKING_URI", uri)
    monkeypatch.setenv("LOAD_ATTEMPTS", "1")
    mlflow.set_tracking_uri(uri)
    mlflow.set_experiment(experiment_id=mlflow.create_experiment("test", artifact_location=str(tmp_path / "art")))
    return MlflowClient()


def train_run(columns: list[str], seed: int) -> str:
    x = pd.DataFrame(np.random.RandomState(seed).rand(40, len(columns)), columns=columns)
    y = (x["realSum"] > 0.5).astype(int)
    with mlflow.start_run() as run:
        model = RandomForestClassifier(n_estimators=3, random_state=seed).fit(x, y)
        info = mlflow.sklearn.log_model(model, name="model", skops_trusted_types=["sklearn.tree._tree.Tree"])
        mlflow.set_tags({"model_id": info.model_id, "git_commit": "test", "dvc_raw_md5": "test"})
        mlflow.log_metrics({"accuracy": 0.8, "f1": 0.7})
    return run.info.run_id


def champion(client: MlflowClient) -> tuple[str | None, str | None]:
    return promote.alias(client, "champion"), promote.alias(client, "benched")


def test_register_promote_rollback_and_serve(registry, columns, listings):
    first = train_run(columns, 0)
    v1, new1 = promote.register(registry, first)
    v2, new2 = promote.register(registry, train_run(columns, 1))
    assert (new1, new2) == (True, True)
    assert promote.register(registry, first) == (v1, False)

    promote.promote(registry, v1)
    promote.promote(registry, v2)
    promote.promote(registry, v2)
    assert champion(registry) == (v2, v1)

    import serve

    with TestClient(serve.app) as api:
        assert api.get("/health").json()["version"] == v2
        body = api.post("/predict", json=listings).json()
        assert body["model_version"] == v2 and len(body["predictions"]) == len(listings)
        assert api.post("/predict", json=[{**listings[0], "city": "oslo"}]).status_code == 422

    assert promote.rollback(registry, None) == v1
    assert champion(registry) == (v1, v2)
    with TestClient(serve.app) as api:
        assert api.get("/health").json()["version"] == v1
