# Loki Alfred

A local AI-powered desktop assistant for semantic document search, built with Tauri, Starlette, Recoll, and Ollama.

## Features
🔍 Semantic document retrieval using Recoll

🤖 Local LLM inference through Ollama

💬 Chat history management

📚 Document preview and citation support

🖥 Native macOS desktop application using Tauri

🔒 Fully local—no cloud services required

## Architecture
                +----------------+
                |   Tauri (UI)   |
                +----------------+
                        |
                        v
                +----------------+
                | Python Backend |
                | Starlette API  |
                +----------------+
                        |
         +--------------+--------------+
         |                             |
         v                             v
    Recoll Index                 Ollama Models

## Prerequisites

Install the following:

* Python 3.11+

* Node.js

* Rust

* Cargo

* [Recoll](https://www.recoll.org/pages/download.html)

* [Ollama](https://ollama.com/download)

* Install at least one Ollama model, for example:

  `ollama pull phi4`

## Installation

### Clone the repository:

`git clone https://github.com/<username>/loki-alfred.git`

`cd loki-alfred`

### Create a virtual environment:

`python3 -m venv .venv`

`source .venv/bin/activate`

### Install Python dependencies:

`pip install -r requirements.txt`

### Install frontend dependencies:

`cd Alfred`

`npm install`

### Building the Backend

From the project root:

`pyinstaller --clean --onefile --name backend backend.py`

### Create the Tauri binaries folder:

`mkdir -p Alfred/src-tauri/binaries`

Copy the backend:

`cp dist/backend \
Alfred/src-tauri/binaries/backend-$(rustc --print host-tuple)`

### Running in Development

* Start the desktop application:

`cd Alfred`

`npm run tauri dev`

* Building the Application

`cd Alfred`

`npm run tauri build`

The application will be generated under:

`src-tauri/target/release/bundle/`

## Project Structure

```text
recoll_demo/
│
├── backend.py
├── app.py
├── templates/
├── static/
├── requirements.txt
│
└── Alfred/
    ├── src/
    ├── src-tauri/
    ├── package.json
    └── ...
```
    
## Configuration

Alfred stores user-specific data in:

`~/Library/Application Support/loki-alfred/`

This includes:

* chat history
* settings
* archived conversations

These files are not tracked by Git.

## Notes

This project requires Ollama to be installed and running. It also requires building [Recoll](https://www.recoll.org/pages/download.html)

Alfred does not ship with language models.

Users should install the desired Ollama model before launching the application.
