# Lesson 11 — PydanticOutputParser

## 1. Problem

Lesson 10 got you a dictionary instead of prose — a large step. But it ended with a warning:

> `JsonOutputParser` validates **syntax**, not **content**.

Here's what that means in practice. Both parsers were fed the same four inputs:

```
=== MISSING a field ===
  json     -> ACCEPTED {'summary': 'a test', 'sentiment': 'negative'}
  pydantic -> OutputParserException

=== wrong TYPE ===
  json     -> ACCEPTED {'summary': 12345, 'sentiment': 'neg', 'language': 'en'}
  pydantic -> OutputParserException
```

**`JsonOutputParser` accepted a reply with `language` missing entirely.** Your endpoint then does:

```python
"language": result["language"]       # KeyError -- 500 to the user
```

The failure moved. Instead of the parser telling you *"the model gave me bad data"*, your endpoint crashes later with a `KeyError` that says nothing about the real cause. You debug your endpoint, when the problem was the model's reply.

Worse, the second case: `"summary": 12345` — a **number** where you need a string. `JsonOutputParser` waves it through, because `{"summary": 12345}` is perfectly valid JSON. Your code then does `result["summary"].strip()` somewhere and dies with `AttributeError: 'int' object has no attribute 'strip'`.

Three problems, all the same shape:

1. **No guarantee the fields you need are there.** You wrote three field names in the prompt; nothing checks the model honored them.
2. **No guarantee of types.** JSON has numbers, booleans, arrays, `null`. Any of them can appear where you expected text.
3. **No autocomplete, no typo protection.** `result["sentement"]` looks fine to your editor and fails at runtime.

You need something that says: *"here is the exact shape I require — verify it before handing it to me."*

---

## 2. New Concepts

### Pydantic, properly this time

You've used Pydantic since Lesson 3 without a proper explanation. Time to fix that.

**Pydantic is a data validation library.** You describe the shape you expect as a class, and Pydantic enforces it.

**`BaseModel`** — the class you inherit from to make a shape:

```python
class ChatResponse(BaseModel):
    summary: str
    sentiment: str
    language: str
```

Read it as: *"a `ChatResponse` has exactly three fields, all strings."* This is the same `class X(BaseModel)` form as `ChatRequest` in `app.py` — but pointed at the model's **output** instead of the user's **input**. Same tool, other end of the pipeline.

**Fields** — each line is a field: a name, a colon, and a type. By default every field is **required**. Add `= something` and it becomes optional with a default (which you discovered yourself in Lesson 5 with `tone: str = "luffy"`).

**`Field(description=...)`** — attaches a human-readable note to a field:

```python
sentiment: str = Field(description="positive, negative or neutral")
```

That description isn't decoration. `PydanticOutputParser` can turn your class into instructions for the model, and the descriptions become part of them.

**Validation** — the actual point. When Pydantic builds a `ChatResponse`, it checks:

- Is every required field present? If not → error.
- Is each value the declared type? If not → error.
- Are there extra fields? → silently dropped (verified below).

Nothing is built unless everything checks out. **You either get a valid object or an exception — never a half-broken object.**

### Analogy: a form vs a passport check

`JsonOutputParser` is a **suggestion box**. You put a note asking for three things. Whatever comes back, you accept and hope.

`PydanticOutputParser` is **passport control**. There's a defined list of required documents. Present them all, correctly typed, and you pass. Miss one, or hand over a driving licence where a passport was required, and you're stopped **at the border** — not three streets later when someone else notices.

The value is *where* the failure happens: at the boundary, immediately, with a message naming what was wrong.

### What is `PydanticOutputParser`?

Another drop-in replacement at the end of a chain — but this one needs to know your class:

```python
pydantic_parser = PydanticOutputParser(pydantic_object=ChatResponse)

report_v2_chain = cleaner | report_prompt | llm | pydantic_parser
#                                                ^^^^^^^^^^^^^^^ only change
```

It does three things in order:

```
model's text  →  1. parse as JSON  →  2. validate against ChatResponse  →  3. build the object
                    (like Json-           (NEW: the actual                  (NEW: an object,
                     OutputParser)         checking)                         not a dict)
```

