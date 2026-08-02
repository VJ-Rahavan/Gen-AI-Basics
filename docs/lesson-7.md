# Lesson 7 — RunnableLambda

## 1. Problem

At the end of Lesson 6 the question was: *if you want both endpoints to strip whitespace from user input, how many places would you edit?* The answer was **two** — and that's the problem.

Right now nothing cleans the input at all. If a user sends `"   What is a set?   \n"`, that padding goes straight into your prompt. Usually harmless, sometimes not: whitespace costs tokens, and a message that's *only* spaces becomes an empty question the model has to guess at.

So you need a cleaning step. But look at your two chains:

```python
chain        = prompt        | llm | parser
simple_chain = simple_prompt | llm | parser
```

Where does `.strip()` go? Three bad options:

**Option A — in `app.py`, in each endpoint:**
```python
answer = chain.invoke({"message": request.message.strip(), "tone": ...})
answer = simple_chain.invoke({"message": request.message.strip()})
```
Two copies of the logic. Add a third endpoint, write it a third time. And your HTTP layer is doing text processing again — the exact thing Lesson 6 got it out of.

**Option B — inside the prompt template.** Not possible. A `ChatPromptTemplate` substitutes values; it can't transform them.

**Option C — a Pydantic validator.** Actually reasonable, but it only fixes input arriving over HTTP. If you later call your chain from a script or a background job, the cleaning is bypassed.

**The real issue:** `|` connects *runnables*, and so far every runnable you have came from LangChain — a prompt, a model, a parser. You have no way to put **your own code** in the pipeline.

That's the gap `RunnableLambda` fills.

---

## 2. New Concepts

### First, the Python feature: `lambda`

A **lambda** is a function written in one line, without a name.

You already know the normal way:

```python
def double(x):
    return x * 2
```

The lambda way — same function, no name, no `def`, no `return`:

```python
lambda x: x * 2
```

Read it as: *"a function taking `x`, which gives back `x * 2`."* The colon separates the parameter from the result, and **the result is returned automatically** — writing `return` inside a lambda is a syntax error.

Side by side:

```python
def   double(x): return x * 2      # named function
      lambda x:  x * 2             # the same logic, unnamed
#     ^^^^^^ no name, no def, no return
```

If you know JavaScript arrow functions, it's the same idea:

```javascript
x => x * 2          // JS arrow function
```
```python
lambda x: x * 2     # Python lambda
```

**The catch: a lambda can only hold one expression.** No `if` statements on their own lines, no loops, no multiple steps. The moment your logic needs two lines, you must use `def`. That limitation is deliberate — lambdas are for logic small enough to read at a glance.

### Now: what is `RunnableLambda`?

`RunnableLambda` **wraps an ordinary Python function so it can join a `|` chain.**

```python
cleaner = RunnableLambda(clean_input)
```

That's all it does. It takes your function and gives back an object with the standard `.invoke()` interface — so LangChain can treat it exactly like a prompt or a model.

### Analogy: an adapter plug

Your chain is a row of sockets, all the same shape. LangChain's components come with the right plug already fitted. Your own function has a plug that doesn't fit — it's just a function.

`RunnableLambda` is the **travel adapter**. Your function is unchanged inside; the adapter gives it the shape the socket expects.

That's why the name is a bit misleading — **it works with any function, not just lambdas:**

```python
RunnableLambda(lambda d: d)      # a lambda   ✓
RunnableLambda(clean_input)      # a named def ✓  ← what we use
```

The class is named after the *typical* case, not a requirement. Don't let the name push you into writing lambdas when a named function reads better.

### Why does it exist?

**1. Your pipeline needs steps LangChain doesn't provide.** Trimming, lowercasing, adding a timestamp, looking something up, reformatting between two components — normal programming that no library can anticipate.

**2. Write the logic once, use it in every chain.** This is your problem, solved:

```python
cleaner = RunnableLambda(clean_input)                    # defined ONCE

chain        = cleaner | prompt        | llm | parser    # used here
simple_chain = cleaner | simple_prompt | llm | parser    # and here
```

Change how cleaning works, edit one function, both chains follow. Compare with Option A above, where the logic was copy-pasted.

**3. Your function stays plain and testable.** `clean_input` is an ordinary function that knows nothing about LangChain. You can call it directly in a test with a dictionary — no chain, no network, no API key.

### When should you use it?

**Use it for:** small, pure data reshaping between components — trim, lowercase, rename a key, pick a field out of a dictionary, format a number.

**Don't use it for:** anything slow or that can fail badly (network calls, database writes, file I/O). Not because it won't work, but because errors inside a chain step produce deep tracebacks that are unpleasant to debug. Keep chain steps boring.

**The one rule that matters:** whatever your function **returns** becomes the next component's **input**. Get that shape wrong and the next component fails. Our `clean_input` returns a dictionary because `prompt` needs a dictionary.

### The Python bit inside our function: `.strip()`

```python
"  hello  ".strip()      # "hello"
```

