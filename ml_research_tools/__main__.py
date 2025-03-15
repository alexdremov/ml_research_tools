import argparse
import sys
import logging

from .tex.latex_improver import main as latex_grammar
from .exp.wandb_downloader import main as wandb_downloader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)


def main():
    parser = argparse.ArgumentParser("ml_research_tools", add_help=False)
    parser.add_argument("tool", choices=["latex-grammar", "wandb_downloader", "help"], help="use latex grammar fix module")
    args, next_args = parser.parse_known_args()

    match args.tool:
        case "latex-grammar":
            return latex_grammar(next_args)
        case "wandb_downloader":
            return wandb_downloader(next_args)
        case "help":
            parser.print_help()
            return 0
        case _:
            raise RuntimeError(f"Unknown tool: {args.tool}")


if __name__ == "__main__":
    sys.exit(main())
