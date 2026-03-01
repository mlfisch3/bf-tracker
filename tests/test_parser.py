from tracker.parser import parse_abbrev_number


def test_parse_abbrev_number_plain():
    assert parse_abbrev_number("123") == 123
    assert parse_abbrev_number("12,345") == 12345


def test_parse_abbrev_number_abbrev():
    assert parse_abbrev_number("1.2K") == 1200
    assert parse_abbrev_number("3M") == 3000000
