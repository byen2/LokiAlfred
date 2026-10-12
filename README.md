# Alfred

**Alfred** is a local AI research assistant that combines **Recoll** and **Ollama** into a native macOS desktop application.

Instead of searching files manually, Alfred searches your indexed documents with Recoll, retrieves the most relevant passages, and uses a local Large Language Model (LLM) through Ollama to answer questions using your own data.

All processing happens locally—your documents never leave your computer.

---

## Features

- 🔍 Semantic search over your personal document collection using Recoll
- 🤖 Local AI responses powered by Ollama
- 💬 Persistent chat history
- 📄 Built-in document preview
- ⚙️ Configurable model selection
- 🖥 Native macOS desktop application using Tauri
- 🔒 Fully offline after installation

---

## Architecture

```
                User
                  │
                  ▼
            Alfred (Tauri)
                  │
                  ▼
        Python Backend (Starlette)
          │                 │
          │                 ▼
          │            Ollama LLM
          │
          ▼
        Recoll Search
          │
          ▼
    Indexed Documents
```

---

## Installation

Clone the repository:

```bash
git clone https://github.com/byen2/LokiAlfred.git
cd LokiAlfred
```

Run the installer:

```bash
./install.sh
```

The installer will:

- create a Python virtual environment
- install Python dependencies
- build the backend executable
- build the Tauri application
- optionally install Ollama
- optionally install Recoll
- optionally download an Ollama model

---

## Running Alfred

After installation:

Double click on the Alfred app to launch. 

The application will automatically launch the bundled backend.

---

## Project Structure

```
LokiAlfred/

├── Alfred/              # Tauri frontend
├── app.py               # Starlette application
├── backend.py           # Backend entry point
├── recoll_ranked.py     # Recoll interface
├── ollama_qa.py         # Ollama prompt generation
├── templates/
├── static/
├── install.sh
├── backend.spec
└── requirements.txt
```

---

## Data Storage

User data is stored in:

```
~/Library/Application Support/loki-alfred/
```

including:

- settings
- chat history
- archived chats

No user data is stored inside the application bundle.

---

## Requirements

Python packages:

```
pip install -r requirements.txt
```

---

## Building

Backend:

```bash
python -m PyInstaller backend.spec
```

Desktop application:

```bash
cd Alfred
npm run tauri build
```

---

## Usage Guide

---

### Running Index in Settings

<img width="2168" height="1690" alt="recoll settings" src="https://github.com/user-attachments/assets/e1be2427-3723-45e7-8a96-2f61a6ad75ae" />

Search Query: Single Keyword most relevant to desired subject

Index Directories: Insert path(s) to directory into this field to instruct Alfred to search through

Top Documents: Top X most relevant files inside directories, based on ranking score. 

Top Passages: Top X most relevant passages in Top Documents, based on ranking score. 

Word Radius: X number of words found before and after the Keyword

Force Full Reindex: Force recoll to fully reindex based on your desired parameters

---

### Preview Tab

---

<img width="2156" height="1682" alt="preview tab" src="https://github.com/user-attachments/assets/289f4e39-462f-4279-b4d1-7a1bae7f09e0" />

Preview tab shows results of Alfred indexing for review and fact checking

---

### Ask Alfred

---

<img width="2166" height="1696" alt="ask alfred" src="https://github.com/user-attachments/assets/8412f54d-fac9-45ab-a425-1e50ec4fefa7" />

Changing Models: Select the Dropdown menu directly to the right of Ask Alfred. It will include all downloaded models in Ollama.

Creating/Deleting Chats: Select "New Chat". To delete, click the check box next to each chat and select "Delete"

---

## Troubleshooting

### Backend won't start

Verify nothing is using port 8001:

```bash
lsof -i :8001
```

---

### Ollama not found

Install Ollama:

https://ollama.com

Download a model:

```bash
ollama pull llama3.2
```

---

### Recoll returns no results

Ensure your Recoll index has been created and is up to date.

---

## Technologies

- Python
- Starlette
- Tauri
- Rust
- JavaScript
- Ollama
- Recoll
- PyInstaller

---

## License

MIT License

---

## Acknowledgements

This project would not be possible without:

- Tauri
- Ollama
- Recoll
- Starlette
