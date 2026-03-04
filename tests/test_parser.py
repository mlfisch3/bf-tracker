from tracker.parser import parse_abbrev_number, parse_thread_items


def test_parse_abbrev_number_plain():
    assert parse_abbrev_number("123") == 123
    assert parse_abbrev_number("12,345") == 12345


def test_parse_abbrev_number_abbrev():
    assert parse_abbrev_number("1.2K") == 1200
    assert parse_abbrev_number("3M") == 3000000


def test_parse_thread_items_extracts_thread_numeric_id():
    html = """
    <article class='structItem structItem--thread'>
      <div class='structItem-title'>
        <a href='/threads/creely-blades-mako-pg-magnacut-g10.2067309/'>Creely</a>
      </div>
      <dl class='pairs pairs--justified'>
        <dt>Views</dt><dd>245</dd>
      </dl>
    </article>
    """
    items = parse_thread_items(html)
    assert items
    assert items[0]["thread_numeric_id"] == "2067309"
    assert items[0]["views"] == 245
