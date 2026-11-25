"""Pure functions: dates, URLs, tokens, quotes, bps, verdict, answer checks, consensus rule."""

import copy
import datetime
import hashlib

import pytest

TEXT = (
    "IronPulse Esports League (fictional league)\n"
    "Anti-Cheat Committee Ruling\n"
    "The committee reviewed the match of 2026-10-16 and finds that\n"
    "Kestrel used a radar hack during the final map.\n"
    "Teammates were not involved in the violation.\n"
)
GUILT = "Kestrel used a radar hack during the final map."
DATE_Q = "The committee reviewed the match of 2026-10-16 and finds that"
START, END = "2026-10-10", "2026-10-18"
HANDLE = "Kestrel"


def ans(finding="SOLO_VIOLATION", guilt=GUILT, dates=(("2026-10-16", DATE_Q),)):
    return {
        "finding": finding,
        "guilt_quote": guilt,
        "incident_dates": [{"date": d, "quote": q} for d, q in dates],
    }


@pytest.fixture
def ntext(gs):
    return gs.norm_ws(TEXT)


# --- hashing -----------------------------------------------------------------

def test_sha256_matches_hashlib(gs):
    assert gs.sha256_hex(b"abc") == hashlib.sha256(b"abc").hexdigest()
    assert gs.sha256_hex(b"") == hashlib.sha256(b"").hexdigest()


@pytest.mark.parametrize("value,ok", [
    ("a" * 64, True),
    ("0123456789abcdef" * 4, True),
    ("A" * 64, False),
    ("a" * 63, False),
    ("a" * 65, False),
    ("g" * 64, False),
    ("", False),
    (None, False),
    (123, False),
])
def test_is_sha256_hex(gs, value, ok):
    assert gs.is_sha256_hex(value) is ok


# --- whitespace and tokens ----------------------------------------------------

def test_norm_ws_collapses_all_whitespace(gs):
    assert gs.norm_ws("a \n\t b\r\n  c ") == "a b c"
    assert gs.norm_ws("") == ""


@pytest.mark.parametrize("text,token,expected", [
    ("Kestrel was banned", "Kestrel", 1),
    ("Kestrel", "Kestrel", 1),
    ("banned: Kestrel.", "Kestrel", 1),
    ("(Kestrel)", "Kestrel", 1),
    ("Kestrel, Kestrel and Kestrel", "Kestrel", 3),
    ("xKestrel", "Kestrel", 0),
    ("Kestrely", "Kestrel", 0),
    ("Kestrel_1", "Kestrel", 0),
    ("Kestrel-2", "Kestrel", 0),
    ("Kestrel.07", "Kestrel", 0),
    ("team.Kestrel", "Kestrel", 0),
    ("big-Kestrel", "Kestrel", 0),
    ("Kestrelé", "Kestrel", 0),
    ("kestrel", "Kestrel", 0),
    ("the kestrel bird", "Kestrel", 0),
    ("value 0.3 units", "0", 0),
    ("value 0 units", "0", 1),
    ("score 10", "0", 0),
    ("on 2026-10-16.", "2026-10-16", 1),
    ("on 2026-10-16, and", "2026-10-16", 1),
    ("on 2026-10-16-17", "2026-10-16", 0),
    ("on 12026-10-16", "2026-10-16", 0),
    ("on 2026-10-16 and 2026-10-16", "2026-10-16", 2),
    ("", "Kestrel", 0),
    ("Kestrel", "", 0),
])
def test_count_token(gs, text, token, expected):
    assert gs.count_token(text, token) == expected


def test_has_token_and_non_str_inputs(gs):
    assert gs.has_token("a Kestrel b", "Kestrel") is True
    assert gs.has_token("a Kestrels b", "Kestrel") is False
    assert gs.count_token(None, "x") == 0
    assert gs.count_token("x", None) == 0


# --- quotes --------------------------------------------------------------------

def test_quote_ok_accepts_verbatim_and_whitespace_variants(gs, ntext):
    assert gs.quote_ok(GUILT, ntext) is True
    assert gs.quote_ok("finds that   Kestrel used a radar hack", ntext) is True
    assert gs.quote_ok("finds that\nKestrel used a radar hack", ntext) is True


@pytest.mark.parametrize("quote", [
    "kestrel used a radar hack during the final map.",
    "Kestrel used a wallhack during the final map.",
    "x" * 12,
    "short one",
    "",
    None,
    123,
])
def test_quote_ok_rejects(gs, ntext, quote):
    assert gs.quote_ok(quote, ntext) is False


