import argparse
import csv
import json
import statistics
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTS = ("multi", "biz", "bedrooms")
BOOLS = ("room_shared", "room_private")


# The first rows of every raw file: 20 files x 5 = 100 distinct listings
def listings(per_file: int = 5) -> list[dict]:
    rows = []
    for path in sorted((ROOT / "data/raw").glob("*.csv")):
        city, day_type = path.stem.split("_")
        with path.open() as f:
            for i, row in enumerate(csv.DictReader(f)):
                if i == per_file:
                    break
                del row[""], row["host_is_superhost"]
                record = {k: int(v) if k in INTS else v == "True" if k in BOOLS else v for k, v in row.items()}
                record = {k: float(v) if isinstance(v, str) and k != "room_type" else v for k, v in record.items()}
                rows.append({**record, "city": city, "day_type": day_type})
    return rows

def call(url: str, path: str, payload: list | None = None) -> tuple[float, dict]:
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(url + path, data=data, headers={"Content-Type": "application/json"})
    start = time.perf_counter()
    with urllib.request.urlopen(request, timeout=30) as response:
        body = json.loads(response.read())
    return (time.perf_counter() - start) * 1000, body

# CD smoke test: wait until the new pods answer with the expected version and image
def smoke(url: str, version: str, image: str, timeout: int, rows: list[dict]) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            health = call(url, "/health")[1]
            if health["version"] == version and health["image_tag"] == image:
                body = call(url, "/predict", rows[:1])[1]
                print(f"smoke ok: version {body['model_version']}, image {image}")
                return
        except OSError:
            pass
        time.sleep(5)
    sys.exit(f"smoke failed: no version {version} / image {image} within {timeout}s")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--requests", type=int, default=500)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--out")
    parser.add_argument("--expect-version")
    parser.add_argument("--expect-image")
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    rows = listings()

    if args.expect_version:
        smoke(args.url, args.expect_version, args.expect_image, args.timeout, rows)
        return

    latencies = [call(args.url, "/predict", [rows[i % len(rows)]])[0] for i in range(args.requests)]
    quantiles = statistics.quantiles(latencies, n=100)

    start = time.perf_counter()
    with ThreadPoolExecutor(args.concurrency) as pool:
        list(pool.map(lambda i: call(args.url, "/predict", [rows[i % len(rows)]]), range(args.requests)))
    rps = args.requests / (time.perf_counter() - start)

    result = {
        "url": args.url,
        "model_version": call(args.url, "/health")[1]["version"],
        "requests": args.requests,
        "distinct_rows": len(rows),
        "p50_ms": round(quantiles[49], 1),
        "p95_ms": round(quantiles[94], 1),
        "p99_ms": round(quantiles[98], 1),
        "mean_ms": round(statistics.mean(latencies), 1),
        "concurrency": args.concurrency,
        "rps": round(rps, 1),
    }
    print(json.dumps(result, indent=2))
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=2) + "\n")

if __name__ == "__main__":
    main()