`.strip()` removes whitespace — spaces, tabs, newlines — from **both ends** of a string. It does **not** touch the middle. Verified:

```
'   a     b   '  →  'a     b'
```

Ends cleaned, the five spaces between `a` and `b` untouched. (Relatives, for later: `.lstrip()` for the left end only, `.rstrip()` for the right.)

---

## 3. Project Changes

**One file changed: `llm.py`.** `app.py` is untouched — and that's the headline.

| File | Change | Why |
|---|---|---|
| `llm.py` | added the `RunnableLambda` import, the `clean_input` function, the `cleaner` runnable, and put `cleaner` at the front of both chains | Cleaning is part of the AI pipeline, so it belongs in the pipeline |
| `app.py` | **nothing** | The endpoints call `chain.invoke(...)` exactly as before |

That `app.py` needs no edit is the payoff from Lesson 6. Because the pipeline is an object, you can insert a step into it without any caller knowing. Had you gone with Option A, you'd have edited every endpoint.

Nothing to install — `RunnableLambda` lives in `langchain_core`, already present.

---

## 4. Complete Code

**`llm.py`** — the new import:

```python
# RunnableLambda turns any ordinary Python function into a chain component
from langchain_core.runnables import RunnableLambda
```

The function, the wrapper, and the updated chain — replacing the old `chain = prompt | llm | parser`:

```python
# An ORDINARY Python function. Nothing about it knows it is part of a chain.
# It receives the dictionary that was passed to the chain, and must return
# a dictionary too -- because the next component (the prompt) expects one.
def clean_input(data):
    # data["message"] reads the value out of the dictionary.
    # .strip() removes spaces, tabs and newlines from BOTH ends of a string.
    # It does not touch spaces in the middle: "  a  b  " becomes "a  b".
    data["message"] = data["message"].strip()

    # Always return the data, or the next component receives nothing.
    return data


# RunnableLambda wraps the plain function so it can join a | chain.
# Written once here, reused by every chain below.
cleaner = RunnableLambda(clean_input)


# THE CHAIN. The | operator joins runnables together, left to right.
# Read it as: "clean the input, THEN fill the prompt, THEN send it to the llm,
# THEN parse the reply."
# Each piece's output becomes the next piece's input, automatically.
# This builds the chain once at startup. It does NOT run anything yet --
# nothing happens until someone calls chain.invoke(...) with real data.
chain = cleaner | prompt | llm | parser
```

And the second chain gets the same treatment:

```python
# The SAME cleaner object, reused. The trimming logic is written once,
# but both chains get it.
simple_chain = cleaner | simple_prompt | llm | parser
```

Notice `clean_input` has **no `import`, no LangChain reference, no decorator**. It's a function that takes a dictionary and returns a dictionary. All the LangChain-ness is in the single `RunnableLambda(...)` line.

### Why a `def` and not a `lambda`?

The class is called `RunnableLambda`, so the obvious move would be:

```python
cleaner = RunnableLambda(lambda d: {"message": d["message"].strip(), "tone": d["tone"]})
```

That works, and it's a bad idea here — three reasons:

1. **It breaks `/simple-chat`.** That chain's input has no `"tone"` key, so `d["tone"]` raises `KeyError`. The named function sidesteps this by only touching `"message"` and passing the rest through untouched.
2. **It can't grow.** Add lowercasing or a length check and you're out of expressions immediately.
3. **It's harder to read**, and unreadable one-liners are exactly what we're avoiding.

**Rule of thumb: `lambda` for one trivial expression, `def` for anything you'd want to test or extend.** Ours is the second kind.

---

## 5. Execution Flow

```
User
 │   POST /chat   {"message": "   \n  What is a set?   \n  ", "tone": "medieval knight"}
 ↓
FastAPI                     validates → request.message, request.tone
 ↓
chain.invoke({...})
 │
 │  ┌───────────────────────────────────────────────────────────────┐
 │  │                                                               │
 │  │  {"message": "   \n  What is a set?   \n  ", "tone": "..."}    │
 │  │            │                                                  │
 │  │            ↓  cleaner  ← NEW. Your own code. No network.      │
 │  │  {"message": "What is a set?",             "tone": "..."}      │
 │  │            │              ^^^^ padding gone                   │
 │  │            ↓  prompt                                          │
 │  │  [SystemMessage, HumanMessage]                                 │
 │  │            │                                                  │
 │  │            ↓  llm             ← the only network hop           │
 │  │  AIMessage(content='Fair sir, a set in Python is...')           │
 │  │            │                                                  │
 │  │            ↓  parser                                          │
 │  │  'Fair sir, a set in Python is...'                              │
 │  │                                                               │
 │  └───────────────────────────────────────────────────────────────┘
 ↓
{"answer": ..., "model": ...}
 ↓
Response
```

The `cleaner` sits at the front, before anything leaves your laptop. `simple_chain` has the identical first step — the *same object*, not a copy.

### Proof both chains changed

