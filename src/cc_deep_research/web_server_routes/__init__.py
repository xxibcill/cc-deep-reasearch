"""FastAPI web server route modules."""

from cc_deep_research.web_server_routes.misc_routes import register_misc_routes
from cc_deep_research.web_server_routes.research_run_routes import register_research_run_routes
from cc_deep_research.web_server_routes.session_routes import register_session_routes
from cc_deep_research.web_server_routes.websocket_adapter import register_websocket_routes

__all__ = [
    "register_misc_routes",
    "register_research_run_routes",
    "register_session_routes",
    "register_websocket_routes",
]
