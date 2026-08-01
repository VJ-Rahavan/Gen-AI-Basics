# Lesson 3 — Talking to a Real Model

## 1. What are we building?

`POST /chat`. You send `{"message": "Hello"}`, your code forwards it to a language model running on Groq, and you get back `{"answer": "..."}`.

This is the first lesson where your API does something you couldn't have written yourself.

Two files change, one file is new:
- **new** `llm.py` — everything about the model lives here
- **new** `.env` — your secret key
- **modified** `app.py` — the new endpoint

---

## 2. New Concepts

### What is Groq?

Groq is a company that **runs open-source models very fast** on custom hardware. They didn't make the models (Meta made Llama); they host them and serve them at high speed.

Keep three things separate in your head, because beginners mash them together:

| Thing | What it is |
|---|---|
| **Llama 3.3** | the model — the actual weights doing the thinking |
| **Groq** | the host — the company running it and exposing an HTTP API |
| **LangChain** | the library in *your* code that talks to Groq |

We use Groq because it has a generous free tier and is noticeably fast.

### What is an API key?

A long secret string that identifies you to Groq. It's a password with billing attached — anyone who has it can spend your quota.

Get yours free: **https://console.groq.com/keys** → *Create API Key*. It starts with `gsk_`. Copy it immediately; the page won't show it again.

### Environment variables — and why the key never goes in your code

An **environment variable** is a named value that lives *outside* your program, in the operating system. Your code reads it at runtime.

Why not just write the key in `llm.py`?

```python
llm = ChatGroq(api_key="gsk_abc123...")   # ← NEVER DO THIS
```

Three reasons, all real:

1. **Git.** Commit that once, push it, and the key is public forever — deleting the line later doesn't remove it from git history. Bots scrape GitHub for exactly this.
2. **Different values per place.** Your laptop, a teammate's laptop, and production each need a different key. Hardcoding forces a code change for a config change.
3. **Sharing.** You want to send someone your code without sending your secrets.

The rule: **code is public, configuration is private.** Keys are configuration.

### `python-dotenv` and the `.env` file

Setting environment variables by hand every time you open a terminal is tedious. So the convention is a file named `.env`:

```
GROQ_API_KEY=gsk_abc123
```

`python-dotenv` reads that file and loads its contents into the environment. One function call:

```python
from dotenv import load_dotenv
load_dotenv()
```

Two critical details:

- **`.env` must be gitignored.** I've already added it to your `.gitignore`, so it can't be committed by accident.
- **Note the package/import mismatch.** You install `python-dotenv` but you import `dotenv`. In Python, the install name and the import name don't have to match — you'll hit this again (`langchain-groq` → `langchain_groq`, hyphens become underscores).

### Python: `class`

A **class** is a blueprint describing a kind of data. We need one to tell FastAPI what shape the incoming JSON must have:

```python
class ChatRequest(BaseModel):
    message: str
```

Read it as: *"`ChatRequest` is a kind of `BaseModel`, and it has one field, `message`, which is a string."*

- `class` — the keyword.
- `(BaseModel)` — **inheritance**: "build on top of Pydantic's BaseModel and get all its powers." Roughly `class ChatRequest extends BaseModel` in JS.
- `message: str` — a field and its **type hint**.

### Type hints

The `: str` and `: ChatRequest` parts are type hints. Normally Python **ignores** them at runtime — they're just documentation for humans and editors, like TypeScript annotations that get stripped.

FastAPI is the exception. It *reads* them and enforces them. This one line:

```python
def chat(request: ChatRequest):
```

...makes FastAPI parse the JSON body, reject anything with the wrong shape (with a helpful error), build a `ChatRequest` object, and document the endpoint in Swagger. Type hints stop being decoration and start doing work.

### Importing your own file

```python
from llm import llm
```

*"From the file `llm.py`, take the thing named `llm`."* Note: no `./`, no `.py` extension — unlike JavaScript's `import { llm } from "./llm.js"`. Python finds `llm.py` because it sits in the same folder.

The repeated word is a little confusing but common: the **file** is `llm.py`, and the **variable inside it** is `llm`.

---

## 3. Project Structure

```
gen-ai-beginner-basics/
    app.py              ← MODIFIED: added POST /chat
    llm.py              ← NEW: the model lives here
    .env                ← NEW: your secret key (gitignored)
    pyproject.toml      ← MODIFIED by uv: 2 new dependencies
    README.md
    uv.lock
    .gitignore          ← MODIFIED: now ignores .env
    .venv/
```

This is the full structure from our original plan — no extra folders needed.

**Why a separate `llm.py`?** Because `app.py` should be about *HTTP* and `llm.py` should be about *the model*. When we change models in Lesson 4, we'll only touch `llm.py`. This split is the smallest useful piece of architecture in the project.

---

## 4. Complete Code

**`.env`** — replace the placeholder with your real key

```
# Secrets live here, NOT in your Python code.
# This file must never be committed to git.
# Format: NAME=value  -- no spaces around =, no quotes needed.

GROQ_API_KEY=paste_your_real_key_here
```

