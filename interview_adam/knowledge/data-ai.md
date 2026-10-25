---
domain: data-ai
---

## Overfitting: how to recognise it and what actually reduces it

type: question
difficulty: intermediate
tags: overfitting, regularization, generalization, cross-validation, variance

Overfitting shows as a wide gap between training and held-out performance while training loss keeps
falling. Before reaching for regularization, check the boring explanations: the model may be seeing
leakage from the target, the split may not be representative, or the metric may be noisy on a small
validation set. Real mitigations, in the order worth trying: more relevant training data, stronger
regularization (L2, dropout, weight decay), a simpler model or fewer features, early stopping against
a real validation curve, and ensembling. Cross-validation with repeated folds tells you whether the
gap is stable or an artefact of one split. A senior answer distinguishes variance from bias — if
training error is already high, regularization makes things worse — and reports both numbers instead
of only the good one.

## Data leakage and split design

type: guideline
difficulty: intermediate
tags: data leakage, train test split, time series, preprocessing, evaluation

Leakage is any information from the future or from the label that reaches the features. The three
common sources: fitting a scaler, imputer or encoder on the whole dataset before splitting, using a
row identifier or a derived field that encodes the target, and splitting a time series randomly so the
model trains on events it is asked to predict. The fix is structural — build a `Pipeline` so every
transformation is fit inside the training fold only — and for temporal data use a time-based split or
`TimeSeriesSplit`. A leakage bug usually looks like an unexpectedly strong model, so an implausible
score is a reason to audit the features before celebrating. Also check group leakage: multiple rows
from the same user must live in one split, or the model simply memorises the person.

## Choosing a metric that matches the decision

type: question
difficulty: intermediate
tags: metrics, precision, recall, f1, roc auc, evaluation

Start from the cost of each error, not from the menu of metrics. When a false negative is expensive —
missing a fraud case, a tumour, a churner worth saving — optimise recall at a precision you can
service, and report the confusion matrix at the operating threshold you would actually use. When human
review capacity is the constraint, precision at k or a fixed recall budget is the honest metric.
Accuracy misleads on imbalanced data: 99 per cent accuracy is a model that predicts the majority class.
ROC-AUC is threshold-free and compares models, but with severe imbalance the precision-recall curve
and PR-AUC are more informative. Always state the baseline you beat — predicting the majority class or
a one-feature rule — because a metric without a baseline proves nothing.

## Handling severe class imbalance

type: question
difficulty: intermediate
tags: imbalanced data, resampling, class weights, sampling, calibration

Rebalancing changes the prior, not the information. Try, in order: a proper metric, class weights in
the loss (cheap and keeps the real distribution), thresholding the probability to the operating point,
then resampling (oversample the minority with SMOTE, or undersample the majority) if the model still
cannot separate. Never resample before splitting: synthesising points inside the training fold only,
otherwise duplicates leak into validation and the score is fiction. Resampling distorts predicted
probabilities, so recalibrate if downstream systems consume probabilities rather than labels. If the
minority class is genuinely tiny and heterogeneous, the useful move is often to redefine the label —
a narrower, better-measured target beats a noisy rare one — or to collect more of that class.

## Feature engineering versus model complexity

type: guideline
difficulty: senior
tags: features, gradient boosting, linear baseline, pipelines, modeling

A simple model with a good feature usually beats a complex model with raw fields. Encode domain
knowledge explicitly: ratios, rates per unit time, rolling windows for temporal data, interactions the
business already describes, text length or category flags. Then prove the complexity pays: fit a
logistic regression or a decision stump on the engineered matrix as a baseline and report the delta.
Gradient-boosted trees handle mixed tabular types and monotonic transforms well, so scaling and one-hot
encoding buy little there — but they still need a sane categorical treatment and a split that respects
time. Beware features that are proxies for the label's date, for a specific system, or for a decision
already taken, because they win offline and fail after deployment. Track feature importance with
permutation importance, not only split counts, and drop features you cannot defend to a stakeholder.

## Building a reliable data pipeline

type: guideline
difficulty: intermediate
tags: etl, data quality, pipelines, idempotence, orchestration

A pipeline is reliable when re-running it is safe and bad input is loud. Make every step idempotent —
overwrite the partition it produced rather than appending — so a retry does not duplicate rows. Pin
the schema at the source and fail on drift instead of silently coercing types. Validate at boundaries
with explicit expectations: row count within a band, no nulls in a key, referential integrity, values
inside a declared range; a check that runs after load is a report, one that runs before is a guard.
Partition by event time, not arrival time, and keep late arrivals correctable. Record lineage: which
run, which source version, which code commit. Backfills should be expressible as "reprocess this date
range" without hand-editing. Finally, monitor freshness and volume, because most pipeline incidents
are silent missing data rather than a stack trace.

## Embeddings, tokenisation and why they matter

type: question
difficulty: intermediate
tags: embeddings, tokenization, vector search, nlp, semantic similarity