Step 1 is what Lesson 10 did. Steps 2 and 3 are new.

### The behavior difference, measured

Four inputs through both parsers:

| Input | `JsonOutputParser` | `PydanticOutputParser` |
|---|---|---|
| all three fields, valid | ✅ dict | ✅ `ChatResponse` object |
| **`language` missing** | ✅ accepted — bug waiting | ❌ `OutputParserException` |
| **extra `mood` field** | ✅ kept `mood` | ✅ accepted, **`mood` dropped** |
| **`summary: 12345`** (a number) | ✅ accepted — bug waiting | ❌ `OutputParserException` |

Two rows deserve a closer look.

**Missing field** — this is the headline. Pydantic stops it; the JSON parser hands you a dictionary that will `KeyError` later, somewhere else, for reasons that won't be obvious.

**Extra field** — both "succeed", but differently. The JSON parser keeps `mood`. Pydantic **silently discards** it, because your class doesn't declare it. That's usually what you want (the model's improvisation can't corrupt your data shape) but do notice it's *silent* — if you meant to capture `mood`, nothing warns you that you didn't.

### The output is an object, not a dictionary

This changes how you read it, verified both directions:

```
=== JsonOutputParser (Lesson 10) ===
type -> dict
read -> 'negative'  (square brackets)
dot  -> AttributeError: 'dict' object has no attribute 'sentiment'

=== PydanticOutputParser (Lesson 11) ===
type -> ChatResponse
read -> 'negative'  (dot access)
[..] -> TypeError: 'ChatResponse' object is not subscriptable
```

So the access style flips:

```python
result["sentiment"]     # Lesson 10, dict     → dot access raises AttributeError
result.sentiment        # Lesson 11, object   → ["..."] raises TypeError
```

That's the dictionary-vs-object distinction from Lesson 3 and Lesson 8, showing up a third time. It keeps recurring because it's the most common source of confusion in this whole project. **The rule, restated: `PydanticOutputParser` → dot. Everything else from a chain → brackets.**

And dot access buys you something brackets can't: **your editor knows the field names.** Type `result.` and it offers `summary`, `sentiment`, `language`. Typo `result.sentement` and you get a warning *before* you run the code. With `result["sentement"]` your editor has no idea.

### Bonus: the parser can write the prompt for you

Because `pydantic_parser` knows your class, it can generate format instructions:

```python
pydantic_parser.get_format_instructions()
```

Which produces (abridged):

```
The output should be formatted as a JSON instance that conforms to the JSON schema below.
...
Here is the output schema:
{"properties": {"summary": {"description": "one short sentence summarising the message",
   "type": "string"}, "sentiment": {"description": "positive, negative or neutral",
   "type": "string"}, ...}, "required": ["summary", "sentiment", "language"]}
```

Note it picked up your `Field(description=...)` text and marked all three as `required`. This means the prompt can be **generated from the class** rather than hand-written — so adding a field to the class updates the instructions automatically, and they can never drift apart.

We're **not** using it in the chain yet (that's the mini exercise) because this lesson's only variable should be the parser.

---

## 3. Project Changes

Both files, additive. Nothing to install — Pydantic has been present since Lesson 1, as a FastAPI dependency.

| File | Change | Why |
|---|---|---|
| `llm.py` | `PydanticOutputParser` added to the parser import; new `from pydantic import BaseModel, Field`; the `ChatResponse` class; `pydantic_parser`; `report_v2_chain` | the output contract belongs with the AI code |
| `app.py` | imported `report_v2_chain`; added `ReportV2Request` and `POST /report-v2` | new endpoint, so `/report` survives for comparison |

**`report_v2_chain` reuses `report_prompt` unchanged.** Same prompt, same model, same cleaner — the *only* difference from `/report` is the parser. That's deliberate: any behavior change you observe is caused by validation and nothing else.

`llm.py` now imports from `pydantic` directly for the first time. `app.py` has always done this; now both ends of the pipeline are described with the same tool.

