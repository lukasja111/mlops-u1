import os
from pathlib import Path
import pandas as pd
from sklearn.model_selection import train_test_split

RAW_DIR = Path("data/raw")
OUT_DIR = "data/processed"
TEST_SIZE = 0.2
SEED = 42


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

    frames = []
    for path in sorted(RAW_DIR.glob("*.csv")):
        city, day_type = path.stem.split("_")
        frames.append(pd.read_csv(path, index_col=0).assign(city=city, day_type=day_type))
    df = pd.concat(frames, ignore_index=True)
    df["target"] = df.pop("host_is_superhost").astype(int)
    df = pd.get_dummies(df, columns=["room_type", "city", "day_type"], dtype=int)
    df = df.astype({"room_shared": int, "room_private": int})

    train, test = train_test_split(
        df, test_size=TEST_SIZE, random_state=SEED, stratify=df["target"]
    )
    train.to_csv(f"{OUT_DIR}/train.csv", index=False)
    test.to_csv(f"{OUT_DIR}/test.csv", index=False)
    print(f"Train: {len(train)}, Test: {len(test)}")


if __name__ == "__main__":
    main()
