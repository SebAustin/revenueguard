"""Cloud Run entrypoint — wraps the ADK agent in a FastAPI app.

ADK discovers the `revenueguard` package (which exposes `root_agent`) by scanning
the agents directory. Locally you can ignore this file and just run `adk web`.
"""

import os

from google.adk.cli.fast_api import get_fast_api_app

# agents_dir = repo root; ADK finds the `revenueguard/` agent package under it.
app = get_fast_api_app(
    agents_dir=os.path.dirname(os.path.abspath(__file__)),
    web=True,  # serve the ADK dev chat UI at / as the public demo surface
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
