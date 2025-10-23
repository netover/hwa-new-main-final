#!/usr/bin/env python3
"""Test script to diagnose admin template rendering issues."""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.templating import Jinja2Templates


def test_template_rendering():
    """Test if admin.html template can be rendered."""
    try:
        # Create templates instance
        templates_dir = os.path.join(os.path.dirname(__file__), "templates")
        templates = Jinja2Templates(directory=templates_dir)

        # Create a mock request
        from starlette.requests import Request as StarletteRequest

        mock_scope = {
            "type": "http",
            "method": "GET",
            "path": "/admin",
            "query_string": b"",
            "headers": [],
        }

        # Create mock request
        request = StarletteRequest(mock_scope)

        # Try to render template
        response = templates.TemplateResponse("admin.html", {"request": request})
        print("Template rendered successfully!")
        print(f"Response type: {type(response)}")
        print(
            f"Response content length: {len(response.body) if hasattr(response, 'body') else 'N/A'}"
        )

    except Exception as e:
        print(f"Error rendering template: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_template_rendering()