**`llm.py`** (new file, complete)

```python
# python-dotenv reads the .env file and loads each line into "environment variables"
from dotenv import load_dotenv

# ChatGroq is LangChain's wrapper around Groq's chat models
from langchain_groq import ChatGroq


# Runs once, when this file is first imported.
# It finds .env and loads GROQ_API_KEY into the environment,
# where ChatGroq will pick it up automatically -- we never type the key in code.
load_dotenv()


# Create the model object ONCE and reuse it for every request.
# This is a module-level variable, so it is created at startup, not per request.
llm = ChatGroq(
    # Which model to use. Groq hosts open models and runs them very fast.
    model="llama-3.3-70b-versatile",
    # 0.0 = focused and repetitive, 1.0 = creative and varied.
    temperature=0.7,
)
```

Notice we never mention the key. `ChatGroq` looks for `GROQ_API_KEY` in the environment by itself — that's the payoff of the naming convention.

**`app.py`** (complete file)

```python
# "import" brings code from another package into this file.
# In JavaScript you would write: import { FastAPI } from "fastapi"
# In Python the same idea is written as: from <package> import <thing>
from fastapi import FastAPI

# BaseModel lets us describe the SHAPE of incoming JSON so FastAPI can validate it
from pydantic import BaseModel

# Import our own file, llm.py, and take the variable named "llm" out of it.
# No "./" and no ".py" -- Python finds llm.py because it sits next to this file.
from llm import llm


# FastAPI is a class. Calling it with () creates an object (an "instance").
# There is no "new" keyword in Python -- calling the class IS creating the object.
# JavaScript equivalent: const app = new FastAPI()
app = FastAPI(title="Gen AI Beginner Basics")


# A "decorator" is the @ line below. It attaches extra behaviour to a function.
# This one tells FastAPI: "when a GET request arrives at the URL /, run home()"
# The function itself stays a plain, normal function.
@app.get("/")
def home():
    # "def" defines a function. The colon and the indentation replace { }.
    # "return" sends a value back, exactly like JavaScript.
    # The { } below is a DICTIONARY -- Python's version of a JS object.
    # Keys must be in quotes. FastAPI converts this dictionary into JSON for us.
    return {"message": "Hello World"}

@app.get("/health")
def health():
    return {"status": "ok"}


# A "class" is a blueprint for a kind of data. This one says:
# "a chat request is any JSON object that has a 'message' field holding text."
# "str" means string. FastAPI uses this to validate the request automatically.
class ChatRequest(BaseModel):
    message: str


# POST, not GET, because the client needs to SEND data in the request body.
@app.post("/chat")
def chat(request: ChatRequest):
    # "request: ChatRequest" is a parameter with a TYPE HINT after the colon.
    # Because the type is a BaseModel, FastAPI reads the JSON body, validates it,
    # and hands us a ready-made ChatRequest object.
    # Dot access here (not ["..."]) -- it is an object, not a dictionary.

    # .invoke() sends the text to Groq and waits for the reply.
    # It returns a MESSAGE OBJECT, not a plain string.
    result = llm.invoke(request.message)

    # .content pulls the actual text out of that message object.
    return {"answer": result.content}
```

That `result.content` is doing something slightly awkward. Hold onto it — Lesson 5 is entirely about why it's there and how to remove it.

**`pyproject.toml`** — `uv add` updated this for you

```toml
dependencies = [
    "fastapi>=0.141.1",
    "uvicorn>=0.52.0",
    "langchain-groq>=1.1.3",     # NEW
    "python-dotenv>=1.2.2",      # NEW
]
```

We asked for 2 packages and got 25. `langchain-core` came along transitively — which is convenient, because Lessons 4 and 5 need it and we now already have it.

---

## 5. How It Works

```
Client
 │   POST /chat   {"message": "Hello"}
 ↓
FastAPI          validates body against ChatRequest
 │               → wrong shape? stops here, returns 422
 ↓
def chat()       request.message  →  "Hello"
 │
 ↓
llm.invoke()     LangChain builds an HTTP request to Groq,
 │               attaching GROQ_API_KEY from the environment
 ↓
GROQ (internet)  Llama 3.3 generates a reply     ← the slow part, ~1 second
 │
 ↓
LangChain        wraps the reply in an AIMessage object
 │
 ↓
result.content   pull the text out of the object
 │
 ↓
{"answer": ...}  dictionary → JSON → back to the client
```

Note where the network boundary is. Everything above `GROQ` is on your laptop; the model itself is not. That means this endpoint can fail for reasons your other endpoints can't — bad key, no internet, rate limit.

---

## 6. Run the Project

### Step 1 — put your key in `.env` (do this first)

Open `.env` and replace `paste_your_real_key_here` with your real key from https://console.groq.com/keys:

```
GROQ_API_KEY=gsk_your_actual_key_here
```

No quotes, no spaces around the `=`.

### Step 2 — start the server

```bash
cd "/Users/purpleslate14mbp/Desktop/Mission G/gen-ai-beginner-basics"

uv run uvicorn app:app --reload
```

