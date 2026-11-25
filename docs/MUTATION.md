# Mutation run

Mutants: 276. Killed: 272. Survived: 4.

| Survivor | Why it cannot change behaviour |
|---|---|
| `event-unknown-type` | Defensive guard for the real GenVM, where a TreeMap lookup with a key of the wrong type may raise instead of returning 'absent'. In Direct Mode the map is a plain dict, so the mutant behaves the same; only the live run can tell them apart. |
| `resolved-status` | Redundant by construction: `verdict` is only written by `_settle`, which also sets status ASSESSED (or EXHAUSTED with verdict UNDETERMINED). No reachable state has a resolved verdict with another status. |
| `split-zeros` | Redundant by construction: every case that is not resolved has all three shares at 0 (unsettled cases keep the initial zeros, UNDETERMINED decisions are 0/0/0). The guard only documents the rule. |
| `penalty-resolved` | Redundant by construction: `penalty` is True only for TEAM_FORFEIT and SOLO_FORFEIT, which are resolved verdicts, so `case.penalty` alone gives the same answer in every reachable state. |
