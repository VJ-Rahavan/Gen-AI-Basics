# Lesson 5 — Output Parsers

## 1. What are we building?

Nothing new from the outside. `POST /chat` behaves identically. This lesson is about the *shape of your code*.

We remove `result.content` — that little reach-into-an-object you've been living with since Lesson 3 — and replace it with a **parser**. The endpoint stops needing to know how a model reply is packaged.

Both files change. No new files, nothing to install.

---

## 2. New Concepts

### Why does LangChain return a message object instead of a string?

You've written this twice now and it probably felt like friction:

```python
result = llm.invoke(messages)
result.content          # ← why the extra step?
```

Because **the text is not the only thing that comes back.** Let me show you the real object rather than describe it. I ran your code and printed the raw return value:

```
type   -> AIMessage
value  -> AIMessage(content='A list in Python is like a treasure chest that can hold ...
```

An `AIMessage` carries the text **plus** everything else the model reported:

| Also on the object | What it's for |
|---|---|
| `response_metadata` | token counts, finish reason, timing |
| `id` | identifies this specific reply |
| `tool_calls` | when the model wants to call a function you gave it |
| `usage_metadata` | how much this request cost you |

If `.invoke()` returned a bare string, all of that would be thrown away. LangChain can't know in advance whether you want the token count or just the words, so it hands you **everything** and lets you decide.

Remember Lesson 4's message list — `SystemMessage`, `HumanMessage`? `AIMessage` is the third member of that family. The model's reply comes back in the same shape the inputs go in. That symmetry is the point: an `AIMessage` can be appended straight onto your message list to build a conversation, which is exactly how chat memory works.

### So why convert it to a string?

Because **most of the time you only want the words**, and reaching into an object every time has real costs:

**1. Your endpoint knows too much.** `result.content` means `app.py` has knowledge of LangChain's internal message format. If that format ever changes, your HTTP layer breaks. The parser absorbs that.

**2. It's a per-call detail that never varies.** You write the same `.content` in every endpoint forever. Say it once instead.

**3. Strings are what the rest of your program wants.** JSON responses, string methods, templates, logs — all want text. After parsing:

```
string methods now work:
  .upper()[:30] -> A LIST IN PYTHON IS LIKE A TRE
  len()         -> 288
```

**4. It's a swappable slot.** This is the real reason. `StrOutputParser` is one of a family:

| Parser | Gives you |
|---|---|
| `StrOutputParser` | a plain string |
| `JsonOutputParser` | a parsed dictionary |
| `PydanticOutputParser` | a validated object of your own class |
| `CommaSeparatedListOutputParser` | a Python list |

By making "extract the output" a named, separate step, you can change *what shape your data arrives in* by swapping one line — instead of rewriting how your endpoint reads its result. `.content` hardcodes you to "raw text, always."

### The parser uses `.invoke()` too — and that's deliberate

Look closely at the new line:

```python
answer = parser.invoke(result)
```

Same method name you already use on the model. That is not a coincidence. In LangChain, prompts, models, and parsers all implement **one shared interface** with an `.invoke()` method. Anything with that interface is called a **Runnable**.

Which means your three steps are now three interchangeable pieces with the same plug shape:

```python
messages = prompt.format_messages(message=..., tone=...)   # a Runnable
result   = llm.invoke(messages)                            # a Runnable
answer   = parser.invoke(result)                           # a Runnable
```

Notice each one's output feeds directly into the next one's input. When three things share an interface and line up end to end, there's an obvious way to connect them — LangChain spells it `prompt | llm | parser`, and that's **LCEL**, the next thing you'd learn. We're deliberately not using it yet. Writing the three steps out by hand means you can *see* what flows between them; the pipe hides that, and hidden things are hard to debug when you're new.

### An honest wrinkle: it isn't literally `str`

I checked what the parser actually returns, and it surprised me:

```
type           -> <class 'langchain_core.messages.base.TextAccessor'>
isinstance str -> True
mro            -> ['TextAccessor', 'str', 'object']
```

Not a `str` — a `TextAccessor`. But look at the second line: **`isinstance(out, str)` is `True`**. `TextAccessor` *inherits from* `str`.

That's the same inheritance you met in Lesson 3, when `ChatRequest(BaseModel)` meant "a kind of BaseModel." Here, `TextAccessor(str)` means "a kind of string" — it has every string method and behaves like one everywhere:

