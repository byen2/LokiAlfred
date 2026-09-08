#!/usr/bin/env python3

import asyncio
import json
import uuid
import time
import subprocess
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path
import re

from starlette.applications import Starlette
from starlette.responses import JSONResponse, StreamingResponse
from starlette.requests import Request
from starlette.templating import Jinja2Templates
from starlette.staticfiles import StaticFiles


# =========================
# PATHS
# =========================

def find_ollama():

    path = shutil.which("ollama")
    if path:
        return path

    candidates = [
        "/opt/homebrew/bin/ollama",
        "/usr/local/bin/ollama",
    ]

    for candidate in candidates:
        p = Path(candidate)
        if p.exists() and p.is_file():
            return str(p)

    return None

OLLAMA_PATH = find_ollama()

if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).parent

PASSAGES_FILE = BASE_DIR / "ml_passages.txt"


ANSI_RE = re.compile(r"\x1B\[[0-9;]*[A-Za-z]")

THINKING_RE = re.compile(
    r"Thinking\.\.\.[\s\S]*?done thinking\.?|"
    r"\.\.\.done thinking\.?|"
    r"<think>[\s\S]*?</think>",
    re.IGNORECASE
)

DUPLICATE_JOINED_RE = re.compile(r"\b([A-Za-z]{3,})\1\b")

def clean_ollama(text: str) -> str:
    if not text:
        return ""

    text = ANSI_RE.sub("", text)
    text = THINKING_RE.sub("", text)

    # Remove remaining leading thinking marker if present
    text = re.sub(r"^\s*\.*done thinking\.?\s*", "", text, flags=re.IGNORECASE)

    # Unwrap terminal-wrapped lines, but preserve Markdown structure
    lines = text.splitlines()
    cleaned = []
    buffer = ""

    for line in lines:
        stripped = line.strip()

        if not stripped:
            if buffer:
                cleaned.append(buffer.strip())
                buffer = ""
            cleaned.append("")
            continue

        is_markdown_block = (
            stripped.startswith(("* ", "- ", "+ ", "#", ">", "```"))
            or re.match(r"^\d+\.\s+", stripped)
        )

        if is_markdown_block:
            if buffer:
                cleaned.append(buffer.strip())
                buffer = ""
            cleaned.append(stripped)
            continue

        if buffer:
            buffer += " " + stripped
        else:
            buffer = stripped

    if buffer:
        cleaned.append(buffer.strip())

    text = "\n".join(cleaned)
    text = re.sub(
        r"\b([A-Za-z]{2,})\s+([A-Za-z]{3,})\b",
        lambda m: m.group(2)
        if m.group(2).lower().startswith(m.group(1).lower())
        else m.group(0),
        text
    )

    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()

# -------------------------
# Persistent user data
# -------------------------

DATA_DIR = Path.home() / "Library/Application Support/loki-alfred"

HISTORY_DIR = DATA_DIR / "history"
ARCHIVE_DIR = DATA_DIR / "archive"
SETTINGS_FILE = DATA_DIR / "settings.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

# =========================
# AUTOMATIC MIGRATION
# =========================

OLD_SETTINGS = BASE_DIR / "settings.json"
OLD_HISTORY = BASE_DIR / "history"
OLD_ARCHIVE = BASE_DIR / "archive"

if not SETTINGS_FILE.exists() and OLD_SETTINGS.exists():
    shutil.copy2(OLD_SETTINGS, SETTINGS_FILE)

if not any(HISTORY_DIR.iterdir()) and OLD_HISTORY.exists():
    shutil.copytree(
        OLD_HISTORY,
        HISTORY_DIR,
        dirs_exist_ok=True
    )

if not any(ARCHIVE_DIR.iterdir()) and OLD_ARCHIVE.exists():
    shutil.copytree(
        OLD_ARCHIVE,
        ARCHIVE_DIR,
        dirs_exist_ok=True
    )

# =========================
# APP INIT
# =========================

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app = Starlette(debug=False)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

CURRENT_SESSION = None


# =========================
# SETTINGS
# =========================

def load_settings():
    default_settings = {
        "query": "",
        "index_dirs": "",
        "top_docs": "5",
        "top_passages": "3",
        "word_radius": "500",
        "full": False
    }

    if not SETTINGS_FILE.exists():
        SETTINGS_FILE.write_text(
            json.dumps(default_settings, indent=2)
        )
        return default_settings

    try:
        saved_settings = json.loads(SETTINGS_FILE.read_text())
        
        #in case additional settings values are added
        return {**default_settings, **saved_settings}

    except (json.JSONDecodeError, OSError):
        return default_settings

def save_settings(settings):
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2))


def get_safe_settings():
    settings = load_settings()
    if not isinstance(settings, dict):
        return {}
    return settings


