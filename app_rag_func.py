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
from migrator_functions import get_current_version
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

model_kwargs = {
    "model": "gpt-4o-mini",
    "temperature": 0.7,
    "max_tokens": 500
}
ENABLE_SYSTEM_PROMPT = True

def get_relevant_docs(message):
    # Retrieve relevant documents
    relevant_docs = retriever.retrieve(message.content)
    # Create a string of the relevant documents
    relevant_docs_content = "\n".join([doc.node.get_content() for doc in relevant_docs])
    #print("Relevant docs = "+relevant_docs_content)
    return relevant_docs_content

@observe
async def generate_response(client, message_history, gen_kwargs):
    response_message = cl.Message(content="")
    await response_message.send()

    stream = await client.chat.completions.create(messages=message_history, stream=True, **gen_kwargs)
    async for part in stream:
        if token := part.choices[0].delta.content or "":
            await response_message.stream_token(token)
    
    await response_message.update()
    return response_message

def parse_response(response_message):
    function_name=""
    try:
        if response_message.content.__contains__("\n\n"):
            print("Response contains double newline.")
            # Split the string to isolate the JSON part
            split_string = response_message.content.split("\n\n")  # Split by the double newline
            # The JSON part is usually the second part after the split
            json_part = split_string[1]
            parsed_json = json.loads(json_part)
            # Print the extracted and parsed JSON
            print(f"parsed json ")
            print (parsed_json)
            function_name = parsed_json["function"]
        else:
            print("Response does not contain double newline.")
              # Split the string to isolate the JSON part
            split_string = response_message.content.split("\n\n")  # Split by the double newline
            # The JSON part is usually the first part after the split
            json_part = split_string[0]
            parsed_json = json.loads(json_part)

            # Print the extracted and parsed JSON
            print(f"parsed json ")
            print (parsed_json)
            function_name = parsed_json["function"]
    except Exception as e:
            print(f"Error calling functions: {e}")
    return function_name

observe()
@cl.on_message
async def on_message(message: cl.Message):
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
    function_name = parse_response(response_message)
    print("Function name = "+function_name)
    
    if function_name == "get_current_version":
        print("Function is get_current_version.")
        # Check if the response contains get_current_version
        # call the function from migrator_functions.py
        current_version = get_current_version()
        #Append the function result to the message history
        message_history.append({"role" : "function", "name" : "get_current_version",  "content": current_version})
        response_message = await generate_response(client, message_history, model_kwargs)
    
    # Record the AI's response in the history
    message_history.append({"role": "assistant", "content": response_message.content})
    cl.user_session.set("message_history", message_history)

if __name__ == "__main__":
    cl.main()