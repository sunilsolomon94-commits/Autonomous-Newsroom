# SETUP: the only human steps

AI wrote this system and AI runs it. Three things need a human, because accounts,
payment, and terms of service are bound to a person by the providers, not by an AI.
Do these once and the pipeline is live.

## Security
Never paste live API keys into a chat. Put them only in a local .env file that
Claude Code reads on your machine. .env is gitignored and never published, even
though the rest of the code is open source.

## 1. LLM key  (editorial brain + scripting)
Create a key at console.anthropic.com. Set ANTHROPIC_API_KEY in .env.

## 2. HeyGen  (Mira's face and voice)
Sign up at heygen.com and add billing. Create the avatar "Mira" and a voice.
Copy the avatar_id and voice_id into config/persona.yaml. Set HEYGEN_API_KEY in .env.

## 3. News API  (sourcing)
Create a key at a news API provider (for example newsapi.org). Set NEWS_API_KEY
in .env. GDELT and the RSS tiers need no key.

## Then run
    cp .env.example .env      # fill in the three keys
    PYTHONPATH=. python orchestration/daily_run.py

Claude Code reads the keys from .env and runs ingest -> cluster -> verify -> audit
-> script -> render, producing Mira's first sourced episode. Cowork can drive the
signup browser flows up to the login and payment steps, which only you can complete.
