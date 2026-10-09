import requests
import json
import subprocess
import os
import sys
import tempfile
import glob
import fnmatch
import re
import platform

# --────────────────────────────────────────────
#  CONFIG
# --────────────────────────────────────────────
OLLAMA_API   = "http://localhost:11434/api/chat"
OLLAMA_TAGS  = "http://localhost:11434/api/tags"
MODEL        = "qwen3-0.6b"      # <-- must match the name you register in Ollama (see main())
TIMEOUT      = 120               # seconds to wait for AI response
PYTHON_CMD   = sys.executable    # uses the SAME python that is running this script

# --────────────────────────────────────────────
#  TOOLS  (pure Python, cross-platform)
# --────────────────────────────────────────────

def tool_list_files(params):
    path = params.get("path", ".") or "."
    path = os.path.abspath(path)
    if not os.path.exists(path):
        return f"❌ Path not found: {path}"
    items = []
    try:
        for entry in os.scandir(path):
            size = entry.stat().st_size if entry.is_file() else 0
            kind = "DIR " if entry.is_dir() else "FILE"
            items.append(f"  [{kind}]  {entry.name:<40}  {size:>10} bytes")
        header = f"📂 Contents of: {path}\n" + "─"*60 + "\n"
        return header + "\n".join(items) if items else header + "  (empty)"
    except Exception as e:
        return f"❌ Error: {e}"


def tool_open_file(params):
    filename = params.get("filename") or params.get("file") or params.get("path")
    if not filename:
        return "❌ No filename provided"
    for candidate in [filename, os.path.join(".", filename), os.path.join(os.getcwd(), filename)]:
        if os.path.isfile(candidate):
            try:
                with open(candidate, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                lines = content.splitlines()
                preview = "\n".join(f"{i+1:>4}  {l}" for i, l in enumerate(lines[:60]))
                note = f"\n  ... ({len(lines)-60} more lines)" if len(lines) > 60 else ""
                return f"📄 File: {candidate}  ({len(lines)} lines)\n{'─'*60}\n{preview}{note}"
            except Exception as e:
                return f"❌ Error reading file: {e}"
    return f"❌ File not found: {filename}"


def tool_search_files(params):
    pattern = params.get("pattern") or params.get("name") or "*.py"
    path    = params.get("path") or params.get("directory") or "."
    path    = os.path.abspath(path)

    if pattern.startswith(".") and "*" not in pattern:
        pattern = f"*{pattern}"

    try:
        matches = []
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fname in files:
                if fnmatch.fnmatch(fname.lower(), pattern.lower()):
                    fpath = os.path.join(root, fname)
                    size  = os.path.getsize(fpath)
                    matches.append(f"  {fpath}  ({size} bytes)")
            if len(matches) >= 50:
                break

        if matches:
            return f"🔍 Found {len(matches)} file(s) matching '{pattern}' in {path}:\n" + "\n".join(matches)
        else:
            return f"🔍 No files matching '{pattern}' found in {path}"
    except Exception as e:
        return f"❌ Error: {e}"


def tool_create_file(params):
    filename = params.get("filename") or params.get("file") or params.get("path")
    content  = params.get("content") or ""
    if not filename:
        return "❌ No filename provided"
    try:
        os.makedirs(os.path.dirname(os.path.abspath(filename)) or ".", exist_ok=True)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)
        return f"✅ Created: {os.path.abspath(filename)}"
    except Exception as e:
        return f"❌ Error: {e}"


def tool_delete_file(params):
    filename = params.get("filename") or params.get("file") or params.get("path")
    if not filename:
        return "❌ No filename provided"
    if not os.path.exists(filename):
        return f"❌ File not found: {filename}"
    try:
        os.remove(filename)
        return f"✅ Deleted: {filename}"
    except Exception as e:
        return f"❌ Error: {e}"


def tool_run_command(params):
    cmd = params.get("command") or params.get("cmd")
    if not cmd:
        return "❌ No command provided"
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=15, encoding="utf-8", errors="replace"
        )
        output = (result.stdout + result.stderr).strip()
        return output[:3000] if output else "(no output)"
    except subprocess.TimeoutExpired:
        return "⏱️ Command timed out"
    except Exception as e:
        return f"❌ Error: {e}"


