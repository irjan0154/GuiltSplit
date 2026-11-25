"""Tests added after the first mutation run: each one kills a mutant that the suite missed."""

import re

import pytest

from helpers import BASE, DATE_Q, DOC, GUILT_Q, HANDLE, URL, answer, sha

DAY = "2026-10-16"

# a document with awkward sentences, used by the verify/stored tests
EXTRA = [
    "The committee notes 2026-02-30 in a clerical error.",
    "Both 2026-10-16 and 2026-10-16 are the same day.",
    "The match of 2026-10-16 was the final map.",
] + ["Incident on 2026-10-1%d was reviewed." % n for n in range(1, 7)] + [
    "Incident on 2026-13-01 was reviewed.",
]
DOC2 = DOC + "\n".join(EXTRA) + "\n"


@pytest.fixture
def norm(gs):
    return gs.norm_ws(DOC2)


# --- limits at their exact edge -------------------------------------------------------------------

def test_url_length_edge(gs):
    ok = BASE + "a" * (300 - len(BASE))
    assert len(ok) == 300 and gs.url_error(ok, BASE) == ""
    assert gs.url_error(ok + "a", BASE) == "BAD_URL"


def test_base_length_edge(gs):
    prefix = "https://ironpulse.example/"
    ok = prefix + "a" * (200 - len(prefix) - 1) + "/"
    assert len(ok) == 200 and gs.base_error(ok) == ""
    assert gs.base_error(ok[:-1] + "a/") == "BAD_BASE"


def test_delete_character_is_not_printable_ascii(gs):
    assert gs.base_error("https://ironpulse.example/ru\x7f/") == "BAD_BASE"
    assert gs.url_error(BASE + "a\x7f", BASE) == "BAD_URL"


def test_host_length_edges(gs):
    assert gs.host_error("a.b") == "BAD_HOST"
    assert gs.host_error("a.bc") == ""
    host100 = "a" * 63 + "." + "b" * 36
    assert len(host100) == 100 and gs.host_error(host100) == ""
    assert gs.host_error(host100 + "b") == "BAD_HOST"


@pytest.mark.parametrize("suffix", [".localhost", ".local", ".internal", ".lan", ".home", ".corp", ".intranet"])
def test_every_local_suffix_is_refused(gs, suffix):
    assert gs.host_error("my" + suffix) == "LOCAL_HOST"
    assert gs.base_error("https://my" + suffix + "/rulings/") == "LOCAL_HOST"


# --- dates ----------------------------------------------------------------------------------------------

def test_november_has_thirty_days(gs):
    assert gs.parse_iso_date("2026-11-30") == (2026, 11, 30)
    assert gs.parse_iso_date("2026-11-31") is None


@pytest.mark.parametrize("bad", [
    "2026-10/16", "2026/10-16", "2026_10-16", "2026-10-1x", "2026-10-x6", "x026-10-16", "2026-1x-16", "2026-x0-16",
])
def test_every_separator_and_digit_position_is_checked(gs, bad):
    assert gs.parse_iso_date(bad) is None


# --- tokens ---------------------------------------------------------------------------------------------------

def test_empty_token_never_matches(gs):
    assert gs.count_token(" ", "") == 0 and gs.has_token(" ", "") is False
    assert gs.count_token("", "") == 0


def test_overlapping_whole_token_occurrences_are_both_counted(gs):
    # a handle may legally contain "--"; both whole occurrences are found
    assert gs.count_token("a--a--a", "a--a") == 2


# --- verify_answer: paths that were not pinned ------------------------------------------------------------

def test_unclear_with_real_quotes_is_stored_empty(gs, norm):
    got = gs.verify_answer(answer("UNCLEAR", GUILT_Q, ((DAY, DATE_Q),)), norm, HANDLE)
    assert got == gs.make_result("DECIDED", "", "UNCLEAR", [], "", [])


def test_impossible_date_in_a_real_quote_makes_the_answer_unclear(gs, norm):
    q = "The committee notes 2026-02-30 in a clerical error."
    got = gs.verify_answer(answer("SOLO_VIOLATION", GUILT_Q, (("2026-02-30", q),)), norm, HANDLE)
    assert got["finding"] == "UNCLEAR"