```
== "hello world" -> True
json.dumps       -> {"answer": "hello world"}
```

That last line is the one that matters for us: FastAPI serializes it as a normal JSON string. The `mro` line is the "method resolution order" — the chain Python walks to find a method. `TextAccessor` → `str` → `object`. When you call `.upper()`, Python doesn't find it on `TextAccessor`, walks up to `str`, finds it there.

So: it's a string with a few extras bolted on, in recent `langchain-core` versions. **Treat it as a string.** I'm telling you because if you ever `print(type(...))` while debugging, you'd otherwise think something had gone wrong.

---

## 3. Project Structure

```
gen-ai-beginner-basics/
    app.py              ← MODIFIED: three steps, no more .content
    llm.py              ← MODIFIED: added the parser
    .env
    pyproject.toml      ← unchanged, nothing to install
    README.md
    docs/
    .venv/
```

The parser goes in `llm.py` for the same reason the prompt did: **`app.py` is HTTP, `llm.py` is AI.** All three AI pieces now live together.

---

## 4. Complete Code

**`llm.py`** (complete file — with your `{tone}` version of the prompt)

```python
# python-dotenv reads the .env file and loads each line into "environment variables"
from dotenv import load_dotenv

# ChatGroq is LangChain's wrapper around Groq's chat models
from langchain_groq import ChatGroq

# ChatPromptTemplate builds a reusable, fill-in-the-blank list of chat messages
from langchain_core.prompts import ChatPromptTemplate

# StrOutputParser turns a model's message object into a plain string
from langchain_core.output_parsers import StrOutputParser


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


# The SYSTEM prompt: standing instructions. Written by us, never by the user.
# Triple quotes """ """ let a string span multiple lines.
SYSTEM_PROMPT = """You are a {tone} who happens to be an expert Python programmer.

Answer every question accurately, but speak like a {tone}.
Never use more than two sentences."""


# The template: a reusable recipe for the list of messages we send to the model.
# The [ ] is a LIST (like a JS array). Each ( ) inside is a TUPLE: a fixed pair
# of (role, text). The two roles here are "system" and "human".
prompt = ChatPromptTemplate.from_messages(
    [
        # Sent every single time, unchanged.
        ("system", SYSTEM_PROMPT),
        # {message} is a PLACEHOLDER, not Python syntax.
        # LangChain fills it in later with the user's actual text.
        ("human", "{message}"),
    ]
)


# The parser: takes the model's reply object and gives back just the text.
# Created once here, reused for every request -- it holds no state.
parser = StrOutputParser()
```

**`app.py`** — the import line and the `chat()` body:

```python
# Import our own file, llm.py, and take THREE things out of it now.
# No "./" and no ".py" -- Python finds llm.py because it sits next to this file.
from llm import llm, prompt, parser
```

```python
# POST, not GET, because the client needs to SEND data in the request body.
@app.post("/chat")
def chat(request: ChatRequest):
    # "request: ChatRequest" is a parameter with a TYPE HINT after the colon.
    # Because the type is a BaseModel, FastAPI reads the JSON body, validates it,
    # and hands us a ready-made ChatRequest object.
    # Dot access here (not ["..."]) -- it is an object, not a dictionary.

    # STEP 1: fill the template's {message} placeholder with the user's text.
    # "message=" is a KEYWORD ARGUMENT -- the name must match the placeholder.
    # This returns a LIST of two messages: our system message, then the human one.
    messages = prompt.format_messages(message=request.message,tone="Luffy")

    # STEP 2: send that whole list of messages to Groq and wait for the reply.
    # .invoke() returns a MESSAGE OBJECT, not a plain string.
    result = llm.invoke(messages)

    # STEP 3: turn that message object into a plain string.
    # The parser does the ".content" reach-in for us, so our endpoint no longer
    # needs to know how a model reply is shaped. Note it is .invoke() again --
    # prompts, models and parsers all share the same one-method interface.
    answer = parser.invoke(result)

    # A dictionary can hold as many key/value pairs as we like, separated by commas.
    # "answer" is now already a string, so there is nothing left to unwrap here.
    # llm.model_name asks the llm object which model it is -- so the name is stored
    # in ONE place (llm.py). Typing "llama-3.3-70b-versatile" again here would mean
    # two copies to keep in sync, and one of them would eventually be wrong.
    return {
        "answer": answer,
        "model": llm.model_name,
    }
```

