import report_builder.build_ultimate_guide as core


def test_parse_incoming_list_with_class_and_transfer():
    raw = "Molly Beatty (So. Setter - Transfer), Jane Roe (Fr. MB)"
    parsed = core._parse_incoming_list(raw, "S")
    assert parsed[0]["name"] == "Molly Beatty"
    assert parsed[0]["class"] == "So"
    assert parsed[0]["is_transfer"] is True
    assert parsed[0]["position"] == "S"

    assert parsed[1]["name"] == "Jane Roe"
    assert parsed[1]["class"] == "Fr"
    assert parsed[1]["position"] == "MB"
