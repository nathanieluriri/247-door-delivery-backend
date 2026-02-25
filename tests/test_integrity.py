from core.storage import _hash_content, verify_integrity


def test_verify_integrity_local(tmp_path):
    data = b"hello world"
    sha, md5 = _hash_content(data)
    file_path = tmp_path / "file.bin"
    file_path.write_bytes(data)
    assert verify_integrity(str(file_path), sha) is True
    assert verify_integrity(str(file_path), "bad") is False


def test_verify_integrity_prefers_local_file_when_backend_is_s3(tmp_path, monkeypatch):
    data = b"local content"
    sha, _ = _hash_content(data)
    file_path = tmp_path / "local.bin"
    file_path.write_bytes(data)

    monkeypatch.setattr("core.storage.STORAGE_BACKEND", "s3")
    assert verify_integrity(str(file_path), sha) is True


class _FakeClientError(Exception):
    pass


class _FakeS3Client:
    def head_object(self, Bucket, Key):  # noqa: N803 - mirrors boto3 signature
        raise _FakeClientError("not found")


class _FakeBoto3:
    @staticmethod
    def client(*_args, **_kwargs):
        return _FakeS3Client()


def test_verify_integrity_s3_client_error_returns_false(monkeypatch):
    monkeypatch.setattr("core.storage.STORAGE_BACKEND", "s3")
    monkeypatch.setattr("core.storage.boto3", _FakeBoto3())
    monkeypatch.setattr("core.storage.ClientError", _FakeClientError)
    monkeypatch.setenv("STORAGE_S3_BUCKET", "test-bucket")
    monkeypatch.setenv("STORAGE_S3_REGION", "auto")
    monkeypatch.setenv("STORAGE_S3_ENDPOINT", "https://example.invalid")

    assert verify_integrity("drivers/1/test.bin", "abc123") is False
