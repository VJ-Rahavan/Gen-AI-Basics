# Lesson 9 — RunnableBranch

## 1. Problem

Every chain you have applies **one prompt to every input**. `/chat` speaks like a pirate whether you ask about tuples or about Shakespeare. `/simple-chat` explains everything as Python, even when the question isn't about Python.

That's a real limitation, because good system prompts are *specific*. Compare:

```
"You are a senior software engineer. Include a short code example."
"You are a friendly assistant. Answer in plain everyday language."
```

Each is excellent for its own kind of question and wrong for the other. A coding prompt asked *"Who wrote Hamlet?"* will awkwardly reach for code. A general prompt asked about `IndexError` gives you a vague paragraph instead of the fix.

The obvious workaround is to merge them:

```
"You are an assistant. If the question is about programming, act like an
engineer and include code. Otherwise answer in plain language. Also..."
```

This is how most people start, and it degrades badly. The prompt gets long, the instructions start to conflict, and the model follows them inconsistently — you're asking it to do the routing *and* the answering in one pass.

`RunnableMap` doesn't help here. It runs **all** branches; you'd pay for both answers and then throw one away.

What you need is **one input, several possible paths, exactly one taken.** That's `RunnableBranch`.

---

## 2. New Concepts

### What is `RunnableBranch`?

`RunnableBranch` picks **one** runnable to run, based on a condition.

```python
routed_chain = RunnableBranch(
    (is_coding_question, coding_chain),   # if the condition is True, use this
    general_chain,                        # otherwise, use this (the default)
)
```

You give it a series of `(condition, runnable)` pairs, and one final runnable with **no** condition. On invoke it:

1. Tests the first condition against the input.
2. If `True` → runs that runnable, and **stops**. Nothing else is tried.
3. If `False` → moves to the next pair.
4. If nothing matched → runs the default.

### It is genuinely just `if/elif/else`

The mapping is exact:

```python
# plain Python                        # RunnableBranch
if is_coding_question(data):          RunnableBranch(
    result = coding_chain(data)           (is_coding_question, coding_chain),
else:                                     general_chain,
    result = general_chain(data)      )
```

So why use the LangChain version instead of writing the `if`?

**Because the result is a runnable.** An `if` statement inside your endpoint is a statement — it can't be composed. `routed_chain` is an object you can put in a `|` pipeline, drop into a `RunnableMap` branch, or nest inside another branch. It's the same argument as Lesson 6: statements don't compose; objects do.

Notice we did exactly that:

```python
ask_chain = cleaner | routed_chain
```

The cleaner runs, then the branch routes. You cannot write that line with an `if` statement.

### Analogy: a hospital reception desk

You walk into a hospital and describe your problem to reception. They don't treat you — they **route** you:

```
"chest pain"      → cardiology
"broken wrist"    → orthopaedics
anything else     → general practice     ← the default
```

Three properties worth noting, because they're exactly `RunnableBranch`'s:

- You go to **one** department, not all of them.
- Each department has its own specialists and its own approach — the equivalent of a focused system prompt.
- **There's always a default.** A hospital that turned you away because your symptom wasn't on the list would be broken. Same for your chain: the last entry has no condition precisely so *something* always handles the input.

### Branch vs Map — the distinction to keep straight

```
RunnableMap        (parallel, ALL branches)
                    ┌→ [A] →┐
   input ──(copy)───┼→ [B] →┼──→ {"a":…, "b":…, "c":…}     all 3 run
                    └→ [C] →┘                              3 LLM calls

RunnableBranch     (routing, ONE branch)
                    ┌→ [A]      ← condition 1 True? take this and stop
   input ──(test)───┼→ [B]      ← else condition 2?
                    └→ [C]      ← else the default
                       └────────→ one result                1 LLM call
```

| | `RunnableMap` | `RunnableBranch` |
|---|---|---|
| How many branches run | **all** | **exactly one** |
| Output | a dictionary of all results | the result of the chosen branch |
| Cost | sum of all branches | cost of one branch |
| Use when | you want several things about one input | you want the right handler for this input |

### The condition function

The condition is an ordinary function that must return `True` or `False`:

```python
def is_coding_question(data):
    message = data["message"].lower()
    for keyword in CODING_KEYWORDS:
        if keyword in message:
            return True
    return False
```

Two important properties:

- **It receives the same input the branches receive.** Ours gets `{"message": "..."}`, so it reads `data["message"]`. If the branch input were a plain string, the condition would receive a plain string.
- **It's plain Python.** No `RunnableLambda` wrapper needed — `RunnableBranch` calls it directly. And because it's plain, you can test it with a dictionary and no network.

### The Python features inside it

Four new things, all fundamental.

**`True` and `False`** — Python's booleans. Note the capital letters; `true` is an error. (JavaScript uses lowercase `true`/`false`.)

