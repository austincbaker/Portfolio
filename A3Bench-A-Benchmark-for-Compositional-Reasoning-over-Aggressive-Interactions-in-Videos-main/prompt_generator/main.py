import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from prompt_generator.cli import run_cli

if __name__ == "__main__":
    run_cli()