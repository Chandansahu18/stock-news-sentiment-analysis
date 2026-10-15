import pytest

from app.services import news_matching


def aliases(symbol, name):
    return news_matching.aliases_for({"symbol": symbol, "name": name})


def test_hindustan_petroleum_is_also_known_as_hpcl_without_any_curated_entry():
    found = aliases("NOTCURATED", "Hindustan Petroleum Corp")  # a symbol that is not in stock_aliases.json
    assert "Hindustan Petroleum" in found and "HPCL" in found
    assert "Hindustan Petroleum Corp" not in found  # "Hindustan Petroleum" already covers it


@pytest.mark.parametrize(
    "symbol,name,expected",
    [
        ("TCS", "Tata Consultancy Services", "TCS"),
        ("BPCL", "Bharat Petroleum Corp", "BPCL"),
        ("HINDUNILVR", "Hindustan Unilever", "HUL"),   # from stock_aliases.json
        ("LT", "Larsen & Toubro", "L&T"),
        ("ITC", "ITC Limited", "ITC"),
        ("NEWCO", "Oil & Natural Gas Corp", "ONGC"),
    ],
)
def test_common_names_are_found(symbol, name, expected):
    assert expected in aliases(symbol, name)


def test_two_letter_tickers_are_not_used_and_three_letter_guesses_are_not_made():
    found = aliases("XY", "Xavier Yard Corp")
    assert "XY" not in found and "XYC" not in found and "XYCL" in found


def test_aliases_have_no_duplicates():
    found = aliases("HINDPETRO", "Hindustan Petroleum Corp")  # curated and derived names overlap
    assert len({name.lower() for name in found}) == len(found)


@pytest.mark.parametrize(
    "headline,expected",
    [
        ("HPCL taps Technip Energies for EPC on new Mumbai refinery unit", True),
        ("Buy, Sell Or Hold: ITC, HPCL, Reliance Industries", True),
        ("Hindustan Petroleum’s Vizag refinery restarts unit", True),     # curly apostrophe
        ("hindustan petroleum corp gets approval", True),                  # names ignore case
        ("Can RBI's six forex measures help stabilise the rupee?", False),
        ("360 One Quant Fund - Regular Plan - Growth", False),
        ("Hindustan Zinc and Hindustan Copper rally", False),             # similar start, different company
        ("HPCLX launches new product", False),                             # whole words only
    ],
)
def test_headline_matching(headline, expected):
    matcher = news_matching.headline_matcher(aliases("HINDPETRO", "Hindustan Petroleum Corp"))
    assert matcher(headline) is expected


def test_tickers_and_acronyms_match_only_in_capitals():
    matcher = news_matching.headline_matcher(["Oil India", "OIL"])
    assert matcher("OIL posts record output") is True
    assert matcher("Crude oil prices fall") is False
    assert matcher("Oil India wins block") is True


def test_names_with_symbols_match_whole():
    matcher = news_matching.headline_matcher(["L&T", "Larsen & Toubro"])
    assert matcher("L&T wins metro order") is True
    assert matcher("Larsen  &  Toubro shares rise") is True  # extra spaces
    assert matcher("LTD results") is False
