import argparse
import os
import subprocess
import sys
from pathlib import Path

import joblib
import mlflow
import mlflow.sklearn
import optuna
import pandas as pd
import yaml
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import StratifiedGroupKFold

ROOT = Path(__file__).resolve().parents[1]

# Paths from the repo root
TRAIN_CSV = "data/processed/train.csv"
TEST_CSV = "data/processed/test.csv"
MODEL_PKL = "models/model.pkl"

# Optuna tuned hyperparameters + objective function baseline. Defaults at params.yaml.
OPTUNA_SEARCH_PARAMETERS = ("n_estimators", "max_depth", "min_samples_leaf")

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

def forest(params: dict) -> RandomForestClassifier:
    return RandomForestClassifier(
        n_estimators=params["n_estimators"],
        max_depth=params["max_depth"],
        min_samples_leaf=params["min_samples_leaf"],
        random_state=params["random_seed"],
        class_weight="balanced",
        n_jobs=-1,
    )

# Hyperparam optimization Optuna trials
def search(params: dict, hpo: dict, x: pd.DataFrame, y: pd.Series) -> dict:

    # Data splitting
    groups = x.groupby(["lat", "lng"]).ngroup()
    cv = StratifiedGroupKFold(n_splits=hpo["cv_folds"], shuffle=True, random_state=params["random_seed"])
    folds = list(cv.split(x, y, groups))
    best_f1 = 0.0

    def objective(trial: optuna.Trial) -> float:
        nonlocal best_f1 # plumber non-local variable trick
        candidate = {**params, **{key: trial.suggest_int(key, *hpo[key]) for key in OPTUNA_SEARCH_PARAMETERS}}

        with mlflow.start_run(run_name=f"trial-{trial.number:02d}", nested=True):
            mlflow.log_params({key: candidate[key] for key in OPTUNA_SEARCH_PARAMETERS})
            scores_f1 = []

            for step, (fit_idx, val_idx) in enumerate(folds):
                model = forest(candidate).fit(x.iloc[fit_idx], y.iloc[fit_idx])
                scores_f1.append(f1_score(y.iloc[val_idx], model.predict(x.iloc[val_idx])))
                mlflow.log_metric("fold_f1", scores_f1[-1], step=step)

            cv_f1 = sum(scores_f1) / len(scores_f1) # trial score

            mlflow.log_metric("cv_f1", cv_f1)

        best_f1 = max(best_f1, cv_f1)

        mlflow.log_metric("trial_cv_f1", cv_f1, step=trial.number)
        mlflow.log_metric("best_cv_f1", best_f1, step=trial.number)

        return cv_f1

    optuna.logging.set_verbosity(optuna.logging.WARNING)

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=params["random_seed"]))

    # params.yaml as baseline for objective fn
    # https://optuna.readthedocs.io/en/stable/reference/generated/optuna.study.Study.html#optuna.study.Study.enqueue_trial
    study.enqueue_trial({key: params[key] for key in OPTUNA_SEARCH_PARAMETERS})
    study.optimize(objective, n_trials=hpo["n_trials"])

    return study.best_params

def main() -> None:

    # Missing URI check
    if not os.environ.get("MLFLOW_TRACKING_URI"):
        # Prints the message and exits with code 1
        sys.exit("MLFLOW_TRACKING_URI wasn't set properly. Point it at the cluster MLflow (e.g. http://127.0.0.1:5000)")

    # PARAMETERS
    config = yaml.safe_load((ROOT / "params.yaml").read_text())

    params, hpo = config["train"], config["hpo"]
    parser = argparse.ArgumentParser()
    for key in (*OPTUNA_SEARCH_PARAMETERS, "random_seed", "n_trials"):
        parser.add_argument(f"--{key}", type=int)
    args = vars(parser.parse_args())

    # set
    n_trials = args.pop("n_trials")

    if n_trials is not None:
        hpo["n_trials"] = n_trials

    for key, value in args.items():
        if value is not None:
            params[key] = value

    mlflow.set_experiment(os.environ.get("MLFLOW_EXPERIMENT_NAME", "airbnb-superhost"))
    mlflow.set_system_metrics_sampling_interval(1)

    # Data loading
    train = pd.read_csv(ROOT / TRAIN_CSV)
    test = pd.read_csv(ROOT / TEST_CSV)
    x_train, y_train = train.drop("target", axis=1), train["target"]
    x_test, y_test = test.drop("target", axis=1), test["target"]

    tuned = hpo["n_trials"] > 0 #post-run trick

    # rf-hpo for a search, rf-n... for model
    run_name = f"rf-hpo{hpo['n_trials']}" if tuned else f"rf-n{params['n_estimators']}-d{params['max_depth']}"

    with mlflow.start_run(run_name=run_name, log_system_metrics=True) as run:

        # Tag settings
        mlflow.set_tags({
            "git_commit": git_commit(),
            "dvc_raw_md5": dvc_md5(ROOT / "data/raw.dvc"),
            "model_family": "RandomForestClassifier",
            "seed": str(params["random_seed"]),
        })

        mlflow.log_input(
            mlflow.data.from_pandas(train, source=TRAIN_CSV, targets="target", name="train"),
            context="training",
        )
        mlflow.log_input(
            mlflow.data.from_pandas(test, source=TEST_CSV, targets="target", name="test"),
            context="evaluation",
        )

        if tuned:
            mlflow.log_params({f"hpo.{key}": value for key, value in hpo.items()})
            params.update(search(params, hpo, x_train, y_train))

        # Final train and model
        mlflow.log_params(params)
        model = forest(params).fit(x_train, y_train)
        preds = model.predict(x_test)
        acc = accuracy_score(y_test, preds)
        f1 = f1_score(y_test, preds)

        # log-model
        info = mlflow.sklearn.log_model(
            model,
            name="model",
            input_example=x_train.head(3),
            skops_trusted_types=["sklearn.tree._tree.Tree"],
        )
        mlflow.set_tag("model_id", info.model_id)
        mlflow.log_metric("accuracy", acc, model_id=info.model_id)
        mlflow.log_metric("f1", f1, model_id=info.model_id)

        os.makedirs(ROOT / "models", exist_ok=True)
        joblib.dump(model, ROOT / MODEL_PKL)
        mlflow.log_metric("model_size_mb", (ROOT / MODEL_PKL).stat().st_size / 1e6)
        (ROOT / "models/run_id.txt").write_text(run.info.run_id + "\n")
        print(f"run_id={run.info.run_id} model_id={info.model_id} params={params} accuracy={acc:.4f} f1={f1:.4f}")

if __name__ == "__main__":
    main()
