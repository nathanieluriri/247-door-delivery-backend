from typing import Literal
# countries configuration

# Add or remove codes here to enable/disable them.
# These must match ISO 3166-1 alpha-2 codes (which Google uses).
# You can comment them out to disable them.


ALLOWED_COUNTRIES = Literal[
    "gb", # United Kingdom, first so clients without a matching locale default to it
    "uk", # United Kingdom (Google accepts 'uk' but 'gb' is the strict ISO standard)
    "us", # United States
    "ng", # Nigeria
    "ca", # Canada
    "de", # Germany
    "fr", # France
    "au", # Australia
    "jp", # Japan
]
