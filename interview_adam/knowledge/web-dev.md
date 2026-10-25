---
domain: web-dev
---

## Designing a REST API resource model

type: guideline
difficulty: intermediate
tags: rest, api design, http, resources, versioning

A good API starts from nouns, not from screen names. Model the resource (`/orders/{id}`), let the
HTTP verb carry the intent (`GET` read, `POST` create, `PATCH` partial update, `DELETE` remove), and
keep collection and item URLs distinct (`/orders` versus `/orders/{id}`). Status codes are part of the
contract: 200 with a body, 201 with a `Location` after a create, 204 for a delete with nothing to
return, 400 for an unparseable request, 401 when the token is missing, 403 when the caller is
authenticated but not allowed, 404 when the row does not exist or is not theirs, 409 for a
duplicate, 422 when the payload validates structurally but fails semantically, 429 for rate limits.
Idempotency matters on retries: `PUT` and `DELETE` must be safe to replay, and a create that can be
retried needs a client-supplied idempotency key. Version from the beginning only if you expect
breaking changes — a URL prefix (`/v1`) or an `Accept` header — because you cannot add it later
without a migration.

## FastAPI versus Flask for a new service

type: question
difficulty: junior
tags: fastapi, flask, python, web framework

A strong junior answer names the deciding factors instead of declaring a winner. FastAPI gives
request and response validation for free through Pydantic models, automatic OpenAPI documentation,
dependency injection, and async handlers, which fits an API-only backend. Flask is smaller, has a
decade of extensions, and stays completely explicit — you choose validation, serialisation and auth
yourself. Mention that FastAPI's speed advantage is irrelevant when the bottleneck is the database or
the LLM, and that type hints are the real productivity gain because editors and mypy catch mistakes
early. A convincing answer also says when neither is right: a template-rendered site may prefer
Django, and a microservice that only reads a queue may prefer a plain script.

## Pydantic as the validation boundary

type: guideline
difficulty: intermediate
tags: pydantic, validation, schemas, boundaries, type coercion

Validate once, at the boundary, then trust the interior. Model input with Pydantic so length limits,
enums, ranges and required fields are declared in one place and a bad request never reaches business
code. Use `field_validator(mode="before")` to normalise what a real client sends — a score that
arrives as the string `"7/10"` should be coerced, not rejected, while `"great"` should fail with a
message the user can act on. Keep two models: the one you accept (which strips unknown fields) and
the one you return (which controls the response shape and can hide internal columns). Never re-check
the same constraint deeper in the stack; if a service function needs a valid object, it should take
the model as its argument. When the caller is an LLM producing JSON, validation doubles as the repair
signal: the error message tells the model exactly which key is missing.

## N+1 queries and how to fix them

type: question
difficulty: intermediate
tags: sql, orm, indexing, performance, database

An N+1 is one query to fetch a list and then one query per row to fetch a relation — 201 queries for
50 sessions with 3 questions each. Detect it by counting queries, not by timing: enable the ORM query
log or a counter in tests, and assert on the number. Fix it by loading the relation eagerly (`joined`
or `selectin` load), by issuing one `WHERE id IN (...)` batch, or by returning the aggregate from the
original query with a `JOIN` and `GROUP BY`. In SQLite, correlated subqueries in the `SELECT` list are
often the clearest and fast enough for a small app. Indexes help only when the predicate matches: an
index on `interview_qa(session_id)` fixes the per-row lookup, while an index on a column used only in
the projection does nothing. After the fix, re-measure — an unbounded eager load can swap an N+1 for a
Cartesian explosion.

## Authentication with tokens: what to put where

type: guideline
difficulty: intermediate
tags: auth, jwt, sessions, password hashing, security

Store only a salted hash of the password — PBKDF2 at a high iteration count, bcrypt or argon2 — and
never a reversible form. A signed stateless token (JWT) carries an identity claim and an expiry; the
server verifies the signature with a secret and needs no session table, which is why it fits an API
used by a separate frontend. The trade-off is revocation: a signed token stays valid until it expires,
so keep the lifetime short, or store a version counter per user and invalidate by bumping it. Put the
token in an `Authorization: Bearer` header for API calls, not in a query string where it leaks into
logs. Send it over HTTPS only, and treat anything a client claims about its own role as untrusted. In
a FastAPI app, one dependency that resolves the current user should guard every private route, so a
forgotten check becomes visible rather than silent.

## The testing pyramid applied to a small web app

type: guideline
difficulty: intermediate
tags: testing, pytest, unit tests, integration, coverage

Write many fast unit tests on pure functions, fewer integration tests on the boundaries, and very few
end-to-end tests. In practice: the anonymiser, the score coercion and the prompt builder are unit
tested with no server at all; the route contract is tested with an in-process test client and a
dependency override for auth; and the real model is exercised manually once, never in CI, because it
is slow and non-deterministic. Mock only what you do not control — HTTP, the clock, randomness — and
assert on the call you made, not on the internals of the client. A test that must be rewritten every
time implementation changes is testing wiring, not behaviour. Keep one fixture per concept so tests
read as sentences, and make test isolation a rule: a test file that writes into the production
database is a bug in the fixture, not a nuisance.

## Structuring an Angular frontend for a feature module

type: guideline
difficulty: intermediate
tags: angular, standalone components, lazy loading, routing, services