```
chain        -> ['RunnableLambda', 'ChatPromptTemplate', 'ChatGroq', 'StrOutputParser']
simple_chain -> ['RunnableLambda', 'ChatPromptTemplate', 'ChatGroq', 'StrOutputParser']
```

Four steps each now, and step 1 is your function in both.

---

## 6. Run the Project

```bash
cd "/Users/purpleslate14mbp/Desktop/Mission G/gen-ai-beginner-basics"

uv run uvicorn app:app --reload
```

Test with deliberately messy input:

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"    \n  What is a set?   \n  ","tone":"medieval knight"}'
```

But the more useful test needs no server at all, because the function is plain Python:

```bash
uv run python -c "
from llm import clean_input, cleaner

print(clean_input({'message': '   What is a set?   ', 'tone': 'pirate'}))
print(cleaner.invoke({'message': '\n\n  hello  \t', 'tone': 'pirate'}))
print(repr(clean_input({'message': '   a     b   '})['message']))
"
```

**Being able to test a chain step directly, with no server and no API key, is the practical reward for keeping the function plain.**

---

## 7. Expected Output

### The function, in isolation

```
=== the plain function ===
{'message': 'What is a set?', 'tone': 'pirate'}

=== the same thing as a runnable ===
{'message': 'hello', 'tone': 'pirate'}

=== strip only touches the ENDS ===
'a     b'
```

Line 1 and line 2 are the same logic reached two ways — `clean_input(...)` directly, and `cleaner.invoke(...)` through the adapter. Identical results, because `RunnableLambda` changes the *interface*, not the behavior.

### Live requests

**`/chat`** with `"    \n  What is a set?   \n  "` and `tone: "medieval knight"`:

```json
{
  "answer": "Fair sir, a set in Python is a collection of unique elements, akin to a noble gathering of distinct knights, where each knight appeareth only once. 'Tis defined by the `set` keyword, and its elements are unordered, like a band of knights assembled for battle.",
  "model": "llama-3.3-70b-versatile"
}
```

**`/simple-chat`** with `"     What is a set?     "` — the same `cleaner`, a different prompt:

```json
{
  "answer": "A set in Python is an unordered collection of unique elements, meaning it stores multiple items without duplicates. For example, `my_set = {1, 2, 3, 2, 1}` will be simplified to `{1, 2, 3}` because sets automatically remove duplicates.",
  "model": "llama-3.3-70b-versatile"
}
```

Both `200`. Neither model saw the padding.

**An honest note on what you can observe:** the visible output is nearly identical to what you'd get *without* the cleaner — models tolerate stray whitespace fine. So don't judge this lesson by the response text. The wins are that the padding never reached the prompt (proven by the isolation test above), and that adding this cost **one** edit to the logic instead of two.

---

## 8. Mini Exercise

**Add lowercasing to the cleaner, then watch it affect both endpoints at once.**

In `clean_input`, add one line after the strip:

```python
    data["message"] = data["message"].lower()
```

Then send `{"message": "WHAT IS A SET?"}` to **both** `/chat` and `/simple-chat`.

Two things to confirm:

1. You edited **one function**, and **two endpoints** changed behavior. That's the whole lesson in one action.
2. Did the answer quality change? Try `{"message": "What is the difference between JSON and Python?"}` lowercased. Lowercasing proper nouns is a *real* downside — worth seeing before you'd ever ship it.

Then remove the lowercasing, keeping the strip.

**Bonus:** try converting `clean_input` into a lambda and putting it in a chain:

```python
cleaner = RunnableLambda(lambda d: d)
```

That works. Now try to make the lambda do *both* the strip and the lowercase. You'll hit the one-expression wall — and that's why we used `def`.

---

## 9. Challenge

**Add a step at the END of the chain, not the beginning.**

Right now `parser` produces the final string. Add a `RunnableLambda` *after* it that appends a signature, so every answer ends with `\n\n— powered by llama-3.3-70b-versatile`.

```python
chain = cleaner | prompt | llm | parser | signer
```

Constraints:

- Write a named function `add_signature`, not a lambda.
- Apply it to `chain` only — leave `simple_chain` unsigned, so you can compare the two endpoints side by side.

Then work through these, because they're where the real learning is:

1. **What type does `add_signature` receive, and what must it return?** It's no longer a dictionary. Check by adding `print(type(text))` inside the function and hitting the endpoint. (Recall Lesson 5 — the parser's output isn't quite what you'd guess.)

2. **Order matters.** Try `cleaner | prompt | llm | signer | parser` — signer *before* the parser. Predict what breaks before you run it. What is `signer` handed in that position?

3. **The interesting one.** Get the model name into the signature without hardcoding it. `llm.model_name` is available in `llm.py`, so this is easy — but ask yourself: your function receives *only* the answer string. How does it know about `llm`? (The answer involves a Python concept you've been using since Lesson 3 without naming it: functions can read module-level variables defined around them.)

4. Once `chain` has five steps and `simple_chain` has four, which pieces are shared objects and which are unique? List them. This is the composability claim from Lesson 6, made concrete.
