# SupportOps AI Demo

Python support investigation demo with local/cloud models, SQLite tools, 50 saved tickets, and explicit human decisions.

## Duplicate-charge review controls

After tools return two equal payments, application code requires a valid order, the policy lookup, and the proposal tool before completing the case. Failed or malformed tool calls do not satisfy prerequisites. OpenAI uses a named tool choice; LM Studio uses a single-tool list with required tool choice. If the model skips the required review, the request fails for human escalation. Final duplicate-charge wording is rendered from verified records and proposal status. Existing approvals are preserved, and no new proposal or approval is invented. These controls apply after payment evidence is retrieved; broader tool-selection coverage remains to be evaluated.

Educational Python 3.10+ demo using the standard library and SQLite. No packages or API key required.

## Run

From this folder, run `python app.py`, then open http://127.0.0.1:8000. Press Ctrl+C to stop.

## Demo scenarios

- ORD-1001: two payments for the same amount and delayed shipping.
- ORD-1002: one payment and a delivered order.
- ORD-9999: an unknown order.

The workflow displays three tool results and creates a proposal requiring human approval. Repeated approval does not create another simulated refund. SQLite preserves status across restarts. Two equal payments indicate a possible duplicate, not conclusive proof.

## Limitations

Simulation uses deterministic rules and does not interpret ticket text. LM Studio and OpenAI modes use a model to interpret tickets and select tools. Policies and data are fictional. Approval only updates proposal status; there is no banking integration. This localhost server has no authentication and is intended for fictional data only.

## Offline tests

Run `python -m unittest discover -s tests -v` from this folder. Tests use isolated databases and mocked model responses, without API calls.

## Architecture

The browser selects a saved ticket. The Python server retrieves its linked order and message. The provider requests tools, application code validates their execution, and SQLite stores results and human decisions. The model can propose a refund but cannot approve it. The interface shows status, latency, tokens, errors, and expandable traces.

## Roadmap

Require policy retrieval before citing it, improve escalation, and compare providers with identical evaluations. An initial local evaluation passed 7/12 cases; regex checks and answers need human review. Add authentication before any deployment beyond localhost.

## Live AI mode

Set OPENAI_API_KEY in the server environment, restart the server, and select Live AI. OPENAI_MODEL optionally overrides gpt-4.1-mini. Credentials stay on the server. Each investigation makes at most six Responses API calls, with 1,200 output tokens per call and a 40-second request timeout. No automatic retries. Fictional ticket data is sent to OpenAI; requests set store=false. API billing applies.

The model selects get_order, get_payments, search_policies, and propose_refund. Tools are scoped to the selected order. Application code validates proposal eligibility and keeps refund approval outside the model's tools. The UI displays actual tool calls, token usage, and latency. Simulation remains available without API credits. Existing proposal approvals persist.

## LM Studio and provider switching

Load a tool-capable model in LM Studio. In Developer, start the local server on port 1234. Select Local AI in the demo and paste the exact model ID shown by LM Studio. The current integration requires /v1/responses support. Set LM_STUDIO_API_KEY only if local server authentication is enabled. Optionally configure LM_STUDIO_MODEL as a server default.

The backend calls http://127.0.0.1:1234/v1/responses with a 120-second timeout per call. OpenAI credentials are never sent to LM Studio. There is no automatic cloud fallback. Select Cloud AI after adding OpenAI credits; no restart is needed to switch providers. Both providers use the same tools, validation, approval flow, and six-call limit. Model quality and valid tool calls must be evaluated separately. Local inference uses your machine's resources but does not consume OpenAI credits.

## Behavioral evaluation (12 tickets)

Run `python evaluate.py --provider lmstudio --model qwen/qwen3-vl-8b` from this folder. Use `--provider openai` to compare the same cases (API billing applies). Each case uses a fresh temporary SQLite database with pending proposals; the demo database is never modified. Reports are saved under evaluation-results as JSON (full answers, tool traces, token usage, latency) and Markdown (pass/fail summary).

Coverage: unknown orders, delivered and delayed shipments, unverified delivery dates, single payments, possible duplicates, and prompt injection against policy, approval, and order scope. Checks measure required successful tools, expected fact patterns, expected escalation patterns, proposal state, database approval state, order scope, and selected unsupported claims. Regex checks are smoke tests, not exhaustive semantic grounding; manually review responses, including negation and unsupported dates. A pass is not a production-readiness claim. API failures are counted as failures.

## Saved tickets and human decisions

The database seeds 50 fictional tickets across ten scenarios (five variations of order IDs and amounts). Missing-order tickets intentionally reference absent orders. Existing records and approvals are preserved. The dropdown selects a ticket and loads its linked order and message together; the backend retrieves them by ticket ID instead of trusting browser fields.

Completed investigations are saved with results, traces, metrics, and case recommendations. Reloading a ticket restores its latest investigation and human decision. Explicit actions approve or reject a pending proposal, confirm escalation, or confirm resolution. Decisions are transactional, idempotent for the same action, reject conflicting actions, and reject decisions on outdated investigations. Escalation is a local recorded decision, not an external notification. Approving a refund does not resolve a shipping delay. Refunds remain simulated.

The Database page includes tickets and human decisions. A rejected proposal stays rejected; it is not silently reopened by another investigation. Failed investigations are shown in the UI but are not persisted in the completed-investigation history. The 50 seeded cases are demo data, not 50 individually evaluated model tests.

## Repository data boundaries

The generated SQLite database, local histories, API keys, caches, and evaluation output are excluded from Git. Seeded data regenerates on first startup. .env.example lists environment variable names only; this app does not load .env files. Use fictional data only.
