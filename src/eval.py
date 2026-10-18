import json
from pathlib import Path

import joblib
import mlflow
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    model = joblib.load(ROOT / "models/model.pkl")
    test = pd.read_csv(ROOT / "data/processed/test.csv")
    x, y = test.drop("target", axis=1), test["target"]
    preds = model.predict(x)
    metrics = {
        "accuracy": accuracy_score(y, preds),
        "f1": f1_score(y, preds),
        "precision": precision_score(y, preds),
        "recall": recall_score(y, preds),
    }
    (ROOT / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    print(json.dumps(metrics, indent=2))

    run_id_file = ROOT / "models/run_id.txt"
    if run_id_file.exists():
        try:
            client = mlflow.MlflowClient()
            for key, value in metrics.items():
                client.log_metric(run_id_file.read_text().strip(), f"eval/{key}", value)
        except Exception as exc:
            print(f"warning: eval metrics not attached to the training run ({exc})")


if __name__ == "__main__":
    main()