I left `tone="Luffy"` exactly as you wrote it — see the note in section 8.

---

## 5. How It Works

```
Client
 │   POST /chat   {"message": "What is a virtual environment?"}
 ↓
FastAPI                          request.message
 ↓
prompt.format_messages(...)      ← STEP 1: local
 │   → [SystemMessage, HumanMessage]
 ↓
llm.invoke(messages)             ← STEP 2: over the internet, to Groq
 │   → AIMessage(content='...', response_metadata={...}, usage_metadata={...})
 │        ^^^^^^^ we want this   ^^^^^^^^^^ we ignore all of this
 ↓
parser.invoke(result)            ← STEP 3: local, NEW
 │   → 'Ooooh, virtual environment be like...'     just the text
 ↓
{"answer": ..., "model": ...}
```

Steps 1 and 3 are both local and free — they're pure data reshaping. Only step 2 costs time and money. And notice the symmetry the parser creates: **step 1 builds the input structure, step 3 tears down the output structure**, and the model sits in the middle dealing only in message objects.

---

## 6. Run the Project

```bash
cd "/Users/purpleslate14mbp/Desktop/Mission G/gen-ai-beginner-basics"

uv run uvicorn app:app --reload
```

http://127.0.0.1:8000/docs → **`POST /chat`** → **Try it out**:

```json
{ "message": "What is a virtual environment?" }
```

### See the conversion with your own eyes

This is the exercise that makes the lesson click. No server needed:

```bash
uv run python -c "
from llm import llm, prompt, parser

messages = prompt.format_messages(message='What is a list?', tone='Luffy')
result = llm.invoke(messages)

print('BEFORE ->', type(result).__name__)
print('AFTER  ->', repr(parser.invoke(result))[:80])
"
```

---

## 7. Expected Output

The live call I ran against your code:

```json
{
  "answer": "Ooooh, virtual environment be like a special box where I can play with different Python powers without messin' up me main ship, I mean, me main Python installation! It helps me keep all me project's treasures, like libraries and dependencies, separate and organized, yeah!",
  "model": "llama-3.3-70b-versatile"
}
```

`200 OK`. Two sentences, correct explanation, in character — your Lesson 4 system prompt and Lesson 5 parser working together.

**The response JSON is byte-for-byte the same shape as before this lesson.** That's the expected result, and it's worth sitting with: this was a **refactor**, not a feature. The output didn't change; the structure of your code did. Recognizing when you're doing one versus the other is a genuinely useful engineering habit.

And the before/after from the direct Python run:

```
BEFORE the parser
  type   -> AIMessage
  value  -> AIMessage(content='A list in Python is like a treasure chest that can hold ...

AFTER the parser
  type   -> TextAccessor
  value  -> 'A list in Python is like a treasure chest that can hold lots of different
             things, ... all stored in a row like my crewmates on the Thousand Sunny!'

string methods now work:
  .upper()[:30] -> A LIST IN PYTHON IS LIKE A TRE
  len()         -> 288
```

An object went in; something you can call `len()` on came out.

---

## 8. Mini Exercise

**1. See what you were throwing away.** Add this line temporarily, just before `return`:

```python
    print(result.usage_metadata)
```

Call the endpoint and look at the **server terminal**. You'll see the input tokens, output tokens, and total for that request — real cost data, sitting on the object your parser discards. Then remove the line.

The lesson: the parser is a *convenience*, not the truth. The full object is still there whenever you need it.

**2. Prove `TextAccessor` really is a string.** In the direct-Python command from section 6, add:

```python
answer = parser.invoke(result)
print(isinstance(answer, str))
print(answer.split()[:5])
print(answer.replace('Python', 'Snake')[:60])
```

All three should work with no complaints.

**3. Finish the `{tone}` exercise properly.** You added `{tone}` to the prompt and hardcoded `tone="Luffy"` in `app.py` — which works, but pins every user to one personality. Make it per-request instead:

- add `tone: str` to the `ChatRequest` class
- change the call to `prompt.format_messages(message=request.message, tone=request.tone)`

Then send `{"message": "What is a list?", "tone": "medieval knight"}` and `{"message": "What is a list?", "tone": "sarcastic teenager"}` back to back.

While you're there — `format_messages(message=request.message,tone="Luffy")` is missing a space after the comma. Python doesn't care, but PEP 8 (the style guide every Python codebase follows) wants `, ` between arguments. Small thing; worth building the habit now.

