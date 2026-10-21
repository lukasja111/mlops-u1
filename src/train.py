import sys
import argparse
import os
import subprocess
from pathlib import Path

import joblib
import mlflow
import mlflow.sklearn
import pandas as pd
import yaml
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score

ROOT = Path(__file__).resolve().parents[1]

# Local git_commit image build arg
def git_commit() -> str:
    if os.environ.get("GIT_COMMIT"):
        return os.environ["GIT_COMMIT"]
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short=8", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        return "unknown"

def dvc_md5(dvc_file: Path) -> str:
    try:
        return yaml.safe_load(dvc_file.read_text())["outs"][0]["md5"]
    except Exception:
        return "untracked"

def main() -> None:

    # Missing URI check
    if not os.environ.get("MLFLOW_TRACKING_URI"):
        sys.exit("MLFLOW_TRACKING_URI wasn't set properly. Point it at the cluster MLflow (e.g. http://127.0.0.1:5000)")

    # PARAMETERS
    params = yaml.safe_load((ROOT / "params.yaml").read_text())["train"]
    parser = argparse.ArgumentParser()
    parser.add_argument("--n_estimators", type=int)
    parser.add_argument("--max_depth", type=int)
    parser.add_argument("--random_seed", type=int)
    for key, value in vars(parser.parse_args()).items():
        if value is not None:
            params[key] = value

    # Logging
    mlflow.set_experiment(os.environ.get("MLFLOW_EXPERIMENT_NAME", "airbnb-superhost"))

    # Data loading
    train = pd.read_csv(ROOT / "data/processed/train.csv")
    test = pd.read_csv(ROOT / "data/processed/test.csv")
    x_train, y_train = train.drop("target", axis=1), train["target"]
    x_test, y_test = test.drop("target", axis=1), test["target"]


    run_name = f"rf-n{params['n_estimators']}-d{params['max_depth']}"

    with mlflow.start_run(run_name=run_name) as run:
        mlflow.log_params(params)
        mlflow.set_tags({
            "git_commit": git_commit(),
            "dvc_raw_md5": dvc_md5(ROOT / "data/raw.dvc"),
            "model_family": "RandomForestClassifier",
        })

        mlflow.log_input(
            mlflow.data.from_pandas(
                train, source="data/processed/train.csv", targets="target", name="train"
            ),
            context="training",
        )

        model = RandomForestClassifier(
            n_estimators=params["n_estimators"],
            max_depth=params["max_depth"],
            random_state=params["random_seed"],
            class_weight="balanced",
        )
        model.fit(x_train, y_train)

        # Quick-check
        preds = model.predict(x_test)
        acc = accuracy_score(y_test, preds)
        f1 = f1_score(y_test, preds)

        info = mlflow.sklearn.log_model(
            model,
            name="model",
            input_example=x_train.head(3),
            skops_trusted_types=["sklearn.tree._tree.Tree"],
        )
        mlflow.log_metric("accuracy", acc, model_id=info.model_id)
        mlflow.log_metric("f1", f1, model_id=info.model_id)

        os.makedirs(ROOT / "models", exist_ok=True)
        joblib.dump(model, ROOT / "models/model.pkl")
        (ROOT / "models/run_id.txt").write_text(run.info.run_id + "\n")
        print(f"run_id={run.info.run_id} model_id={info.model_id} accuracy={acc:.4f} f1={f1:.4f}")

if __name__ == "__main__":
    main()
