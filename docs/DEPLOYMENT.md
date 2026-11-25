# Deployment

How to deploy GuiltSplit in GenLayer Studio and run the six live scenarios, followed by the record of the real run.

## Prerequisites

- Python 3 (all checks here were run on Python 3.13), with `pip install -r requirements.txt`.
- A GitHub repository with this project, so the fixtures have public raw links.
- Access to https://studio.genlayer.com (StudioNet has no fees; a zero balance is normal).
- The runner pin on the first line of `contracts/guilt_split.py`:
  `# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }`

## 1. Check the source locally

```bash
pytest
genvm-lint check contracts/guilt_split.py
python scripts/make_manifest.py --check
```

Expected: all tests pass, the linter passes with 11 methods, `manifest.json is up to date`. The full mutation run is optional (`python scripts/mutate.py`, about 15 minutes).

## 2. Publish the fixtures at stable raw links

1. Upload the repository to GitHub. Keep `.gitattributes` so `fixtures/*.txt` keep LF line endings; CRLF would change their hashes.
2. Note the commit SHA that contains the fixtures. Use that SHA, not a branch name: a branch link changes when the file changes.
3. Build the live manifest:

   ```bash
   python scripts/make_manifest.py --base-url https://raw.githubusercontent.com/<user>/<repo>/<commit-sha>/fixtures/
   ```

4. Check that each published file has the hash in the manifest:

   ```bash
   for f in team-complicit solo-violation outside-window cleared ambiguous injection; do
     curl -sL "https://raw.githubusercontent.com/<user>/<repo>/<commit-sha>/fixtures/ruling-$f.txt" | sha256sum
   done
   ```

   (On macOS use `shasum -a 256` instead of `sha256sum`.) Compare with the `sha256` values in `manifest.live.json`. A difference means the file was altered on upload.

## 3. Deploy in Studio

1. Open Studio, create a contract file and paste `contracts/guilt_split.py`.
2. Check that the first line is the pinned runner. If Studio rejects the pin, stop and record it: the network may have been upgraded.
3. Deploy with no constructor arguments. Note the contract address and the transaction hash.
4. Open the transaction details and check that the GenVM result is `SUCCESS`. Statuses `ACCEPTED` or `FINALIZED` do not mean the code ran.

## 4. Run the six scenarios, one at a time

```bash
python scripts/print_live_commands.py        # event + all scenarios
python scripts/print_live_commands.py 3      # only scenario 3
```

1. Call `register_event` once, from the account that deployed, with the printed values.
2. For each scenario: `propose_case` with the printed values, note the returned case id, then `assess(case_id)`.
3. Wait for the transaction. Check that the GenVM result is `SUCCESS`.
4. Read `get_case(id)`, `get_split_bps(id)`, `is_resolved(id)` and `get_stats()`.
5. Copy the result into the Live record below immediately, before the next scenario.

Do not click buttons in series: StudioNet limits requests per IP and unconfirmed transactions per sender.

| # | Scenario | Expected verdict / reason | Shares (player / teammates / second) |
|---|---|---|---|
| 1 | team-complicit | `TEAM_FORFEIT` / `TEAM_COMPLICIT_IN_WINDOW` | 0 / 0 / 10000 |
| 2 | solo-violation | `SOLO_FORFEIT` / `SOLO_VIOLATION_IN_WINDOW` | 0 / 8000 / 2000 |
| 3 | outside-window | `NO_FORFEIT` / `OUTSIDE_EVENT_WINDOW` | 2000 / 8000 / 0 |
| 4 | cleared | `NO_FORFEIT` / `PLAYER_CLEARED` | 2000 / 8000 / 0 |
| 5 | ambiguous | `UNDETERMINED` / `AMBIGUOUS_RULING` | 0 / 0 / 0 |
| 6 | injection | `NO_FORFEIT` / `PLAYER_CLEARED` | 2000 / 8000 / 0 |

## 5. Record the run

Fill in the Live record. Record only what was observed, record failures too, and call one run one run.

## Troubleshooting

| Symptom | Likely cause and action |
|---|---|
| Studio rejects the runner pin | The network may have changed runners. Do not edit the pin by guess; record the message |
| Transaction `ACCEPTED` or `FINALIZED` but nothing changed | Open the transaction and read the GenVM result; it must be `SUCCESS` |
| `assess` fails with `[EXTERNAL] HTTP 404` | The raw link is wrong or not yet published; check the manifest URL |
| `assess` fails with `[TRANSIENT]` | The source or network was unavailable; call `assess` again |
| `assess` fails with `[LLM_ERROR]` | The model call failed or returned a wrong shape; call `assess` again and record it as an incident |
| Case becomes `RETRYABLE` with `HASH_MISMATCH` | The file served differs from the manifest hash: line endings, an edited file, or a wrong URL |
| `[EXPECTED] URL_OUTSIDE_BASE` | `ruling_url` does not start with the event's `ruling_base` |
| `[EXPECTED] NOT_ASSESSABLE` | The case is already assessed, exhausted or withdrawn; propose a new case |
| A read shows `OPEN` after a finished assess | Stale read; call it again |
| Values vanished after a page refresh | Studio does not keep entered values; keep them in a separate file (`print_live_commands.py` regenerates them) |
| `withdraw` sent instead of `assess` | The write panels each have their own Send button; expand only the panel you need and check the method name in its header |
| `get_stats` has no input field | It takes no arguments |
| `open_slots` fails | It needs a full `0x` address of 40 hex characters |

## Live record

**Status: not run yet.** Nothing below has been observed. Every placeholder is replaced with a real observation after the run; until then this section claims nothing.

### Deployment

| Item | Value |
|---|---|
| Network and mode | pending |
| Contract address and explorer link | pending |
| Deploy transaction and GenVM result | pending |
| Deploying account | pending |
| SHA-256 of `contracts/guilt_split.py` | pending |
| Commit containing the fixtures | pending |
| Not compared | pending (for example, a byte-for-byte comparison with the explorer's Code tab) |

### Scenarios

| # | Scenario | Case id | Expected | Observed GenVM result | Observed status / verdict / reason | Observed shares |
|---|---|---|---|---|---|---|
| 1 | team-complicit | pending | `TEAM_FORFEIT` | pending | pending | pending |
| 2 | solo-violation | pending | `SOLO_FORFEIT` | pending | pending | pending |
| 3 | outside-window | pending | `NO_FORFEIT` / `OUTSIDE_EVENT_WINDOW` | pending | pending | pending |
| 4 | cleared | pending | `NO_FORFEIT` / `PLAYER_CLEARED` | pending | pending | pending |
| 5 | ambiguous | pending | `UNDETERMINED` | pending | pending | pending |
| 6 | injection | pending | `NO_FORFEIT` / `PLAYER_CLEARED` | pending | pending | pending |

### Other reads after the run

`get_stats`: pending.

### Incidents during the run

pending. Every mistake, stale read, failed call or surprise goes here, with its effect on case ids.

### What this run does and does not show

pending. To be written from the observations. It will say at least that each scenario was run once, that individual validator votes were not inspected unless they were, and that stability across repeats was not measured.
