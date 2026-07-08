from dnd_and_beyond.state import _extract_verification_token


def test_extract_verification_token_accepts_raw_code_or_full_link():
    assert _extract_verification_token("abc123") == "abc123"
    assert (
        _extract_verification_token("http://localhost:3000/?verify_token=abc123")
        == "abc123"
    )
