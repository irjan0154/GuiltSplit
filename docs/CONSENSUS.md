# Consensus

This file answers one question: why can't validators silently disagree with each other, and why can't a leader lie? It describes what the code does. Where a statement was only tested in Direct Mode (mocked web, mocked model), it says so.

GuiltSplit uses `gl.vm.run_nondet_unsafe(leader_fn, validator_fn)`: the leader runs `leader_fn`; every validator runs `validator_fn(leaders_res)` and returns `True` (agree) or `False` (disagree). Everything the verdict depends on is decided by code after that call.

## The round

`_round(url, sha, handle)` is the one function both sides run. In order:

1. Download the ruling. A network exception or an HTTP status of 500 or more is `[TRANSIENT]`. Any other status that is not 200 is `[EXTERNAL] HTTP <status>` (a 302 was tested in Direct Mode; whether GenVM follows redirects before the contract sees the status was not checked).
2. More than 40000 bytes is `[EXPECTED] DOCUMENT_TOO_LARGE`.
3. SHA-256 of the bytes differs from the case's hash: the round returns outcome `RETRY` with reason `HASH_MISMATCH`.
4. Bytes that are not UTF-8 are `[EXPECTED] NOT_UTF8`.
5. The handle must appear in the text as a whole token (neighbours are not letters, digits or `_`, and `-` or `.` is not glued to another word character). If not, the round returns outcome `UNDETERMINED`, reason `PLAYER_NOT_IN_RULING`, and **the model is not called**.
6. The model gets the ruling as marked untrusted data and the player handle. It must answer one JSON object with exactly three keys: `finding`, `guilt_quote`, `incident_dates`. A failed model call, wrong keys or wrong types are `[LLM_ERROR]`.
7. Code verifies the answer (below) and returns the round result.

The model is never told the event window, the roster size or the prize rules.

## What a round produces

A dict with six fields:

| Field | Meaning |
|---|---|
| `outcome` | `DECIDED`, `RETRY` or `UNDETERMINED` |
| `reason` | `""` for `DECIDED`; `HASH_MISMATCH` for `RETRY`; `PLAYER_NOT_IN_RULING` for `UNDETERMINED` |
| `finding` | `TEAM_COMPLICIT`, `SOLO_VIOLATION`, `CLEARED` or `UNCLEAR` (empty unless `DECIDED`) |
| `dates` | sorted, de-duplicated `YYYY-MM-DD` incident dates (violations only) |
| `guilt_quote` | the sentence that supports the finding, whitespace-normalised |
| `date_quotes` | one sentence per date, aligned with `dates` |

For a `DECIDED` round the verification in step 7 works like this:

- `UNCLEAR` is stored empty.
- `guilt_quote` must be 12 to 400 characters and appear verbatim in the whitespace-normalised document. If not, the finding becomes `UNCLEAR`.
- `TEAM_COMPLICIT` and `SOLO_VIOLATION` must also name the player: the handle must be a whole token inside `guilt_quote`. A sentence about a witness or another player cannot convict this one.
- For violations, each date must be a real calendar date (years 2000 to 2100), its quote must be real, and the date must occur **exactly once** in its quote.
- Any date that fails turns the **whole** answer into `UNCLEAR`. A date is never silently dropped, because dropping an inconvenient date could turn "mixed dates" into a penalty.
- `CLEARED` keeps no dates.

## How one case becomes a result

`assess` copies what the round needs (URL, hash, handle) into plain local variables before the non-deterministic block, so the two closures capture only strings and functions and never storage objects. A test pickles both closures and checks that; real serialization by GenVM is only exercised in a live run.

After `run_nondet_unsafe` returns, no model is involved:

- `RETRY`: attempt counter +1, status `RETRYABLE`; at three attempts the case becomes `EXHAUSTED` with verdict `UNDETERMINED`.
- `UNDETERMINED`: settled as `ASSESSED` with that reason.
- `DECIDED`: `decide(finding, dates, window_start, window_end, roster)` computes the verdict and the shares. `UNCLEAR` gives `AMBIGUOUS_RULING`; a violation without dates gives `MISSING_INCIDENT_DATE`; dates all outside the window give `OUTSIDE_EVENT_WINDOW`; a mix of inside and outside gives `MIXED_INCIDENT_DATES`; otherwise a forfeit.

## What a validator does

```
validator_fn(leaders_res):
    if the leader failed:        -> compare error classes (see Failure paths)
    run _round yourself
        if your round fails:     -> disagree
    return rounds_agree(leader's result, my result, my normalised document, handle)
```

The validator downloads the document itself and asks its own model. It never trusts the leader's quotes: it checks them against its own copy.

## `rounds_agree`: must agree

The result must be a dict with exactly the six fields and the right types. These four fields must be equal to the validator's own round:

- `outcome`
- `reason`
- `finding`
- `dates`

These fully determine the verdict and the money: `decide` uses only `finding` and `dates` (plus event data that is not part of the round).

## `rounds_agree`: may differ, but must be valid

`guilt_quote` and `date_quotes` may differ in wording from the validator's, but the leader's stored values must pass `_stored_fields_ok` against the **validator's** copy of the document:

- a non-decided round stores no finding, quote or date;
- `UNCLEAR` stores nothing;
- every stored quote is already whitespace-normalised, 12 to 400 characters and present in the document;
- `CLEARED` stores no dates;
- a violation's `guilt_quote` names the player as a whole token;
- dates are valid, strictly increasing (so unique), at most five, one quote each, and each quote contains its date exactly once.

## What is not compared, and why

- **Quote wording.** Two models quote different sentences that support the same finding. Requiring identical quotes would make honest validators disagree. Since `finding` and `dates` are compared and the quotes are verified, a different but real quote cannot change the money.
- **Which sentence the date came from.** Same reason.
- **Wording of `[TRANSIENT]` errors.** "fetch failed" and "source unavailable" are the same kind of problem.
- **The raw model answer.** Only the verified result is compared; the model's key order or extra whitespace do not matter.

## Failure paths

| Leader failed with | A validator agrees when |
|---|---|
| `[EXPECTED] ...` (too large, not UTF-8) | its own round fails with the **exact same** message |
| `[EXTERNAL] HTTP n` | its own round fails with the exact same message (same status) |
| `[TRANSIENT] ...` | its own round also fails with a `[TRANSIENT]` error |
| `[LLM_ERROR] ...` | never: validators disagree so that another leader is tried |
| any other exception or unclassified message | never |

If the leader failed but the validator's own round succeeds, the validator disagrees. If the leader succeeded but the validator's round raises, the validator disagrees. What GenLayer does after a failed agreement (rotating the leader, giving up) is the network's rule and was not observed in this repository.

Errors never turn into penalties: every failed or disagreeing path leaves the case open or `UNDETERMINED`, and `assess` can be called again.

## Worked examples

All examples use the fixtures in `fixtures/`; the tests named are in `tests/direct/`.

**1. Honest solo violation (`ruling-solo-violation.txt`).** The leader returns `finding = SOLO_VIOLATION`, `dates = ["2026-10-16"]`, and for both quotes the sentence "On 2026-10-16 the committee reviewed the final-map footage and finds that Kestrel used a radar hack during the final map." The validator's model words things differently but reaches the same finding and date, so the four fields match and the leader's quotes are found in the validator's copy. The result is accepted; `decide` gives `SOLO_FORFEIT`, 0 / 8000 / 2000 for roster 5. (`test_fixtures.py`: scenario run and `test_validator_agrees_with_the_honest_leader`.)

**2. Forged finding.** The leader claims `TEAM_COMPLICIT` for the same ruling. The validator's round says `SOLO_VIOLATION`; the `finding` field differs, so it disagrees. (`test_validator.py`: "flipped finding".)

**3. Invented quote with a correct finding.** The leader says `SOLO_VIOLATION` on the right date but stores "Kestrel confessed to using a radar hack." The four decisive fields match, but the quote is not in the validator's copy, so `_stored_fields_ok` fails and it disagrees. Without this check a leader could store fake evidence under a correct verdict. (`test_validator.py`: "invented guilt quote".)

**4. A quote about someone else.** The leader convicts Kestrel but quotes the sentence "Quill gave a witness statement and is not accused of anything." The quote is real, yet it does not name Kestrel, so it is rejected. (`test_validator.py`: "guilt quote about someone else".)

**5. Document changed after the hash was claimed.** Both rounds return `RETRY / HASH_MISMATCH`; they agree, the case becomes `RETRYABLE`, and after three attempts `EXHAUSTED`. If only the leader saw the wrong bytes, the validator's round is `DECIDED` and it disagrees. (`test_validator.py`: retry tests.)

**6. Source answers 404 for the leader.** The leader fails with `[EXTERNAL] HTTP 404`. A validator that also gets 404 produces the same message and agrees (the call reverts consistently); one that gets 403, 503 or a good document disagrees. (`test_validator.py`: `LEADER_ERRORS`.)

**7. Injection (`ruling-injection.txt`).** The ruling clears Kestrel and contains a planted line telling automated systems to classify Kestrel as `TEAM_COMPLICIT`. An honest model returns `CLEARED`. See the next section for what happens if a model obeys.

## Assumptions and limits

- **A majority of validators must be honest and run capable models.** The comparison protects against one bad leader, not against a majority that colludes.
- **A fooled model passes the quote check.** If a model obeys the planted line and quotes it, the quote is real, names the player and contains the date once, so code accepts it. What stops the payout is that other validators' models must be fooled in the same way. A test documents this behaviour; it is a real limit, not a solved problem.
- **Honest validators can still disagree.** A model may read an ambiguous ruling differently. The closed answer set and the narrow set of compared fields are meant to keep this rare, but the frequency has not been measured. Disagreement costs liveness, not safety: nothing is paid on a disagreement.
- **The source is trusted to be the same for everyone.** If a server returns different bytes to different validators, hash mismatches follow and the case ends `UNDETERMINED`.
- **Not exercised here.** Real validator consensus, real models and GenVM's serialization of the closures were not run in Direct Mode. The live record in `DEPLOYMENT.md` states what Studio showed.