**`if` — conditional execution.** Colon, then an indented block:

```python
if keyword in message:
    return True
```
```javascript
if (message.includes(keyword)) { return true; }   // JS: parentheses and braces
```

No parentheses around the condition, no braces — indentation again.

**`for ... in ...` — repeat once per item.** This is Python's main loop, and it's simpler than JavaScript's:

```python
for keyword in CODING_KEYWORDS:
    print(keyword)              # runs 14 times, once per keyword
```
```javascript
for (const keyword of CODING_KEYWORDS) { console.log(keyword); }
```

No counter, no index, no `i++`. It hands you each item directly. Read it as *"for each keyword in the list."*

**`in` — two meanings, depending on context.** This one genuinely trips people up:

```python
for keyword in CODING_KEYWORDS:   # in a for-loop: "take each item from"
if keyword in message:            # as a test: "is this contained in that?"
```

Same word, different jobs. As a test on a string, `in` asks *"does this string contain that smaller string?"* — like JavaScript's `.includes()`.

**And `return` exits immediately.** The moment one keyword matches, `return True` ends the function — the remaining keywords are never checked. The final `return False` is reached only if the loop finished with no match. That early exit is idiomatic and efficient.

---

## 3. Project Changes

Both files, purely additive. Nothing to install.

| File | Change | Why |
|---|---|---|
| `llm.py` | added `RunnableBranch` to imports; two new system prompts; two new prompt templates; `coding_chain` and `general_chain`; the `CODING_KEYWORDS` list; the `is_coding_question` function; `routed_chain`; `ask_chain` | routing is AI plumbing |
| `app.py` | imported `ask_chain` and `is_coding_question`; added `AskRequest` and `POST /ask` | new capability, new endpoint |

Nothing existing was touched — `/chat`, `/simple-chat` and `/analyze` all still work (confirmed `200`).

**Note the condition function is imported into `app.py` too.** Not for routing — the branch handles that — but so the response can *report* which route was taken. That's a small deliberate duplication: the function runs twice per request. It costs nothing (no LLM call, just string checks) and makes the endpoint's behavior visible to whoever calls it. Worth knowing you're doing it, though.

---

## 4. Complete Code

**`llm.py`** — updated import:

```python
# RunnableLambda turns any ordinary Python function into a chain component.
# RunnableMap runs several runnables AT THE SAME TIME on the same input.
# RunnableBranch picks ONE runnable to run, based on a condition.
from langchain_core.runnables import RunnableLambda, RunnableMap, RunnableBranch
```

New code, appended at the bottom:

```python
# ----- Lesson 9: send the question to the right specialist -----

CODING_SYSTEM_PROMPT = """You are a senior software engineer.

Answer the programming question precisely.
Include a very short code example when it helps.
Never use more than three sentences."""

GENERAL_SYSTEM_PROMPT = """You are a friendly, knowledgeable assistant.

Answer the question clearly, in plain everyday language.
Never use more than three sentences."""


coding_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", CODING_SYSTEM_PROMPT),
        ("human", "{message}"),
    ]
)

general_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", GENERAL_SYSTEM_PROMPT),
        ("human", "{message}"),
    ]
)


coding_chain = coding_prompt | llm | parser
general_chain = general_prompt | llm | parser


# A LIST of words that suggest a programming question.
# This is a crude test, and that is fine for now -- see the lesson notes.
CODING_KEYWORDS = [
    "python",
    "javascript",
    "code",
    "function",
    "error",
    "bug",
    "api",
    "list",
    "dictionary",
    "loop",
    "class",
    "variable",
    "install",
    "syntax",
]


# THE CONDITION. An ordinary function that must return True or False.
# It receives the same dictionary the branches will receive.
def is_coding_question(data):
    # .lower() so "Python" and "python" both match.
    message = data["message"].lower()

    # "for X in Y" repeats the indented block once for every item in the list.
    for keyword in CODING_KEYWORDS:
        # "in" on a string asks: does this string contain that smaller string?
        if keyword in message:
            # Found one -- we are done, no need to check the rest.
            return True

    # The loop finished without finding anything.
    return False


# THE BRANCH. Each ( ) is a pair: (condition, runnable to use if it is True).
# The LAST item has no condition -- it is the default, used when nothing matched.
routed_chain = RunnableBranch(
    (is_coding_question, coding_chain),
    general_chain,
)


# Clean the input first, then route it to exactly ONE of the two chains.
ask_chain = cleaner | routed_chain
```

**`app.py`** — updated import:

```python
from llm import llm, chain, simple_chain, analyze_chain, ask_chain, is_coding_question
```

The new endpoint:

```python
class AskRequest(BaseModel):
    message: str


@app.post("/ask")
def ask(request: AskRequest):
    # The branch inside ask_chain decides which prompt to use. We never
    # choose here -- we just hand over the message.
    answer = ask_chain.invoke({"message": request.message})

    # We also want to TELL the caller which route was taken.
    # is_coding_question is a plain function, so we can simply call it.
    # "if / else" picks one of two values -- note the colons and indentation.
    if is_coding_question({"message": request.message}):
        route = "coding"
    else:
        route = "general"

    return {
        "answer": answer,
        "route": route,
        "model": llm.model_name,
    }
```

Returning `"route"` is a small thing that pays off enormously in practice: **when routing misbehaves, you can see it in the response** instead of guessing from the answer's tone.

---

## 5. Execution Flow

```
User
 │   POST /ask   {"message": "How do I reverse a list in Python?"}
 ↓
FastAPI                    validates → request.message
 ↓
ask_chain.invoke({...})
 │
 │  ┌────────────────────────────────────────────────────────────────┐
 │  │  {"message": "How do I reverse a list in Python?"}              │
 │  │            │                                                   │
 │  │            ↓  cleaner                                          │
 │  │  {"message": "How do I reverse a list in Python?"}              │
 │  │            │                                                   │
 │  │            ↓                                                   │
 │  │     is_coding_question(data)   ← plain Python, NO network       │
 │  │            │                                                   │
 │  │      ┌─────┴─────┐                                             │
 │  │  True│           │False                                        │
 │  │      ↓           ↓                                             │
 │  │ coding_chain   general_chain      ← only ONE of these runs      │
 │  │      │           ✗ skipped                                     │
 │  │      ↓                                                          │
 │  │  coding_prompt → llm → parser     ← ONE call to Groq            │
 │  │      │                                                          │
 │  │  'You can reverse a list using slicing... my_list[::-1]'         │
 │  └────────────────────────────────────────────────────────────────┘
 ↓
{"answer": ..., "route": "coding", "model": ...}
 ↓
Response
```

Contrast with Lesson 8's diagram: there, both paths ran and both cost money. Here one path is **skipped entirely** — the `✗` never touches the network.

Also note the routing decision itself is free. It's string matching on your own machine, before any API call.

---

## 6. Run the Project

```bash
cd "/Users/purpleslate14mbp/Desktop/Mission G/gen-ai-beginner-basics"

uv run uvicorn app:app --reload
```

http://127.0.0.1:8000/docs now has **five** endpoints. Try `POST /ask` with both kinds of question:

```bash
curl -X POST http://127.0.0.1:8000/ask -H "Content-Type: application/json" \
  -d '{"message":"How do I reverse a list in Python?"}'

curl -X POST http://127.0.0.1:8000/ask -H "Content-Type: application/json" \
  -d '{"message":"Who wrote Hamlet?"}'
```

### Test the router without spending a single token

The condition is plain Python, so you can check the routing logic on its own — no server, no API key, no cost:

```bash
uv run python -c "
from llm import is_coding_question

tests = [
    'How do I reverse a list in Python?',
    'What causes an IndexError?',
    'Who wrote Hamlet?',
    'What is the capital of France?',
    'How tall is Mount Everest?',
    'Can you help me install this?',
    'I need a shopping list for dinner',
]
for t in tests:
    tag = 'CODING ' if is_coding_question({'message': t}) else 'general'
    print(tag, '|', t)
"
```

**Do run this.** It's how you'll find the bugs in the next section.

---

## 7. Expected Output

### The two routes working correctly

**A — a coding question:**
```json
{
  "answer": "You can reverse a list in Python using slicing with a step of -1, such as `my_list[::-1]`. Alternatively, you can use the `reverse()` method, which modifies the list in-place. For example: `my_list = [1, 2, 3]; my_list.reverse()`...",
  "route": "coding",
  "model": "llama-3.3-70b-versatile"
}
```

**B — a general question:**
```json
{
  "answer": "The play Hamlet was written by William Shakespeare. It is one of his most famous tragedies and is still widely performed and studied today. Shakespeare is believed to have written Hamlet around 1599-1602.",
  "route": "general",
  "model": "llama-3.3-70b-versatile"
}
```

Two clearly different voices, from two different prompts, chosen automatically. The `"route"` field confirms which fired.

### Now the interesting part — where it goes wrong

The full routing table:

```
CODING  | How do I reverse a list in Python?      ✓ correct
CODING  | What causes an IndexError?              ✓ correct  ("error")
general | Who wrote Hamlet?                       ✓ correct
CODING  | What is the capital of France?          ✗ WRONG
general | How tall is Mount Everest?              ✓ correct
CODING  | Can you help me install this?           ✗ questionable
CODING  | I need a shopping list for dinner       ✗ WRONG
```

**Three of seven are wrong.** Which keyword fired in each case:

```
'What is the capital of France?'      matched: ['api']
'I need a shopping list for dinner'   matched: ['list']
'Can you help me install this?'       matched: ['install']
```

