"""Server entrypoint.

Serves the JSON API and the Gradio UI from one process:

    python main.py

    http://127.0.0.1:8000/ui      Gradio interface
    http://127.0.0.1:8000/docs    OpenAPI docs
    http://127.0.0.1:8000/healthz Liveness

For the interactive command-line version, use ``python cli.py``.
"""

from __future__ import annotations

import uvicorn

from app.application import create_app
from app.settings import get_settings

app = create_app()


def main() -> None:
    """Run the development server."""
    settings = get_settings()
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
