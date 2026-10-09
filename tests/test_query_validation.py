import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import validate_queries


def test_query_validator_rejects_unknown_message_id(tmp_path, monkeypatch):
    data = yaml.safe_load(validate_queries.QUERIES.read_text())
    data["queries"][0]["relevant"]["synthetic:eng:unknown"] = 1
    path = tmp_path / "queries.yaml"
    path.write_text(yaml.safe_dump(data))
    monkeypatch.setattr(validate_queries, "QUERIES", path)
    with pytest.raises(SystemExit, match="missing corpus message synthetic:eng:unknown"):
        validate_queries.main()