def test_quote_ok_length_bounds(gs):
    text = "a" * 500
    assert gs.quote_ok("a" * 11, text) is False
    assert gs.quote_ok("a" * 12, text) is True
    assert gs.quote_ok("a" * 400, text) is True
    assert gs.quote_ok("a" * 401, text) is False


# --- identifiers -----------------------------------------------------------------

@pytest.mark.parametrize("value,ok", [
    ("ironpulse-s4-final", True), ("abc", True), ("a" * 40, True),
    ("ab", False), ("a" * 41, False), ("Abc", False), ("a_b", False),
    ("a b", False), ("abé", False), ("", False), (None, False), (5, False),
])
def test_slug_error(gs, value, ok):
    assert (gs.slug_error(value, "EVENT") == "") is ok
    if not ok:
        assert gs.slug_error(value, "EVENT") == "BAD_EVENT"


@pytest.mark.parametrize("value,ok", [
    ("Kestrel", True), ("K3", True), ("a_b-c", True), ("Ab" * 16, True),
    ("K", False), ("A" * 33, False), ("-ab", False), ("ab-", False),
    ("_ab", False), ("ab_", False), ("a b", False), ("a.b", False),
    ("Кеst", False), ("", False), (None, False),
])
def test_handle_error(gs, value, ok):
    assert (gs.handle_error(value) == "") is ok


@pytest.mark.parametrize("value,ok", [
    (1, True), (5, True), (10, True), (0, False), (11, False), (-1, False),
    (True, False), (5.0, False), ("5", False), (None, False),
])
def test_roster_error(gs, value, ok):
    assert (gs.roster_error(value) == "") is ok


# --- dates --------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    ("2026-10-16", (2026, 10, 16)),
    ("2028-02-29", (2028, 2, 29)),
    ("2000-02-29", (2000, 2, 29)),
    ("2026-12-31", (2026, 12, 31)),
    ("2000-01-01", (2000, 1, 1)),
    ("2100-12-31", (2100, 12, 31)),
])
def test_parse_iso_date_valid(gs, value, expected):
    assert gs.parse_iso_date(value) == expected


@pytest.mark.parametrize("value", [
    "2027-02-29", "2100-02-29", "2026-02-30", "2026-04-31", "2026-13-01",
    "2026-00-10", "2026-10-00", "2026-10-32", "2026-1-01", "2026-10-1",
    "20261016", "2026/10/16", "2026-10-16 ", " 2026-10-16", "2026-10-166",
    "1999-12-31", "2101-01-01", "２０２６-10-16",
    "", None, 20261016,
])
def test_parse_iso_date_invalid(gs, value):
    assert gs.parse_iso_date(value) is None
    assert gs.is_valid_date(value) is False


def test_day_number_matches_datetime_differences(gs):
    base = datetime.date(2000, 1, 1)
    base_n = gs.day_number(2000, 1, 1)
    d = base
    while d <= datetime.date(2101, 1, 1):
        assert gs.day_number(d.year, d.month, d.day) - base_n == (d - base).days
        d += datetime.timedelta(days=37)


@pytest.mark.parametrize("start,end,expected", [
    ("2026-10-10", "2026-10-18", ""),
    ("2026-10-10", "2026-10-10", ""),
    ("2026-10-01", "2026-11-29", ""),
    ("2026-10-01", "2026-11-30", "WINDOW_TOO_LONG"),
    ("2026-01-01", "2026-12-31", "WINDOW_TOO_LONG"),
    ("2026-10-18", "2026-10-10", "END_BEFORE_START"),
    ("2026-13-01", "2026-12-01", "BAD_START"),
    ("2026-10-01", "2026-02-30", "BAD_END"),
    ("", "2026-10-01", "BAD_START"),
    (None, None, "BAD_START"),
])
def test_window_error(gs, start, end, expected):
    assert gs.window_error(start, end) == expected


def test_window_error_across_leap_day(gs):
    assert gs.window_error("2028-02-01", "2028-03-31") == ""
    assert gs.window_error("2028-02-01", "2028-04-01") == "WINDOW_TOO_LONG"


