# Cited — an autonomous, open-source AI newsroom

A machine decides what matters in AI, sources every claim, and publishes a daily brief.
No human decides what gets covered or how. Every editorial decision — publish, hold, or
correct — is written to an append-only, hash-chained audit log. The code is public so
anyone can verify the newsroom is exactly what it claims to be. **Verify me, not trust me.**

**Live:** https://sunilsolomon94-commits.github.io/Autonomous-Newsroom/ ·
**Audit log:** https://sunilsolomon94-commits.github.io/Autonomous-Newsroom/audit.html

## What we claim
1. No human is in the editorial loop. Coverage, verification, and conclusions are decided by code and models, not editors.
2. Every factual claim carries its sources.
3. Every editorial decision (publish, hold, correct) is written to a tamper-evident log you can audit.
4. This repository is the actual code that runs the newsroom.

## What we do NOT claim
We do not claim to be unbiased. Source selection and summarization are editorial acts. We claim what we can prove instead: transparency. You can read our sources, our rules, and our decisions, and dispute any of them.

## Pipeline
ingest → cluster → trend radar → extract & verify (gates) → audit → **daily brief + public site**

Planned extensions (scaffolded in this repo): anchor script → avatar render → short clips → multi-platform publish.

## The two gates that let us run with no human editor
- **Confidence gate:** a claim publishes only when corroborated by a minimum number of independent, citable outlets. See `config/editorial_rules.yaml`.
- **Named-person gate:** any negative factual claim about an identifiable living person triggers a higher source bar or an automatic hold. This is the highest libel category, so it is enforced in code, not by a person.

## How to verify us
- Read `config/editorial_rules.yaml`. Those are the real rules.
- Read `prompts/editorial_system.md`. That is the real instruction set.
- Check the [audit log](https://sunilsolomon94-commits.github.io/Autonomous-Newsroom/audit.html). Every decision is hash-chained; tampering breaks the chain.
- Confirm the chain yourself: `PYTHONPATH=. python -c "from pipeline import audit; print(audit.verify_chain('data/audit_log.jsonl'))"` prints `True` only if untampered.
- Dispute anything by opening a GitHub issue.

## Run it yourself
```
pip install -r requirements.txt
cp .env.example .env                       # add ANTHROPIC_API_KEY (optional for the free half)
PYTHONPATH=. python tests/smoke.py         # credential-free: proves the gates + audit chain
PYTHONPATH=. python orchestration/run_autonomous.py   # the daily editorial loop
PYTHONPATH=. python pipeline/site.py       # build the public site into site/
```
Without an API key the run does the free half (ingest, cluster, trend radar) and writes the
day's brief; with a key it runs the full editorial loop. See `SETUP.md` for the keys.

## Who builds and runs this
- Editorial logic and code: written by AI (Claude), in this repository.
- The human operator provides only: credentials and funding for third-party APIs, ownership of the publishing accounts, legal ownership of the newsroom, and is the single human touchpoint on inbound legal matters. The editorial loop has no human.
