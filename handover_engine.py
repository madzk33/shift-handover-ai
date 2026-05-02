"""Core engine: LLM-powered structuring of raw shift notes into validated handover documents."""

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq
from openai import OpenAI

from schema import Handover

load_dotenv()

PROMPTS_DIR = Path(__file__).parent / "prompts"
GROQ_MODEL = "llama-3.3-70b-versatile"
WHISPER_MODEL = "whisper-1"


def load_system_prompt() -> str:
    """Read the system prompt from prompts/system_prompt.md."""
    prompt_path = PROMPTS_DIR / "system_prompt.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"System prompt not found at {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")


def transcribe_audio(audio_file_path: str) -> str:
    """Transcribe an audio file to text using the OpenAI Whisper API.

    Args:
        audio_file_path: Path to the audio file (.mp3, .wav, or .m4a).

    Returns:
        Transcribed text string.

    Raises:
        ValueError: If the OPENAI_API_KEY is not configured.
        RuntimeError: If the transcription API call fails.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set. Add it to your .env file.")

    try:
        client = OpenAI(api_key=api_key)
        with open(audio_file_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model=WHISPER_MODEL,
                file=audio_file,
            )
        return transcript.text
    except Exception as e:
        raise RuntimeError(f"Audio transcription failed: {e}") from e


def generate_handover(raw_notes: str, shift_metadata: dict) -> Handover:
    """Structure raw shift notes into a validated Handover document via LLM.

    Args:
        raw_notes: Free-text notes from the operative.
        shift_metadata: Dict with keys: shift_date, shift_type, operative, line_or_area.

    Returns:
        Validated Handover instance.

    Raises:
        ValueError: If the API key is missing or LLM output fails validation.
        RuntimeError: If the Groq API call fails.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set. Add it to your .env file.")

    system_prompt = load_system_prompt()

    user_message = (
        f"## Shift Metadata\n"
        f"- Date: {shift_metadata.get('shift_date', 'unspecified')}\n"
        f"- Shift type: {shift_metadata.get('shift_type', 'unspecified')}\n"
        f"- Operative: {shift_metadata.get('operative', 'unspecified')}\n"
        f"- Line / Area: {shift_metadata.get('line_or_area', 'unspecified')}\n\n"
        f"## Raw Notes\n"
        f"{raw_notes}"
    )

    try:
        client = Groq(api_key=api_key)
        chat_completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        raise RuntimeError(f"Groq API call failed: {e}") from e

    raw_json = chat_completion.choices[0].message.content

    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}\nRaw output: {raw_json}") from e

    try:
        handover = Handover(**parsed)
    except Exception as e:
        raise ValueError(
            f"LLM output failed schema validation: {e}\nParsed JSON: {json.dumps(parsed, indent=2)}"
        ) from e

    return handover