def tool_system_info(params):
    """Cross-platform system info (Windows / Linux / Termux)."""
    info = {
        "OS":       platform.platform(),
        "Machine":  platform.machine(),
        "Python":   sys.version.split()[0],
        "Directory": os.getcwd(),
    }
    try:
        if os.path.exists("/proc/meminfo"):           # Linux / Termux
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal"):
                        kb = int(line.split()[1])
                        info["RAM"] = f"{round(kb/1024**2, 1)} GB"
                        break
        elif sys.platform == "win32":
            r = subprocess.run(
                ["powershell", "-Command",
                 "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory"],
                capture_output=True, text=True, timeout=10)
            gb = round(int(r.stdout.strip()) / (1024**3), 1)
            info["RAM"] = f"{gb} GB"
    except Exception as e:
        info["RAM"] = f"(unavailable: {e})"
    return "\n".join(f"  {k}: {v}" for k, v in info.items())


def tool_make_code(params):
    code_prompt = params.get("code_prompt") or params.get("prompt") or params.get("task")
    if not code_prompt:
        return "❌ No code prompt provided"

    print(f"\n{'─'*60}")
    print(f"🔧 Generating code for: {code_prompt}")
    print(f"{'─'*60}")

    messages = [{
        "role": "user",
        "content": (
            "Write ONLY working Python 3 code. No explanations, no markdown, no backticks. "
            "Just raw Python code that runs immediately.\n\n"
            f"Task: {code_prompt}"
        )
    }]

    try:
        response = requests.post(
            OLLAMA_API,
            json={"model": MODEL, "messages": messages, "stream": False},
            timeout=TIMEOUT
        )
        response.raise_for_status()
        code = response.json()["message"]["content"].strip()
    except Exception as e:
        return f"❌ AI timed out or failed: {e}"

    if "```python" in code:
        code = code.split("```python", 1)[1].split("```", 1)[0].strip()
    elif "```" in code:
        code = code.split("```", 1)[1].split("```", 1)[0].strip()

    print("\n✍️  Generated code:")
    print("─" * 60)
    print(code)
    print("─" * 60)

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py",
                                         delete=False, encoding="utf-8") as f:
            f.write(code)
            tmp = f.name

        print("\n▶️  Running code...\n")
        result = subprocess.run(
            [PYTHON_CMD, tmp],
            capture_output=True, text=True,
            timeout=30, encoding="utf-8", errors="replace"
        )
        output = (result.stdout + result.stderr).strip()
        os.remove(tmp)

        print(output if output else "(no output)")
        return output or "(no output)"
    except subprocess.TimeoutExpired:
        return "⏱️ Code took too long (>30s)"
    except Exception as e:
        return f"❌ Run error: {e}"


# --────────────────────────────────────────────
#  TOOL REGISTRY
# --────────────────────────────────────────────
TOOLS = {
    "list_files":    tool_list_files,
    "open_file":     tool_open_file,
    "search_files":  tool_search_files,
    "create_file":   tool_create_file,
    "delete_file":   tool_delete_file,
    "run_command":   tool_run_command,
    "system_info":   tool_system_info,
    "make_code":     tool_make_code,
}

TOOL_DESCRIPTIONS = """
list_files    → list files in a folder          params: {path}
open_file     → read a file's contents          params: {filename}
search_files  → find files by name/pattern      params: {pattern, path}
create_file   → create/write a file             params: {filename, content}
delete_file   → delete a file                   params: {filename}
run_command   → run a shell command             params: {command}
system_info   → show OS, RAM, Python info       params: {}
make_code     → write & execute Python code     params: {code_prompt}
"""

# --────────────────────────────────────────────
#  AI BRAIN
# --────────────────────────────────────────────
SYSTEM_PROMPT = f"""You are a smart computer assistant. You control the machine you run on.

AVAILABLE TOOLS:
{TOOL_DESCRIPTIONS}

RULES:
1. When user asks to DO something on the computer, respond with ONLY valid JSON (no other text):
   {{"action": "tool_name", "params": {{"key": "value"}}, "reason": "short explanation"}}

2. When user asks a QUESTION that doesn't need a tool (like "what is python?" or "who are you?"),
   respond with plain text, no JSON.

3. For file searches, use search_files.
4. For listing directory contents, use list_files.
5. For code generation tasks, use make_code.
6. ALWAYS fill in the correct params — never leave filename/pattern as null.
7. Current working directory is: {os.getcwd()}
"""