@pytest.mark.parametrize("date,inside", [
    ("2026-10-09", False), ("2026-10-10", True), ("2026-10-14", True),
    ("2026-10-18", True), ("2026-10-19", False), ("2026-08-04", False),
])
def test_in_window_is_inclusive(gs, date, inside):
    assert gs.in_window(date, START, END) is inside


# --- URLs ------------------------------------------------------------------------------

@pytest.mark.parametrize("host,expected", [
    ("raw.githubusercontent.com", ""),
    ("ironpulse.example", ""),
    ("a-b.example.org", ""),
    ("localhost", "BAD_HOST"),
    ("example", "BAD_HOST"),
    ("1.2.3.4", "HOST_IS_IP"),
    ("999.1.1.1", "HOST_IS_IP"),
    ("a.localhost", "LOCAL_HOST"),
    ("printer.local", "LOCAL_HOST"),
    ("db.internal", "LOCAL_HOST"),
    ("Raw.Example", "BAD_HOST"),
    ("ex_ample.com", "BAD_HOST"),
    ("-a.example", "BAD_HOST"),
    ("a-.example", "BAD_HOST"),
    ("a..example", "BAD_HOST"),
    (".example", "BAD_HOST"),
    ("a.example.", "BAD_HOST"),
    ("a:80.example", "BAD_HOST"),
    ("", "BAD_HOST"),
    (None, "BAD_HOST"),
    ("a" * 64 + ".example", "BAD_HOST"),
])
def test_host_error(gs, host, expected):
    assert gs.host_error(host) == expected


GOOD_BASE = "https://ironpulse.example/rulings/"


@pytest.mark.parametrize("base,expected", [
    (GOOD_BASE, ""),
    ("https://raw.githubusercontent.com/u/r/abc123/fixtures/", ""),
    ("https://ironpulse.example/", ""),
    ("http://ironpulse.example/rulings/", "BAD_BASE"),
    ("https://ironpulse.example/rulings", "BAD_BASE"),
    ("https://ironpulse.example:8443/rulings/", "BAD_BASE"),
    ("https://user@ironpulse.example/rulings/", "BAD_BASE"),
    ("https://ironpulse.example/rulings/?a=1/", "BAD_BASE"),
    ("https://ironpulse.example/rulings/#x/", "BAD_BASE"),
    ("https://ironpulse.example/%2e%2e/", "BAD_BASE"),
    ("https://ironpulse.example/a/../", "BAD_BASE"),
    ("https://ironpulse.example/р/", "BAD_BASE"),
    ("https://ironpulse.example/a b/", "BAD_BASE"),
    ("https://127.0.0.1/rulings/", "HOST_IS_IP"),
    ("https://localhost/rulings/", "BAD_HOST"),
    ("https://nas.local/rulings/", "LOCAL_HOST"),
    ("https:///rulings/", "BAD_BASE"),
    ("https://ironpulse.example/" + "a" * 200 + "/", "BAD_BASE"),
    ("", "BAD_BASE"),
    (None, "BAD_BASE"),
])
def test_base_error(gs, base, expected):
    assert gs.base_error(base) == expected


@pytest.mark.parametrize("url,expected", [
    (GOOD_BASE + "ruling-1.txt", ""),
    (GOOD_BASE + "sub/ruling-1.txt", ""),
    (GOOD_BASE, "URL_OUTSIDE_BASE"),
    ("https://ironpulse.example/other/ruling-1.txt", "URL_OUTSIDE_BASE"),
    ("https://ironpulse.example/rulings-evil/x.txt", "URL_OUTSIDE_BASE"),
    ("https://ironpulse.example.evil.com/rulings/x.txt", "URL_OUTSIDE_BASE"),
    ("http://ironpulse.example/rulings/x.txt", "URL_OUTSIDE_BASE"),
    (GOOD_BASE + "../secret.txt", "BAD_URL"),
    (GOOD_BASE + "%2e%2e/secret.txt", "BAD_URL"),
    (GOOD_BASE + "x.txt?token=1", "BAD_URL"),
    (GOOD_BASE + "x.txt#frag", "BAD_URL"),
    (GOOD_BASE + "x\\y.txt", "BAD_URL"),
    (GOOD_BASE + "x y.txt", "BAD_URL"),
    (GOOD_BASE + "р.txt", "BAD_URL"),
    (GOOD_BASE + "a" * 300, "BAD_URL"),
    ("", "BAD_URL"),
    (None, "BAD_URL"),
])
def test_url_error(gs, url, expected):
    assert gs.url_error(url, GOOD_BASE) == expected


