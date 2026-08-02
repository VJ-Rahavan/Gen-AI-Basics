# Lesson 6 — LCEL (LangChain Expression Language)

## 1. Problem

Your `/chat` endpoint worked, but look at what it was doing:

```python
messages = prompt.format_messages(message=..., tone=...)   # step 1
result   = llm.invoke(messages)                            # step 2
answer   = parser.invoke(result)                           # step 3
```

Three statements, two throwaway variables (`messages`, `result`), and **the order lives in your HTTP endpoint**. That's the problem. Three specific issues:

**1. The pipeline isn't a thing.** There is no object called "my chat pipeline." It's an implicit sequence of statements. You can't pass it around, reuse it in a second endpoint, or test it without spinning up FastAPI.

**2. Every new step means editing `app.py`.** Want to trim whitespace before the prompt? Add a translation step? You'd edit the HTTP layer — which shouldn't care about AI plumbing at all.

**3. You wire it up by hand every time.** You have to remember that the prompt's output goes into the model, and the model's output goes into the parser. Get the order wrong and it breaks. The computer already knows this order; you're re-stating it.

At Lesson 5's end I pointed out that all three pieces share the same `.invoke()` interface, and that each one's output feeds the next one's input. When that's true, the connection can be automated. **That's what LCEL does.**

---

## 2. New Concepts

### What is LCEL?

**LCEL** (LangChain Expression Language) is a way to **connect components with the `|` symbol** instead of calling them one at a time.

```python
chain = prompt | llm | parser
```

That single line replaces all three of your steps. Read it left to right, and read `|` as the word **"then"**:

> *"Fill the prompt, **then** send it to the llm, **then** parse the reply."*

The result is a new object — a **chain** — which is itself a runnable you can `.invoke()`.

### Real-world analogy: a factory assembly line

Think of a bottling plant.

**Without LCEL**, you're a worker manually carrying each item between machines:

```
you pick up the bottle → carry it to the filler → wait
you pick up the filled bottle → carry it to the capper → wait
you pick up the capped bottle → carry it to the labeler → wait
```

**With LCEL**, you bolt the machines together with conveyor belts and switch the line on:

```
[filler] ═══> [capper] ═══> [labeler]
```

You put one bottle in at the start. The line handles every hand-off. The `|` symbol *is* the conveyor belt.

The important shift: **you now own the assembly line as a single object.** You can point at it, name it, move it to another factory. Before, the "line" only existed as your habit of doing things in a certain order.

### What does the `|` operator actually do?

You already know `|` from the shell:

```bash
cat file.txt | grep "error" | wc -l
```

The output of `cat` flows into `grep`, whose output flows into `wc`. Same idea, same symbol, deliberately.

Here's the part that surprises people: **`|` is a normal Python operator that classes can define behavior for.** In plain Python, `|` means "bitwise OR" on numbers:

```python
5 | 3        # 7  -- bitwise OR
```

But Python lets a class decide what `|` means for *its* objects. LangChain's runnables define it to mean "connect these in sequence." So when Python sees `prompt | llm`, it asks `prompt`: *"what does `|` mean for you?"* — and LangChain's answer is *"build a sequence."*

This is called **operator overloading**. You don't need to write it yourself; just know that `|` is not magic syntax invented by LangChain. It's a regular operator with a custom meaning, which is why the code looks so clean.

### How does data flow between components?

Each component's **output becomes the next component's input**, automatically:

```
{"message": "...", "tone": "..."}     ← you provide this dictionary
        │
        ↓  prompt
[SystemMessage, HumanMessage]          ← a list of messages
        │
        ↓  llm
AIMessage(content='...')               ← a message object
        │
        ↓  parser
'...'                                  ← a plain string
```

Compare that to Lesson 5's diagram. **It is the exact same data flow.** Nothing about the mechanics changed — LCEL just stopped making you write the hand-offs by hand.

Two consequences worth internalizing:

