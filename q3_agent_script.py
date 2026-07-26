import json
import subprocess
from openai import OpenAI

# 1. Setup client using aipipe as the OpenAI-compatible proxy
client = OpenAI(
    base_url="https://aipipe.org/openai/v1",
    api_key="eyJhbGciOiJIUzI1NiJ9.eyJlbWFpbCI6IjIxZjMwMDE2NDdAZHMuc3R1ZHkuaWl0bS5hYy5pbiIsImlhdCI6MTc4NDk4NTA3OSwiaXNzIjoiaHR0cHM6Ly9haXBpcGUub3JnIiwiYXVkIjoiYWlwaXBlLWFwaSIsImV4cCI6MTc4NTU4OTg3OX0.AbADHACeaN4Dofbfv-10OUwHG9HSHz0gdP3ogZ2Lack"  # from aipipe.org/login
)

# 2. System + task prompt — this becomes your JSONL log
messages = [
    {"role": "system", "content": "You are a cloud engineer agent. You can run terminal commands using the 'run_command' tool. Detect your shell type before running OS-specific commands, and adapt syntax accordingly."},
    {"role": "user", "content": (
        "gcloud is already installed. Do not install it. "
        "Check auth status with `gcloud auth list`; if not authenticated, run `gcloud auth login` "
        "and pause for me to complete browser login. Then set project to tds-project-503607, "
        "enable storage.googleapis.com, create bucket gs://q1-38f8c0c4b95fe57 in asia-south1, "
        "make it publicly readable and listable (grant allUsers both roles/storage.objectViewer "
        "and roles/storage.legacyBucketReader), then run describe and list to confirm. "
        "Print status after each step."
    )}
]

# 3. Tool definition
tools = [{
    "type": "function",
    "function": {
        "name": "run_command",
        "description": "Run a terminal command on the user's computer",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to run"}
            },
            "required": ["command"]
        }
    }
}]

# 4. Agent loop
print("Starting agent...")
MAX_ITERATIONS = 25
iterations = 0

while iterations < MAX_ITERATIONS:
    iterations += 1
    response = client.chat.completions.create(
        model="gpt-5-nano",
        messages=messages,
        tools=tools
    )

    response_message = response.choices[0].message
    messages.append(response_message.model_dump(exclude_unset=True))

    if response_message.tool_calls:
        for tool_call in response_message.tool_calls:
            if tool_call.function.name == "run_command":
                args = json.loads(tool_call.function.arguments)
                command = args["command"]

                print(f"\n[Agent wants to run]: {command}")

                # NOTE: gcloud auth login will require you to manually open the
                # printed URL in a browser and sign in — the script cannot do this.
                try:
                    result = subprocess.run(
                        command, shell=True, capture_output=True, text=True, timeout=300
                    )
                    output = result.stdout if result.returncode == 0 else result.stderr
                except subprocess.TimeoutExpired:
                    output = "Command timed out after 300 seconds."
                except Exception as e:
                    output = str(e)

                print(f"[Command Output]:\n{output}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call.function.name,
                    "content": output
                })
    else:
        print(f"\n[Agent Final Answer]: {response_message.content}")
        break
else:
    print("\nReached max iterations without the agent finishing — check the log for a stuck loop.")

# 5. Save the log
with open("agent_log.jsonl", "w") as f:
    for msg in messages:
        f.write(json.dumps(msg) + "\n")

print("\nSaved conversation log to agent_log.jsonl")