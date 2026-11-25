# GuiltSplit

An Intelligent Contract that turns an esports anti-cheat committee ruling into a prize split.

An organizer registers a tournament (dates, roster size, and the web folder where its rulings are published). Anyone can then propose a case: a ruling document, its SHA-256 hash and a player handle. GenLayer validators each download the document, ask a model one narrow question about that player, and agree on the answer. Plain code then turns the agreed answer into integer basis-point shares of the prize pool. The contract holds no funds: an escrow reads `is_resolved` and `get_split_bps` and moves the money.

Everything in this repository is fictional: the *IronPulse Esports League*, its rulings and the player *Kestrel* do not exist. The fixtures are test data, not records of real people.

## Release status

| | |
|---|---|
| Network | studio.genlayer.com (StudioNet) |
| Runner pin | `py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6` |
| Contract address | **not deployed yet**: filled in after the live run |
| Live run | **not done yet**: six scenarios planned, one run each |
| Local verification | 606 tests, linter clean, 272 of 276 mutants killed (see [Verification](#verification)) |

This table is filled only with what was observed. The live record, including incidents, goes into [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

## The problem

Prize money in esports is often paid out before an anti-cheat ruling arrives, and clawing it back is a dispute of its own. A contract that could read the committee's published ruling and split the pool accordingly would make the payout follow the decision. The hard part is the reading: a ruling is prose, and money must not move on a guess.

GuiltSplit asks for the smallest decision that moves money: what did the committee decide about this one player, and on which dates did the proven violations happen?

## Why GenLayer

A contract cannot fetch a web page and cannot tell whether a sentence convicts or clears someone. GuiltSplit needs both, and it needs the result to be something an escrow can trust without trusting one server.

### Delete GenLayer: what breaks?

- **Reading the ruling.** Without GenVM web access the contract has no way to see the document. Someone would have to push the text in, and the pusher could pick the version.
- **Understanding the ruling.** "The committee found no evidence that the teammates knew" versus "the committee finds the whole roster complicit" cannot be told apart by string matching. That needs a model.
- **Trusting one reader.** Replace validators with one backend calling one model and the payout depends on that server's availability, its prompt and its honesty. Here every validator re-downloads the document, re-asks the model and re-verifies the leader's quotes before the result is accepted.

### Why this is not a rejected pattern

| Pattern the portal rejects | Answer |
|---|---|
| Basic example or plain data storage | The stored data is a verified verdict with evidence (quotes and dates), and the contract enforces a state machine around it: slots, retries, withdrawal, exhaustion. |
| Thin wrapper around a model call | The model answers a closed question (four values) about one player. Code checks every quote against the document, checks every date, and computes the verdict and the money itself. The model never sees the event window or the roster size. |
| Validators that only check the answer's format | A validator redoes the whole round (download, hash check, model call, verification) and compares the decisive fields. It also re-verifies the leader's stored quotes against its own copy of the document. |
| Copy of a template | The mechanism is its own: attribution of guilt to a named player, window logic on proven incident dates, and fail-closed handling where doubt never produces a penalty. |
| "AI decides X" with no checkable condition | Every positive claim needs a verbatim quote from a hash-pinned document, and the date inside it must be a real calendar date appearing exactly once in its quote. |

## Boundary: who owns what

| Owner | Does |
|---|---|
| Code | Input validation, URL filter and pinned ruling folder, hash check, whole-token player match, quote and date verification, calendar arithmetic, event window, verdict table, basis-point shares, state machine, storage. |
| Model | Reads one ruling and returns `finding` (`TEAM_COMPLICIT`, `SOLO_VIOLATION`, `CLEARED`, `UNCLEAR`), one supporting `guilt_quote`, and the incident dates with a quote for each. Nothing else. |
| Validators | Repeat the round independently and agree only if the decisive fields match and the leader's stored quotes are real. |

## Cases and verdicts

An event fixes the window (at most 60 days), the roster size (1 to 10) and the `ruling_base` URL prefix. A case points at a ruling under that prefix.

| Verdict | Reason | Player / teammates / second place (roster 5) | Penalty |
|---|---|---|---|
| `TEAM_FORFEIT` | `TEAM_COMPLICIT_IN_WINDOW` | 0 / 0 / 10000 | yes |
| `SOLO_FORFEIT` | `SOLO_VIOLATION_IN_WINDOW` | 0 / 8000 / 2000 | yes |
| `NO_FORFEIT` | `OUTSIDE_EVENT_WINDOW` | 2000 / 8000 / 0 | no |
| `NO_FORFEIT` | `PLAYER_CLEARED` | 2000 / 8000 / 0 | no |
| `UNDETERMINED` | `AMBIGUOUS_RULING`, `MIXED_INCIDENT_DATES`, `MISSING_INCIDENT_DATE`, `PLAYER_NOT_IN_RULING`, `EXHAUSTED` | 0 / 0 / 0 | no |

Shares are integer basis points summing to 10000. The player's equal share is `10000 // roster`; the rest belongs to teammates. When the player alone is guilty, their share goes to second place. Doubt never produces a penalty: any unverifiable date turns the whole finding into `UNCLEAR`, and an `UNCLEAR` finding is `UNDETERMINED`.

## Lifecycle

1. `register_event(event_id, start, end, roster_size, ruling_base)`: once per tournament.
2. `propose_case(event_id, case_label, ruling_url, ruling_sha256, player_handle)`: returns a case id. A proposer may hold three open cases at a time.
3. `assess(case_id)`: runs the round. Outcomes:
   - decided or undetermined: the case becomes `ASSESSED` and the proposer's slot is freed;
   - hash mismatch: the case becomes `RETRYABLE` (attempt +1). After three mismatches it becomes `EXHAUSTED` with verdict `UNDETERMINED`;
   - a failed round (`[EXPECTED]`, `[EXTERNAL]`, `[TRANSIENT]` or `[LLM_ERROR]`) reverts the call and the case stays open for another try.
4. `withdraw(case_id)`: only the proposer, only while the case is `OPEN` or `RETRYABLE`.

## Contract surface

| Method | Kind | Purpose |
|---|---|---|
| `register_event` | write | Create an event. |
| `propose_case` | write | Create a case under an event. |
| `assess` | write | Run the consensus round and settle the case. |
| `withdraw` | write | Close an open case. |
| `get_event` | view | Event data, including `organizer`. |
| `get_case` | view | Everything about a case, including stored quotes and dates. |
| `is_resolved` | view | `True` once the case holds a verdict that moves money. |
| `get_split_bps` | view | Player, teammates and second-place shares; all zero until resolved. |
| `is_penalty_applied` | view | `True` for the two forfeit verdicts. |
| `get_stats` | view | Counters per verdict, withdrawals and exhaustions. |
| `open_slots` | view | Free case slots for an address. |

## Consensus

The leader and every validator run the same function: download, check size and hash, require the player handle as a whole token, ask the model, verify quotes and dates. Validators compare the decisive fields and re-verify what the leader stored. The full rule set, failure paths and worked examples are in [`docs/CONSENSUS.md`](docs/CONSENSUS.md).

| | Validators must agree on | May differ, but must be valid |
|---|---|---|
| Round result | `outcome`, `reason`, `finding`, `dates` | Wording of `guilt_quote` and of date quotes: each is only checked against the validator's own copy of the document |
| Failed round | Error class for `[EXPECTED]` and `[EXTERNAL]`, compared exactly | Wording of `[TRANSIENT]` errors: two transient failures agree |
| Model failure | Never agree (a new leader is chosen) | |

## Reading the verdict from another contract

An escrow reads three things for a case id: `is_resolved(case_id)`, then `get_split_bps(case_id)` and, if it needs the reason, `get_case(case_id)`. It must also compare `get_event(event_id)["organizer"]` with the address it expects, because the contract does not authenticate the organizer (see Limitations). A cross-contract call was not built or tested in this repository.

## Verification

| Check | Result | How to reproduce |
|---|---|---|
| Direct Mode tests | 606 passed | `pytest` |
| Linter | passed, 11 methods (7 view, 4 write) | `genvm-lint check contracts/guilt_split.py` |
| Mutation run | 276 mutants, 272 killed, 4 explained survivors | `python scripts/mutate.py` (about 15 minutes) |
| Fixtures and manifest | hashes match files | `python scripts/make_manifest.py --check` |
| Live run in Studio | not done yet | [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) |

The four surviving mutants are redundant guards; the reason for each is written in [`docs/MUTATION.md`](docs/MUTATION.md). Direct Mode uses mocked models and a mocked web: it runs no real consensus, no real model and no closure serialization by GenVM. Only the live run shows those.

## Limitations

1. **The organizer is not authenticated.** Anyone can register an event id. An escrow must check `get_event(id)["organizer"]`.
2. **The ruling folder pins the path, not the author.** On shared hosting (the demo uses raw.githubusercontent.com) the `ruling_base` prefix stops a case from pointing elsewhere, but does not prove who wrote the file. The contract sees bytes at a URL whose hash the proposer claimed.
3. **Injection inside the ruling can still sway the model.** The text is passed as marked untrusted data, answers use a closed set, quotes must be real, and every validator reruns the round. A planted sentence that the model quotes as evidence is a real quote; a test documents this. Independent validators are the defense, not the quote check.
4. **UTF-8 text only.** PDF and HTML rulings are not read.
5. **Equal split.** The pool is divided equally by roster size; the violator's share goes to second place when the player alone is guilty. Real prize rules are richer.
6. **Handles are case-sensitive and whole-token.** `Kestrel-2` is a different handle from `Kestrel`.
7. **Dates come from the model, then are verified.** Up to five incident dates; each must appear exactly once in its quote. A finding without dates is `UNDETERMINED`.
8. **Oversize or non-UTF-8 documents revert the call.** The case stays open until withdrawn.
9. **One live run per scenario.** Stability across repeated runs has not been measured.
10. **No funds.** The contract holds nothing and has no escrow integration.
11. **Runner pin.** The contract pins one GenVM runner hash for studio.genlayer.com. A network upgrade may require a new pin.
12. **Window and roster bounds.** Windows up to 60 days, rosters of 1 to 10.

## Repository layout

```
contracts/guilt_split.py      the contract (pure functions first, contract class below)
docs/CONSENSUS.md             what validators compare and why
docs/SECURITY.md              threat model
docs/DEPLOYMENT.md            deployment steps and the live record
docs/MUTATION.md              mutation run summary
fixtures/                     six fictional rulings, one per live scenario
manifest.json                 fixture hashes and expected results
scripts/                      manifest builder, live command printer, mutation runner
tests/direct/                 Direct Mode tests
pytest.ini  requirements.txt  .gitattributes
```

## Reviewer fast path

1. This README, then [`docs/CONSENSUS.md`](docs/CONSENSUS.md).
2. `contracts/guilt_split.py`: `verify_answer`, `rounds_agree` and `_round`, then `decide`.
3. `tests/direct/test_validator.py`: forged leader results and error classes.
4. [`docs/MUTATION.md`](docs/MUTATION.md) and [`docs/SECURITY.md`](docs/SECURITY.md).
5. [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md): the live record, including what the run does not show.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
pytest
genvm-lint check contracts/guilt_split.py
python scripts/make_manifest.py --check
```

The contract pins its runner on the first line. Re-verify the pin by pasting the header into Studio before deploying.
