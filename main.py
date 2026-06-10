"""Cloud Run entrypoint — wraps the ADK agent in a FastAPI app.

ADK discovers the `revenueguard` package (which exposes `root_agent`) by scanning
the agents directory. Locally you can ignore this file and just run `adk web`.
"""

import os

from google.adk.cli.fast_api import get_fast_api_app

# agents_dir = repo root by default; ADK finds the `revenueguard/` agent package
# under it. In the container, ADK_AGENTS_DIR points at a dir holding ONLY the
# agent package so stray dirs (vendor/) don't show up as selectable apps.
app = get_fast_api_app(
    agents_dir=os.environ.get(
        "ADK_AGENTS_DIR", os.path.dirname(os.path.abspath(__file__))
    ),
    web=True,  # serve the ADK dev chat UI at / as the public demo surface
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