- **The pieces must line up.** Each component's output type has to be something the next one accepts. `prompt | parser` would fail, because a parser can't consume a list of messages.
- **Order matters, and it's now stated once.** `prompt | llm | parser`, declared at startup in `llm.py`, instead of re-derived per request in `app.py`.

### The input is a dictionary now

This is the one thing that actually changes in how you call it. Before:

```python
prompt.format_messages(message="hi", tone="pirate")     # keyword arguments
```

After:

```python
chain.invoke({"message": "hi", "tone": "pirate"})       # ONE dictionary
```

Why the change? Because `.invoke()` is the *shared* interface — every runnable has it, and it takes **exactly one argument**. A chain can't accept arbitrary keyword arguments, because it doesn't know in advance what its first component wants. So everything travels as a single value, and when you need to pass several named things, that value is a dictionary.

**The dictionary keys must match your template's placeholders.** You have `{message}` and `{tone}` in the prompt, so the keys are `"message"` and `"tone"`. Misspell one and you get a `KeyError` — the same strictness you saw in Lesson 4.

### Why did LangChain introduce LCEL?

Four reasons, in rough order of how soon they'll matter to you:

**1. Composability.** A chain is an object. Name it, reuse it in two endpoints, pass it to a function, build a chain *out of* chains.

**2. Readability at a glance.** `prompt | llm | parser` tells you the whole architecture in six words. Ten lines of imperative steps don't.

**3. Free features, for the whole chain at once.** Because LangChain controls the hand-offs, it can offer things you'd otherwise hand-build:

| Method | What you get |
|---|---|
| `.invoke()` | run once, wait for the result (what we use) |
| `.stream()` | words arrive as they're generated |
| `.batch()` | run many inputs at once, in parallel |
| `.ainvoke()` | the async version |

You get all four on **any** chain, for free, just by composing with `|`. With hand-written steps you'd implement each yourself.

**4. It's the foundation for everything in lessons 7–12.** `RunnableLambda`, `RunnableMap`, `RunnableBranch` — every one of them is a piece you drop into a `|` chain. Learning LCEL now is what makes the rest of the series possible.

---

## 3. Project Changes

Two files. No new files, nothing to install.

| File | Change | Why |
|---|---|---|
| `llm.py` | added `chain = prompt \| llm \| parser` at the bottom | The pipeline is an AI concern, so it's defined next to the pieces it connects. Built once at startup. |
| `app.py` | three steps → one `chain.invoke(...)`; import changed | The endpoint no longer knows the order of operations. It just runs the chain. |

`prompt` and `parser` are no longer imported into `app.py` — they're sealed inside the chain. `llm` is still imported, but only for `llm.model_name` in the response.

`pyproject.toml`, `.env`, and `README.md` are unchanged.

### One honest trade-off: you lost `usage_metadata`

Your `print(result.usage_metadata)` line is gone, and it had to be. It read the `AIMessage` **between** the model and the parser — and that intermediate value now lives inside the chain where your endpoint can't reach it.

That's a genuine cost of LCEL, not something I'm papering over: **the chain hides its intermediate values.** You traded visibility for composability.

You can get it back when you need it — the simplest way is to invoke a shorter chain (`prompt | llm`) and parse separately, which is exactly what you had before. There are proper tools for this (callbacks, `.astream_events()`), but they're well past where we are. For now, know that the information still exists; you just can't see it from `app.py`.

---

## 4. Complete Code

**`llm.py`** — only the bottom changed; everything above `parser` is untouched

```python
# The parser: takes the model's reply object and gives back just the text.
# Created once here, reused for every request -- it holds no state.
parser = StrOutputParser()


# THE CHAIN. The | operator joins runnables together, left to right.
# Read it as: "fill the prompt, THEN send it to the llm, THEN parse the reply."
# Each piece's output becomes the next piece's input, automatically.
# This builds the chain once at startup. It does NOT run anything yet --
# nothing happens until someone calls chain.invoke(...) with real data.
chain = prompt | llm | parser
```

**`app.py`** — the import line and the body of `chat()`

