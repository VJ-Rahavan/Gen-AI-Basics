# Lesson 2 — Your First Endpoint

## 1. What are we building?

That 404 from Lesson 1 goes away. We create one endpoint — `GET /` — that returns `{"message": "Hello World"}`, and then we test it three different ways.

Only one file changes: `app.py`. Still no LangChain.

---

## 2. New Concepts

### What is an API?

An **API** is a contract between two programs: *"send me a request shaped like this, and I'll send back a response shaped like that."*

A web API is just that contract over HTTP. Your browser does the same thing when it loads a page — the difference is that an API usually returns **data** (JSON) rather than a page (HTML).

### What is an endpoint?

One specific address on your API that does one specific job. An endpoint is really a **pair**: a path *and* a method.

```
GET  /users     ← get the list of users     ┐
POST /users     ← create a new user         ├ same path, three endpoints
GET  /users/5   ← get user number 5         ┘
```

These are not one endpoint with options. They are separate endpoints with separate code.

### HTTP methods

The **verb** of the request — what you intend to *do*.

| Method | Meaning | Has a body? |
|---|---|---|
| `GET` | Read something. Changes nothing. | No |
| `POST` | Send data / create something. | **Yes** |
| `PUT` / `PATCH` | Update something. | Yes |
| `DELETE` | Remove something. | No |

We use `GET` today because we're only reading. In Lesson 3 we need to *send* a message to the AI, which needs a body — so that one will be `POST`.

### Request and response

```
REQUEST  (client → server)          RESPONSE (server → client)
  method:  GET                        status:  200 OK
  path:    /                          headers: content-type: application/json
  headers: ...                        body:    {"message": "Hello World"}
  body:    (none, it's a GET)
```

**Status codes** are the server's one-glance summary:

- `2xx` — worked (`200 OK`)
- `4xx` — *you* made a mistake (`404` wrong path, `422` bad data)
- `5xx` — *the server* made a mistake (`500` your code crashed)

### JSON

The text format both sides agree to speak. You already know it from JavaScript. The relevant Python fact:

```python
{"message": "Hello World"}    # a Python dictionary
{"message": "Hello World"}    # JSON text — looks identical!
```

They *look* the same but are different things: one is a live object in memory, one is a string being sent over a network. FastAPI does the conversion automatically, which is why we can just `return` a dictionary.

### Python: `def`, `return`, dictionaries, and indentation

```python
# JavaScript                          # Python
function greet(name) {                def greet(name):
  return "Hi " + name;                    return "Hi " + name
}
```

Four differences to burn in:

1. `def` instead of `function`.
2. A **colon** `:` ends the header line.
3. **Indentation defines the body.** There are no `{ }`. Four spaces, consistently — wrong indentation is a *syntax error*, not a style problem.
4. No semicolons.

A **dictionary** is Python's object literal — but the keys are always quoted:

```javascript
const d = { message: "hi" };   // JS: quotes optional
```
```python
d = {"message": "hi"}          # Python: quotes required
d["message"]                   # read it — no dot access
```

### Decorators — the `@` line

This is the one genuinely new idea. A **decorator** is a line starting with `@` placed directly above a function. It *registers* or *wraps* that function without changing the function's own code.

```python
@app.get("/")      # ← "FastAPI, please call the function below for GET /"
def home():
    return {...}
```

Compare to Express, where you pass the function in as an argument:

```javascript
app.get("/", (req, res) => { res.json({...}) });   // JS: function passed in
```
```python
@app.get("/")                                       # Python: function registered above
def home():
    return {"message": "Hello World"}
```

Same outcome, different mechanics. The decorator hands your function to FastAPI so FastAPI can call it later, when a matching request arrives.

Two things follow from this that trip beginners up:

- **You never call `home()` yourself.** FastAPI calls it. Your job is only to define it.
- **The function name doesn't matter to the URL.** `home` could be `read_root` or `banana`. The URL comes from `"/"` in the decorator, not the name.

---

## 3. Project Structure

Unchanged — we only edited an existing file.

```
gen-ai-beginner-basics/
    app.py              ← MODIFIED: added one endpoint
    pyproject.toml
    README.md
    uv.lock
    .python-version
    .venv/
```

---

## 4. Complete Code

**`app.py`** (complete file)

```python
# "import" brings code from another package into this file.
# In JavaScript you would write: import { FastAPI } from "fastapi"
# In Python the same idea is written as: from <package> import <thing>
from fastapi import FastAPI


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
```

