import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


# Named failed metrics
def check_metrics(metrics: dict, gate: dict) -> list[str]:
    failed_metrics = []
    for key, threshold in gate.items():
        metric = key.removeprefix("min_")
        measured_value = metrics.get(metric)
        # Threshold check
        ok = measured_value is not None and measured_value >= threshold
        print(f"{'PASS' if ok else 'FAIL'}: {metric} = {measured_value} (threshold >= {threshold})")

        if not ok:
            failed_metrics.append(metric)
    return failed_metrics

def main() -> None:
    metrics = json.loads((ROOT / "metrics.json").read_text())
    gate = yaml.safe_load((ROOT / "params.yaml").read_text())["gate"]

    sys.exit(1 if check_metrics(metrics, gate) else 0)

if __name__ == "__main__":
    main()