def test_date_that_appears_twice_in_its_quote_makes_the_answer_unclear(gs, norm):
    q = "Both 2026-10-16 and 2026-10-16 are the same day."
    got = gs.verify_answer(answer("SOLO_VIOLATION", GUILT_Q, ((DAY, q),)), norm, HANDLE)
    assert got["finding"] == "UNCLEAR"


def test_the_first_quote_for_a_repeated_date_is_kept(gs, norm):
    second = "The match of 2026-10-16 was the final map."
    got = gs.verify_answer(answer("SOLO_VIOLATION", GUILT_Q, ((DAY, DATE_Q), (DAY, second))), norm, HANDLE)
    assert got["dates"] == [DAY] and got["date_quotes"] == [DATE_Q]
    got = gs.verify_answer(answer("SOLO_VIOLATION", GUILT_Q, ((DAY, second), (DAY, DATE_Q))), norm, HANDLE)
    assert got["date_quotes"] == [second]


# --- _stored_fields_ok called directly (defence in depth behind rounds_agree) -----------------------------

def stored(gs, **over):
    res = gs.make_result("DECIDED", "", "SOLO_VIOLATION", [DAY], GUILT_Q, [DATE_Q])
    res.update(over)
    return res


def test_stored_baseline_is_accepted(gs, norm):
    assert gs._stored_fields_ok(stored(gs), norm, HANDLE) is True


def test_stored_unknown_finding_is_refused(gs, norm):
    assert gs._stored_fields_ok(stored(gs, finding="BOGUS"), norm, HANDLE) is False


def test_stored_more_than_five_dates_is_refused(gs, norm):
    dates = ["2026-10-1%d" % n for n in range(1, 7)]
    quotes = ["Incident on %s was reviewed." % d for d in dates]
    assert gs._stored_fields_ok(stored(gs, dates=dates[:5], date_quotes=quotes[:5]), norm, HANDLE) is True
    assert gs._stored_fields_ok(stored(gs, dates=dates, date_quotes=quotes), norm, HANDLE) is False


def test_stored_impossible_date_is_refused(gs, norm):
    res = stored(gs, dates=["2026-13-01"], date_quotes=["Incident on 2026-13-01 was reviewed."])
    assert gs._stored_fields_ok(res, norm, HANDLE) is False


def test_stored_repeated_date_is_refused(gs, norm):
    q = "Incident on 2026-10-11 was reviewed."
    assert gs._stored_fields_ok(stored(gs, dates=["2026-10-11"], date_quotes=[q]), norm, HANDLE) is True
    assert gs._stored_fields_ok(stored(gs, dates=["2026-10-11"] * 2, date_quotes=[q] * 2), norm, HANDLE) is False


def test_stored_quote_with_double_space_is_refused(gs, norm):
    q = "Incident on  2026-10-11 was reviewed."
    assert gs._stored_fields_ok(stored(gs, dates=["2026-10-11"], date_quotes=[q]), norm, HANDLE) is False


def test_leader_cannot_pass_date_quotes_as_a_string(gs, norm):
    mine = gs.make_result("DECIDED", "", "SOLO_VIOLATION", [], GUILT_Q, [])
    leader = dict(mine)
    assert gs.rounds_agree(leader, mine, norm, HANDLE) is True
    leader["date_quotes"] = ""
    assert gs.rounds_agree(leader, mine, norm, HANDLE) is False
    leader["date_quotes"], leader["dates"] = [], ""
    assert gs.rounds_agree(leader, mine, norm, HANDLE) is False


# --- validator: a leader that fails in a way we did not classify ---------------------------------------------

def test_validator_rejects_when_replaying_the_leader_raises_something_unexpected(assessed, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(assessed.m, "_round", boom)
    assert assessed.vm.run_validator(leader_error=Exception("[TRANSIENT] fetch failed")) is False


def test_empty_response_body_is_a_hash_mismatch_not_a_crash(world):
    world.register()
    world.vm.mock_web(re.escape(URL) + "$", {"status": 200, "body": None})
    cid = world.propose(doc=DOC)
    out = world.assess(cid)
    assert out["status"] == "RETRYABLE" and out["reason"] == "HASH_MISMATCH"