# =========================
# ARCHIVE OLD CHATS
# =========================

def archive_old_chats(days=30):
    cutoff = datetime.now() - timedelta(days=days)

    for folder in HISTORY_DIR.iterdir():
        if not folder.is_dir():
            continue

        try:
            folder_date = datetime.strptime(folder.name, "%Y%m%d")
        except Exception:
            continue

        if folder_date < cutoff:
            target = ARCHIVE_DIR / folder.name
            if not target.exists():
                folder.rename(target)


@app.on_event("startup")
async def startup_event():
    archive_old_chats()


# =========================
# PASSAGES
# =========================

def read_passages():
    if PASSAGES_FILE.exists():
        return PASSAGES_FILE.read_text()
    return ""


# =========================
# SESSION HANDLING
# =========================

def create_session(settings):
    date_folder = datetime.now().strftime("%Y%m%d")
    folder = HISTORY_DIR / date_folder
    folder.mkdir(parents=True, exist_ok=True)

    timestamp = time.time()

    session = {
        "id": str(uuid.uuid4()),
        "created": timestamp,
        "model": settings.get("model", "phi4"),
        "settings": settings,
        "search_result": read_passages(),
        "messages": []
    }

    file = folder / f"{timestamp}.json"
    file.write_text(json.dumps(session, indent=2))

    return file

def append_message(session, role, content, model=None):
    data = json.loads(session.read_text())

    msg = {
        "timestamp": time.time(),
        "role": role,
        "content": content
    }

    if model:
        msg["model"] = model

    data["messages"].append(msg)
    session.write_text(json.dumps(data, indent=2))


# =========================
# ROUTES (PAGES)
# =========================

@app.route("/")
async def ask(request):
    return templates.TemplateResponse(
        "ask.html",
        {"request": request, "settings": get_safe_settings()}
    )


@app.route("/settings")
async def settings(request):
    return templates.TemplateResponse(
        "settings.html",
        {"request": request, "settings": get_safe_settings()}
    )


@app.route("/preview")
async def preview(request):
    return templates.TemplateResponse(
        "preview.html",
        {"request": request, "text": read_passages(), "settings": get_safe_settings()}
    )


@app.route("/about")
async def about(request):
    return templates.TemplateResponse(
        "about.html",
        {"request": request, "settings": get_safe_settings()}
    )


# =========================
# OLLAMA MODELS API
# =========================

@app.route("/ollama_models")
async def ollama_models(request):
    """
    Dynamically fetch installed Ollama models
    """

    if OLLAMA_PATH is None:
        return JSONResponse({
            "models": [],
            "error": "Ollama is not installed."
        })

    try:
        result = subprocess.run(
            [OLLAMA_PATH, "list"],
            capture_output=True,
            text=True,
            check=True
        )

        lines = result.stdout.strip().split("\n")[1:]  # skip header
        models = []

        for line in lines:
            parts = line.split()
            if len(parts) > 0:
                models.append(parts[0])

        return JSONResponse({
            "models": models,
            "error": None
        })

    except Exception as e:
        return JSONResponse({
            "models": [],
            "error": str(e)
        })


# =========================
# CHAT SESSIONS
# =========================

@app.route("/delete_chats", methods=["POST"])
async def delete_chats(request):
    global CURRENT_SESSION

    data = await request.json()
    files = data.get("files", [])

    deleted = 0

    for file_str in files:
        file = Path(file_str)

        if file.exists() and file.suffix == ".json":
            file.unlink()
            deleted += 1

            if CURRENT_SESSION == file:
                CURRENT_SESSION = None

    return JSONResponse({
        "status": "ok",
        "deleted": deleted
    })

@app.route("/chat_sessions")
async def chat_sessions(request):

    sessions = []

    def scan(folder):
        if not folder.exists():
            return

        for file in folder.rglob("*.json"):
            try:
                data = json.loads(file.read_text())
                messages = data.get("messages", [])

                preview = messages[0]["content"][:50] if messages else "New Chat"

                sessions.append({
                    "id": data.get("id", str(file)),
                    "created": data.get("created", file.stat().st_mtime),
                    "preview": preview,
                    "file": str(file)
                })

            except:
                continue

    scan(HISTORY_DIR)
    scan(ARCHIVE_DIR)

    sessions.sort(key=lambda x: x["created"], reverse=True)

    return JSONResponse({
        "sessions": sessions,
        "count": len(sessions)
    })


@app.route("/switch_chat", methods=["POST"])
async def switch_chat(request):
    global CURRENT_SESSION

    data = await request.json()
    file = Path(data["file"])

    CURRENT_SESSION = file

    session = json.loads(file.read_text())

    return JSONResponse({
        "history": session["messages"],
        "model": session.get("model", "phi4")
    })


