from accelerator.reconciliation import compare_keyed, compare_scalar


def test_scalar_exact_and_tolerance():
    assert compare_scalar(100, 100)[0] == "PASS"
    assert compare_scalar(100, 101)[0] == "FAIL"
    assert compare_scalar("10.00", "10.005", tol_abs=0.01)[0] == "PASS"
    assert compare_scalar(1000, 1004, tol_pct=0.5)[0] == "PASS"
    assert compare_scalar(None, None)[0] == "PASS"
    assert compare_scalar(1, None)[0] == "FAIL"


def test_keyed_detects_missing_extra_and_mismatch():
    status, d = compare_keyed({"a": 1, "b": 2, "c": 3}, {"a": 1, "b": 5, "d": 4})
    assert status == "FAIL"
    assert d["missing_in_target"] == 1 and d["missing_in_source"] == 1 and d["mismatched"] == 1


def test_keyed_pass():
    assert compare_keyed({"a": 1, "b": "2.0"}, {"a": 1, "b": 2})[0] == "PASS"
