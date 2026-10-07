# SoulSync MVP

SoulSync is a Streamlit-based student life planning application with Journaling, AI-assisted planning, supportive chat, missions, XP, streaks, and shields.

## Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Configuration

- `DATABASE_URL`: defaults to `sqlite:///soulsync.db`.
- `GOOGLE_API_KEY`: optional; deterministic fallback behavior remains available when absent.
- `GEMINI_MODEL_ID`: Gemini model identifier.

## Active features

- Dashboard stats, streak, and shield summary.
- Daily Journal and structured signal extraction.
- Mission planning, swaps, micro actions, and Party suggestions.
- Your Voice supportive chat with explicit permission before private Journal context is used.
- Gemini integration with deterministic fallback behavior.

Legacy governance and story subsystems are not part of the active MVP. Existing database tables from earlier builds may remain inert for compatibility.
