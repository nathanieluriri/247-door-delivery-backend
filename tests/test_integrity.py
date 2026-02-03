from core.storage import _hash_content, verify_integrity
import tempfile
import os


def test_verify_integrity_local(tmp_path):
    data = b"hello world"
    sha, md5 = _hash_content(data)
    file_path = tmp_path / "file.bin"
    file_path.write_bytes(data)
    assert verify_integrity(str(file_path), sha) is True
    assert verify_integrity(str(file_path), "bad") is False
