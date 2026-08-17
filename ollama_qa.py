#!/usr/bin/env python3
import requests
import argparse
from pathlib import Path
import textwrap

#https://ollama.com/library/gpt-oss
#https://ollama.com/library/gemma3

# ---------- CONFIG ----------
OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "phi4"   # or "mistral", "phi3", etc.


# ---------- HELPER ----------
def load_passages(path: Path) -> str:
    """Load the background text from ml_passages.txt."""
    if not path.exists():
        raise FileNotFoundError(f"Knowledge file not found: {path}")

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError("Knowledge file is empty.")
    return text


def build_prompt(context: str, question: str) -> str:
    """Construct a grounded prompt for the model."""
    prompt = textwrap.dedent(f"""
    You are a factual assistant. 
    Use only the information from the background text below to answer the question.

    If the background text does not contain enough information,
    respond exactly with: "I do not have enough information."

    --------------------
    BACKGROUND TEXT:
    {context}
    --------------------

    QUESTION:
    {question}

    Provide a concise, factual answer grounded only in the background text.
    """).strip()
    return prompt


def query_ollama(model: str, prompt: str) -> str:
    """Send a prompt to Ollama and return the generated text."""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False  # Wait for full completion
    }

    response = requests.post(OLLAMA_URL, json=payload)
    response.raise_for_status()

    data = response.json()
    return data.get("response", "").strip()


def format_text(answer: str, width: int = 90) -> str:
    """Nicely wrap and format the text for readability."""
    paragraphs = answer.strip().split("\n")
    wrapped = "\n\n".join(
        textwrap.fill(p.strip(), width=width) for p in paragraphs if p.strip()
    )
    return wrapped


# ---------- MAIN ----------
def main():
    parser = argparse.ArgumentParser(
        description="Ask questions using ml_passages.txt as context (via Ollama)."
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=(Path(__file__).resolve().parent.parent / "ml_passages.txt"),
        help="Path to passages file (default: ml_passages.txt)"
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Ollama model to use (default: {DEFAULT_MODEL})"
    )
    parser.add_argument(
        "--question",
        help="Question to ask (if not provided, prompts interactively)"
    )

    args = parser.parse_args()

    # Load background context
    try:
        context = load_passages(args.file)
    except Exception as e:
        print(f"[ERROR] {e}")
        return

    # Get user question
    question = args.question or input("Enter your question: ").strip()
    if not question:
        print("No question provided.")
        return

    # Build prompt
    prompt = build_prompt(context, question)

    # Query Ollama
    print(f"\n[Using model: {args.model}]\n")
    print("Thinking...\n")

    try:
        answer = query_ollama(args.model, prompt)
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Ollama request failed: {e}")
        return

    formatted = format_text(answer)

    print("Answer:\n")
    print(formatted)
    print("\n" + "-" * 60)


if __name__ == "__main__":
    main()