Eight real lines. That is a working JSON API.

---

## 5. How It Works

```
Browser / curl
 │   GET / HTTP/1.1
 ↓
uvicorn                    receives raw bytes from the network
 │                         parses them into an HTTP request
 ↓
FastAPI router             "GET + / ... who registered that?"
 │                         → the @app.get("/") decorator did
 ↓
def home()                 YOUR CODE RUNS. returns {"message": "Hello World"}
 │
 ↓
FastAPI                    dictionary → JSON text
 │                         adds status 200 + content-type: application/json
 ↓
uvicorn                    writes bytes back over the network
 │
 ↓
Browser / curl             {"message":"Hello World"}
```

Your function is a small step in the middle. Everything around it — parsing, routing, JSON conversion, status codes, headers — is handled for you.

---

## 6. Run the Project

```bash
cd "/Users/purpleslate14mbp/Desktop/Mission G/gen-ai-beginner-basics"

uv run uvicorn app:app --reload
```

Now test it **three ways**, because each teaches you something different.

### Way 1 — the browser

Open http://127.0.0.1:8000/

### Way 2 — Swagger UI (the good one)

Open http://127.0.0.1:8000/docs

This page is **generated automatically** from your code. You wrote no documentation; FastAPI read your decorator and your function and built it. To test the endpoint:

1. Click the green **`GET /`** row to expand it
2. Click **`Try it out`**
3. Click the blue **`Execute`** button
4. Scroll to **Server response** — you'll see the status code, the response body, and the headers

Swagger UI will be your main testing tool from here on. Once we add `POST /chat` in Lesson 3, it gives you an editable text box for the request body — far easier than typing `curl` commands.

> There is a second free page at http://127.0.0.1:8000/redoc — the same information in a different layout. And http://127.0.0.1:8000/openapi.json is the raw machine-readable spec that both pages are built from.

### Way 3 — the terminal

```bash
# -i shows the response headers as well as the body
curl -i http://127.0.0.1:8000/
```

---

## 7. Expected Output

Browser at `/`:

```json
{"message":"Hello World"}
```

The `curl -i` output — I ran this to confirm:

```
HTTP/1.1 200 OK
date: Sat, 01 Aug 2026 17:06:19 GMT
server: uvicorn
content-length: 25
content-type: application/json

{"message":"Hello World"}
```

Read those headers, because they are the whole lesson in miniature:

- `200 OK` — the status code. Lesson 1's request said `404 Not Found`; now something is registered at `/`.
- `content-type: application/json` — FastAPI set this itself, because you returned a dictionary.
- `content-length: 25` — the body is exactly 25 characters. Note it's `{"message":"Hello World"}` with **no space** after the colon; FastAPI writes compact JSON.

And in the terminal running the server, one log line per request:

```
INFO:     127.0.0.1:49940 - "GET / HTTP/1.1" 200 OK
```

Keep an eye on that log. It is your first debugging tool — it tells you whether a request even *reached* the server, and what status went back.

### One thing worth seeing: the wrong method

I also sent a `POST` to the same path:

```bash
curl -X POST http://127.0.0.1:8000/
```
```
status: 405 Method Not Allowed
```

Not 404 — the path `/` exists. It's `405`, meaning *"that path is real, but it doesn't accept POST."* This is the proof of what I said earlier: an endpoint is a **path plus a method**, and `@app.get` registered only the `GET` half.

---

## 8. Mini Exercise

Add a second endpoint that returns more than one field.

Goal: `GET /health` returns

```json
{"status": "ok", "lesson": 2}
```

Hints, no full answer:

- Copy the existing block. Change `"/"` to `"/health"` in the decorator, and give the function a different name — two functions can't share a name.
- A dictionary can hold several pairs, separated by commas: `{"a": 1, "b": 2}`
- Values don't have to be strings. `2` with no quotes is a number, and FastAPI will emit it as a JSON number (`2`, not `"2"`).

Then check three things:

1. Does http://127.0.0.1:8000/health return your JSON?
2. Did http://127.0.0.1:8000/docs grow a **second row** by itself?
3. In the JSON output, is `lesson` shown as `2` or `"2"`? Try it both with and without quotes in your Python and watch the JSON change.

**Bonus:** delete the four spaces of indentation before `return` and save. Read the error message carefully — `IndentationError: expected an indented block`. Getting familiar with that error now will save you time later, because it will happen to you again. Then put it back.
