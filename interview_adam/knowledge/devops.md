---
domain: devops
---

## Writing a small, safe Docker image

type: guideline
difficulty: intermediate
tags: docker, container image, layers, multi-stage, security

Keep the build reproducible and the attack surface small. Pin the base image to a digest or at least a
major version, install build dependencies in a first stage and copy only the artefacts into a slim
runtime stage. Order layers by churn — dependency manifest first, source last — so the cache survives a
code change. Run as a non-root user, set `read-only` filesystem where possible, drop Linux capabilities,
and never bake secrets into an image layer; use a mounted secret or an environment injected at runtime.
Add a `HEALTHCHECK` so the orchestrator can distinguish a started process from a serving one. Multi-stage
builds for Python usually mean installing into a virtual environment in the builder and copying that
directory, which avoids carrying pip and compilers into production. Finally, a `.dockerignore` that
excludes `.venv`, `node_modules`, `.git` and local data keeps the context small and the build honest.

## CI/CD: what a good pipeline actually guarantees

type: question
difficulty: intermediate
tags: ci, cd, github actions, pipeline, deployment, testing

A pipeline's job is to make the merge safe and the rollback boring. Cheap gates first — formatting,
lint, type check — then unit tests, then the build, then integration tests against real dependencies,
then deploy to a staging environment that exercises the same artefact that will reach production.
Promote one immutable artefact through the environments rather than rebuilding per environment,
otherwise what you tested is not what you shipped. Deployments must be repeatable and reversible:
database migrations forward-compatible, feature flags for anything risky, and an automatic revert when
the health check fails. Cache dependencies but never cache something that changes correctness. Make
failures loud and fast, with logs at the top of the output — a pipeline that takes forty minutes to
say "no" gets ignored.

## Docker Compose for local development of a full stack

type: guideline
difficulty: junior
tags: docker compose, local development, services, volumes, env

Compose describes services, networks and volumes so a new developer runs one command instead of
following a wiki. Each process gets its own service: API, database, frontend dev server, maybe the
model server. Bind-mount the source for hot reload but use a named volume for installed dependencies
so the host's platform-specific build is not copied into the container. Publish only the ports a human
needs; services reach each other over the internal network by service name as DNS. Put secrets in an
`.env` file that is git-ignored, and provide `.env.example` so the required keys are discoverable.
`depends_on` orders startup, it does not wait for readiness — the practical fix is a health check plus
retry-on-connect in the client, not a longer sleep. Keep the production image and the compose file
pointing at the same build so "works on my machine" is a claim you can defend.

## Kubernetes objects that matter for a small service

type: question
difficulty: senior
tags: kubernetes, deployment, service, ingress, configmap, hpa

A `Deployment` runs a replicated, versioned `Pod` template behind a rolling update with readiness and
liveness probes; the `Service` gives those pods a stable cluster-internal name, and an `Ingress` or
`LoadBalancer` exposes it outside. Configuration arrives through `ConfigMap` and secrets, mounted as
files or environment, and is immutable per version — changing one triggers a rollout. Scaling is
horizontal: a `HorizontalPodAutoscaler` on CPU or a custom metric adds replicas; vertical scaling
changes requests and limits, and requests, not limits, drive scheduling. Set both requests and limits,
or the node overcommits and the quality of service decides who gets OOM-killed under pressure.
Persistent data does not belong in a Deployment: use a `StatefulSet` with a volume, or better, a managed
database. A senior answer mentions probe design, because a wrong readiness gate turns one slow start
into a cascading outage.

## Infrastructure as code with Terraform

type: guideline
difficulty: senior
tags: terraform, iac, state, modules, drift

Declare infrastructure so the plan is reviewable before the apply. Keep state remote and locked — a
state file in a git repo is a secret store and a merge hazard, and a lost state file means recreating
production. Write a plan review into the workflow: the diff is the safety mechanism, which is why
`destroy` previews and replacement notices must be read, not skipped. Split by blast radius: separate
state for network, data and application layers so an experiment cannot delete the database. Use modules
for repeated shapes, with variables validated and outputs documented, but do not abstract a resource
that will only ever have one instance. Drift detection — `plan` on a schedule — tells you who changed
the console. Tag every resource with owner, environment and cost centre; the tag is what makes a
billing report actionable later.

## Observability: logs, metrics and traces, and which to reach for

type: question
difficulty: intermediate
tags: observability, metrics, logging, tracing, prometheus, alerting

Metrics answer "is it fine" cheaply and continuously: request rate, error rate, duration percentiles,
saturation, plus the domain counters that precede a symptom, such as queue depth or model load time.
Alert on the symptom the user feels, not on the cause, so you are not woken by every noisy dependency.
Logs answer "what exactly happened" and are too expensive to alert on, so keep them structured,
sampled, correlated by request id, and free of personal data. Traces answer "where did the time go"
across services, and are worth the instrumentation only once a request crosses more than one boundary.
The three are one system when they share identifiers: a latency alert on a metric should deep-link to a
trace, whose slow span points at the log lines. Cardinality is the failure mode to respect — a label
per user id or per URL path explodes the metrics backend; use a bounded set of labels and put the
rest in logs.

## SLOs, error budgets and how they change behaviour

type: question
difficulty: senior
tags: slo, sli, error budget, reliability, on call, release management