All five older endpoints confirmed `200`.

---

## 4. Complete Code

**`llm.py`** — the imports:

```python
# StrOutputParser turns a model's message object into a plain string.
# JsonOutputParser turns the model's JSON text into a real Python dictionary.
# PydanticOutputParser goes further: it CHECKS the data and builds an object.
from langchain_core.output_parsers import (
    StrOutputParser,
    JsonOutputParser,
    PydanticOutputParser,
)

# BaseModel describes a shape. Field lets us describe each individual value.
from pydantic import BaseModel, Field
```

New code at the bottom:

```python
# ----- Lesson 11: describe the answer as a CLASS, and check it -----

# The SHAPE we expect back, written as a class -- exactly like ChatRequest
# in app.py, but describing the model's OUTPUT instead of the user's input.
# Field(description=...) is a note for the model about what belongs here.
class ChatResponse(BaseModel):
    summary: str = Field(description="one short sentence summarising the message")
    sentiment: str = Field(description="positive, negative or neutral")
    language: str = Field(description="the language the message is written in")


# This parser knows about ChatResponse, so it can CHECK the model's reply
# against it. If a field is missing or has the wrong type, it refuses.
pydantic_parser = PydanticOutputParser(pydantic_object=ChatResponse)


# The prompt is the same one from Lesson 10 -- we only swap the parser,
# so the difference we see is caused by validation and nothing else.
report_v2_chain = cleaner | report_prompt | llm | pydantic_parser
```

**`app.py`** — the new endpoint:

```python
class ReportV2Request(BaseModel):
    message: str


@app.post("/report-v2")
def report_v2(request: ReportV2Request):
    # This chain ends with PydanticOutputParser, so "result" is a
    # ChatResponse OBJECT -- already checked against the class.
    result = report_v2_chain.invoke({"message": request.message})

    # DOT access now, not ["..."], because it is an object and not a dictionary.
    # Your editor can even autocomplete these field names.
    return {
        "summary": result.summary,
        "sentiment": result.sentiment,
        "language": result.language,
        "model": llm.model_name,
    }
```

Notice this endpoint has **no defensive code**. No `if "language" in result`, no `.get("sentiment", "unknown")`, no `try`. It doesn't need any, because if the code reaches line one of that `return`, the object is already valid. **Validation at the boundary removes checks everywhere downstream.**

---

## 5. Execution Flow

```
User
 │   POST /report-v2   {"message": "I am so frustrated about the water issue..."}
 ↓
FastAPI                    ← Pydantic validates the INPUT (since Lesson 3)
 ↓
report_v2_chain.invoke({...})
 │
 │  ┌────────────────────────────────────────────────────────────────────────┐
 │  │  {"message": "..."}                                                     │
 │  │            ↓  cleaner                                                   │
 │  │            ↓  report_prompt                                             │
 │  │            ↓  llm                    ← ONE network call                  │
 │  │  AIMessage(content='{"summary": "...", "sentiment": "negative", ...}')   │
 │  │            │                                                            │
 │  │            ↓  pydantic_parser                                           │
 │  │            │                                                            │
 │  │            ├─ step 1: read the text as JSON        → a dict             │
 │  │            ├─ step 2: check against ChatResponse   → ALL FIELDS?        │
 │  │            │                                          RIGHT TYPES?      │
 │  │            │            ✗ no → OutputParserException, stop here         │
 │  │            └─ step 3: ✓ yes → build the object                          │
 │  │                                                                         │
 │  │  ChatResponse(summary='...', sentiment='negative', language='english')   │
 │  └────────────────────────────────────────────────────────────────────────┘
 ↓
result.sentiment  →  'negative'      ← dot access, autocompleted
 ↓
Response
```

Your pipeline is now **validated at both ends**:

```
user's JSON  →  [ChatRequest checks it]  →  chain  →  [ChatResponse checks it]  →  your code
                 ^^^^^^^^^^^^^^ Lesson 3               ^^^^^^^^^^^^^^^ Lesson 11
```

Untrusted data enters through a gate and leaves through a gate. Everything between them can assume the data is well-formed — which is why neither the endpoint nor the chain needs defensive checks.