```python
# We only need TWO things now: the finished chain, and llm (for its model name).
# prompt and parser are no longer imported here -- they live inside the chain.
from llm import llm, chain
```

```python
# POST, not GET, because the client needs to SEND data in the request body.
@app.post("/chat")
def chat(request: ChatRequest):
    # "request: ChatRequest" is a parameter with a TYPE HINT after the colon.
    # Because the type is a BaseModel, FastAPI reads the JSON body, validates it,
    # and hands us a ready-made ChatRequest object.
    # Dot access here (not ["..."]) -- it is an object, not a dictionary.

    # ONE step now, instead of three. The chain already knows the order:
    # prompt -> llm -> parser.
    # The input is a DICTIONARY, not keyword arguments. Its keys must match the
    # placeholders in the prompt template: {message} and {tone}.
    answer = chain.invoke({"message": request.message, "tone": request.tone})

    # A dictionary can hold as many key/value pairs as we like, separated by commas.
    # "answer" is already a string -- the parser inside the chain did that for us.
    # llm.model_name asks the llm object which model it is -- so the name is stored
    # in ONE place (llm.py). Typing "llama-3.3-70b-versatile" again here would mean
    # two copies to keep in sync, and one of them would eventually be wrong.
    return {
        "answer": answer,
        "model": llm.model_name,
    }
```

The endpoint body is now **one line of real logic**. Nine lines of code became one, and the one that remains says *what* you want rather than *how* to get it.

---

## 5. Execution Flow

```
User
 │   POST /chat   {"message": "What is a tuple?", "tone": "medieval knight"}
 ↓
FastAPI                    validates → request.message, request.tone
 ↓
chain.invoke({...})        ← ONE call. Everything below is inside the chain.
 │
 │  ┌──────────────────────────────────────────────────────┐
 │  │                                                      │
 │  │   {"message": ..., "tone": ...}     the dictionary   │
 │  │            │                                         │
 │  │            ↓  prompt                                 │
 │  │   [SystemMessage, HumanMessage]                       │
 │  │            │                                         │
 │  │            ↓  llm            ← the only network hop   │
 │  │   AIMessage(content='Verily, a tuple is...')          │
 │  │            │                                         │
 │  │            ↓  parser                                 │
 │  │   'Verily, a tuple is...'          a plain string     │
 │  │                                                      │
 │  └──────────────────────────────────────────────────────┘
 ↓
{"answer": ..., "model": ...}
 ↓
Response
```

The dashed box is the whole point: that machinery used to be spelled out in `app.py`, and now it's sealed inside one object.

### Proof the chain knows its own structure

I asked the chain to describe itself:

```
type -> RunnableSequence

steps in order:
  1 ChatPromptTemplate
  2 ChatGroq
  3 StrOutputParser
```

`prompt | llm | parser` didn't just run three things — it **built an object** called a `RunnableSequence` that holds your three components in order. That object is inspectable, reusable, and passable. Your three loose statements never were.

---

## 6. Run the Project

```bash
cd "/Users/purpleslate14mbp/Desktop/Mission G/gen-ai-beginner-basics"

uv run uvicorn app:app --reload
```

Test at http://127.0.0.1:8000/docs → **`POST /chat`**, or from the terminal:

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"What is a tuple?","tone":"medieval knight"}'
```

To inspect the chain yourself, without the server:

```bash
uv run python -c "
from llm import chain
print(type(chain).__name__)
for step in chain.steps:
    print(' ', type(step).__name__)
