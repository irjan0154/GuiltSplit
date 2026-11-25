# Security

This is a threat model for a contract that reads a public document and outputs prize shares. It lists what protects each risk and what remains. "Tested" means a Direct Mode test with mocked web and model; it does not mean the same thing as "observed in Studio".

## What is stored (all public)

Everything on a GenLayer contract is readable by anyone.

| Record | Fields |
|---|---|
| Event | organizer address, start and end date, roster size, ruling base URL |
| Case | event id, case label, proposer address, ruling URL, ruling SHA-256, player handle, status, attempts, verdict, reason, finding, incident dates, the supporting quotes, the three shares, penalty flag |
| Counters | events, cases, assessed, per-verdict counts, withdrawn, exhausted |

No private data is stored. A player handle is a public nickname; do not register real names. The quotes are short excerpts (12 to 400 characters) of a public ruling.

## Trust assumptions

- A majority of validators is honest and runs capable models.
- The ruling host serves the same bytes to everyone who asks for the pinned URL. If it does not, hashes differ and the case ends `UNDETERMINED`.
- The proposer's hash is for the document the proposer means. The contract cannot know the ruling is authentic; it only knows that the bytes at the URL match the claimed hash.
- The escrow or integrator reads `get_event(id)["organizer"]` and trusts only organizers it expects, and pins the case id it pays on.

## Threats and mitigations

| Threat | Protection | Residual risk |
|---|---|---|
| Prompt injection inside the ruling | The ruling is passed as marked untrusted data; the answer is a fixed JSON shape with a closed set of findings; a guilty finding needs a real quote naming the player; dates are checked by code; every validator reruns the round; doubt never produces a penalty | A model that obeys a planted line can quote it as real evidence. A test (`test_injection_that_fools_the_model_is_a_documented_limitation`) shows code accepts it. Independent validators are the only defense |
| Leader forges the result | Validators redo the round and compare `outcome`, `reason`, `finding` and `dates` | Needs a majority of honest validators |
| Leader stores invented evidence under a correct verdict | Validators re-verify the leader's stored quotes against their own copy of the document | Tested only against mocks |
| Conviction by a witness mention | A guilty `guilt_quote` must contain the handle as a whole token; a sentence about someone else is rejected | A sentence that names the player but is not the committee's finding can still be quoted; the model is asked for the committee's decision only |
| Wrong player (substring match) | Whole-token match, case-sensitive: `Kestrel` is not found in `Kestrel-2` or `Kestrelle`; no model call if the handle is absent | Two players whose handles differ only by case are different players |
| Document replaced after the case was proposed | Hash check each round; hash mismatch is `RETRY`, then `EXHAUSTED` after three attempts | A host that serves the right bytes to the proposer and others to validators causes `UNDETERMINED`, not a penalty |
| Inconvenient date dropped or invented | Any date that fails (not a real date, quote not in document, date not exactly once in its quote) makes the whole finding `UNCLEAR` | The model may still pick the wrong dates from a confusing ruling |
| Old incident counted inside the event window | The window test uses only dates with verified quotes; dates outside give `OUTSIDE_EVENT_WINDOW`; a mix gives `MIXED_INCIDENT_DATES` | Whether a date is the proven incident is the model's reading |
| SSRF through the ruling URL | HTTPS only; no userinfo or port; no IP hosts; local suffixes refused; no `?`, `#`, `%`, backslash or `..`; the URL must sit under the event's pinned base | The contract does not see DNS results or redirects. A public host that redirects inward is not caught |
| Fake event or organizer | Not prevented | Anyone may register an event id; the escrow must check `organizer` |
| Spam of cases and events | At most 3 open cases per proposer and 10 events per address | New addresses get new limits |
| Oversized document | 40000 byte limit, checked before hashing | The call reverts and the case stays open until withdrawn |
| Rounding or overflow in money | Integer basis points; shares always sum to 10000 (or all zero); tested for rosters 1, 2, 3, 5, 7 and 10 | None known |
| Assessing a case twice | Only `OPEN` or `RETRYABLE` cases can be assessed | None known |
| Third party withdraws someone's case | `withdraw` accepts only the proposer | None known |

## Misuse to avoid

- Paying out from `get_case` fields without `is_resolved(case_id)`. An `UNDETERMINED` case holds all-zero shares and moves nothing.
- Not checking `organizer`. Any address can register `ironpulse-s4` first.
- Not pinning the case id. Several cases can point at the same ruling and handle.
- Using a mutable link (a branch name) for rulings. Use a link pinned to a commit.
- Treating `NO_FORFEIT` as proof of innocence. It means no penalty under this ruling and this window.
- Using real names as handles.

## Not covered

- Collusion of a validator majority.
- Whether the committee's ruling is correct, authentic or lawful. The contract reads the document; it does not judge the committee.
- Reading quality of the model for languages other than English; the fixtures are English only.
- Availability of the ruling host.
- Sybil addresses working around the per-address limits.
- Real funds: the contract holds none and has no escrow code here.

## Testing

| What | Result |
|---|---|
| Direct Mode tests | 606 passed (`pytest`) |
| Mutation run | 276 mutants, 272 killed, 4 survivors explained in `MUTATION.md` |
| Linter | passed, 11 methods |
| Live run in Studio | see the Live record in `DEPLOYMENT.md` |

## Reporting an issue

Open an issue in this repository's GitHub project. Please include the case id, the ruling URL and hash, and what you expected.
