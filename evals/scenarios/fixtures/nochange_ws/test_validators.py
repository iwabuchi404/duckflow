from validators import is_email, is_port


def test_valid_email() -> None:
    assert is_email("user@example.com") is True


def test_invalid_email() -> None:
    assert is_email("not-an-email") is False


def test_valid_port() -> None:
    assert is_port(8080) is True
