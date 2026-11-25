"""Validator side: the validator redoes the round and rejects a leader that lies or errs.

Direct Mode keeps the last leader/validator pair; run_validator() replays the
validator against the CURRENT mocks, so swapping mocks between assess() and
run_validator() simulates a validator that sees different data.
"""

import copy
import types

import pytest

from helpers import (
    DATE_Q, DOC, GUILT_Q, HANDLE, NEUTRAL_Q, WITNESS_Q, answer,
)


@pytest.fixture
def honest(assessed):
    return copy.deepcopy(assessed.last_leader_result())


# --- an honest leader is accepted ----------------------------------------------------------

def test_stored_leader_result_is_accepted(assessed):
    assert assessed.vm.run_validator() is True


def test_explicit_copy_of_the_honest_result_is_accepted(assessed, honest):
    assert assessed.vm.run_validator(leader_result=honest) is True


def test_different_wording_of_real_quotes_is_still_accepted(assessed, honest):
    # quotes are not compared between validators, only checked against the validator's own copy
    honest["guilt_quote"] = "finds that Kestrel used a radar hack"
    honest["date_quotes"] = ["The committee reviewed the match of 2026-10-16"]
    assert assessed.vm.run_validator(leader_result=honest) is True


# --- a forged leader result is rejected -------------------------------------------------------

FORGERIES = {
    "flipped finding": lambda r: r.update(finding="TEAM_COMPLICIT"),
    "cleared instead of guilty": lambda r: r.update(finding="CLEARED", dates=[], date_quotes=[]),
    "unclear instead of guilty": lambda r: r.update(finding="UNCLEAR", guilt_quote="", dates=[], date_quotes=[]),
    "different date": lambda r: r.update(dates=["2026-10-17"]),
    "no dates": lambda r: r.update(dates=[], date_quotes=[]),
    "extra date": lambda r: r.update(dates=["2026-10-16", "2026-10-17"], date_quotes=[DATE_Q, DATE_Q]),
    "undetermined outcome": lambda r: r.update(
        outcome="UNDETERMINED", reason="PLAYER_NOT_IN_RULING", finding="", dates=[], guilt_quote="", date_quotes=[]),
    "retry outcome": lambda r: r.update(
        outcome="RETRY", reason="HASH_MISMATCH", finding="", dates=[], guilt_quote="", date_quotes=[]),
    "invented guilt quote": lambda r: r.update(guilt_quote="Kestrel confessed to using a radar hack."),
    "invented date quote": lambda r: r.update(date_quotes=["The match of 2026-10-16 was a decisive one."]),
    "guilt quote that does not name the player": lambda r: r.update(guilt_quote=NEUTRAL_Q),
    "guilt quote about someone else": lambda r: r.update(guilt_quote=WITNESS_Q),
    "date quote without its date": lambda r: r.update(date_quotes=["Anti-Cheat Committee Ruling"]),
    "quote not normalised": lambda r: r.update(guilt_quote="Kestrel used a radar hack  during the final map."),
    "reason changed": lambda r: r.update(reason="SOMETHING_ELSE"),
    "stuffed quote on a non-decided result": lambda r: r.update(
        outcome="UNDETERMINED", reason="PLAYER_NOT_IN_RULING", finding=""),
}


@pytest.mark.parametrize("name", sorted(FORGERIES))
def test_forged_leader_result_is_rejected(assessed, honest, name):
    FORGERIES[name](honest)
    assert assessed.vm.run_validator(leader_result=honest) is False


@pytest.mark.parametrize("leader_result", [
    None, "x", 5, [], {},
    {"outcome": "DECIDED"},
])
def test_malformed_leader_result_is_rejected(assessed, leader_result):
    assert assessed.vm.run_validator(leader_result=leader_result) is False


@pytest.mark.parametrize("breaker", [
    lambda r: r.pop("dates"),
    lambda r: r.pop("guilt_quote"),
    lambda r: r.update(extra="x"),
    lambda r: r.update(outcome=1),
    lambda r: r.update(dates="2026-10-16"),
    lambda r: r.update(dates=[20261016]),
    lambda r: r.update(date_quotes=[None]),
    lambda r: r.update(guilt_quote=None),
])
def test_malformed_fields_are_rejected(assessed, honest, breaker):
    breaker(honest)
    assert assessed.vm.run_validator(leader_result=honest) is False


# --- the validator has its own view of the world ------------------------------------------------

def test_validator_whose_model_says_something_else_disagrees(assessed):
    assessed.reset()
    assessed.serve()
    assessed.model(answer("TEAM_COMPLICIT"))
    assert assessed.vm.run_validator() is False


def test_validator_whose_model_reads_another_date_disagrees(assessed):
    assessed.reset()
    assessed.serve()
    assessed.model(answer(dates=(("2026-10-16", DATE_Q),)) | {"incident_dates": []})
    assert assessed.vm.run_validator() is False


def test_validator_whose_model_downgrades_to_unclear_disagrees(assessed):
    assessed.reset()
    assessed.serve()
    assessed.model(answer("UNCLEAR", guilt="", dates=()))
    assert assessed.vm.run_validator() is False


def test_validator_whose_model_invents_a_quote_ends_up_unclear_and_disagrees(assessed):
    assessed.reset()
    assessed.serve()
    assessed.model(answer(guilt="Kestrel was seen using a radar hack by everyone."))
    assert assessed.vm.run_validator() is False


