import bcrypt


def hash_password(password: str | bytes) -> bytes:
    if password is None:
        raise ValueError("Password is required")
    if isinstance(password, bytes):
        raw = password
    else:
        raw = str(password).encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(raw, salt)


def check_password(password: str, hashed: bytes | str | None) -> bool:
    if not hashed:
        return False
    if isinstance(hashed, str):
        hashed = hashed.encode("utf-8")
    return bcrypt.checkpw(password.encode("utf-8"), hashed)