---

## 6. Run the Project

```bash
cd "/Users/purpleslate14mbp/Desktop/Mission G/gen-ai-beginner-basics"

uv run uvicorn app:app --reload
```

**Seven** endpoints. Try `POST /report-v2`:

```bash
curl -X POST http://127.0.0.1:8000/report-v2 -H "Content-Type: application/json" \
  -d '{"message":"I am so frustrated right now because of a water issue in my apartment."}'
```

### The experiment that teaches the lesson

Feed both parsers deliberately broken data. No server, no tokens spent:

```bash
uv run python -c "
from llm import json_parser, pydantic_parser

bad = '{\"summary\": \"a test\", \"sentiment\": \"negative\"}'    # language MISSING

print('json     ->', json_parser.invoke(bad))
try:
    pydantic_parser.invoke(bad)
except Exception as e:
    print('pydantic ->', type(e).__name__)
    print(str(e)[:300])
"
```

**Read that exception carefully.** It names the missing field. That message is the entire value proposition of this lesson.

### See the access style flip

```bash
uv run python -c "
from llm import report_chain, report_v2_chain
text = 'I am so frustrated about the water issue.'

d = report_chain.invoke({'message': text})
print('Json     ->', type(d).__name__, '| d[\"sentiment\"] =', repr(d['sentiment']))

o = report_v2_chain.invoke({'message': text})
print('Pydantic ->', type(o).__name__, '| o.sentiment    =', repr(o.sentiment))
print('full object ->', o)
"
```

### And see the generated instructions

```bash
uv run python -c "
from llm import pydantic_parser
print(pydantic_parser.get_format_instructions())
"
```

---

## 7. Expected Output

**A — normal request** (`200`, 0.46s):
```json
{
  "summary": "user is experiencing frustration due to a water issue",
  "sentiment": "negative",
  "language": "english",
  "model": "llama-3.3-70b-versatile"
}
```

**B — Tamil input:**
```json
{
  "summary": "the user mentions python lists are modifiable",
  "sentiment": "neutral",
  "language": "tamil",
  "model": "llama-3.3-70b-versatile"
}
```

**Identical JSON shape to `/report`.** Same fields, same values, same speed (0.46s vs 0.38s — within noise). From the outside, nothing changed.

**That's expected, and it's the point.** The gain isn't in the happy path — it's in what happens when the model misbehaves. On a good day both endpoints are equivalent. On a bad day one raises a clear exception naming the problem and the other hands you corrupt data.

### The validation, seen directly

```
=== MISSING a field ===
  json     -> ACCEPTED {'summary': 'a test', 'sentiment': 'negative'}
  pydantic -> OutputParserException : Failed to parse ChatResponse from completion
                                      {"summary": "a test", "sentiment": "negative"}

=== wrong TYPE ===
  json     -> ACCEPTED {'summary': 12345, ...}
  pydantic -> OutputParserException : Failed to parse ChatResponse from completion
                                      {"summary": 12345, ...}
```

### The access flip, seen directly

```
=== JsonOutputParser (Lesson 10) ===
type -> dict
read -> 'negative' (square brackets)
dot  -> AttributeError: 'dict' object has no attribute 'sentiment'

=== PydanticOutputParser (Lesson 11) ===
type -> ChatResponse
read -> 'negative' (dot access)
[..] -> TypeError: 'ChatResponse' object is not subscriptable

the whole object -> summary='user is experiencing frustration due to a water issue'
                    sentiment='negative' language='english'
```

That last line is `print()` on a Pydantic object — it shows every field and value. Genuinely useful when debugging; `print(dict)` gives you the same information but noisier.

### One honest limitation

Pydantic validated *presence* and *type*. It did **not** validate the *value*. Right now `sentiment: str` accepts:

```python
"negative"        ✓ what you wanted
"Negative."       ✓ also accepted -- it IS a string
"banana"          ✓ also accepted
```

Your Lesson 8 bug is **still possible**. `str` means "any text", and `"Negative."` is text. To constrain the *set* of allowed values you need a stricter type than `str` — that's the Challenge.

