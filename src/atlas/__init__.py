"""ATLAS BI: auditable retail analytics."""
from pathlib import Path
from dotenv import load_dotenv

# Process environment values take precedence over local configuration.
load_dotenv(Path(__file__).resolve().parents[2] / '.env', override=False)

__version__ = "0.1.0"