# --- bps -------------------------------------------------------------------------------------

@pytest.mark.parametrize("roster,player,mates", [
    (1, 10000, 0), (2, 5000, 5000), (3, 3333, 6667), (4, 2500, 7500),
    (5, 2000, 8000), (6, 1666, 8334), (7, 1428, 8572), (8, 1250, 8750),
    (9, 1111, 8889), (10, 1000, 9000),
])
def test_shares(gs, roster, player, mates):
    assert gs.shares(roster) == (player, mates)
    assert player + mates == 10000


# --- verdict -----------------------------------------------------------------------------------

def total(v):
    return v["player_bps"] + v["teammates_bps"] + v["second_place_bps"]


def verdict(gs, finding, dates, roster=5):
    return gs.decide(finding, dates, START, END, roster)


def test_decide_team_forfeit(gs):
    v = verdict(gs, "TEAM_COMPLICIT", ["2026-10-16"])
    assert (v["verdict"], v["reason"], v["penalty"]) == ("TEAM_FORFEIT", "TEAM_COMPLICIT_IN_WINDOW", True)
    assert (v["player_bps"], v["teammates_bps"], v["second_place_bps"]) == (0, 0, 10000)


def test_decide_solo_forfeit(gs):
    v = verdict(gs, "SOLO_VIOLATION", ["2026-10-16"])
    assert (v["verdict"], v["reason"], v["penalty"]) == ("SOLO_FORFEIT", "SOLO_VIOLATION_IN_WINDOW", True)
    assert (v["player_bps"], v["teammates_bps"], v["second_place_bps"]) == (0, 8000, 2000)


def test_decide_outside_window_keeps_payout(gs):
    v = verdict(gs, "SOLO_VIOLATION", ["2026-08-04"])
    assert (v["verdict"], v["reason"], v["penalty"]) == ("NO_FORFEIT", "OUTSIDE_EVENT_WINDOW", False)
    assert (v["player_bps"], v["teammates_bps"], v["second_place_bps"]) == (2000, 8000, 0)


def test_decide_team_finding_outside_window_also_keeps_payout(gs):
    v = verdict(gs, "TEAM_COMPLICIT", ["2026-09-01"])
    assert v["verdict"] == "NO_FORFEIT" and v["reason"] == "OUTSIDE_EVENT_WINDOW"


def test_decide_cleared(gs):
    v = verdict(gs, "CLEARED", [])
    assert (v["verdict"], v["reason"], v["penalty"]) == ("NO_FORFEIT", "PLAYER_CLEARED", False)
    assert (v["player_bps"], v["teammates_bps"], v["second_place_bps"]) == (2000, 8000, 0)


def test_decide_cleared_ignores_dates(gs):
    assert verdict(gs, "CLEARED", ["2026-10-16"])["reason"] == "PLAYER_CLEARED"


def test_decide_unclear_is_undetermined(gs):
    v = verdict(gs, "UNCLEAR", [])
    assert (v["verdict"], v["reason"], v["penalty"]) == ("UNDETERMINED", "AMBIGUOUS_RULING", False)
    assert total(v) == 0


def test_decide_unknown_finding_fails_closed(gs):
    assert verdict(gs, "SOMETHING", ["2026-10-16"])["verdict"] == "UNDETERMINED"
    assert verdict(gs, "", [])["verdict"] == "UNDETERMINED"


@pytest.mark.parametrize("finding", ["TEAM_COMPLICIT", "SOLO_VIOLATION"])
def test_decide_violation_without_dates_is_undetermined(gs, finding):
    v = verdict(gs, finding, [])
    assert (v["verdict"], v["reason"], v["penalty"]) == ("UNDETERMINED", "MISSING_INCIDENT_DATE", False)
    assert total(v) == 0


@pytest.mark.parametrize("finding", ["TEAM_COMPLICIT", "SOLO_VIOLATION"])
def test_decide_mixed_dates_is_undetermined(gs, finding):
    v = verdict(gs, finding, ["2026-08-04", "2026-10-16"])
    assert (v["verdict"], v["reason"], v["penalty"]) == ("UNDETERMINED", "MIXED_INCIDENT_DATES", False)
    assert total(v) == 0


