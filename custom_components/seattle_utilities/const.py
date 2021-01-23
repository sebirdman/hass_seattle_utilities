"""Constants for seattle_utilities."""
# Base component constants
NAME = "Seattle Utilities"
DOMAIN = "seattle_utilities"
DOMAIN_DATA = f"{DOMAIN}_data"
VERSION = "0.0.1"
ATTRIBUTION = "Data provided by Seattle Utilities"
ISSUE_URL = "https://github.com/sebirdman/hass_seattle_utilities/issues"

# Icons
ICON = "mdi:power-plug"

# Platforms
SENSOR = "sensor"
PLATFORMS = [SENSOR]

# Configuration and options
CONF_ENABLED = "enabled"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

# Defaults
DEFAULT_NAME = DOMAIN


STARTUP_MESSAGE = f"""
-------------------------------------------------------------------
{NAME}
Version: {VERSION}
This is a custom integration for Seattle Utilities!
If you have any issues with this you need to open an issue here:
{ISSUE_URL}
-------------------------------------------------------------------
"""