### Step 3 — test it in Swagger UI

Open http://127.0.0.1:8000/docs

You can no longer test this one in the browser address bar — browsers only send `GET`. Swagger UI is now genuinely necessary:

1. Click the **`POST /chat`** row
2. **`Try it out`**
3. The **Request body** box is pre-filled with an editable example. Change it to:
   ```json
   { "message": "Explain what a virtual environment is in one sentence." }
   ```
4. **`Execute`**

Wait a moment — this call goes over the internet.

Or from the terminal:

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello"}'
```

---

## 7. Expected Output

```json
{
  "answer": "Hello! How can I assist you today?"
}
```

The exact words will differ every time — `temperature=0.7` makes it non-deterministic. That's expected, and it's a real shift from every API you've written before: **the same request does not produce the same response.**

### What I verified for you

I ran the server with the placeholder key still in place, to prove the wiring is correct and isolate the one remaining step:

| Test | Result | Meaning |
|---|---|---|
| Server starts | ✅ | both new imports resolve; `llm.py` is valid |
| `GET /health` | `200` | old endpoints still fine |
| `POST /chat` with `{"message":"Hello"}` | `500` | reached Groq, rejected: `401 Invalid API Key` |
| `POST /chat` with `{"msg":"Hello"}` | `422` | Pydantic caught the wrong field name |

The 500 is the *expected* result of a placeholder key — and it's the last thing standing between you and a working AI endpoint. Put your real key in and it becomes a 200.

That 422 is worth reading in full, because it's free error handling you didn't write:

```json
{"detail":[{"type":"missing","loc":["body","message"],
            "msg":"Field required","input":{"msg":"Hello"}}]}
```

It names the exact location (`body` → `message`), the problem, and what you actually sent. All from `message: str`.

### Two problems you may hit

**Squiggly red underlines in VS Code** saying `Import "pydantic" could not be resolved` — your editor is using the wrong Python. The code runs fine; the editor just doesn't know about `.venv`. Fix: `Cmd+Shift+P` → *Python: Select Interpreter* → pick the one with `.venv` in the path.

**`500 Internal Server Error`** — look at the *terminal running the server*, not the browser. The real reason is in the traceback's last line. `Invalid API Key` means the key in `.env` is wrong, or you saved `.env` outside the project folder.

---

## 8. Mini Exercise

Prove to yourself that the key really comes from the environment and not from your code.

1. **Break it deliberately.** In `.env`, change `GROQ_API_KEY` to `GROQ_KEY`. Restart the server (`--reload` does **not** re-read `.env` — you must Ctrl+C and start again). Call `/chat`.
   - What error appears in the server terminal? Notice it fails at *startup* now, not at request time — `ChatGroq` looks for the key when it's created. Change the name back.

2. **Return a second field.** Make the response:
   ```json
   {"answer": "...", "model": "llama-3.3-70b-versatile"}
   ```
   Hint: the dictionary in the `return` can hold two pairs.

3. **Turn creativity off.** In `llm.py`, set `temperature=0.0`. Restart, then send the *exact* same message three times. Are the replies now identical, or just very similar? Then try `temperature=1.0` and send it three more times. This single number is one of the most useful knobs you have.

---

## Addendum — Exercise 2, worked

**It works — that's a real reply from Llama 3.3 running on Groq.**

```json
{"answer":"Hello to you my friend.","model":"llama-3.3-70b-versatile"}
```

Status `200`. Your whole chain is live end to end.

### What changed

Only the `return` in `app.py`:

```python
    # A dictionary can hold as many key/value pairs as we like, separated by commas.
    # .content pulls the actual text out of that message object.
    # llm.model_name asks the llm object which model it is -- so the name is stored
    # in ONE place (llm.py). Typing "llama-3.3-70b-versatile" again here would mean
    # two copies to keep in sync, and one of them would eventually be wrong.
    return {
        "answer": result.content,
        "model": llm.model_name,
    }
```

### Two things worth noticing

**1. I didn't hardcode the model name.** The obvious answer was `"model": "llama-3.3-70b-versatile"`, and it would work. But then the name exists in two files, and the day you change it in `llm.py` your API starts lying. `llm.model_name` asks the object itself, so there's a **single source of truth**.

That works because `ChatGroq` is a Pydantic model too — the same `BaseModel` idea as your `ChatRequest`. When you passed `model="llama-3.3-70b-versatile"`, Pydantic stored it on the object as `model_name`, and you can read it back with dot access.

**2. Multi-line dictionaries.** I split it across lines:

```python
return {
    "answer": result.content,
    "model": llm.model_name,
}
```

Two Python details in there:
- **Indentation rules relax inside brackets.** Normally indentation is strict, but once a `{`, `[`, or `(` is open, Python ignores line breaks until it closes. That's why this is legal.
- **That trailing comma after the last pair is intentional and idiomatic.** Python allows it, and it means adding a third field tomorrow is a one-line diff instead of a two-line one. (JavaScript allows this too, but it's more strongly a convention in Python.)
