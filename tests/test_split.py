import pandas as pd

from data_prep import split


def test_split_keeps_each_listing_on_one_side():
    rows = [
        {"lat": 50 + i * 0.001, "lng": 4 + i * 0.001, "weekend": weekend, "target": int(i % 4 == 0)}
        for i in range(200)
        for weekend in (0, 1)
    ]
    df = pd.DataFrame(rows)
    train, test = split(df, df.groupby(["lat", "lng"]).ngroup())
    assert len(test) > 0
    assert not set(zip(train.lat, train.lng)) & set(zip(test.lat, test.lng))