Standalone components removed the need for feature modules: the unit of composition is now a component
plus a route. Register the feature as a lazy `loadComponent` route so its code only downloads when
the user opens it, which keeps the initial bundle small. Put server communication in an injectable
service that returns typed observables; components should not know URLs, and models should be
interfaces mirroring the API contract so a renamed field fails at compile time. Keep state that
belongs to one screen in the component, and cross-screen state in a service with a signal or a
`BehaviorSubject`. Style with the design system the app already uses rather than a second palette; a
feature that looks foreign is read as unfinished even when it works. Guard routes by the auth signal so
an anonymous visitor is redirected before the request ever fails.

## Designing the frontend/backend contract for a new feature

type: question
difficulty: junior
tags: api contract, cors, error handling, openapi, collaboration

Agree the contract before either side writes code. For each endpoint: the method and path, the request
body with its limits, the success shape including the field every screen binds to, and the error shape.
A single error convention — `{"detail": "human message in the user's language"}` with the right status
code — lets the frontend show a message without parsing exceptions, and lets a 503 be retried while a
422 is not. Declare input limits on both sides: the client prevents pointless round-trips, the server
enforces them because the client can be bypassed. Use the generated OpenAPI document to keep the two
in sync, and version or extend additively — a new optional field breaks nobody, a renamed one breaks
everything. Finally, decide the loading and empty states explicitly; most integration bugs are a
frontend expecting an array where the backend returns null.

## SQL injection and its modern relatives

type: guideline
difficulty: intermediate
tags: security, sql injection, parameter binding, xss, prompt injection

Injection happens whenever user text is concatenated into an interpreter. In SQL, use bound parameters
— `WHERE id = ?` with the value passed separately — so the input can only ever be a value, never
syntax. Second-order injection still bites when a stored string is later interpolated, so keep the
discipline at the point of use, not only at the entry point. On the frontend, Angular sanitises
bindings by default; bypassing it with a `bypassSecurityTrust*` call on user content is the XSS
equivalent of string-built SQL. In an LLM feature the same class of bug appears as prompt injection:
the mitigation is structural — clip the length, strip template control tokens, wrap the untrusted text
in a labelled block and instruct the model that content inside the delimiter is data, not orders — and
never let model output execute with privileges.

## Caching, keep-alive and other VRAM-size constraints

type: question
difficulty: senior
tags: performance, gpu, memory, vram, ollama, resource contention

When two models cannot fit in memory at once, treat memory as a shared, schedulable resource. Load
models lazily, release them explicitly when a phase ends (`keep_alive: 0` to evict an Ollama model),
and cap concurrency to one GPU-bound call at a time so two requests cannot each reserve half the card.
A shorter context window reduces key-value cache growth, which is usually the dominant term at
inference time, so ask for the smallest context that fits the prompt. Pin the quantisation level you
tested: a Q4 model behaves differently under load than the FP16 one you benchmarked. Persist the
result rather than the model — an evaluation you already scored should be read from the database, not
recomputed. A senior answer names the measurement that proves it: peak resident memory, tokens per
second, and the queue wait introduced by serialisation.

## Code review: what a reviewer should actually look for

type: guideline
difficulty: intermediate
tags: code review, pull request, quality, maintainability

Read the diff in this order: does it solve the stated problem, can it break an existing caller, does
it fail safely, is it testable, and only then does it match the style. Correctness first — a change
that renames a field, alters a status code, or writes to a shared database is a contract change and
needs the consumers listed. Then failure modes: what happens on a timeout, an empty input, a
permission mismatch, a duplicate submission. Then the tests: do they assert behaviour or just
coverage, and would they fail if the fix were reverted. Comment on the code, never on the person, and
separate blocking issues from preferences so the author knows what must change before merge. A
reviewer who asks "which line proves this works" prevents more regressions than one who fixes naming.

## WebSockets, polling, and when SSE fits better

type: question
difficulty: senior
tags: realtime, websocket, sse, polling, infrastructure

Choose the cheapest transport that satisfies the latency requirement. Polling needs no new
infrastructure and is fine for a two-second budget on a small user base, but it wastes requests and
hides real latency behind the interval. Server-Sent Events is one-way HTTP: the server streams
increments, reconnects with `Last-Event-ID`, and it passes through most proxies without a protocol
upgrade — the right answer for token-by-token model output. WebSockets give a full duplex channel, at
the cost of connection state, heartbeats, and a load balancer that must stick sessions to one worker.
Any of them needs backpressure and an explicit reconnect policy; a client that silently stops
listening looks exactly like a slow server. If instances scale horizontally, the event source has to
be shared (a pub/sub broker), otherwise two workers hold two halves of one conversation.

## Designing a database schema without an ORM or migrations

type: guideline
difficulty: intermediate
tags: sqlite, schema, foreign keys, migrations, concurrency

`CREATE TABLE IF NOT EXISTS` at import is acceptable for a small app, but it means the schema is code:
every added column must be nullable or backfilled by an explicit `ALTER TABLE` guarded by a
`PRAGMA table_info` check, or existing databases fail to start. Use `INTEGER`/`TEXT` honestly, store
UUID hex as text, and keep timestamps in UTC ISO-8601 so ordering works lexicographically. Declare
`FOREIGN KEY ... ON DELETE CASCADE` and turn `PRAGMA foreign_keys = ON` per connection — SQLite
ignores the constraint otherwise, and orphan rows become silent wrong aggregates. Add the index the
query needs, typically the foreign key used in "list my sessions". With one process and a connection
per module, a lock plus short transactions beats WAL when writes are tiny; longer timeouts simply
convert contention into a wait instead of an error. Persist derived numbers, like an average score,
only if you also persist the inputs needed to recompute them.
