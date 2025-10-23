import re
from typing import Dict, Optional


class CSPParser:
    """Parser for Content Security Policy headers."""

    @staticmethod
    def parse(csp_header: str) -> Dict[str, list]:
        """Parse CSP header into directives and values."""
        directives = {}
        if not csp_header:
            return directives

        # Split by semicolon but keep quoted values intact
        parts = re.split(r';(?![^"]*"+)', csp_header)

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Handle quoted values
            if '"' in part:
                directive, value = re.split(r"\s+", part, 1)
                directive = directive.strip()
                value = value.strip('"')
                directives.setdefault(directive, []).append(value)
            else:
                if " " in part:
                    directive, value = part.split(" ", 1)
                    directive = directive.strip()
                    value = value.strip()
                    directives.setdefault(directive, []).append(value)
                else:
                    directive = part
                    directives.setdefault(directive, []).append("")

        return directives

    @staticmethod
    def has_directive(csp_header: str, directive: str) -> bool:
        """Check if CSP header contains a specific directive."""
        parsed = CSPParser.parse(csp_header)
        return directive in parsed

    @staticmethod
    def get_directive_values(csp_header: str, directive: str) -> list:
        """Get all values for a specific directive."""
        parsed = CSPParser.parse(csp_header)
        return parsed.get(directive, [])


class SecurityHeaderParser:
    """Parser for security headers."""

    @staticmethod
    def parse_x_frame_options(header_value: str) -> Optional[str]:
        """Parse X-Frame-Options header."""
        if not header_value:
            return None
        return header_value.strip().upper()

    @staticmethod
    def parse_x_xss_protection(header_value: str) -> Optional[dict]:
        """Parse X-XSS-Protection header."""
        if not header_value:
            return None

        result = {"enabled": False, "directive": None}
        parts = header_value.split(";")

        if parts[0].strip().lower() == "1":
            result["enabled"] = True

            if len(parts) > 1:
                directive = parts[1].strip().lower()
                if directive.startswith("mode="):
                    result["directive"] = directive.split("=")[1].strip()

        return result
