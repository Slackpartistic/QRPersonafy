from qrpersonafy.registry import REG_BINARY, REG_DWORD, REG_MULTI_SZ, REG_SZ, RegValue, normalize


def test_empty_values_from_winreg_become_empty_data():
    # winreg returns None for a zero-length value.
    assert normalize(REG_BINARY, None) == RegValue(REG_BINARY, b"")
    assert normalize(REG_SZ, None) == RegValue(REG_SZ, "")
    assert normalize(REG_MULTI_SZ, None) == RegValue(REG_MULTI_SZ, [])
    assert normalize(REG_DWORD, None) is None
    assert RegValue.from_json(normalize(REG_BINARY, None).to_json()) == RegValue(REG_BINARY, b"")
