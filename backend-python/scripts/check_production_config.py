"""Validate production environment variables without contacting external services."""

import sys
from pathlib import Path

from pydantic import ValidationError

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import Settings  # noqa: E402


def main() -> int:
    try:
        settings = Settings()
    except ValidationError as exc:
        print("Production configuration check failed:")
        for error in exc.errors(include_url=False, include_input=False):
            print(f"- {error['msg']}")
        return 1

    if settings.app_env.strip().lower() not in {"production", "prod"}:
        print("Production configuration check failed:")
        print("- APP_ENV must be production or prod")
        return 1

    print("Production configuration check passed.")
    print(
        "Providers: "
        f"ai={settings.ai_provider}, embedding={settings.embedding_provider}, "
        f"speech={settings.speech_to_text_provider}, tts={settings.text_to_speech_provider}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
