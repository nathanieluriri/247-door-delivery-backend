from typing import Literal
# countries configuration

# Add or remove codes here to enable/disable them.
# These must match ISO 3166-1 alpha-2 codes (which Google uses).
# You can comment them out to disable them.


ALLOWED_COUNTRIES = Literal[
    "us", # United States
    "ng", # Nigeria
    "uk", # United Kingdom (Google accepts 'uk' but 'gb' is the strict ISO standard)
    "ca", # Canada
    "de", # Germany
    "fr", # France
    "au", # Australia
    "jp", # Japan
]
