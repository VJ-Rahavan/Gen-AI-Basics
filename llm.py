# python-dotenv reads the .env file and loads each line into "environment variables"
from dotenv import load_dotenv

# ChatGroq is LangChain's wrapper around Groq's chat models
from langchain_groq import ChatGroq

# ChatPromptTemplate builds a reusable, fill-in-the-blank list of chat messages
from langchain_core.prompts import ChatPromptTemplate

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

# The @tool decorator turns an ordinary function into something the model can call.
from langchain_core.tools import tool

# RunnableLambda turns any ordinary Python function into a chain component.
# RunnableMap runs several runnables AT THE SAME TIME on the same input.
# RunnableBranch picks ONE runnable to run, based on a condition.
from langchain_core.runnables import RunnableLambda, RunnableMap, RunnableBranch


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

SIMPLE_SYSTEM_PROMPT = """You are an expert Python programmer who explains everything in simple terms and give examples.

Answer every question accurately.
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

simple_prompt = ChatPromptTemplate.from_messages(
    [
        # Sent every single time, unchanged.
        ("system", SIMPLE_SYSTEM_PROMPT),  

        # {message} is a PLACEHOLDER, not Python syntax.
        # LangChain fills it in later with the user's actual text.
        ("human", "{message}"),
    ]
)

# The SAME cleaner object, reused. The trimming logic is written once,
# but both chains get it.
simple_chain = cleaner | simple_prompt | llm | parser


# ----- Lesson 8: two small jobs we want done at the same time -----

# Job 1: shorten the message.
SUMMARY_SYSTEM_PROMPT = """Summarize the user's message in ONE short sentence.

Reply with the summary only. Do not add any explanation."""

# Job 2: translate the message.
TRANSLATE_SYSTEM_PROMPT = """Translate the user's message into Tamil.

Reply with the translation only. Do not add any explanation."""

SENTIMENT_SYSTEM_PROMPT = """Reply with ONE word describing the tone of the user's message.

Choose from: positive, negative, neutral.
Reply with the single word only."""

summary_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SUMMARY_SYSTEM_PROMPT),
        ("human", "{message}"),
    ]
)

translate_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", TRANSLATE_SYSTEM_PROMPT),
        ("human", "{message}"),
    ]
)

sentiment_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SENTIMENT_SYSTEM_PROMPT),
        ("human", "{message}"),
    ]
)

# Two ordinary chains, built exactly the way you already know.
# Note both reuse the same llm and the same parser.
summary_chain = summary_prompt | llm | parser
translate_chain = translate_prompt | llm | parser
sentiment_chain = sentiment_prompt | llm | parser

# A BRIDGE function. summary_chain gives back a plain STRING, but
# translate_chain begins with translate_prompt, which needs a DICTIONARY
# holding a "message" key. So this WRAPS the string into that shape.
# Name it after what goes in and what comes out -- it makes the mismatch obvious.
def summary_to_message(summary):
    return {"message": summary}


summary_wrapper = RunnableLambda(summary_to_message)


# SEQUENTIAL on purpose: translation cannot start until the summary exists.
# str -> dict -> str is the shape flowing through here.
translate_summary_chain = summary_chain | summary_wrapper | translate_chain
# THE MAP. RunnableMap takes a DICTIONARY of runnables.
# It sends the SAME input to every one of them, runs them AT THE SAME TIME,
# and gives back a dictionary with the same keys -- each holding that
# branch's result.
analysis_map = RunnableMap(
    {
        "summary": summary_chain,
        "translation": translate_chain,
        "sentiment": sentiment_chain,
        # This branch is itself a 2-step sequential chain. A branch of a
        # parallel map can be as complicated as you like.
        "tamil_summary": translate_summary_chain,
    }
)


# The cleaner runs first (once), then the map fans out to both branches.
analyze_chain = cleaner | analysis_map


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


# Characters we want to throw away before looking at words, so that
# "list?" and "class." are seen as "list" and "class".
PUNCTUATION = ".,?!;:()\"'`"


# THE CONDITION. An ordinary function that must return True or False.
# It receives the same dictionary the branches will receive.
def is_coding_question(data):
    # .lower() so "Python" and "python" both match.
    message = data["message"].lower()

    # A "for" over a STRING gives one character at a time.
    # Replacing each punctuation mark with a space keeps words separated.
    for mark in PUNCTUATION:
        message = message.replace(mark, " ")

    # .split() breaks the text into a LIST of separate words.
    # "for X in Y" repeats the indented block once for every item in the list.
    for word in message.split():
        # "in" on a LIST asks for an exact item, not a substring.
        # This is why "capital" no longer matches the keyword "api".
        if word in CODING_KEYWORDS:
            # Found one -- we are done, no need to check the rest.
            return True

        # Error names are their own word: IndexError, TypeError, KeyError...
        # .endswith() catches all of them without listing each one.
        if word.endswith("error"):
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


# ----- Lesson 10: ask for JSON instead of prose -----

# NOTE THE DOUBLED BRACES {{ and }}.
# A single { starts a placeholder, so {"summary": ...} would be read as a
# variable named '"summary"' and crash. Doubling them means "a literal brace".
REPORT_SYSTEM_PROMPT = """You analyse the user's message.

