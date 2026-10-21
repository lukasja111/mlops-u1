from pathlib import Path
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data/raw"
OUT_DIR = ROOT / "data/processed"
N_SPLITS = 5
SEED = 133707331

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # One frame per city and day type
    frames = []
    for path in sorted(RAW_DIR.glob("*.csv")):
        city, day_type = path.stem.split("_")
        frames.append(pd.read_csv(path, index_col=0).assign(city=city, day_type=day_type))
    df = pd.concat(frames, ignore_index=True)

    df["target"] = df.pop("host_is_superhost").astype(int)

    listing = df.groupby(["city", "lat", "lng"]).ngroup()

    # Encoding
    df = pd.get_dummies(df, columns=["room_type", "city", "day_type"], dtype=int)
    df = df.astype({"room_shared": int, "room_private": int})

    split = StratifiedGroupKFold(n_splits=N_SPLITS, shuffle=True, random_state=SEED)

    # 4/5 training. 1/5 testing
    train_idx, test_idx = next(split.split(df, df["target"], groups=listing))
    train, test = df.iloc[train_idx], df.iloc[test_idx]
    train.to_csv(OUT_DIR / "train.csv", index=False)
    test.to_csv(OUT_DIR / "test.csv", index=False)
    print(f"Train: {len(train)}, Test: {len(test)}")

if __name__ == "__main__":
    main()
