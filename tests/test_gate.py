from gate import check_metrics

GATE = {"min_f1": 0.62, "min_accuracy": 0.75}


def test_passes_exactly_at_threshold():
    assert check_metrics({"f1": 0.62, "accuracy": 0.75}, GATE) == []


def test_fails_below_threshold():
    assert check_metrics({"f1": 0.6199, "accuracy": 0.80}, GATE) == ["f1"]


def test_missing_metric_fails():
    assert check_metrics({"f1": 0.70}, GATE) == ["accuracy"]
