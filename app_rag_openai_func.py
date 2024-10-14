import chainlit as cl
#import openai
from langfuse.openai import openai
from langfuse.decorators import observe
import os
from dotenv import load_dotenv
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.core import Settings
from llama_index.core.callbacks import CallbackManager
from langfuse.llama_index import LlamaIndexCallbackHandler
from prompts import SYSTEM_PROMPT
from migrator_functions import get_current_version, get_target_version, get_migration_steps
import json

# Load environment variables
load_dotenv()

langfuse_callback_handler = LlamaIndexCallbackHandler()
Settings.callback_manager = CallbackManager([langfuse_callback_handler])

client = openai.AsyncClient()

# Load documents from a directory (you can change this path as needed)
documents = SimpleDirectoryReader("data").load_data()

# Create an index from the documents
index = VectorStoreIndex.from_documents(documents)

# Create a retriever to fetch relevant documents
retriever = index.as_retriever(retrieval_mode='similarity', k=3)

# Define the tools for OpenAI function calling
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_current_version",
            "description": "Get the current version of the application",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_target_version",
            "description": "Get the target version for migration",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_migration_steps",
            "description": "Get the migration steps from current to target version",
            "parameters": {
                "type": "object",
                "properties": {
                    "current_version": {"type": "string"},
                    "target_version": {"type": "string"}
                },
                "required": ["current_version", "target_version"]
            }
        }
    }
]
model_kwargs = {
    "model": "gpt-4-0613",
    "temperature": 0.7,
    "max_tokens": 500,
    "tools": tools,
    "tool_choice": "auto"
}
ENABLE_SYSTEM_PROMPT = True

def get_relevant_docs(message):
    print("Getting relevant docs")
    # Retrieve relevant documents
    relevant_docs = retriever.retrieve(message.content)
    # Create a string of the relevant documents
    relevant_docs_content = "\n".join([doc.node.get_content() for doc in relevant_docs])
    #print("Relevant docs = "+relevant_docs_content)
    return relevant_docs_content

@observe
async def generate_response(client, message_history, gen_kwargs):
    print("Generating response")
    response_message = cl.Message(content="")
    await response_message.send()

    stream = await client.chat.completions.create(messages=message_history, stream=True, **gen_kwargs)
      
    function_name = ""
    function_arguments = ""

    async for part in stream:
        delta = part.choices[0].delta
        if delta.content:
            await response_message.stream_token(delta.content)
        elif delta.tool_calls:
            tool_call = delta.tool_calls[0]
            if tool_call.function.name:
                function_name += tool_call.function.name
            if tool_call.function.arguments:
                function_arguments += tool_call.function.arguments

    if function_name:
        function_response = await execute_function(function_name, json.loads(function_arguments))
        message_history.append({"role": "function", "name": function_name, "content": function_response})
        #send tools response back to LLM
        #await response_message.stream_token(function_response)
        return await generate_response(client, message_history, gen_kwargs)

    await response_message.update()
    return response_message

async def execute_function(function_name, arguments):
    print("Executing function "+function_name)
    if function_name == "get_current_version":
        return get_current_version()
    elif function_name == "get_target_version":
        return get_target_version()
    elif function_name == "get_migration_steps":
        return get_migration_steps(arguments["current_version"], arguments["target_version"])
    else:
        return f"Error: Unknown function {function_name}"


observe()
@cl.on_message
async def on_message(message: cl.Message):
    print("Received message")
    # Maintain an array of messages in the user session
    message_history = cl.user_session.get("message_history", [])
 
    if ENABLE_SYSTEM_PROMPT and (not message_history or message_history[0].get("role") != "system"):
        system_prompt_content = SYSTEM_PROMPT
        message_history.insert(0, {"role": "system", "content": system_prompt_content})

    # Get relevant documents from RAG
    relevant_docs_content = get_relevant_docs(message)
    message.content = relevant_docs_content + "\nUser Query: " + message.content
    message_history.append({"role": "user", "content": message.content})

    response_message = await generate_response(client, message_history, model_kwargs)
   
    print("Response = "+response_message.content)
       
    # Record the AI's response in the history
    message_history.append({"role": "assistant", "content": response_message.content})
    cl.user_session.set("message_history", message_history)

if __name__ == "__main__":
    cl.main()