import os
import sys
import time
from contextlib import asynccontextmanager
from typing import Literal

import mlflow
import mlflow.sklearn
import pandas as pd
from fastapi import FastAPI
from mlflow import MlflowClient
from pydantic import BaseModel

from features import encode

MODEL_URI = os.environ.get("MODEL_URI", "models:/airbnb-superhost@champion")
IMAGE_TAG = os.environ.get("IMAGE_TAG", "local")


class Listing(BaseModel):
    realSum: float
    room_type: Literal["Entire home/apt", "Private room", "Shared room"]
    room_shared: bool
    room_private: bool
    person_capacity: float
    multi: int
    biz: int
    cleanliness_rating: float
    guest_satisfaction_overall: float
    bedrooms: int
    dist: float
    metro_dist: float
    attr_index: float
    attr_index_norm: float
    rest_index: float
    rest_index_norm: float
    lng: float
    lat: float
    city: Literal["amsterdam", "athens", "barcelona", "berlin", "budapest", "lisbon", "london", "paris", "rome", "vienna"]
    day_type: Literal["weekdays", "weekends"]


# models:/<name>@<alias> -> the version behind the alias, loaded as models:/<name>/<version>
def resolve(uri: str) -> tuple[str, dict]:
    if uri.startswith("models:/") and "@" in uri:
        name, alias = uri.removeprefix("models:/").split("@", 1)
        version = MlflowClient().get_model_version_by_alias(name, alias)
        return f"models:/{name}/{version.version}", {
            "model": name, "alias": alias, "version": version.version, "run_id": version.run_id,
        }
    return uri, {"model": uri, "alias": None, "version": "local", "run_id": None}

# MLflow can come up after this pod: retry, then exit so Kubernetes restarts the pod
def load(uri: str, attempts: int, delay: float):
    for attempt in range(1, attempts + 1):
        try:
            pinned, info = resolve(uri)
            model = mlflow.sklearn.load_model(pinned)
            model.n_jobs = 1
            print(f"loaded {pinned}", flush=True)
            return model, info
        except Exception as exc:
            print(f"model load failed ({attempt}/{attempts}): {exc}", flush=True)
            time.sleep(delay)
    sys.exit(1)

@asynccontextmanager
async def lifespan(app: FastAPI):
    attempts = int(os.environ.get("LOAD_ATTEMPTS", "30"))
    app.state.model, app.state.info = load(MODEL_URI, attempts, float(os.environ.get("LOAD_DELAY", "5")))
    yield

app = FastAPI(title="airbnb-superhost", lifespan=lifespan)

@app.get("/livez")
def livez() -> dict:
    return {"status": "alive"}

@app.get("/health")
def health() -> dict:
    return {"status": "ok", **app.state.info, "image_tag": IMAGE_TAG}

@app.post("/predict")
def predict(listings: list[Listing]) -> dict:
    model = app.state.model
    columns = list(model.feature_names_in_)
    x = pd.DataFrame(encode([listing.model_dump() for listing in listings], columns), columns=columns)
    labels = model.predict(x)
    probabilities = model.predict_proba(x)[:, 1]
    return {
        "model_version": app.state.info["version"],
        "predictions": [
            {"superhost": bool(label), "probability": round(float(p), 4)} for label, p in zip(labels, probabilities)
        ],
    }
