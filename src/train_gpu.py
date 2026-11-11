import argparse
import os
import sys
import time

import mlflow
import mlflow.pytorch
import pandas as pd
import torch
import yaml
from sklearn.metrics import accuracy_score, f1_score
from torch import nn
from torch.profiler import ProfilerActivity, profile, schedule

from train import ROOT, TEST_CSV, TRAIN_CSV, dvc_md5, git_commit

# Profiler steps: skipped, warm-up, recorded
PROFILER_STEPS = {"wait": 1, "warmup": 1, "active": 3}


def main() -> None:

    # Missing URI check
    if not os.environ.get("MLFLOW_TRACKING_URI"):
        sys.exit("MLFLOW_TRACKING_URI wasn't set properly. Point it at the cluster MLflow (e.g. http://127.0.0.1:5000)")

    # PARAMETERS
    seed = yaml.safe_load((ROOT / "params.yaml").read_text())["train"]["random_seed"]
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--hidden", type=int, default=256)
    parser.add_argument("--amp", action="store_true")

    args = parser.parse_args()
    torch.manual_seed(seed)

    cuda = torch.cuda.is_available()
    device = torch.device("cuda" if cuda else "cpu")

    mlflow.set_experiment(os.environ.get("MLFLOW_EXPERIMENT_NAME", "airbnb-superhost"))
    mlflow.set_system_metrics_sampling_interval(1)

    # Data loading
    train = pd.read_csv(ROOT / TRAIN_CSV)
    test = pd.read_csv(ROOT / TEST_CSV)

    x_train, y_train = train.drop("target", axis=1), train["target"]
    x_test, y_test = test.drop("target", axis=1), test["target"]

    # BatchNorm cannot train on a batch of one row
    if args.batch_size < 2 or len(x_train) % args.batch_size == 1:
        sys.exit("--batch-size leaves a batch of one row. Pick another size.")

    x = torch.tensor(x_train.to_numpy(), dtype=torch.float32, device=device)
    y = torch.tensor(y_train.to_numpy(), dtype=torch.float32, device=device).unsqueeze(1)

    # raw features
    model = nn.Sequential(
        nn.BatchNorm1d(x.shape[1]),

        # Hidden layer 1
        nn.Linear(x.shape[1], args.hidden), nn.ReLU(), nn.Dropout(0.2),

        # Hidden layer 2
        nn.Linear(args.hidden, args.hidden), nn.ReLU(), nn.Dropout(0.2),

        # Output: 1 logit, above 0 = Superhost
        nn.Linear(args.hidden, 1),

    ).to(device)

    loss_fn = nn.BCEWithLogitsLoss(pos_weight=(y == 0).sum() / y.sum()) # class_weight="balanced" substitute

    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)

    # LR decays to 0 over the epochs
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    # AMP gradient scaling, off without --amp
    scaler = torch.amp.GradScaler(device.type, enabled=args.amp)

    def step(idx: torch.Tensor) -> torch.Tensor:
        optimizer.zero_grad()

        with torch.autocast(device_type=device.type, enabled=args.amp):
            loss = loss_fn(model(x[idx]), y[idx])

        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()

        return loss.detach()

    with mlflow.start_run(run_name="mlp-amp" if args.amp else "mlp-fp32", log_system_metrics=True) as run:
        mlflow.set_tags({
            "git_commit": git_commit(),
            "dvc_raw_md5": dvc_md5(ROOT / "data/raw.dvc"),
            "model_family": "MLP",
            "seed": str(seed),
            "device": torch.cuda.get_device_name() if cuda else "cpu",
            "amp": str(args.amp),
        })

        mlflow.log_input(
            mlflow.data.from_pandas(train, source=TRAIN_CSV, targets="target", name="train"),
            context="training",
        )
        mlflow.log_input(
            mlflow.data.from_pandas(test, source=TEST_CSV, targets="target", name="test"),
            context="evaluation",
        )

        mlflow.log_params({**vars(args), "random_seed": seed})


        activities = [ProfilerActivity.CPU, ProfilerActivity.CUDA] if cuda else [ProfilerActivity.CPU]

        with profile(activities=activities, schedule=schedule(**PROFILER_STEPS, repeat=1)) as prof:
            for _ in range(sum(PROFILER_STEPS.values())):
                step(torch.randint(len(x), (args.batch_size,), device=device))

                prof.step()

        sort_by = "self_cuda_time_total" if cuda else "self_cpu_time_total"
        mlflow.log_text(prof.key_averages().table(sort_by=sort_by, row_limit=15), "profiler.txt")

        # Training loop
        train_seconds = 0.0
        for epoch in range(args.epochs):
            start = time.perf_counter()
            total = 0.0
            for idx in torch.randperm(len(x), device=device).split(args.batch_size):
                total += step(idx) * len(idx)

            train_loss = (total / len(x)).item()
            epoch_seconds = time.perf_counter() - start
            train_seconds += epoch_seconds

            scheduler.step()
            mlflow.log_metrics({"train_loss": train_loss, "epoch_seconds": epoch_seconds}, step=epoch)

        mlflow.log_metric("train_seconds", train_seconds)
        model.eval()

        with torch.no_grad():
            logits = model(torch.tensor(x_test.to_numpy(), dtype=torch.float32, device=device))

        preds = (logits > 0).int().squeeze(1).cpu().numpy()
        acc = accuracy_score(y_test, preds)
        f1 = f1_score(y_test, preds)

        # pickle keeps the DataFrame input
        info = mlflow.pytorch.log_model(
            nn.Sequential(model.cpu(), nn.Sigmoid()),
            name="model",
            input_example=x_train.head(3),
            serialization_format="pickle",
        )

        mlflow.set_tag("model_id", info.model_id)
        mlflow.log_metric("accuracy", acc, model_id=info.model_id)
        mlflow.log_metric("f1", f1, model_id=info.model_id)
        print(f"run_id={run.info.run_id} model_id={info.model_id} device={device} amp={args.amp} "
              f"train_seconds={train_seconds:.1f} accuracy={acc:.4f} f1={f1:.4f}")

if __name__ == "__main__":
    main()