"
```

---

## 7. Expected Output

**Request A** — explicit tone:

```json
{ "message": "What is a tuple?", "tone": "medieval knight" }
```

Real response I got:

```json
{
  "answer": "Verily, a tuple is an immutable collection of values, akin to a shield with fixed emblems, that can be used to store and retrieve data in a most noble and efficient manner. 'Tis defined by enclosing values in parentheses, thus: `my_tuple = (1, 2, 3)`, a noble construct indeed.",
  "model": "llama-3.3-70b-versatile"
}
```

**Request B** — tone omitted, your default applies:

```json
{ "message": "What is a tuple?" }
```
```json
{
  "answer": "Ooooh, tuple be like a collection of things that can't be changed, like a treasure chest that's locked up tight, ya know, it's immutable! You can access the things inside, but ya can't add or remove anything, or it'll be like tryin' to break into the chest, won't work, matey!",
  "model": "llama-3.3-70b-versatile"
}
```

**Request C** — validation still works:

```json
{ "tone": "pirate" }
```
```json
{"detail":[{"type":"missing","loc":["body","message"],"msg":"Field required","input":{"tone":"pirate"}}]}
```
`422` — Pydantic is untouched by any of this.

**The headline: your API's behavior did not change at all.** Same fields, same voices, same status codes. Like Lesson 5, this was a **refactor** — the external contract held while the internals got simpler. Being able to make a change like this *without* your users noticing is a large part of what good structure buys you.

---

## 8. Mini Exercise

**Break the chain deliberately, and read the error.** Three experiments, in order:

**a)** Change the invoke call to omit `tone`:

```python
answer = chain.invoke({"message": request.message})
```

Call the endpoint. You'll get a `500`, and the server terminal will name the missing variable. Which component raised the error — the prompt, the llm, or the parser? (Read the traceback; the answer tells you where in the chain validation happens.)

**b)** Pass a string instead of a dictionary:

```python
answer = chain.invoke(request.message)
```

Different error. Why doesn't the chain just figure out that the string is the message?

**c)** Reverse two components in `llm.py`:

```python
chain = llm | prompt | parser
```

Does this fail when the chain is *built*, or only when it's *invoked*? This one is genuinely worth predicting before you run it.

Put everything back afterward.

---

## 9. Challenge

**Add a second endpoint that reuses the same chain — with a chain of its own.**

Build `POST /explain-simply` that answers as if to a complete beginner, regardless of the `tone` the caller sends.

Constraints, to make it a real exercise:

- Do **not** modify `chain`, `prompt`, or the `/chat` endpoint. Both endpoints must keep working.
- Create a **second** prompt template and a **second** chain in `llm.py`, e.g. `simple_prompt` and `simple_chain`, and compose it the same way: `simple_prompt | llm | parser`.
- Reuse the **same** `llm` and the **same** `parser` objects in both chains.

Then answer these, because they're the actual lesson:

1. You reused one `llm` object in two chains. Did that cause any problem? Why not? (Hint: what state does `llm` hold between calls?)
2. Your new prompt probably has only `{message}` and no `{tone}`. What dictionary does `simple_chain.invoke()` need — and what happens if you pass `tone` anyway?
3. If you later want *both* endpoints to strip whitespace from the user's input, how many places would you edit right now? Hold that thought — **Lesson 7 (`RunnableLambda`)** is precisely the tool for it.

---

## Addendum — Challenge, worked (`/simple-chat`)

The submitted code is correct. `/simple-chat` returns `200` with a clean answer, and `/chat` still works unchanged.

### The code

**`llm.py`** — a second system prompt, a second template, a second chain:

```python
SIMPLE_SYSTEM_PROMPT = """You are an expert Python programmer who explains everything in simple terms and give examples.

Answer every question accurately.
Never use more than two sentences."""


simple_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SIMPLE_SYSTEM_PROMPT),
        ("human", "{message}"),
    ]
)

simple_chain = simple_prompt | llm | parser
```

**`app.py`** — a second request class and a second endpoint:

```python
from llm import llm, chain, simple_chain


class SimpleChatRequest(BaseModel):
    message: str


@app.post("/simple-chat")
def simple_chat(request: SimpleChatRequest):
    answer = simple_chain.invoke({"message": request.message})
    return {
        "answer": answer,
        "model": llm.model_name,
    }
```

### A 422 that was NOT a code bug: the trailing comma

While testing, Swagger UI reported `422 Unprocessable Entity` on `/chat`. The request body was:

```json
{
"message": "What is expo in react native ?",
}
                                          ↑
                              this comma is the bug
