---
domain: rubrics
---

## Criterion: relevance

type: rubric
difficulty: junior
tags: relevance, on topic, question intent, scoring criterion

Relevance measures whether the answer addresses the question that was asked, including every part of a
compound question. Score 9-10: directly answers, and anticipates the follow-up the question implies.
7-8: answers fully, with a short digression that still returns to the point. 4-6: partially answers —
one clause ignored, or the candidate substitutes a question they prefer. 1-3: answers a different
question, or recites prepared material that does not engage with what was asked. 0: nothing addressable.
Typical deductions: pivoting to a favourite topic, answering the theory while the question asked about
their own decision, treating a behavioral question as a technical lecture. Do not penalise a concise
answer that is on target, and do not reward length in place of fit: an irrelevant paragraph is a
deduction, not a credit.

## Criterion: clarity

type: rubric
difficulty: junior
tags: clarity, language, jargon, sentence structure, readability

Clarity measures how much effort the listener spends to follow the answer. Score 9-10: one idea per
sentence, terms defined when used, no unexplained acronyms, a listener could restate it after one pass.
7-8: mostly clean with a few overloaded sentences or one unexplained term. 4-6: understandable only
with effort — long run-ons, jargon used as a substitute for precision, pronouns without antecedents.
1-3: contradictory or fragmented; the reader has to reconstruct the meaning. Concrete signals: hedging
words stacked together ("basically kind of maybe"), buzzword clusters with no mechanism, sentences over
thirty words. Note that a simple explanation of a hard thing scores high — clarity rewards understanding,
not vocabulary, and a candidate who says "it caches the result so the database is not hit twice" beats
one who says "it leverages a high-performance caching layer".

## Criterion: structure

type: rubric
difficulty: junior
tags: structure, star, sequencing, organization, signposting

