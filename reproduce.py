import argparse
import subprocess
import sys
import time
from pathlib import Path

import mlflow
import yaml

ROOT = Path(__file__).resolve().parent
PARAMS = ROOT / "params.yaml"
RAW_DVC = ROOT / "data/raw.dvc"
TRAIN_KEYS = ("n_estimators", "max_depth", "random_seed")
METRICS = ("accuracy", "f1")


def sh(*cmd: str) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id")
    parser.add_argument("--tolerance", type=float, default=0.005)
    args = parser.parse_args()
    started = time.time()

    if git("status", "--porcelain", "--untracked-files=no"):
        sys.exit("uncommitted changes: commit or stash them first (the script ends with git checkout --force)")
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    if branch == "HEAD":
        sys.exit("detached HEAD: check out a branch first")

    original = mlflow.get_run(args.run_id)
    commit = original.data.tags.get("git_commit", "unknown")
    if commit == "unknown":
        sys.exit("run has no git_commit tag")

    ok = False
    new_id = "none"
    try:
        sh("git", "checkout", "--quiet", commit)
        sh("dvc", "checkout", "--force", str(RAW_DVC.relative_to(ROOT)))
        md5 = yaml.safe_load(RAW_DVC.read_text())["outs"][0]["md5"]
        if md5 != original.data.tags.get("dvc_raw_md5"):
            sys.exit(f"data/raw.dvc at {commit} is {md5}, the run was trained on {original.data.tags.get('dvc_raw_md5')}")

        cfg = yaml.safe_load(PARAMS.read_text())
        for key in TRAIN_KEYS:
            cfg["train"][key] = int(original.data.params[key])
        PARAMS.write_text(yaml.safe_dump(cfg, sort_keys=False))

        sh("dvc", "repro", "--force")
        new_id = (ROOT / "models/run_id.txt").read_text().strip()
        reproduced = mlflow.get_run(new_id).data.metrics
        mlflow.MlflowClient().set_tag(new_id, "reproduces", args.run_id)

        ok = True
        for key in METRICS:
            delta = abs(reproduced[key] - original.data.metrics[key])
            ok &= delta <= args.tolerance
            print(f"{key}: original={original.data.metrics[key]:.4f} reproduced={reproduced[key]:.4f} delta={delta:.4f}")
    finally:
        sh("git", "checkout", "--quiet", "--force", branch)
        sh("dvc", "checkout", "--force")

    print(f"{'REPRODUCED' if ok else 'MISMATCH'} in {time.time() - started:.0f}s -> new run {new_id}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
