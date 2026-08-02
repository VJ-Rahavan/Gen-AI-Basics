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


# THE CHAIN. The | operator joins runnables together, left to right.
# Read it as: "fill the prompt, THEN send it to the llm, THEN parse the reply."
# Each piece's output becomes the next piece's input, automatically.
# This builds the chain once at startup. It does NOT run anything yet --
# nothing happens until someone calls chain.invoke(...) with real data.
chain = prompt | llm | parser

simple_prompt = ChatPromptTemplate.from_messages(
    [
        # Sent every single time, unchanged.
        ("system", SIMPLE_SYSTEM_PROMPT),  

        # {message} is a PLACEHOLDER, not Python syntax.
        # LangChain fills it in later with the user's actual text.
        ("human", "{message}"),
    ]
)

simple_chain = simple_prompt | llm | parser