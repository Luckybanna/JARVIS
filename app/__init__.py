"""
JARVIS - Windows Desktop Proactive AI Assistant
"""

# Ensure Windows native SSL certificates are trusted across all HTTP libraries
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

__version__ = "1.0.0"
__author__ = "JARVIS Architect"