Structure measures whether the answer has a shape the listener can track. For a behavioral question,
the expected shape is STAR: context in one or two sentences, own responsibility, actions with
decisions, outcome. For an explanatory question, the expected shape is claim, then mechanism, then a
trade-off or example. 9-10: shape is obvious without labels, with signposting ("first… then… the part I
would change"). 7-8: shape present but one stage is underweight — usually the result. 4-6: content is
there but arrives out of order, or context consumes half the answer. 1-3: stream of consciousness, no
beginning or end, or the candidate restarts mid-answer. A named structure used mechanically with no
substance scores mid-band at best: structure is a vehicle for the reasoning, and rubrics should not
reward the labels alone.

## Criterion: technical accuracy

type: rubric
difficulty: intermediate
tags: technical accuracy, correctness, depth, mechanism, verifiable claims

Technical accuracy measures whether the stated mechanism is correct and complete enough to be acted
on. 9-10: correct concept, correct terminology, at least one verifiable detail — a flag, a complexity
figure, a failure mode, the reason a trade-off exists. 7-8: correct overall with a minor imprecision
that does not change the design. 4-6: half right — right tool, wrong reason; or a correct definition
that cannot be applied. 1-3: a factual error that would mislead a teammate, or confident name-dropping
with no mechanism. 0: nothing correct. Score the claim, not the confidence: an answer that says "I am
not sure, but I would check X" and names the right check loses little, while a wrong statement presented
as fact is a hard deduction. Where the answer is about the candidate's own experience, accuracy includes
whether the described scale is plausible for what they claim to have built.

## Score bands and the overall verdict

type: rubric
difficulty: intermediate
tags: bands, overall score, verdict, calibration, aggregation

Map the aggregate score to what the interviewer would say out loud. 9-10 ready to hire on this point:
correct, structured, evidence present, would hold up in a follow-up probe. 7-8 good: solid answer with
one gap, usually a missing number or an unaddressed trade-off. 5-6 acceptable: the shape is right, the
substance is thin — hire-no-hire undecided on this question alone. 3-4 weak: significant missing piece,
vague, or a factual error that needs correction before it can be relied on. 0-2 unsuitable: off-topic,
incorrect, or empty. Derive the overall score from the four criteria rather than from a gut feeling, but
round down when any single criterion is at 3 or below: a technically accurate answer that is off-topic
still fails the interview. The verdict line must be one sentence that a candidate can act on, naming the
single highest-leverage change.

## What evidence distinguishes a strong answer

type: guideline
difficulty: intermediate
tags: evidence, numbers, artifacts, verification, specificity

Evidence is anything the interviewer cannot dismiss as decoration: a measured before-and-after, a named
file or flag, a real error message, a colleague's reaction, a decision recorded in a pull request, the
count of rows or users or tests. Rubrics should reward three specific kinds. First, quantification
attached to a verb — "cut the export from seventeen minutes to ninety seconds", not "improved
performance". Second, mechanism named precisely — "added a composite index on (session_id, created_at)
and rewrote the aggregate as a single GROUP BY". Third, falsifiable scope — "on the fifty-thousand-row
fixture on my laptop", which shows the candidate knows the limits of their own claim. Absence of
evidence is the most common reason a well-structured answer lands at six. Never invent evidence on the
candidate's behalf when evaluating; state the missing evidence as the gap.

## Anti-patterns to penalise consistently

type: rubric
difficulty: intermediate
tags: anti patterns, buzzwords, hypothetical, hedging, name dropping

Apply the same deductions to everyone. Name-dropping without mechanism — a list of tools with no verb
attached — caps technical accuracy at the mid-band. Hypothetical framing — "I would usually…" in answer
to "tell me about a time…" — is a relevance deduction because it declines the question. Hedging stacks
("I think maybe roughly quite possibly") undermine clarity. Borrowed authority — "as everyone knows",
"best practice is" — with no reason given. Buzzword substitution: saying "microservices" where a module
boundary is meant. Unscaled claims: "millions of users", "very fast", "huge dataset" with no figure.
Retelling someone else's work in the first person plural to hide that they did little. Blame language
about past teammates in a behavioral answer, which is a professional-judgement flag independent of
content. Note the difference between an anti-pattern and a preference: a candidate who answers briefly
and correctly is not being penalised for brevity.

## Junior versus senior expectations on the same question

type: rubric
difficulty: senior
tags: seniority, calibration, expectations, progression, scoring

The same answer scores differently by seniority, and the rubric must say why. A junior is expected to
explain a concept correctly, name one trade-off when prompted, show ownership of a defined task, and be
honest about the limits of what they did. A senior is expected to volunteer the trade-offs nobody asked
about, quantify impact and constraints, describe what they changed structurally after the incident, and
show influence beyond their own code — reviews, mentoring, decisions recorded. Deduct from a senior for
a story with no rejected alternative; do not deduct from a junior for the same gap, but flag it as the
coaching point. Do not credit a senior answer for vocabulary alone: the distinguishing signal is
judgement under uncertainty, not terminology. When seniority is unclear, score at the declared level and
state what evidence would move the candidate up a band.

## Scoring a technical answer versus a behavioral answer

type: guideline
difficulty: intermediate
tags: question type, behavioral, technical, weighting, criteria

The four criteria keep their names but change weight. For a technical question, technical accuracy
dominates and structure matters only insofar as it makes the reasoning traceable; a technically correct
answer delivered in messy prose can still reach seven or eight. For a behavioral question, structure
and relevance dominate — STAR completion, own agency, and a result — and technical accuracy applies to
whether the described events are plausible and the terminology is used honestly. A useful default:
technical = 45 per cent accuracy, 20 each relevance, clarity, structure; behavioral = 35 structure,
30 relevance, 20 clarity, 15 accuracy of the described facts. Say explicitly which weighting was used so
two answers of the same quality are not scored inconsistently, and never let the weighting rescue an
answer that is off-topic: relevance has a floor in both cases.

## Writing the feedback a candidate can act on

type: guideline
difficulty: senior
tags: feedback, improvement, coaching tone, actionable, verdict

Feedback is graded on usefulness, not on kindness. Structure it in three parts: what already worked,
named specifically — "the result had a real number"; the single highest-leverage gap, phrased as the
change to make rather than the flaw — "your Action block says what the team did; rewrite it as the two
decisions you personally made"; and a concrete model of what good looks like, ideally one rewritten
sentence the candidate can imitate. Avoid a list of five problems, which nobody can act on in the next
answer, and avoid adjectives that describe the person ("vague", "weak") instead of the text. Do not
praise in place of a score, and do not soften a factual error into a preference. When the answer was
empty or off-topic, say so plainly and give the structure to use next time: an honest low score with a
path is more useful than a flattering non-answer.
