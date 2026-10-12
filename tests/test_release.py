import os
from pathlib import Path
import socket

import pytest

from tools.release_check import export, inspect_file


def test_release_check_redacts_credentials_and_excludes_local_files(tmp_path):
    path = tmp_path / "example.py"
    secret = b"private-value-for-test"
    path.write_bytes(secret)
    reasons, record = inspect_file(tmp_path, "example.py", [secret])
    assert "contains an active environment credential" in reasons
    assert secret.decode() not in str(reasons) + str(record)
    (tmp_path / ".env").write_text("EXAMPLE=1")
    assert "private/local file included" in inspect_file(tmp_path, ".env")[0]
    path.write_text('AccountKey = "' + 'x' * 32 + '"')
    assert inspect_file(tmp_path, "example.py")[0]


def test_release_export_preserves_bytes_and_does_not_overwrite(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "README.md").write_bytes(b"Example\r\n")
    reasons, record = inspect_file(source, "README.md")
    assert reasons == []
    dest = export(source, tmp_path / "copy", [record])
    assert (dest / "README.md").read_bytes() == b"Example\r\n"
    with pytest.raises(ValueError, match="new directory"):
        export(source, dest, [record])
    (source / "README.md").write_bytes(b"Changed")
    with pytest.raises(ValueError, match="changed"):
        export(source, tmp_path / "other", [record])


def test_suite_network_guard_and_no_real_keys():
    assert "LTA_DATAMALL_API_KEY" not in os.environ
    assert "LTA_ACCOUNT_KEY" not in os.environ
    with pytest.raises(AssertionError, match="forbidden"):
        socket.getaddrinfo("example.com", 443)
    with socket.socket() as sock:
        with pytest.raises(AssertionError, match="forbidden"):
            sock.connect(("1.1.1.1", 443))


def test_reference_relative_network_is_not_tied_to_working_directory(tmp_path, monkeypatch):
    import json
    from experiments.compare_pei_hwa_reference import MODEL, OBSERVATIONS, compare
    model = json.loads(MODEL.read_text(encoding="utf-8"))
    observed = json.loads(OBSERVATIONS.read_text(encoding="utf-8"))
    assert not Path(model["network_path"]).is_absolute()
    monkeypatch.chdir(tmp_path)
    assert compare(observed, model, model["network_path"])["comparisons"]