@pytest.mark.parametrize("date", ["2026-10-10", "2026-10-18"])
def test_decide_window_edges_are_inside(gs, date):
    assert verdict(gs, "TEAM_COMPLICIT", [date])["verdict"] == "TEAM_FORFEIT"


@pytest.mark.parametrize("date", ["2026-10-09", "2026-10-19"])
def test_decide_just_outside_the_window(gs, date):
    assert verdict(gs, "TEAM_COMPLICIT", [date])["verdict"] == "NO_FORFEIT"


def test_decide_several_dates_all_inside(gs):
    v = verdict(gs, "SOLO_VIOLATION", ["2026-10-11", "2026-10-16", "2026-10-18"])
    assert v["verdict"] == "SOLO_FORFEIT"


@pytest.mark.parametrize("roster", range(1, 11))
@pytest.mark.parametrize("finding,dates", [
    ("TEAM_COMPLICIT", ["2026-10-16"]),
    ("SOLO_VIOLATION", ["2026-10-16"]),
    ("SOLO_VIOLATION", ["2026-08-04"]),
    ("CLEARED", []),
    ("UNCLEAR", []),
    ("TEAM_COMPLICIT", []),
    ("SOLO_VIOLATION", ["2026-08-04", "2026-10-16"]),
])
def test_decide_splits_always_sum_to_zero_or_10000(gs, roster, finding, dates):
    v = verdict(gs, finding, dates, roster)
    if v["verdict"] == "UNDETERMINED":
        assert total(v) == 0 and v["penalty"] is False
    else:
        assert total(v) == 10000
    assert (v["penalty"] is True) == (v["verdict"] in ("TEAM_FORFEIT", "SOLO_FORFEIT"))


def test_decide_solo_roster_one_gives_everything_to_second_place(gs):
    for finding in ("TEAM_COMPLICIT", "SOLO_VIOLATION"):
        v = verdict(gs, finding, ["2026-10-16"], roster=1)
        assert (v["player_bps"], v["teammates_bps"], v["second_place_bps"]) == (0, 0, 10000)


# --- model answer: strict parse -------------------------------------------------------------------

def test_parse_llm_answer_accepts_valid(gs):
    parsed, err = gs.parse_llm_answer(ans())
    assert err == "" and parsed["finding"] == "SOLO_VIOLATION"
    assert parsed["incident_dates"][0]["date"] == "2026-10-16"


def test_parse_llm_answer_accepts_empty_dates(gs):
    assert gs.parse_llm_answer(ans("CLEARED", dates=()))[1] == ""


def test_parse_llm_answer_reads_null_as_empty(gs):
    parsed, err = gs.parse_llm_answer(
        {"finding": "UNCLEAR", "guilt_quote": None, "incident_dates": None}
    )
    assert err == ""
    assert parsed == {"finding": "UNCLEAR", "guilt_quote": "", "incident_dates": []}


def mutate_answer(**changes):
    base = ans()
    base.update(changes)
    return base


@pytest.mark.parametrize("obj", [
    None, [], "text", 5,
    {},
    {"finding": "CLEARED", "guilt_quote": "x"},
    mutate_answer(extra="x"),
    mutate_answer(finding="cleared"),
    mutate_answer(finding="GUILTY"),
    mutate_answer(finding=None),
    mutate_answer(finding=["CLEARED"]),
    mutate_answer(guilt_quote=5),
    mutate_answer(incident_dates="2026-10-16"),
    mutate_answer(incident_dates=[{"date": "2026-10-16"}]),
    mutate_answer(incident_dates=[{"date": "2026-10-16", "quote": "q", "extra": 1}]),
    mutate_answer(incident_dates=[{"date": 20261016, "quote": "q"}]),
    mutate_answer(incident_dates=[{"date": "2026-10-16", "quote": None}]),
    mutate_answer(incident_dates=["2026-10-16"]),
    mutate_answer(incident_dates=[{"date": "2026-10-1%d" % i, "quote": "q"} for i in range(6)]),
])
def test_parse_llm_answer_rejects(gs, obj):
    parsed, err = gs.parse_llm_answer(obj)
    assert parsed is None and err != ""


# --- model answer: verification by code --------------------------------------------------------------

def test_verify_accepts_real_quotes_and_dates(gs, ntext):
    r = gs.verify_answer(ans(), ntext, HANDLE)
    assert (r["outcome"], r["finding"]) == ("DECIDED", "SOLO_VIOLATION")
    assert r["dates"] == ["2026-10-16"] and r["date_quotes"] == [DATE_Q]
    assert r["guilt_quote"] == GUILT


