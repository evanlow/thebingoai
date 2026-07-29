from backend.api.dashboards import _strip_source_suffix


def _widgets(*sources):
    return [{"id": "w1", "sources": list(sources)}]


def test_strips_suffix_naming_a_source():
    assert _strip_source_suffix(
        "HR Attrition Drivers & Risk Patterns (csv_104)", _widgets("csv_104")
    ) == "HR Attrition Drivers & Risk Patterns"


def test_strips_multi_table_suffix():
    assert _strip_source_suffix(
        "Sales vs Returns (csv_1, csv_2)", _widgets("csv_1", "csv_2")
    ) == "Sales vs Returns"


def test_keeps_suffix_that_is_not_a_source():
    assert _strip_source_suffix(
        "Q3 Sales (2024)", _widgets("csv_104")
    ) == "Q3 Sales (2024)"


def test_keeps_suffix_when_only_some_tokens_match():
    assert _strip_source_suffix(
        "Sales (csv_1, 2024)", _widgets("csv_1")
    ) == "Sales (csv_1, 2024)"


def test_noop_when_widgets_carry_no_sources():
    assert _strip_source_suffix("Sales (csv_104)", [{"id": "w1"}]) == "Sales (csv_104)"
    assert _strip_source_suffix("Sales (csv_104)", []) == "Sales (csv_104)"
    assert _strip_source_suffix("Sales (csv_104)", None) == "Sales (csv_104)"


def test_keeps_title_that_is_only_the_table_name():
    assert _strip_source_suffix("(csv_104)", _widgets("csv_104")) == "(csv_104)"


def test_ignores_parens_that_are_not_a_suffix():
    assert _strip_source_suffix(
        "Sales (csv_104) by Region", _widgets("csv_104")
    ) == "Sales (csv_104) by Region"
