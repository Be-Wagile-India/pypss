from pypss.storage.sqlite import SQLiteStorage


def test_sqlite_storage_save_and_get(tmp_path):
    db_path = tmp_path / "test.db"
    storage = SQLiteStorage(db_path=str(db_path))

    report = {
        "pss": 85.5,
        "breakdown": {
            "timing_stability": 0.9,
            "memory_stability": 0.8,
            "error_volatility": 1.0,
            "branching_entropy": 0.5,
            "concurrency_chaos": 0.7,
        },
    }
    meta = {"env": "test"}

    storage.save(report, meta)

    history = storage.get_history()
    assert len(history) == 1
    assert history[0]["pss"] == 85.5
    assert history[0]["meta"]["env"] == "test"

    # Add another
    report["pss"] = 90.0
    storage.save(report)

    history = storage.get_history(limit=5)
    assert len(history) == 2
    assert history[0]["pss"] == 90.0  # Latest first