### Regressions
```
/chat -> 200   /simple-chat -> 200   /ask -> 200   /report -> 200   /analyze -> 200
```

---

## 8. Mini Exercise

**Let the class write the prompt.**

Right now `report_prompt` has the JSON shape hand-typed with doubled braces, *and* `ChatResponse` describes the same shape in Python. Two descriptions of one thing — they can drift apart.

Fix it so the class is the single source of truth:

**Step 1** — a new prompt with a placeholder for the instructions:

```python
REPORT_V2_SYSTEM_PROMPT = """You analyse the user's message.

{format_instructions}

Reply with the JSON object only."""
```

Note: **no doubled braces needed.** The schema arrives as a *value*, and values aren't scanned for placeholders.

**Step 2** — fill that placeholder once, at startup, with `.partial()`:

```python
report_v2_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", REPORT_V2_SYSTEM_PROMPT),
        ("human", "{message}"),
    ]
).partial(format_instructions=pydantic_parser.get_format_instructions())
```

`.partial()` means *"fill in this blank permanently, now."* `{message}` stays empty for each request.

**Step 3** — point the chain at the new prompt and test the endpoint.

Then the questions:

1. Add a fourth field to `ChatResponse` — `word_count: int`. **How many places did you edit?** With the old hand-written prompt it would be two. Does the model now return it without you touching the prompt at all?
2. `word_count: int` — an integer, not a string. What happens if the model replies `"word_count": "twelve"`? Try to make it fail, and read the error.
3. Change a `Field(description=...)` — say `sentiment` to `"one lowercase word: positive, negative or neutral"`. Print the format instructions again. Did the description reach the model?

---

## 9. Challenge

**Make `"Negative."` impossible, not just unlikely.**

Your Lesson 8 bug survives: `sentiment: str` accepts any text at all. Close it for real.

**Part 1 — restrict the allowed values.** Python has a type for "one of exactly these":

```python
from typing import Literal


class ChatResponse(BaseModel):
    summary: str = Field(description="one short sentence")
    sentiment: Literal["positive", "negative", "neutral"] = Field(
        description="exactly one of: positive, negative, neutral"
    )
    language: str = Field(description="the language the message is written in")
```

`Literal[...]` means the value must be **exactly** one of those three strings. Not `"Negative"`, not `"negative."`, not `"very negative"`.

Then:

1. Test it directly with `pydantic_parser.invoke('{"summary": "a", "sentiment": "Negative.", "language": "en"}')`. It should now be rejected. Read the error — does it list the allowed values?
2. Print `get_format_instructions()` again. Did the enum reach the schema? (It should appear as `"enum": [...]`.) This matters: you're not just rejecting bad values, you're **telling the model exactly what's acceptable** — so it's less likely to produce a bad one in the first place.
3. Hit `/report-v2` about ten times with different messages. Any failures? Compare against the four-out-of-four you got in Lesson 10 — this is now *enforced* rather than *observed*.

**Part 2 — the hard question: what should happen when validation fails?**

You've made failures loud, which is right. But loud means `OutputParserException`, which means FastAPI returns a bare `500` with no explanation. That's worse for your users than the silent-corruption version.

Work out what you'd do:

4. What *should* `/report-v2` return when the model produces an invalid sentiment? A `500`? A `502` (bad upstream)? A `200` with `sentiment: "unknown"`? Pick one and justify it.
5. **Retrying** is the standard answer — ask the model again, telling it what was wrong. Sketch how you'd do that with what you know. Where would the retry live: in the endpoint, in a `RunnableLambda`, or somewhere else? What stops it looping forever?
6. What if the model is *reliably* wrong — say it always returns `"Negative"` capitalized? Retrying won't help. Would you loosen the validation, or add a normalizing step before the parser? Where in the chain would that step go, and which Lesson-7 tool would you build it with?

Question 6 is the one to sit with. **Validation tells you the data is wrong; it doesn't tell you whose fault it is or how to fix it.** Deciding that is engineering judgement, and it's the last thing a library can do for you.