def test_validator_with_other_wording_but_same_decision_agrees(assessed):
    assessed.reset()
    assessed.serve()
    assessed.model(answer(guilt="finds that Kestrel used a radar hack during the final map."))
    assert assessed.vm.run_validator() is True


def test_validator_that_sees_a_tampered_document_disagrees(assessed):
    assessed.reset()
    assessed.serve(body=DOC + "Added later.\n")  # hash no longer matches: validator gets RETRY
    assessed.model(answer())
    assert assessed.vm.run_validator() is False


def test_validator_whose_fetch_now_fails_disagrees(assessed):
    assessed.reset()
    assessed.serve(body="", status=404)
    assessed.model(answer())
    assert assessed.vm.run_validator() is False


def test_validator_whose_model_is_down_disagrees(assessed):
    assessed.reset()
    assessed.serve()  # no model mock: the validator's round fails with an LLM error
    assert assessed.vm.run_validator() is False


# --- retry and player-not-in-ruling rounds -----------------------------------------------------------

def test_retry_round_is_agreed_when_the_validator_sees_the_same_mismatch(world):
    world.register()
    world.serve(body=DOC + "Added after the hash.\n")
    world.model(answer())
    cid = world.propose()
    assert world.assess(cid)["status"] == "RETRYABLE"
    assert world.vm.run_validator() is True


def test_retry_leader_is_rejected_when_the_validator_sees_the_right_document(world):
    world.register()
    world.serve(body=DOC + "Added after the hash.\n")
    world.model(answer())
    cid = world.propose()
    world.assess(cid)
    world.reset()
    world.serve()
    world.model(answer())
    assert world.vm.run_validator() is False


def test_player_not_in_ruling_is_agreed_without_any_model(world):
    world.register()
    world.serve()
    cid = world.propose(handle="Nobody")
    assert world.assess(cid)["reason"] == "PLAYER_NOT_IN_RULING"
    assert world.vm.run_validator() is True


def test_a_leader_cannot_convict_a_player_who_is_not_in_the_ruling(world):
    world.register()
    world.serve()
    cid = world.propose(handle="Nobody")
    world.assess(cid)
    forged = copy.deepcopy(world.last_leader_result())
    forged.update(outcome="DECIDED", reason="", finding="SOLO_VIOLATION", guilt_quote=GUILT_Q,
                  dates=["2026-10-16"], date_quotes=[DATE_Q])
    assert world.vm.run_validator(leader_result=forged) is False


# --- leader errors: classified, compared by class ------------------------------------------------------

def setup_validator_view(world, state):
    world.reset()
    if state == "ok":
        world.serve()
        world.model(answer())
    elif state in ("404", "403", "503"):
        world.serve(body="", status=int(state))
    elif state == "nomock":
        pass
    elif state == "too_large":
        world.serve(body=b"x" * 40001)
    elif state == "llm_garbage":
        world.serve()
        world.model("not json")
    elif state == "no_llm":
        world.serve()
    else:
        raise AssertionError(state)


LEADER_ERRORS = [
    # exact-match classes
    ("[EXTERNAL] HTTP 404", "404", True),
    ("[EXTERNAL] HTTP 403", "404", False),
    ("[EXTERNAL] HTTP 404", "403", False),
    ("[EXTERNAL] HTTP 404", "503", False),
    ("[EXTERNAL] HTTP 404", "nomock", False),
    ("[EXTERNAL] HTTP 404", "ok", False),
    ("[EXPECTED] DOCUMENT_TOO_LARGE", "too_large", True),
    ("[EXPECTED] NOT_UTF8", "too_large", False),
    ("[EXPECTED] DOCUMENT_TOO_LARGE", "ok", False),
    # transient: agree when both are transient, wording may differ
    ("[TRANSIENT] source unavailable", "503", True),
    ("[TRANSIENT] fetch failed", "nomock", True),
    ("[TRANSIENT] fetch failed", "503", True),
    ("[TRANSIENT] source unavailable", "404", False),
    ("[TRANSIENT] source unavailable", "ok", False),
    ("[TRANSIENT] source unavailable", "no_llm", False),
    # model failures: always disagree, so the leader is replaced
    ("[LLM_ERROR] model call failed", "ok", False),
    ("[LLM_ERROR] model call failed", "no_llm", False),
    ("[LLM_ERROR] unexpected keys", "llm_garbage", False),
    # unknown or unclassified messages never agree
    ("some plain error", "404", False),
    ("", "404", False),
    ("[EXTERNAL] HTTP 404", "llm_garbage", False),
]


@pytest.mark.parametrize("leader_msg,state,agree", LEADER_ERRORS)
def test_leader_errors_are_compared_by_class(assessed, leader_msg, state, agree):
    setup_validator_view(assessed, state)
    assert assessed.vm.run_validator(leader_error=Exception(leader_msg)) is agree


# --- the closures that cross the VM boundary ---------------------------------------------------------------

def test_closures_are_picklable_and_capture_only_plain_values(assessed):
    cloudpickle = pytest.importorskip("cloudpickle")
    _result, leader_fn, validator_fn = assessed.vm._captured_validators[-1]
    for fn in (leader_fn, validator_fn):
        cloudpickle.dumps(fn)
        for cell in fn.__closure__ or ():
            value = cell.cell_contents
            assert isinstance(value, (str, int, types.FunctionType)), (
                "closure captured %r: storage proxies must not cross the VM boundary" % type(value))