```

Sending that exact body reproduces the error. Removing the single comma fixes it:

| Body | Result |
|---|---|
| `{"message": "...",}` | `422` `json_invalid` — *"Expecting property name enclosed in double quotes"* |
| `{"message": "..."}` | `200` — *"Ooooh, Expo be a tool that helps me build React Native apps super fast, like a Gum-Gum Fruit powerup..."* |

**JSON does not allow trailing commas. Python does.**

This directly contradicts the Lesson 3 advice to use trailing commas — which still stands, *for Python*:

```python
return {
    "answer": answer,
    "model": llm.model_name,     # ← trailing comma: correct, idiomatic Python
}
```
```json
{
    "message": "hello",          ← trailing comma: SYNTAX ERROR in JSON
}
```

Same-looking braces, opposite rules. The habit built in `.py` files will break `.json` request bodies. (JavaScript sides with Python: trailing commas are legal in JS object literals but *not* in `JSON.parse`.)

Read the error backwards and it makes sense: after a comma, JSON expects **another `"key"`**. It found `}`, so it reports a missing property name.

### Two different 422s — worth telling apart

| | `type: "json_invalid"` | `type: "missing"` |
|---|---|---|
| What's wrong | Not valid JSON at all | Valid JSON, wrong shape |
| Who caught it | The **JSON decoder** | **Pydantic** |
| Reached `ChatRequest`? | **No** — died before that | Yes, and was rejected |
| `loc` | `["body", 47]` ← a **character position** | `["body", "message"]` ← a **field name** |

That `loc` is the fastest diagnostic. **A number means "your JSON is malformed, look at that character."** A field name means "your JSON parsed fine, but the data is wrong." (The exact number varies with whitespace in the body — 47 vs 49 for the same bug.)

### Answers to the challenge questions

**1. Reusing one `llm` object in two chains — any problem?**

No, because **`llm` is stateless between calls.** It holds *configuration* — model name, temperature, API key — not conversation data. Every `.invoke()` builds a fresh HTTP request to Groq and keeps nothing afterward.

If it stored conversation history, sharing it would be a bug: `/simple-chat` would leak context into `/chat`. It doesn't, so one object serving both endpoints is correct and cheaper than building two. Same applies to `parser` — hence the Lesson 5 comment *"it holds no state."*

**2. What dictionary does `simple_chain.invoke()` need, and what if you pass `tone` anyway?**

Just `{"message": ...}`. Tested at both layers:

- **HTTP layer:** `{"message":"What is a set?","tone":"pirate"}` → **`200`**, and the answer had no pirate voice. `SimpleChatRequest` doesn't declare `tone`, so Pydantic **silently discards** it.
- **Chain layer:** `simple_prompt.format_messages(message='hi', tone='pirate')` → builds fine, 2 messages, and `'pirate' in msgs[0].content` is `False`.

So: **extra keys are ignored; missing keys are fatal.** Lesson 4 showed the fatal direction (`KeyError`); this is the forgiving direction. Worth knowing, because silent-ignore means a *typo* in a key name gives no error — just a placeholder that never got filled, which then fails as a missing key.

**3. How many places to add whitespace-trimming right now?**

**Two** — once per chain, with duplicated logic in both. That is exactly what `RunnableLambda` solves in Lesson 7.

### Small notes

Nothing wrong; three cosmetic things:

1. **Trailing whitespace** after `("system", SIMPLE_SYSTEM_PROMPT),` and after the final `}` of `simple_chat`. Invisible and harmless, but most Python formatters strip it.
2. **PEP 8 wants two blank lines** before a top-level `class` or decorated function; there is one before `class SimpleChatRequest` and one before `@app.post("/simple-chat")`.
3. **Ordering in `llm.py`** is `prompt` → `chain` → `simple_prompt` → `simple_chain`. This works perfectly. Grouping all prompts, then all chains, reads slightly better as the file grows — a preference, not a rule.
