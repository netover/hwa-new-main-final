"""Jinja2 extension for CSP nonce support."""

from jinja2 import Environment
from jinja2.ext import Extension


class CSPNonceExtension(Extension):
    """
    Jinja2 extension that provides access to CSP nonce in templates.

    This extension makes the CSP nonce available as a global variable
    in Jinja2 templates, allowing scripts to include the nonce attribute
    required by Content Security Policy.
    """

    def __init__(self, environment: Environment):
        """
        Initialize the CSP nonce extension.

        Args:
            environment: The Jinja2 environment
        """
        super().__init__(environment)

        # Add the nonce function to the global namespace
        environment.globals["csp_nonce"] = self._get_csp_nonce

    def _get_csp_nonce(self) -> str:
        """
        Get the CSP nonce from the current request context.

        Returns:
            The CSP nonce string, or empty string if not available
        """
        # CSP nonce is not available in template context during rendering
        # This function is called during template rendering, but the request context
        # is not directly accessible here. The nonce should be passed explicitly
        # in the template context instead.
        return ""


def setup_csp_jinja_extension(templates):
    """
    Set up CSP support for Jinja2 templates.

    Args:
        templates: The Jinja2Templates instance
    """
    # Add the CSP nonce extension to the Jinja2 environment
    templates.env.add_extension(CSPNonceExtension)

    # Add a filter for CSP nonce in script tags
    def script_nonce(nonce: str) -> str:
        """Generate a script tag with nonce attribute."""
        return f'nonce="{nonce}"'

    templates.env.filters["script_nonce"] = script_nonce
