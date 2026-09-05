# Local Development Setup and Run Guide

This guide runs YouTube Research Canvas locally with Python 3.13, `uv`, SQLite,
and either OpenAI or Gemini for report generation.

## Prerequisites

- Git
- `uv`
- An OpenAI or Gemini API key
- Internet access for YouTube captions and model requests

The project targets Python 3.13. `uv` can install that Python version if it is
not already available locally.

## 1. Create the virtual environment

Run these commands from the project root:

```bash
uv python install 3.13
uv venv --python 3.13 .venv
source .venv/bin/activate
python --version
```

The reported version should begin with `Python 3.13`.

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

## 2. Install dependencies

With the virtual environment active:

```bash
uv pip install -r requirements.txt
```

## 3. Configure the analysis model

Create the local environment file:

```bash
cp .env.example .env
```

Use one of the following configurations.

### OpenAI

Leave `AI_BASE_URL` empty so the OpenAI SDK uses its default endpoint:

```dotenv
AI_API_KEY=your-openai-api-key
AI_MODEL=gpt-5.6-terra
AI_BASE_URL=
DATABASE_PATH=data/youtube_analyzer.sqlite3
```

Replace the model value if your OpenAI account uses a different supported
model.

### Gemini

Point the same OpenAI-compatible client at Google's compatibility endpoint:

```dotenv
AI_API_KEY=your-gemini-api-key
AI_MODEL=gemini-2.5-flash
AI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
DATABASE_PATH=data/youtube_analyzer.sqlite3
```

Replace the model value with a Gemini model available to your Google AI
account. Do not commit `.env` or expose its API key.

The legacy variables `OPENAI_API_KEY`, `OPENAI_MODEL`, and
`OPENAI_BASE_URL` remain supported, but new local configurations should use the
provider-neutral `AI_*` names.

## 4. Run the application

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000> in a browser. Submit one YouTube URL for single
mode or comma-separated URLs for batch mode. The dashboard lets you reopen,
edit, or delete completed canvases. Canvas edits are stored as Markdown in the
same SQLite database; editing does not alter the source transcript.

Run exactly one Uvicorn worker. Background analysis tracking is intentionally
in-process, and the application uses one local SQLite database.

Stop the server with `Ctrl+C`.

## 5. Verify application health

With the application running:

```bash
curl --fail http://127.0.0.1:8000/health
```

A healthy application responds with:

```json
{"status":"ok","database":"ok"}
```

The endpoint returns HTTP 503 when SQLite cannot be queried.

## 6. Run the test suite

```bash
pytest -q
```

Tests use fake transcript and analysis providers. They do not call YouTube,
OpenAI, or Gemini and do not consume API credits.

## Local data

By default, application records, cached transcripts, and LangGraph checkpoints
are stored together in:

```text
data/youtube_analyzer.sqlite3
```

SQLite may also create `-wal` and `-shm` files while the server is running.
Keep these files local and stop the application before manually copying the
database. A future backup feature should use SQLite's online backup API rather
than copying a live WAL-mode database directly.

Set `DATABASE_PATH` in `.env` if you need the database in another location.

Deleting a canvas removes its run and LangGraph checkpoint data. A transcript
is removed only when no remaining canvas references it.

## Common problems

### `AI_API_KEY is not configured`

Confirm `.env` exists in the project root, contains `AI_API_KEY`, and has no
quotes or spaces around the variable name.

### Model-not-found or authentication response

Confirm the API key belongs to the provider selected by `AI_BASE_URL` and that
`AI_MODEL` is available to that account. Gemini requires the Google-compatible
base URL shown above; OpenAI should leave `AI_BASE_URL` empty.

### Address already in use

Choose another local port:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8001
```

### Captions unavailable

The application can only analyze caption tracks accessible from YouTube. A
video can be valid and public while still lacking usable captions in the
configured languages.