Look at the first one. **`c-api-tal`.** The word "capital" contains "api" as a substring, so a geography question got routed to a software engineer. And the consequence is visible in the actual response:

```json
{
  "answer": "The capital of France is Paris. This information is not related to programming, but it can be stored in a variable like `country_capital = \"Paris\"`. In a programming context, this data might be used in a geography-related application.",
  "route": "coding"
}
```

The model answered correctly, then — because its system prompt told it to be an engineer and include code — bolted on a variable assignment nobody asked for. **Bad routing produces bad answers even when the model behaves perfectly.**

The three failures have two distinct causes, and it's worth separating them:

1. **Substring matching** — `"api" in "capital"` is `True`. The `in` operator doesn't know about word boundaries. Same class of bug would hit `"class" in "classical music"` or `"loop" in "loophole"`.
2. **Genuinely ambiguous words** — "list" and "install" are ordinary English *and* programming terms. No keyword list fixes that, because the word really is ambiguous. Only meaning disambiguates it, and keywords don't do meaning.

**This is the honest lesson of Lesson 9.** `RunnableBranch` works exactly as advertised — it routed faithfully every time. The weak part is the *condition*, and conditions are your job. Keyword matching is the simplest thing that could work, it's free and instant, and it's wrong roughly a third of the time on realistic input.

### Regression check
```
/chat        -> 200
/simple-chat -> 200
```

---

## 8. Mini Exercise

**Fix the `"api"` bug, then discover you can't fix the rest.**

**Step 1** — see it directly:
```bash
uv run python -c "print('api' in 'capital')"
```

**Step 2** — fix it by matching whole words. Change `is_coding_question` to split the message into words first:

```python
def is_coding_question(data):
    message = data["message"].lower()

    # .split() breaks a string into a list of words at every space.
    words = message.split()

    for keyword in CODING_KEYWORDS:
        # Now we check the LIST of words, not the raw string.
        # "in" on a list asks: is this an exact item in the list?
        if keyword in words:
            return True

    return False
```

Note `in` changed meaning again — on a **list** it tests for an exact item, not a substring. That single change kills the `capital`/`api` bug.

**Step 3** — re-run the routing table. Then answer:

1. Is `"What is the capital of France?"` fixed? ✓
2. Is `"I need a shopping list for dinner"` fixed? **No** — "list" *is* a whole word there. Why can't whole-word matching help?
3. Now try `"How do I reverse a list in Python?"` — still correct?
4. Try `"What is a python list?"` with a question mark attached to a word: `"list?"`. Does `.split()` handle punctuation? Test `'list' in 'what is a python list?'.split()` and explain the result.

That last one is the sting in the tail: fixing one bug in string matching usually introduces another.

---

## 9. Challenge

**Replace keyword matching with an LLM classifier.**

The real fix for ambiguity is to ask a model *"is this a programming question?"* — because models understand meaning, and keyword lists don't.

Build it:

1. **A classifier prompt.** A system prompt that answers with exactly one word, `yes` or `no`:
   ```python
   CLASSIFIER_SYSTEM_PROMPT = """Is the user's message a programming or software question?

   Reply with exactly one word: yes or no.
   Do not explain."""
   ```
   Then `classifier_chain = classifier_prompt | llm | parser`.

2. **A condition function that uses it.** Remember the condition must return `True`/`False`, but the chain returns a string:
   ```python
   def is_coding_question_ai(data):
       answer = classifier_chain.invoke(data)
       # what goes here?
   ```
   Careful — in Lesson 8 the sentiment branch returned `"Negative."` when asked for one lowercase word. Your comparison must survive capitals and stray punctuation. `.strip()`, `.lower()`, and `.startswith()` are the tools.

3. **Swap it into the branch** and re-run the full routing table from section 6. Check specifically: `"What is the capital of France?"` and `"I need a shopping list for dinner"`.

Then the questions that matter more than the code:

4. **What did this cost?** `/ask` now makes **two** LLM calls per request instead of one — a classify, then an answer. Time it against the keyword version. Is the accuracy worth roughly doubling latency and tokens?

5. **The condition runs twice.** Your endpoint calls `is_coding_question` again just to report `"route"`. With keywords that was free; with an LLM classifier it's a **third** paid call. Two options: drop the `"route"` field, or restructure so the decision is made once and reused. Which would you choose, and why? (Recall the summary-runs-twice problem — same shape of waste, and this time it's not free.)

6. **The hybrid.** Best of both: use keywords for the *obvious* cases (a message containing "python" or "javascript" needs no classifier) and fall back to the LLM only when keywords are unsure. Sketch this with `RunnableBranch` — remember it accepts **several** `(condition, runnable)` pairs, not just one. How many conditions do you need, and in what order?
