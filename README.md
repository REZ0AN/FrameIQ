# YouTube Research Canvas

A personal FastAPI application that turns one or more YouTube caption tracks
into structured research reports. LangGraph orchestrates transcription and
analysis, while one SQLite database stores application records and graph
checkpoints.

## Requirements

- Python 3.13
- `uv`
- An OpenAI or Gemini API key

## Setup

For complete installation, provider configuration, health checks, local data,
and troubleshooting instructions, see the
[`local development setup and run guide`](docs/local-development-setup-and-run-guide.md).

From the project root:

```bash
uv venv --python 3.13 .venv
source .venv/bin/activate
uv pip install -r requirements.txt
cp .env.example .env
```

Set the analysis provider in `.env`.

For OpenAI, leave `AI_BASE_URL` empty:

```dotenv
AI_API_KEY=your-openai-key
AI_MODEL=gpt-5.6-terra
AI_BASE_URL=
```

For Gemini, use Google's OpenAI-compatible endpoint and a Gemini model available
to your account:

```dotenv
AI_API_KEY=your-gemini-key
AI_MODEL=gemini-2.5-flash
AI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
```

The legacy `OPENAI_API_KEY`, `OPENAI_MODEL`, and `OPENAI_BASE_URL` variables
remain supported.

## Run

```bash
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>. Use one Uvicorn worker because background run
tracking is intentionally in-process for this personal-use version.

The `GET /health` endpoint verifies that the application can query SQLite.
Configure Render's health check path as `/health`.

## Test

```bash
source .venv/bin/activate
pytest -q
```

The default tests use fake YouTube and analysis adapters, so they neither need
network access nor spend API credits.

## Runtime behavior

- A single URL creates a single-video report.
- Commas select batch mode, with up to ten unique videos and partial success.
- Equivalent YouTube URL forms share one cached transcript.
- `/dashboard` lists recent canvases and deduplicated saved transcripts.
- Completed canvases can be edited as Markdown or deleted from the dashboard.
- Deleting a canvas also removes its checkpoints and any transcript no other
  canvas uses.
- Caption lookup prefers English, Hindi, then Bangla.
- `youtube-transcript-api` is the primary caption source; `yt-dlp` is the
  fallback.
- Results update through server-sent events and remain available from SQLite.

The product reasoning, market conclusions, and transcript PoC lessons are
preserved in
[`docs/product-reasoning-and-design-history.md`](docs/product-reasoning-and-design-history.md).