def test_verify_stores_normalised_quotes(gs, ntext):
    wrapped = "finds that\n   Kestrel used a radar hack"
    r = gs.verify_answer(ans(guilt=wrapped), ntext, HANDLE)
    assert r["finding"] == "SOLO_VIOLATION"
    assert r["guilt_quote"] == "finds that Kestrel used a radar hack"


def test_verify_unclear_passes_through_empty(gs, ntext):
    r = gs.verify_answer(ans("UNCLEAR", guilt="", dates=()), ntext, HANDLE)
    assert r["finding"] == "UNCLEAR" and r["guilt_quote"] == "" and r["dates"] == []


def test_verify_cleared_needs_real_guilt_quote_and_drops_dates(gs, ntext):
    cleared_q = "Teammates were not involved in the violation."
    r = gs.verify_answer(ans("CLEARED", guilt=cleared_q), ntext, HANDLE)
    assert r["finding"] == "CLEARED" and r["dates"] == [] and r["date_quotes"] == []
    fake = gs.verify_answer(ans("CLEARED", guilt="The player was fully exonerated."), ntext, HANDLE)
    assert fake["finding"] == "UNCLEAR"


@pytest.mark.parametrize("finding", ["TEAM_COMPLICIT", "SOLO_VIOLATION"])
def test_verify_violation_with_invented_guilt_quote_is_unclear(gs, ntext, finding):
    r = gs.verify_answer(ans(finding, guilt="Kestrel confessed to using a cheat."), ntext, HANDLE)
    assert r["finding"] == "UNCLEAR" and r["dates"] == []


@pytest.mark.parametrize("dates", [
    (("2026-10-17", DATE_Q),),
    (("2026-02-30", "match of 2026-02-30 and then more words"),),
    (("2026-10-16", "this quote is not in the ruling at all 2026-10-16"),),
    (("2026-10-16", "Kestrel used a radar hack during the final map."),),
    (("2026-10-16", "2026-10-16"),),
    (("2026-10-16", "The committee reviewed 2026-10-16 and again 2026-10-16 ok"),),
])
def test_verify_bad_date_makes_the_whole_answer_unclear(gs, ntext, dates):
    r = gs.verify_answer(ans(dates=dates), ntext, HANDLE)
    assert r["finding"] == "UNCLEAR" and r["dates"] == [] and r["guilt_quote"] == ""


def test_verify_one_bad_date_is_never_dropped(gs, ntext):
    good = ("2026-10-16", DATE_Q)
    bad = ("2026-08-04", "a made up sentence about 2026-08-04 hacks")
    r = gs.verify_answer(ans(dates=(good, bad)), ntext, HANDLE)
    assert r["finding"] == "UNCLEAR"


def test_verify_violation_without_dates_stays_a_violation(gs, ntext):
    r = gs.verify_answer(ans(dates=()), ntext, HANDLE)
    assert r["finding"] == "SOLO_VIOLATION" and r["dates"] == []


def test_verify_dates_sorted_and_deduplicated(gs):
    text = "Match on 2026-10-17 was dirty today. Match on 2026-10-12 was dirty today. Kestrel cheated hard."
    nt = gs.norm_ws(text)
    q17, q12 = "Match on 2026-10-17 was dirty today.", "Match on 2026-10-12 was dirty today."
    r = gs.verify_answer(
        ans(guilt="Kestrel cheated hard.", dates=(("2026-10-17", q17), ("2026-10-12", q12), ("2026-10-17", q17))),
        nt, HANDLE,
    )
    assert r["dates"] == ["2026-10-12", "2026-10-17"]
    assert r["date_quotes"] == [q12, q17]


def test_verify_date_must_be_a_whole_token_in_its_quote(gs):
    text = "Incident 2026-10-16-17 was logged. Kestrel cheated hard."
    r = gs.verify_answer(
        ans(guilt="Kestrel cheated hard.", dates=(("2026-10-16", "Incident 2026-10-16-17 was logged."),)),
        gs.norm_ws(text), HANDLE,
    )
    assert r["finding"] == "UNCLEAR"


def test_make_result_copies_lists(gs):
    dates = ["2026-10-16"]
    r = gs.make_result("DECIDED", "", "CLEARED", dates, "q", [])
    dates.append("x")
    assert r["dates"] == ["2026-10-16"]


