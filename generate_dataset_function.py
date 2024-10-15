# Import necessary libraries
from dotenv import load_dotenv
from llama_index.core import SimpleDirectoryReader
import json
import os
from openai import OpenAI

# Load environment variables
load_dotenv()

# Load documents from a directory (you can change this path as needed)
documents = SimpleDirectoryReader("data").load_data()

client = OpenAI()

# Define the functions that we want the model to learn to call
functions = [
    {
        "name": "get_current_version",
        "description": "Get the current version of the application",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_target_version",
        "description": "Get the target version for migration",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
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
]

# Function to generate questions and answers with function calls
def generate_qa(prompt, text, temperature=0.2):    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": text}
        ],
        functions=functions,
        function_call="auto",
        temperature=temperature,
    )
    print(response.choices[0].message.content)
    # Strip extraneous symbols from the response content
    content = response.choices[0].message.content.strip()
    
    # Remove potential JSON code block markers
    content = content.strip()
    if content.startswith('```'):
        content = content.split('\n', 1)[-1]
    if content.endswith('```'):
        content = content.rsplit('\n', 1)[0]
    content = content.strip()

    # Attempt to parse the cleaned content as JSON
    try:
        parsed_content = json.loads(content.strip())
        return parsed_content
    except json.JSONDecodeError:
        print("Error: Unable to parse JSON. Raw content:")
        print(content)
        return []

    

factual_prompt = """
You are a highly advanced AI Code Migrator tasked with generating factual questions and answers specifically for upgrading libraries like Java, Vert.x, Spring Boot, or other frameworks.

Instructions:

- Generate **5** factual questions, each with a corresponding **expected_output**.
- Ensure all questions are directly related to the document excerpt.
- Present the output in the following structured JSON format:

[
  {
    "question": "What is the main purpose of the project described in the document?",
    "expected_output": "To help upgrade libraries like Java, Vert.x, Spring Boot using AI-powered tools."
  },
  {
    "question": "Who authored the report mentioned in the document?",
    "expected_output": "Dr. Jane Smith."
  }
]
"""

# Generate dataset
dataset_file = 'qa_dataset_function_calling.json'

####
if os.path.exists(dataset_file):
    # Load dataset from local file if it exists
    with open(dataset_file, 'r') as f:
        dataset = json.load(f)
else:
    # Generate dataset if local file doesn't exist
    dataset = []
    for doc in documents:
        qa_pair = generate_qa(factual_prompt, doc.text, temperature=0.2)
        dataset.append(qa_pair)
    
    # Write dataset to local file
    with open(dataset_file, 'w') as f:
        json.dump(dataset, f, indent=2)

print(f"Dataset created with {len(dataset)} items.")

# Optional: Print a sample of the dataset
print("\nSample question and answer:")
print(json.dumps(dataset[0], indent=2))