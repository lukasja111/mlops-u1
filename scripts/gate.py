import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


# gate key min_<metric> -> metrics.json key <metric>, passes when value >= threshold
def check(metrics: dict, gate: dict) -> list[str]:
    failed = []
    for key, threshold in gate.items():
        metric = key.removeprefix("min_")
        value = metrics.get(metric)
        ok = value is not None and value >= threshold
        print(f"{'PASS' if ok else 'FAIL'}: {metric} = {value} (threshold >= {threshold})")
        if not ok:
            failed.append(metric)
    return failed

def main() -> None:
    metrics = json.loads((ROOT / "metrics.json").read_text())
    gate = yaml.safe_load((ROOT / "params.yaml").read_text())["gate"]
    sys.exit(1 if check(metrics, gate) else 0)

if __name__ == "__main__":
    main()