def ask_ai(user_message):
    """Send message to Ollama and get response, or a structured error."""
    try:
        response = requests.post(
            OLLAMA_API,
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_message}
                ],
                "stream": False
            },
            timeout=TIMEOUT
        )
        if response.status_code == 404:
            return ("__MODEL_MISSING__",
                    f"Model '{MODEL}' is not loaded in Ollama.\n"
                    f"Register your GGUF first:\n"
                    f"  1. Create a file named 'Modelfile' containing:\n"
                    f"       FROM /storage/emulated/0/PC_DATA/AI_Model/Qwen3-0.6B/Qwen3-0.6B-Q4_K_M.gguf\n"
                    f"  2. Run:  ollama create qwen3-0.6b -f Modelfile\n"
                    f"  3. Run this script again.")
        response.raise_for_status()
        return ("ok", response.json()["message"]["content"].strip())
    except requests.exceptions.ConnectionError:
        return ("__NO_OLLAMA__", "Cannot connect to Ollama. Start it with:  ollama serve")
    except requests.exceptions.Timeout:
        return ("__TIMEOUT__", None)
    except Exception as e:
        return ("__ERROR__", str(e))


def extract_json(text):
    """Try to find and parse JSON in AI response."""
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            if "action" in data:
                return data
        except Exception:
            pass
    return None


# --────────────────────────────────────────────
#  MAIN LOOP
# --────────────────────────────────────────────
def main():
    print("""
╔══════════════════════════════════════════════════════╗
║        🤖  Ollama Qwen3 Agent  —  v2 (fixed)         ║
║──────────────────────────────────────────────────────║
║  Ask me to do ANYTHING on your computer:             ║
║  • "show files in this folder"                       ║
║  • "open hi.py"                                      ║
║  • "find all .py files"                              ║
║  • "generate code to calculate fibonacci"            ║
║  Type 'exit' to quit                                 ║
╚══════════════════════════════════════════════════════╝
""")

    # Check Ollama connection + that the configured model exists
    try:
        r = requests.get(OLLAMA_TAGS, timeout=5)
        models = [m["name"] for m in r.json().get("models", [])]
        print(f"✅ Connected to Ollama  |  Models available: {', '.join(models) if models else '(none)'}\n")

        if not any(m == MODEL or m.startswith(MODEL + ":") for m in models):
            print(f"⚠️  Model '{MODEL}' NOT found in Ollama.\n"
                  f"   Register your GGUF with:\n"
                  f"     echo FROM /path/to/Qwen3-0.6B-Q4_K_M.gguf > Modelfile\n"
                  f"     ollama create {MODEL} -f Modelfile\n")
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to Ollama. Make sure 'ollama serve' is running.\n")
        sys.exit(1)

    retry_count = 0

    while True:
        try:
            user_input = input("👤 You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n👋 Goodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "q"):
            print("👋 Goodbye!")
            break

        print("⏳ Thinking...", end="\r")

        status, ai_response = ask_ai(user_input)

        if status == "__TIMEOUT__":
            retry_count += 1
            print(f"⏱️  Timeout ({retry_count}). Try a shorter/simpler request.")
            continue
        if status == "__NO_OLLAMA__":
            print(f"❌ {ai_response}")
            sys.exit(1)
        if status == "__MODEL_MISSING__":
            print(f"\n⚠️  {ai_response}\n")
            continue
        if status == "__ERROR__":
            print(f"❌ Error: {ai_response}")
            continue

        retry_count = 0
        action_data = extract_json(ai_response)

        if action_data:
            action = action_data.get("action", "").strip()
            params = action_data.get("params") or {}
            reason = action_data.get("reason", "")

            if action not in TOOLS:
                print(f"❓ Unknown action '{action}'. Replying as text:\n{ai_response}")
                continue

            print(f"\n{'═'*54}")
            print(f"🤖 Action : {action}")
            if reason:
                print(f"💭 Reason : {reason}")
            print(f"{'═'*54}")

            result = TOOLS[action](params)

            if action != "make_code":   # make_code prints its own output
                print(f"\n{result}\n")
        else:
            print(f"\n🤖 {ai_response}\n")


if __name__ == "__main__":
    main()
    