Reply with a JSON object in exactly this shape:
{{"summary": "one short sentence", "sentiment": "positive or negative or neutral", "language": "the language the message is written in"}}

Use lowercase for sentiment.
Reply with the JSON object only. No code fences, no explanation."""


report_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", REPORT_SYSTEM_PROMPT),
        ("human", "{message}"),
    ]
)


# The new parser. StrOutputParser gave us text; this one reads that text AS
# JSON and hands back a real Python dictionary.
json_parser = JsonOutputParser()


# Same shape of chain as always -- only the last piece changed.
report_chain = cleaner | report_prompt | llm | json_parser


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


# ----- Lesson 12: let the MODEL know the shape, instead of asking in words -----

# No JSON example, no braces to double, no "reply with JSON only".
# The shape is sent separately, through the API, by with_structured_output.
REPORT_V3_SYSTEM_PROMPT = """You analyse the user's message.

Keep the summary to one short sentence.
Use lowercase for the sentiment and the language."""


report_v3_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", REPORT_V3_SYSTEM_PROMPT),
        ("human", "{message}"),
    ]
)


# Attach the ChatResponse shape to the model itself.
# Groq is told the exact schema through the API, so the model replies in that
# shape by construction instead of being asked for it in words.
# This does not remove the parsing step -- LangChain still adds one for us,
# inside structured_llm. We just no longer write it, or describe the shape twice.
structured_llm = llm.with_structured_output(ChatResponse)


# We write three pieces; LangChain expands structured_llm into two, so the
# finished chain still has four steps. Print chain.steps to see it.
report_v3_chain = cleaner | report_v3_prompt | structured_llm


# ----- Lesson 13: give the model a tool it can choose to use -----


# @tool turns this ordinary function into a Tool the model is allowed to call.
# The DOCSTRING below is not a comment -- LangChain sends it to the model as the
# tool's description, and the model reads it to decide when this tool applies.
# A tool without a docstring is an error.
@tool
def calculator(operation: str, first_number: float, second_number: float) -> str:
    """Do arithmetic on two numbers.

    Use this whenever the user asks for a calculation.
    operation must be one of: add, subtract, multiply, divide.
    """
    # "elif" means "else if" -- it checks the next condition only if the
    # previous ones were False. Python has no "switch" statement.
    if operation == "add":
        result = first_number + second_number
    elif operation == "subtract":
        result = first_number - second_number
    elif operation == "multiply":
        result = first_number * second_number
    elif operation == "divide":
        # Dividing by zero would crash Python, so we stop before that happens.
        if second_number == 0:
            return "Cannot divide by zero."
        result = first_number / second_number
    else:
        # The model sent an operation we do not support.
        return "Unknown operation. Use add, subtract, multiply or divide."

    # We return TEXT rather than a number, so that answers and error messages
    # can both travel back the same way.
    return str(result)


# Give the model a list of tools it is allowed to use.
# This does NOT run anything -- it only tells Groq which tools exist.
# The model stays free to answer normally instead.
llm_with_tools = llm.bind_tools([calculator])


# A plain function that does the two steps by hand, so we can watch them.
def answer_with_calculator(message):
    """Ask the model, then run the calculator only if the model asked us to."""
    # STEP 1: the model reads the question and DECIDES.
    reply = llm_with_tools.invoke(message)

    # reply.tool_calls is a LIST. It is empty when the model chose to answer
    # by itself, and holds one entry per tool the model wants called.
    if len(reply.tool_calls) == 0:
        return {
            "answer": reply.content,
            "tool_used": None,
            "tool_args": None,
        }

    # STEP 2: the model asked for a tool. [0] is the first (and here, only) one.
    first_call = reply.tool_calls[0]

    # WE run the tool -- the model cannot run code, it can only ask.
    # first_call["args"] is the dictionary of arguments the model filled in.
    tool_result = calculator.invoke(first_call["args"])

    return {
        "answer": tool_result,
        "tool_used": first_call["name"],
        "tool_args": first_call["args"],
    }