An SLO is a target on an SLI over a window: 99.5 per cent of requests served under 300 ms over 30 days.
The complement, the error budget, is the shared currency that decides shipping pace: while budget
remains, release fast; when it is exhausted, feature work stops and reliability work starts. That is
what makes it effective — it converts an argument between product and platform into an arithmetic
constraint both sides agreed to in advance. Choose the SLI the user actually experiences, not the
easiest counter to scrape; a service that is up but returning errors is not available. Measure over a
window long enough that a single bad hour does not burn everything, and define exclusions for planned
maintenance so the number stays credible. A senior answer admits the political part: an SLO nobody
enforces is a dashboard, not a policy.

## Git branching and the size of a pull request

type: guideline
difficulty: junior
tags: git, branching, pull request, code review, merge strategy

Short-lived branches on small, reviewable changes. Trunk-based or `feature/` branches cut from an
up-to-date main, rebased or merged often, so divergence stays cheap; a branch that lives three weeks
becomes its own integration project. One pull request should be readable in fifteen minutes and revert
as a unit — if it fixes a bug, adds a feature and reformats files, split it, and put the mechanical
formatting in its own commit or its own request. Write the message for the future reader of `git log`:
what and why, with the symptom and the chosen approach, not a list of touched files. Prefer merges that
keep history legible over the convenience of a squash when the branch contains distinct decisions.
Never rewrite a shared branch after others have built on it, and never commit generated artefacts,
virtual environments or local data.

## Secrets management in an application

type: guideline
difficulty: intermediate
tags: secrets, env vars, security, key rotation, vault

Secrets live in the environment or a secret manager, never in source, never in the image, and never in
a log line. Provide a `.env.example` with empty placeholders so the required keys are discoverable
without disclosing values, and git-ignore `.env`. If a key is committed, revoke it immediately —
removing it from the file does not remove it from history, and rotation is the only real fix. Scope
keys narrowly: a token that can only write to one bucket damages less than an admin credential, and
short-lived credentials beat long-lived ones whenever the platform supports them. Inject at runtime in
the orchestrator rather than baking into configuration files. Add a secret-scanning gate to CI so the
mistake is caught before the push. Treat any value a model could echo back as a secret too, because a
prompt can leak what the process holds.

## Blue-green, canary and rolling deployments

type: question
difficulty: senior
tags: deployment strategy, canary, blue green, rollback, database migration

All three answer the same question — how do you limit the blast radius of a bad version — with
different machinery. Rolling updates replace replicas gradually and need no duplicate capacity, but a
subtle bug still reaches a share of traffic before the health check notices. Blue-green runs two full
environments and flips the router, giving an instant rollback to the previous stack at the cost of
double capacity during the window. Canary sends a small, measured slice — one per cent, then five,
then twenty-five — and gates each step on metrics, which is the only strategy that gives you evidence
rather than a binary pass. The hard part is shared state: schema changes must be backward-compatible
across versions, add column then backfill then switch reads, and never drop a column in the same
release that stops using it. Decide the abort criteria before starting, and rehearse the rollback.

## Designing for failure: timeouts, retries, idempotency

type: guideline
difficulty: senior
tags: reliability, retries, timeout, circuit breaker, backpressure, resilience

Assume every remote call fails, slowly. Give every outbound call an explicit connect and read timeout,
because the default is usually infinite and one hung dependency will consume the whole worker pool.
Retry only idempotent operations, with exponential backoff plus jitter, a small attempt budget, and a
deadline so retries do not outlive the client's patience. Cap total concurrency where the resource is
scarce — a GPU, a database pool — and return a fast 429 or 503 with `Retry-After` rather than queueing
until everything times out together. A circuit breaker stops calling a dependency that is already down
and lets it recover, and should trip on the class of error that means "unavailable", not on a
validation failure that will fail identically. Make duplicates harmless with idempotency keys. Then
test it: kill the dependency in staging and watch the shape of the failure.

## Incident response and the postmortem that changes something

type: question
difficulty: senior
tags: incident, postmortem, blameless, on call, runbook

Detection first: the alert that woke someone should be tied to a runbook that says what to look at and
what mitigation exists — rollback, feature flag off, scale out, degrade gracefully. Declare roles
early, one person coordinates and one investigates, because an unstructured channel produces three
people trying the same restart. Communicate on a cadence even when the update is "no change"; silence
escalates pressure from stakeholders faster than the outage does. Mitigate before you diagnose fully —
restoring service is the objective, root cause can follow offline. Then write a blameless postmortem:
timeline with timestamps, contributing factors rather than a single cause, and each action item with an
owner and a date. The test of a postmortem is whether the same incident can recur; a system where one
person's mistake stops it was not resilient, and that is the finding worth recording.

## Scaling state: from one process to many

type: question
difficulty: senior
tags: scaling, statelessness, database, cache, load balancing, architecture

The first step is removing in-process state so any worker can serve any request: sessions move to a
shared store or a signed token, uploads to object storage, caches to an external service. Then measure
before splitting anything: read/write ratio, slow queries, lock contention, and where the queue forms.
Vertical scaling buys time cheaply; horizontal scaling of a stateless API is routine, while a
GPU-bound model server scales on memory, not CPU, and needs a queue in front of it. Add read replicas
for analytical reads, and index or rewrite the query before replicating — most "we need to scale"
problems are one bad query. Microservices are an organisational answer to a coordination problem, not
a performance one; they cost you deployment maturity, distributed tracing and a network you can no
longer reason about. Prefer the boring change that removes a bottleneck over the one that adds a
platform.