@app.route("/clear_chat", methods=["POST"])
async def clear_chat(request):
    global CURRENT_SESSION
    CURRENT_SESSION = create_session(get_safe_settings())
    return JSONResponse({"status": "ok"})


@app.route("/chat_history")
async def chat_history(request):
    global CURRENT_SESSION

    if not CURRENT_SESSION:
        return JSONResponse({"history": []})

    data = json.loads(CURRENT_SESSION.read_text())

    return JSONResponse({
        "history": data["messages"],
        "model": data.get("model", "phi4")
    })

@app.route("/ask_ollama", methods=["POST"])
async def ask_ollama(request):

    global CURRENT_SESSION

    data = await request.json()
    question = data.get("question", "").strip()
    model = data.get("model", "phi4")

    if not question:
        return JSONResponse({"error": "No question provided."}, status_code=400)

    if not CURRENT_SESSION:
        CURRENT_SESSION = create_session(get_safe_settings())

    session = json.loads(CURRENT_SESSION.read_text())
    session["model"] = model
    CURRENT_SESSION.write_text(json.dumps(session, indent=2))

    context = session["search_result"]

    prompt = f"""
        You are Alfred, a concise desktop AI assistant.

        Formatting rules:
        - Answer in clean Markdown.
        - Use short paragraphs.
        - Use bullets when helpful.
        - Use fenced code blocks for code.
        - Do not output hidden reasoning.
        - Do not write "Thinking..." or "done thinking."
        - Do not explain your reasoning process.
        - Only provide the final answer.

        Context:
        {context}

        Question:
        {question}

        Answer:
        """

    append_message(CURRENT_SESSION, "user", question)

    if OLLAMA_PATH is None:
        return JSONResponse({
            "error": "Ollama is not installed."
        }, status_code=500)

    proc = await asyncio.create_subprocess_exec(
        OLLAMA_PATH,
        "run",
        model,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await proc.communicate(input=prompt.encode())

    raw_answer = stdout.decode(errors="ignore")
    err_text = stderr.decode(errors="ignore")

    print("OLLAMA RETURN CODE:", proc.returncode)
    print("========== STDERR ==========")
    print(err_text)
    print("========== RAW ==========")
    print(raw_answer)
    print("=========================")

    if proc.returncode != 0:
        return JSONResponse({
            "error": err_text.strip() or "Ollama failed to generate a response."
        }, status_code=500)

    answer = clean_ollama(raw_answer)

    append_message(CURRENT_SESSION, "bot", answer, model)

    return JSONResponse({
        "answer": answer,
        "model": model
    })


# =========================
# STREAMING (NOW WITH MODEL SWITCHING)
# =========================

@app.route("/stream_ollama")
async def stream_ollama(request):

    global CURRENT_SESSION

    question = request.query_params.get("question")
    model = request.query_params.get("model", "phi4")

    if not CURRENT_SESSION:
        CURRENT_SESSION = create_session(get_safe_settings())

    session = json.loads(CURRENT_SESSION.read_text())
    session["model"] = model
    CURRENT_SESSION.write_text(json.dumps(session, indent=2))
    context = session["search_result"]

    prompt = f"""
You are Alfred, a concise desktop AI assistant.

Formatting rules:
- Answer in clean Markdown.
- Use short paragraphs.
- Use bullets when helpful.
- Use fenced code blocks for code.
- Do not output hidden reasoning.
- Do not write "Thinking..." or "done thinking."
- Do not explain your reasoning process.
- Only provide the final answer.

Context:
{context}

Question:
{question}

Answer:
"""

    async def generator():

        append_message(CURRENT_SESSION, "user", question)

        if OLLAMA_PATH is None:
            yield "data: Ollama is not installed.\n\n"
            yield "data: [DONE]\n\n"
            return

        proc = await asyncio.create_subprocess_exec(
            OLLAMA_PATH,
            "run",
            model,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await proc.communicate(input=prompt.encode())

        raw_answer = stdout.decode(errors="ignore")
        err_text = stderr.decode(errors="ignore")

        print("OLLAMA RETURN CODE:", proc.returncode)
        print("========== STDERR ==========")
        print(err_text)
        print("========== RAW ==========")
        print(raw_answer)
        print("=========================")

        if proc.returncode != 0:
            error_msg = err_text.strip() or "Ollama failed to generate a response."
            yield "data: " + error_msg.replace("\n", "\\n") + "\n\n"
            yield "data: [DONE]\n\n"
            return

        answer = clean_ollama(raw_answer)

        append_message(CURRENT_SESSION, "bot", answer, model)

        payload = json.dumps({
            "content": answer
        })

        yield f"data: {payload}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generator(), media_type="text/event-stream")


# =========================
# START SERVER
# =========================

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)