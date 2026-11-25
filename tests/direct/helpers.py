"""Shared constants and the World helper for the flow and validator tests."""

import contextlib
import hashlib
import json
import re

EVENT = "ironpulse-s4"
BASE = "https://ironpulse.example/rulings/"
URL = BASE + "ruling-solo.txt"
START, END = "2026-10-10", "2026-10-18"
HANDLE = "Kestrel"

DATE_Q = "The committee reviewed the match of 2026-10-16 and finds that"
OLD_Q = "The committee also confirmed the earlier incident of 2026-08-04 at the previous tournament."
GUILT_Q = "Kestrel used a radar hack during the final map."
NEUTRAL_Q = "Teammates were not involved in the violation."
WITNESS_Q = "Quill gave a witness statement and is not accused of anything."

DOC = "\n".join([
    "IronPulse Esports League (fictional league)",
    "Anti-Cheat Committee Ruling",
    "The committee reviewed the match of 2026-10-16 and finds that",
    "Kestrel used a radar hack during the final map.",
    "Teammates were not involved in the violation.",
    "The committee also confirmed the earlier incident of 2026-08-04 at the previous tournament.",
    "Quill gave a witness statement and is not accused of anything.",
]) + "\n"


def sha(data) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def answer(finding="SOLO_VIOLATION", guilt=GUILT_Q, dates=(("2026-10-16", DATE_Q),)):
    return {
        "finding": finding,
        "guilt_quote": guilt,
        "incident_dates": [{"date": d, "quote": q} for d, q in dates],
    }


class World:
    """Thin wrapper around a deployed contract plus the Direct Mode cheatcodes."""

    def __init__(self, vm, contract, module, alice, bob, charlie):
        self.vm, self.c, self.m = vm, contract, module
        self.alice, self.bob, self.charlie = alice, bob, charlie

    def addr(self, raw):
        # Direct Mode accounts are raw bytes; views that take an Address need the wrapper
        return self.m.Address(raw)

    def _as(self, sender):
        return contextlib.nullcontext() if sender is None else self.vm.prank(sender)

    def register(self, event_id=EVENT, start=START, end=END, roster=5, base=BASE, sender=None):
        with self._as(sender):
            return self.c.register_event(event_id, start, end, roster, base)

    def propose(self, event_id=EVENT, label="case-1", url=URL, doc=DOC, handle=HANDLE,
                sender=None, digest=None):
        with self._as(sender):
            return self.c.propose_case(event_id, label, url, digest or sha(doc), handle)

    def assess(self, case_id, sender=None):
        with self._as(sender):
            return self.c.assess(case_id)

    def withdraw(self, case_id, sender=None):
        with self._as(sender):
            return self.c.withdraw(case_id)

    def serve(self, body=DOC, status=200, url=URL):
        self.vm.mock_web(re.escape(url) + "$", {"status": status, "body": body})

    def model(self, value):
        text = value if isinstance(value, str) else json.dumps(value)
        self.vm.mock_llm("UNTRUSTED DATA", text)

    def reset(self):
        self.vm.clear_mocks()

    def case(self, case_id):
        return self.c.get_case(case_id)

    def slots(self, who=None):
        return self.c.open_slots(self.addr(who or self.alice))

    def stats(self):
        return self.c.get_stats()

    def last_leader_result(self):
        return self.vm._captured_validators[-1][0]