A model reads subword tokens, not words, so a rare word becomes fragments and long documents become
many tokens — which is why context limits and cost are measured in tokens. An embedding maps text to a
fixed-length vector such that similar meanings sit close together; similarity is usually cosine or dot
product on unit-normed vectors, which is why normalising before the comparison matters. Small models
like MiniLM encode topic well but are weak at long-range structure and numbers, so chunking strategy
and retrieved context length drive answer quality more than the choice of embedding model. Embeddings
are not a hash: two runs of the same model agree, but different models produce incomparable spaces —
never mix the vector space of the index with that of the query. Useful practical checks: token count
per chunk, a nearest-neighbour spot check on five queries, and recall of the retrieval step before
judging the generator.

## RAG versus fine-tuning: what to choose and when

type: question
difficulty: senior
tags: rag, fine-tuning, lora, llm, retrieval, knowledge grounding

Retrieval fixes knowledge; fine-tuning fixes behaviour. Use RAG when the facts change, come from a
corpus you can index, or must be cited — it keeps sources fresh, is auditable, and needs no
retraining. Use fine-tuning when the model must learn a stable format, tone, or domain style, or when
latency forbids a long prompt; a LoRA adapter is cheap in memory and reversible, but it cannot teach
facts reliably and it can hallucinate confidently. In practice combine them: an adapter that makes the
model follow your output contract, plus retrieval that supplies the current content. Guard the retrieval
path with a quality check — if nothing clears the similarity threshold, say you do not know instead of
answering from a weak match. Cite the retrieved chunk identifiers in logs so an evaluation can trace
which document produced which sentence.

## LLM output validation and repair loops

type: guideline
difficulty: intermediate
tags: llm, json, pydantic, validation, repair, structured output

Treat model output as untrusted input from a slow, unreliable network. Ask for a machine-readable
format, and when the serving stack can constrain decoding — a JSON schema on the request — use it
rather than pleading in the prompt. Validate with a real schema: reject unknown keys, coerce the
formats clients genuinely send, clamp numeric ranges, and require the fields the UI binds to. On a
validation failure, one repair attempt with the exact rejection reason is enough; more attempts raise
cost and usually converge to the same mistake. Keep a deterministic fallback for every feature so the
user always gets an answer with a `degraded` marker rather than a 500, and log which path served the
request. Temperature belongs to the task: generation near 0.6, extraction or scoring near 0.1, because
a scoring model that is creative produces numbers nobody can reproduce.

## Model deployment, drift and monitoring

type: question
difficulty: senior
tags: mlops, monitoring, drift, deployment, incident response

A model at rest is not a model in production: inputs shift, upstream schemas change, and label feedback
arrives late. Ship the artefact with its feature definition and a version id, serve behind a contract
test that pins the output schema, and log features plus prediction — without logged labels you cannot
reconstruct performance. Monitor three layers: data (distribution and null rates per feature),
prediction (score histogram, calibration, share above threshold), and business (acceptance rate,
downstream outcome). Detect drift with population stability index on features and alert on the
business metric, which is the one that actually degrades. Keep a champion/challenger or shadow mode so
a new model scores silently before it decides. Define the rollback in advance: an old version still
deployed, feature snapshots available, and a retraining trigger with an owner.

## Running a trustworthy experiment

type: question
difficulty: senior
tags: experimentation, ab testing, statistics, power, causal inference

Decide the metric and the stopping rule before you start. Choose one primary metric tied to the
decision, a couple of guardrails, and compute the sample size from the smallest effect worth acting
on — an underpowered test produces noise that reads as a win. Randomise at the unit that matches the
interference structure: users, not sessions, when behaviour carries over. Check assignment with an A/A
run and a covariate balance table. Peeking invalidates the p-value, so fix the horizon or use a
sequential method designed for early stopping. Analyse by assigned group, not by completed group —
that is what keeps it causal. Report the effect size with its interval, and record the negative results;
a dashboard of past experiments prevents the same test being re-run every quarter.

## Pandas and SQL: what each is for

type: guideline
difficulty: junior
tags: pandas, sql, analytics, data wrangling, performance

Push the filtering and the joins to the database, then do the exploration locally. SQL is set-based,
runs where the data lives, and is the only sane way to shrink a table of hundreds of millions of rows;
pandas is for the residual work — reshaping, window arithmetic, plotting, quick what-ifs — where
interactivity beats re-running a query. The classic junior mistake is loading a whole table to drop 90
per cent of it: read only the columns and rows needed, and use `GROUP BY` server-side. Watch for
silent type object columns, which make numeric comparisons useless, and for chained assignment, which
silently fails to update. When a notebook step stops being reproducible, that is the signal to move it
into a versioned SQL view or a function with a test.

## Statistics a data interviewer expects cold

type: question
difficulty: junior
tags: statistics, confidence interval, correlation, p-value, bayes

Be able to state these without notes. A confidence interval covers the true value in a repeated-sampling
sense — saying "95 per cent probability the parameter is inside" is the common misreading. Correlation
measures linear association only, is sensitive to outliers, and never implies causation; report the
spearman rank version when the relationship is monotonic but not linear. A p-value is the probability of
data at least this extreme assuming the null, not the probability the null is true. Simpson's paradox:
a trend that reverses when you split by a confounding group, which is why aggregate ratios mislead. The
base-rate fallacy: a 99 per cent accurate test on a 1 per cent prevalence still yields mostly false
positives — Bayes' rule gives the positive predictive value. Know the median versus mean distinction,
because interviewers ask it about skewed data such as salaries.
