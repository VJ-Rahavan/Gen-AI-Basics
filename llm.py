# python-dotenv reads the .env file and loads each line into "environment variables"
from dotenv import load_dotenv

# ChatGroq is LangChain's wrapper around Groq's chat models
from langchain_groq import ChatGroq

# ChatPromptTemplate builds a reusable, fill-in-the-blank list of chat messages
from langchain_core.prompts import ChatPromptTemplate


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
SYSTEM_PROMPT = """You are a friendly Python tutor.

The student already knows JavaScript but is new to Python.
Compare Python to JavaScript whenever it helps.
Keep every answer under four sentences."""


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