# --- consensus rule ---------------------------------------------------------------------------------------

@pytest.fixture
def leader(gs, ntext):
    return gs.verify_answer(ans(), ntext, HANDLE)


def test_rounds_agree_identical(gs, leader, ntext):
    assert gs.rounds_agree(leader, copy.deepcopy(leader), ntext, HANDLE) is True


def test_rounds_agree_ignores_quote_wording_when_decisive_fields_match(gs, leader, ntext):
    mine = copy.deepcopy(leader)
    mine["guilt_quote"] = "finds that Kestrel used a radar hack"
    assert gs.rounds_agree(leader, mine, ntext, HANDLE) is True


@pytest.mark.parametrize("field,value", [
    ("outcome", "UNDETERMINED"),
    ("reason", "HASH_MISMATCH"),
    ("finding", "TEAM_COMPLICIT"),
    ("dates", ["2026-10-17"]),
    ("dates", []),
])
def test_rounds_agree_rejects_when_a_decisive_field_differs(gs, leader, ntext, field, value):
    mine = copy.deepcopy(leader)
    mine[field] = value
    assert gs.rounds_agree(leader, mine, ntext, HANDLE) is False


def test_rounds_agree_rejects_forged_leader_quote(gs, leader, ntext):
    forged = copy.deepcopy(leader)
    forged["guilt_quote"] = "Kestrel confessed to using a radar hack."
    assert gs.rounds_agree(forged, copy.deepcopy(leader), ntext, HANDLE) is False


def test_rounds_agree_rejects_forged_date_quote(gs, leader, ntext):
    forged = copy.deepcopy(leader)
    forged["date_quotes"] = ["The match of 2026-10-16 was a decisive one."]
    assert gs.rounds_agree(forged, copy.deepcopy(leader), ntext, HANDLE) is False


def test_rounds_agree_rejects_quote_missing_from_validators_own_copy(gs, leader):
    other_doc = gs.norm_ws("A different document that says nothing relevant about anyone.")
    assert gs.rounds_agree(leader, copy.deepcopy(leader), other_doc, HANDLE) is False


def test_rounds_agree_rejects_unnormalised_stored_quote(gs, ntext):
    leader = gs.verify_answer(ans(), ntext, HANDLE)
    leader["guilt_quote"] = "Kestrel used a radar hack  during the final map."
    mine = gs.verify_answer(ans(), ntext, HANDLE)
    assert gs.rounds_agree(leader, mine, ntext, HANDLE) is False


@pytest.mark.parametrize("breaker", [
    lambda r: r.pop("dates"),
    lambda r: r.update(extra=1),
    lambda r: r.update(outcome=5),
    lambda r: r.update(dates="2026-10-16"),
    lambda r: r.update(date_quotes=[5]),
    lambda r: r.update(guilt_quote=None),
])
def test_rounds_agree_rejects_malformed_leader(gs, leader, ntext, breaker):
    bad = copy.deepcopy(leader)
    breaker(bad)
    assert gs.rounds_agree(bad, copy.deepcopy(leader), ntext, HANDLE) is False


@pytest.mark.parametrize("leader_value", [None, [], "x", 5])
def test_rounds_agree_rejects_non_dict_leader(gs, leader, ntext, leader_value):
    assert gs.rounds_agree(leader_value, leader, ntext, HANDLE) is False


def test_rounds_agree_rejects_unsorted_or_mismatched_dates(gs):
    text = "Match on 2026-10-17 was dirty today. Match on 2026-10-12 was dirty today. Kestrel cheated hard."
    nt = gs.norm_ws(text)
    q17, q12 = "Match on 2026-10-17 was dirty today.", "Match on 2026-10-12 was dirty today."
    good = gs.make_result("DECIDED", "", "SOLO_VIOLATION", ["2026-10-12", "2026-10-17"], "Kestrel cheated hard.", [q12, q17])
    assert gs.rounds_agree(good, copy.deepcopy(good), nt, HANDLE) is True
    unsorted = gs.make_result("DECIDED", "", "SOLO_VIOLATION", ["2026-10-17", "2026-10-12"], "Kestrel cheated hard.", [q17, q12])
    assert gs.rounds_agree(unsorted, copy.deepcopy(unsorted), nt, HANDLE) is False
    short = gs.make_result("DECIDED", "", "SOLO_VIOLATION", ["2026-10-12", "2026-10-17"], "Kestrel cheated hard.", [q12])
    assert gs.rounds_agree(short, copy.deepcopy(short), nt, HANDLE) is False
    swapped = gs.make_result("DECIDED", "", "SOLO_VIOLATION", ["2026-10-12", "2026-10-17"], "Kestrel cheated hard.", [q17, q12])
    assert gs.rounds_agree(swapped, copy.deepcopy(swapped), nt, HANDLE) is False


