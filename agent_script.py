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
    {"role": "user", "content": f"""
You are a cloud engineer agent working in a terminal. The Google Cloud CLI (gcloud) is already installed and authenticated on this machine — do not attempt to install it or run gcloud auth login unless `gcloud auth list` shows no active account.

First, detect which shell/terminal you are running in (e.g. PowerShell, cmd, bash, zsh) and use the correct command syntax for that shell throughout this task. Do not assume a shell — check first and adapt.

Complete this entire task autonomously without asking me questions — make reasonable decisions yourself and keep going until done. After each major step, print a clear status line (e.g. "STEP X DONE: ...") before moving to the next step. If a command fails, print the exact error and try one reasonable fix before moving on — don't silently skip a failed step.

Details:
- Project ID: tds-project-503607
- Bucket name: q2-13399c477f9bbba
- Location: asia-south1
- Local file to upload: /Users/mervinjosephl/Documents/GA2.0/Q3-Project/eval.jsonl

Steps:
1. Verify gcloud is available and check auth status with `gcloud auth list`. Confirm the active project is tds-project-503607 (set it if not already).
2. Compute the SHA-256 hash of the local file BEFORE upload, using the correct command for this shell. Print this hash clearly labeled as "LOCAL HASH BEFORE UPLOAD".
3. Ensure the Cloud Storage API is enabled: `gcloud services enable storage.googleapis.com`.
4. Create the bucket: `gcloud storage buckets create gs://q2-13399c477f9bbba --location=asia-south1`. If it already exists, skip this step and note that.
5. Upload the file unchanged, preserving the exact filename `eval.jsonl`: `gcloud storage cp "/Users/mervinjosephl/Documents/GA2.0/Q3-Project/eval.jsonl" gs://q2-13399c477f9bbba/eval.jsonl`
6. Make the bucket publicly readable and listable by granting `roles/storage.objectViewer` and `roles/storage.legacyBucketReader` to `allUsers`.
7. Download the uploaded object back to a temp location and compute its SHA-256 hash, or use `gcloud storage objects describe` to check the object's stored hash/metadata. Print this clearly labeled as "UPLOADED FILE VERIFICATION".
8. Confirm by running `gcloud storage buckets describe` and `gcloud storage ls`.
9. Print a final summary: project confirmed, API enabled, bucket created/existing, file uploaded, LOCAL HASH BEFORE UPLOAD, UPLOADED FILE VERIFICATION, public access granted, and full describe/list output. Explicitly state whether the local hash and the uploaded file appear to match.
"""}
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
print("Starting Q4 agent...")
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

                print(f"\\n[Agent wants to run]: {command}")

                try:
                    result = subprocess.run(
                        command, shell=True, capture_output=True, text=True, timeout=300
                    )
                    output = result.stdout if result.returncode == 0 else result.stderr
                except subprocess.TimeoutExpired:
                    output = "Command timed out after 300 seconds."
                except Exception as e:
                    output = str(e)

                print(f"[Command Output]:\\n{output}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call.function.name,
                    "content": output
                })
    else:
        print(f"\\n[Agent Final Answer]: {response_message.content}")
        break
else:
    print("\\nReached max iterations without the agent finishing — check the log for a stuck loop.")

# 5. Save the log
with open("q4_agent_log.jsonl", "w") as f:
    for msg in messages:
        f.write(json.dumps(msg) + "\\n")

print("\\nSaved conversation log to q4_agent_log.jsonl")