# Product reasoning and design history

This document preserves the decisions that led to the current YouTube Research
Canvas. It replaces the earlier market-research artifacts and transcript proof
of concept, which were useful during discovery but are no longer part of the
working application.

## Problem framing

“YouTube summarization” is several different capabilities bundled under one
label:

- Transcript acquisition: obtain caption or speech text with useful timestamps.
- Single-video understanding: extract summaries, themes, takeaways, highlights,
  and questions.
- Batch processing: reliably accept and process several URLs.
- Cross-video synthesis: find agreement, disagreement, repeated claims, and
  unique contributions across selected videos.
- Critical appraisal: separate claims, evidence, assumptions, counterarguments,
  and limitations.
- Implication analysis: explain possible consequences without presenting
  inference as observed fact.

A transcript proves only what was spoken. It does not capture an unspoken chart,
demonstration, slide, or code example. Visual analysis remains a separate future
capability and should be disclosed as such if added.

## Market findings that shaped the product

The basic summary market is crowded. Products such as Gemini Notebook,
LilysAI, Recall, NoteGPT, Mindgrasp, Glasp, Mapify, Eightify, and
summarize.tech already cover combinations of captions, summaries, notes,
question answering, study aids, and batch ingestion.

The strongest benchmarks identified during discovery were:

- Gemini Notebook for bounded, citation-oriented research across selected
  sources.
- LilysAI for rich multi-source reports and navigation back to video passages.
- Recall for an ongoing personal research library and cross-source chat.

The resulting product hypothesis was not “another YouTube summarizer.” It was a
reviewable personal research brief that distinguishes:

1. What a speaker said.
2. What evidence in the transcript supports.
3. What the analysis infers.
4. What remains uncertain or unsupported.

That led to the fixed output contract used by the application: executive
summary, key takeaways, timestamped highlights, discussion themes, impacts,
strengths, weaknesses, claims and evidence, assumptions, logical gaps, and
cross-video synthesis.

The market research was a documented-capability comparison, not a hands-on
quality benchmark or market-size estimate. Vendor claims, pricing, quotas, and
product names change; they should be revalidated before making current
commercial decisions.

## Transcript PoC findings

The original Python PoC tested whether a personal tool could retrieve YouTube
transcripts quickly without a paid transcription API. It established the
following approach:

1. Normalize every supported YouTube form to a video ID and canonical watch URL.
2. Try `youtube-transcript-api` first for public manual or automatic captions.
3. Fall back to `yt-dlp` for subtitle discovery.
4. Parse JSON3, WebVTT, or XML/TTML caption payloads.
5. Preserve timestamps and normalize caption whitespace.
6. Avoid unnecessary metadata calls on the latency-sensitive path.

For public videos with captions, the primary path was fast enough to support the
target of roughly seven to eight seconds per URL. A representative live PoC run
completed in about two seconds. Audio transcription cannot guarantee that
latency for arbitrary full-length videos, so local or hosted Whisper-style ASR
was deliberately left as a future fallback.

The relevant limitations remain:

- YouTube can rate-limit or block requests by IP, region, account, or video.
- Private, members-only, age-restricted, or region-blocked videos can fail.
- Some videos expose no usable caption track.
- Caption quality varies, especially for names, code, mixed language, and noisy
  speech.
- English, Hindi, and Bangla are preferences, not availability guarantees.

## Current architectural decisions

The PoC logic was incorporated into the FastAPI application and the duplicate
CLI implementation was retired.

- One FastAPI process serves HTTP routes, Jinja templates, static assets, SSE,
  and background work.
- LangGraph provides deterministic orchestration. Transcription is a tool node;
  analysis and batch synthesis are explicit graph stages.
- One SQLite file stores application records and LangGraph checkpoints.
- URL hashes deduplicate equivalent `youtu.be`, `watch`, `shorts`, `embed`, and
  `live` links before any network call.
- Raw transcripts live in the transcript table. Graph checkpoints store
  conversation messages, transcript references, errors, and structured reports,
  avoiding repeated copies of large transcript bodies.
- Every submission creates an isolated thread. A background reaper persists
  active-run heartbeats every fifteen seconds.
- Processing runs outside the request lifecycle. The server-rendered results
  page receives progress through SSE and reloads at a terminal state.
- Batch mode allows up to ten unique videos and retains successful results when
  another URL is invalid or unavailable.
- OpenAI structured output is validated through Pydantic schemas. Long
  transcripts are split on timestamp boundaries, reduced per video, and only
  then synthesized across videos.
- The UI remains reading-first, with a lightweight Markdown override for
  correcting or reshaping a generated canvas. It is not a full document editor
  or separate frontend application.

Repository protocols and FastAPI dependency injection keep routes independent
of SQLite. Services own business rules, repositories own persistence, graph
nodes own orchestration steps, and models define the contracts between them.

## Quality benchmark for future work

Future model or competitor evaluations should use the same mixed test set:
short explainers, long interviews, conflicting positions, visually important
videos, missing-caption videos, and multilingual or noisy recordings.

Score these dimensions separately:

| Criterion | Suggested weight | What to measure |
| --- | ---: | --- |
| Factual fidelity | 25% | Correct claims, numbers, names, and attribution |
| Evidence traceability | 20% | Whether cited passages support the analysis |
| Coverage | 15% | Important points retained with qualifications |
| Cross-video synthesis | 15% | Correct agreements, conflicts, and attribution |
| Critical appraisal | 15% | Specific gaps without invented criticism |
| Usefulness and clarity | 10% | Readability, actionability, and low redundancy |

Track import success, latency, cost per processed hour, and manual correction
time outside the quality score. Treat fabricated quotations or timestamps as
critical defects.

## Deliberate v1 boundaries

The personal-use first version does not include accounts, sharing, billing,
thread browsing, transcript search, a collaborative editor, automatic crash replay,
audio ASR, or visual frame analysis. These should be added only when a real
workflow demonstrates their value.

The next most useful extensions are likely searchable saved research, explicit
export formats, optional audio-ASR fallback, and a visual-analysis mode that
clearly labels evidence coming from frames rather than captions.
