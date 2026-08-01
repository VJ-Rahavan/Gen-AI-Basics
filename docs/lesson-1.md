# Lesson 1 — Python, uv, and Your First Server

## 1. What are we building?

Nothing visible yet. This lesson builds the **foundation**: a Python project that has its own isolated set of packages, and a web server that starts up and responds.

Think of it like `npm init` + `npm install` + `npm run dev` in the JavaScript world — but we need to understand the Python versions of those ideas, because they are *not* identical.

By the end, a server will be running at `http://127.0.0.1:8000`.

---

## 2. New Concepts

### Python itself

Python is already installed on your machine — **version 3.12.2**, managed by `pyenv`. Nothing to do here. If you were on a fresh machine, `uv` can install Python for you (`uv python install 3.12`), which is one of the reasons we use it.

### What is `uv`?

`uv` is the modern Python project manager. One tool that replaces four older ones:

| JavaScript | Python (old way) | Python with uv |
|---|---|---|
| `npm` | `pip` | `uv add` |
| `nvm` | `pyenv` | `uv python install` |
| `package.json` | `requirements.txt` | `pyproject.toml` |
| `package-lock.json` | (often nothing!) | `uv.lock` |

It is written in Rust, so it is very fast. Notice the install above took **43 milliseconds** for 13 packages.

### Why do virtual environments exist?

This is the biggest difference from JavaScript, so it's worth understanding properly.

In Node, `npm install` puts packages in `./node_modules` — **local to your project by default**. Two projects can use different versions of the same library and never conflict.

Python's default is the opposite. `pip install fastapi` installs it **globally**, for the whole computer. So:

```
Project A needs fastapi 0.90
Project B needs fastapi 0.141
→ Global install: they overwrite each other. One project breaks.
```

A **virtual environment** (`.venv`) fixes this. It is a private folder holding a copy of Python plus only this project's packages — Python's answer to `node_modules`.

`uv` created it automatically. You can see it in the file list: `.venv`.

> **You never need to "activate" it.** Older Python tutorials tell you to run `source .venv/bin/activate`. With `uv` you just prefix commands with `uv run`, and it uses `.venv` automatically. Simpler, and harder to get wrong.

### What is `pyproject.toml`?

This is Python's `package.json`. It declares what the project is and what it depends on. `.toml` is just a config file format (like JSON or YAML, but with `key = value` and `[sections]`).

### How does package installation work?

```
uv add fastapi
   │
   ├─→ 1. writes "fastapi>=0.141.1" into pyproject.toml   (the intent)
   ├─→ 2. resolves every sub-dependency, exact versions   (the math)
   ├─→ 3. writes uv.lock                                  (the record)
   └─→ 4. downloads them into .venv/                       (the reality)
```

Three files, three jobs — worth keeping straight:

- **`pyproject.toml`** — what *you* asked for. Loose ranges. You edit this (via `uv add`).
- **`uv.lock`** — what was actually installed, pinned exactly. Machine-written. Never edit by hand.
- **`.venv/`** — the actual code on disk. Disposable — delete it anytime and `uv sync` rebuilds it.

Note we ran `uv add fastapi uvicorn`, but 13 packages installed. The other 11 are **transitive dependencies** — things FastAPI itself needs. `pydantic` and `starlette` arrived this way, which is handy: we'll use Pydantic in a later lesson without ever installing it.

---

## 3. Project Structure

```
gen-ai-beginner-basics/
    app.py              ← our code (only 3 real lines so far)
    pyproject.toml      ← project + dependency declaration
    README.md           ← notes and run instructions
    uv.lock             ← auto-generated, don't edit
    .python-version     ← auto-generated: pins this project to 3.12
    .venv/              ← auto-generated: the isolated packages
```

`llm.py` and `.env` are in our final plan, but they don't exist yet — we create files only when we actually need them. Those arrive in Lesson 3.

---

## 4. Complete Code

**`app.py`**

```python
# "import" brings code from another package into this file.
# In JavaScript you would write: import { FastAPI } from "fastapi"
# In Python the same idea is written as: from <package> import <thing>
from fastapi import FastAPI


# FastAPI is a class. Calling it with () creates an object (an "instance").
# There is no "new" keyword in Python -- calling the class IS creating the object.
# JavaScript equivalent: const app = new FastAPI()
app = FastAPI(title="Gen AI Beginner Basics")

# That is all for Lesson 1.
# We have a running web server, but no endpoints yet.
# Lesson 2 will add our first endpoint here.
```

**`pyproject.toml`**

```toml
[project]
name = "gen-ai-beginner-basics"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.12"      # this project refuses to run on older Python
dependencies = [
    "fastapi>=0.141.1",         # the web framework
    "uvicorn>=0.52.0",          # the server that actually runs it
]
```

---

## 5. How It Works

```
uv run uvicorn app:app --reload
 │
 ↓
uv          finds .venv, uses that Python
 │
 ↓
uvicorn     the web server -- listens on port 8000 for HTTP requests
 │
 ↓
app:app     "in the file app.py, use the variable named app"
 │           ^^^      ^^^
 │           file     variable
 ↓
FastAPI     receives the request... and has no endpoints yet
```

That `app:app` argument confuses everyone the first time. The part before the colon is the **filename** (`app.py`, without `.py`). The part after is the **variable name** inside it. If you renamed the file to `server.py`, the command would become `uvicorn server:app`.

FastAPI and uvicorn are two separate things doing two separate jobs: FastAPI decides *what to do* with a request; uvicorn is the thing that actually speaks HTTP over the network. FastAPI can't listen on a port by itself.

---

## 6. Run the Project

```bash
cd "/Users/purpleslate14mbp/Desktop/Mission G/gen-ai-beginner-basics"

uv run uvicorn app:app --reload
```

`--reload` restarts the server automatically when you save a file — like `nodemon`. Use it while learning, never in production.

To stop the server: **Ctrl+C**.

---

## 7. Expected Output

I ran this to confirm it works. Your terminal will show:

```
INFO:     Started server process [7753]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

Now open two URLs in your browser:

| URL | What you get | Why |
|---|---|---|
| http://127.0.0.1:8000/docs | An interactive API page ✅ | FastAPI builds this for free |
| http://127.0.0.1:8000/ | `{"detail":"Not Found"}` — a 404 | Correct! We have not created any endpoint yet |

**That 404 is success, not failure.** It proves the server is alive and answering — it just has nothing to serve at `/`. Fixing that is exactly what Lesson 2 does.

Two harmless things you may notice:
- A warning: `VIRTUAL_ENV=... does not match the project environment path .venv`. This is because `pyenv` sets a variable in your shell. `uv` correctly ignores it and uses `.venv`. Safe to disregard.
- `uv init` also made a `.git` folder, so the project is already a git repository.

---

## 8. Mini Exercise

Run this and read the output:

```bash
uv add requests
```

Then answer for yourself:

1. What new line appeared in `pyproject.toml`?
2. Did `uv.lock` change?
3. Did more than one package get installed? Why?

Then undo it, because we don't actually need it:

```bash
uv remove requests
```

Confirm `pyproject.toml` is back to just `fastapi` and `uvicorn`. The point of the exercise is to see that **`uv add` and `uv remove` edit `pyproject.toml` for you** — you should almost never type dependencies in by hand.