---

# Series complete

Five lessons, and you have a working AI API. What you actually learned:

| | Python | LangChain / FastAPI |
|---|---|---|
| **1** | virtual environments, `pyproject.toml`, `import` | uvicorn, ASGI |
| **2** | `def`, `return`, dictionaries, indentation, **decorators** | endpoints, HTTP methods, JSON, Swagger |
| **3** | **classes**, inheritance, type hints, env vars | `ChatGroq`, `.invoke()`, Pydantic validation |
| **4** | lists, tuples, keyword args, triple-quoted strings, constants | `ChatPromptTemplate`, system vs human roles |
| **5** | inheritance again (`str` subclass), refactoring | `StrOutputParser`, the Runnable interface |

Your final project is five files, `app.py` is under 70 lines, and every line has a reason you could explain.

**Where you'd go next**, in order:

1. **LCEL** — `chain = prompt | llm | parser`, collapsing your three steps into one composable object. You've already met all three pieces; only the syntax is new.
2. **Streaming** — `.stream()` instead of `.invoke()`, so words appear as they're generated instead of after a 2-second wait.
3. **Memory** — appending `AIMessage` back onto the message list so the assistant remembers the conversation. This is why Lesson 4's "roles" detour mattered.
4. **Error handling** — right now a bad key gives your users a bare `500`. `try`/`except` and FastAPI's `HTTPException` fix that.

---

## Addendum — Exercise 3, worked (per-request `tone`)

All four tests pass. The submitted version is **better than the exercise asked for**.

### Test results

| Test | Result |
|---|---|
| `{"message":"What is a list?","tone":"medieval knight"}` | `200` — *"a collection of items, akin to a noble's retinue... 'Tis a most useful data structure"* |
| `{"message":"What is a list?","tone":"sarcastic teenager"}` | `200` — *"stores a collection of items in a specific order, **duh**... okay?"* |
| `{"message":"What is a list?"}` — tone omitted | `200` — *"like me treasure chest filled with goodies... **arrr!**"* ← default kicked in |
| `{"tone":"pirate"}` — message omitted | `422` — validation still catches the missing field |

Same question all three times. Three completely different voices, one correct answer each.

`print(result.usage_metadata)` from exercise 1 also works — the server terminal shows:

```
{'input_tokens': 73, 'output_tokens': 58, 'total_tokens': 131}
{'input_tokens': 75, 'output_tokens': 45, 'total_tokens': 120}
{'input_tokens': 73, 'output_tokens': 57, 'total_tokens': 130}
```

### The code

```python
class ChatRequest(BaseModel):
    message: str
    tone: str = "luffy"  # Default value if the user doesn't provide one
```

```python
    messages = prompt.format_messages(message=request.message, tone=request.tone)
```

### New concept: default values

The exercise said to add `tone: str`. This version adds `= "luffy"` as well — a **default value**, which changes the field from *required* to *optional*: if the JSON has no `tone`, Pydantic fills in `"luffy"` instead of rejecting the request.

This matters more than it looks. With a plain `tone: str`, the field would have been **required**, and every existing caller sending only `{"message": "..."}` would have started failing with a 422. The default keeps them all working. That is backward compatibility.

FastAPI picks it up automatically. The generated schema:

```json
"tone": { "type": "string", "default": "luffy" },
...
"required": ["message"]
```

`message` is in `required`; `tone` isn't, and carries its default. Swagger UI reads this, so `/docs` shows `tone` as optional with `luffy` pre-filled — free documentation from four characters of code.

**The rule to remember:** in Python, a default makes something optional. This works in function parameters too:

```python
def greet(name, greeting="Hello"):    # greeting is optional
    return greeting + " " + name

greet("Vijay")              # "Hello Vijay"
greet("Vijay", "Hi")        # "Hi Vijay"
```

One strict catch — **in a function signature, defaults must come last**:

```python
def f(a=1, b):     # SyntaxError: non-default argument follows default argument
```

Pydantic classes are more forgiving about field order, but the function rule is absolute.

### Two small things

1. `message=request.message,tone=request.tone` is missing the space after the comma. PEP 8 wants `, `. Python does not care; humans reading the code do.
2. The `print(result.usage_metadata)` line was meant to be temporary. Keeping it is fine, but a real app would use `logging` instead — `print` writes straight to stdout with no severity level and no way to switch it off in production.
