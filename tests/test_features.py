import pandas as pd

from data_prep import one_hot
from features import encode


def test_serving_encoding_matches_training_encoding(columns, listings):
    expected = one_hot(pd.DataFrame(listings)).reindex(columns=columns, fill_value=0)
    assert encode(listings, columns) == expected.astype(float).values.tolist()


def test_one_hot_marks_only_the_listing_category(columns, listings):
    row = dict(zip(columns, encode(listings[:1], columns)[0]))
    assert row["city_rome"] == 1.0 and row["city_vienna"] == 0.0
    assert row["room_type_Private room"] == 1.0 and row["day_type_weekends"] == 1.0