def test_rounds_agree_cleared_must_not_carry_dates(gs, ntext):
    q = "Teammates were not involved in the violation."
    ok = gs.make_result("DECIDED", "", "CLEARED", [], q, [])
    assert gs.rounds_agree(ok, copy.deepcopy(ok), ntext, HANDLE) is True
    bad = gs.make_result("DECIDED", "", "CLEARED", ["2026-10-16"], q, [DATE_Q])
    assert gs.rounds_agree(bad, copy.deepcopy(bad), ntext, HANDLE) is False


def test_rounds_agree_non_decided_results_must_store_nothing(gs, ntext):
    retry = gs.make_result("RETRY", "HASH_MISMATCH", "", [], "", [])
    assert gs.rounds_agree(retry, copy.deepcopy(retry), ntext, HANDLE) is True
    stuffed = gs.make_result("RETRY", "HASH_MISMATCH", "", [], GUILT, [])
    assert gs.rounds_agree(stuffed, copy.deepcopy(stuffed), ntext, HANDLE) is False
    undetermined = gs.make_result("UNDETERMINED", "PLAYER_NOT_IN_RULING", "", [], "", [])
    assert gs.rounds_agree(undetermined, copy.deepcopy(undetermined), ntext, HANDLE) is True


def test_rounds_agree_unclear_must_store_nothing(gs, ntext):
    unclear = gs.make_result("DECIDED", "", "UNCLEAR", [], "", [])
    assert gs.rounds_agree(unclear, copy.deepcopy(unclear), ntext, HANDLE) is True
    stuffed = gs.make_result("DECIDED", "", "UNCLEAR", [], GUILT, [])
    assert gs.rounds_agree(stuffed, copy.deepcopy(stuffed), ntext, HANDLE) is False


def test_rounds_agree_rejects_unknown_finding(gs, ntext):
    weird = gs.make_result("DECIDED", "", "GUILTY", [], "", [])
    assert gs.rounds_agree(weird, copy.deepcopy(weird), ntext, HANDLE) is False


# --- attribution: a guilty finding must quote a sentence that names the player -----------------

def test_verify_guilty_quote_must_name_the_player(gs, ntext):
    # a real sentence of the ruling, but it does not mention Kestrel
    r = gs.verify_answer(ans(guilt="Teammates were not involved in the violation."), ntext, HANDLE)
    assert r["finding"] == "UNCLEAR" and r["dates"] == [] and r["guilt_quote"] == ""


def test_verify_guilty_quote_about_another_player_is_unclear(gs, ntext):
    # the model quotes Kestrel's sentence while the case is about Quill
    r = gs.verify_answer(ans("TEAM_COMPLICIT"), ntext, "Quill")
    assert r["finding"] == "UNCLEAR"


def test_verify_a_longer_handle_does_not_count_as_the_player(gs):
    text = "Kestrel-2 used a radar hack during the final map. The match of 2026-10-16 was reviewed."
    r = gs.verify_answer(
        ans(guilt="Kestrel-2 used a radar hack during the final map.",
            dates=(("2026-10-16", "The match of 2026-10-16 was reviewed."),)),
        gs.norm_ws(text),
        HANDLE,
    )
    assert r["finding"] == "UNCLEAR"


def test_verify_cleared_does_not_need_the_handle_in_the_quote(gs, ntext):
    r = gs.verify_answer(ans("CLEARED", guilt="Teammates were not involved in the violation.", dates=()), ntext, HANDLE)
    assert r["finding"] == "CLEARED"


def test_rounds_agree_rejects_leader_guilt_quote_that_does_not_name_the_player(gs, ntext):
    leader = gs.make_result(
        "DECIDED", "", "SOLO_VIOLATION", ["2026-10-16"],
        "Teammates were not involved in the violation.", [DATE_Q],
    )
    assert gs.rounds_agree(leader, copy.deepcopy(leader), ntext, HANDLE) is False
