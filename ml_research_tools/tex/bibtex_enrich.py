#!/usr/bin/env python3
import argparse
import logging

import bibtexparser
import requests
from rich import print
from tqdm.auto import tqdm

from ml_research_tools.cache import RedisCache
from ml_research_tools.core.base_tool import BaseTool
from ml_research_tools.core.config import Config


def make_search_request(query):
    request = requests.get("https://dblp.org/search/publ/api", dict(q=query, format="json"))
    if request.status_code != 200:
        return None
    return request.json()


def get_bib_for_url(url):
    request = requests.get(url + ".bib", dict(param=1))
    if request.status_code != 200:
        return None
    return request.text


class BibtexEnrichTool(BaseTool):
    name = "bibtex-enrich"
    description = "Enrich bibtex file entries with publication information"

    def __init__(self, services) -> None:
        """Initialize the LaTeX grammar tool."""
        super().__init__(services)
        self.logger = logging.getLogger(__name__)

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """Add tool-specific arguments to the parser."""
        parser.add_argument("input_file", help="Path to the LaTeX file to process")
        parser.add_argument(
            "--output",
            "-o",
            help="Path to save the diff file (default: <input>_improved.bib)",
        )

    def execute(self, config: Config, args: argparse.Namespace) -> int:
        args.output = args.output or f"{args.input_file}_improved.bib"

        with open(args.input_file, "r") as f:
            library = bibtexparser.load(f)
        result = []
        for entry in tqdm(library.entries):
            query = entry["title"]
            found = make_search_request(query)
            if found is None:
                tmp_db = bibtexparser.bibdatabase.BibDatabase()
                tmp_db.entries = [entry]
                result.append(bibtexparser.dumps(tmp_db))
                self.logger.warning(f"Did not find info about {query}")
                continue
            found = found["result"]["hits"]
            if found is None or len(found) == 0 or "hit" not in found:
                tmp_db = bibtexparser.bibdatabase.BibDatabase()
                tmp_db.entries = [entry]
                result.append(bibtexparser.dumps(tmp_db))
                self.logger.warning(f"Did not find info about {query}")
                continue

            found = found["hit"][0]
            url = found["info"]["url"]
            bib = get_bib_for_url(url)

            parsed = bibtexparser.loads(bib)
            parsed_entry = parsed.entries[0]

            if parsed.entries[0].get("title", None) != entry["title"]:
                self.logger.warning(
                    f"Title mismatch for {query}: {parsed.entries[0]['title']} != {entry['title']}"
                )
                tmp_db = bibtexparser.bibdatabase.BibDatabase()
                tmp_db.entries = [entry]
                result.append(bibtexparser.dumps(tmp_db))
                continue

            parsed_entry["ID"] = entry["ID"]
            bib = bibtexparser.dumps(parsed)

            result.append(bib)

        result = "\n\n".join(result)

        with open(args.output, "w") as f:
            f.write(result)

        return 0


class BibtexFindTool(BaseTool):
    name = "bibtex-find"
    description = "Find bibtex by title"

    def __init__(self, services) -> None:
        """Initialize the LaTeX grammar tool."""
        super().__init__(services)
        self.logger = logging.getLogger(__name__)

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """Add tool-specific arguments to the parser."""
        parser.add_argument("query", help="Path to the LaTeX file to process")

    def execute(self, config: Config, args: argparse.Namespace) -> int:
        found = make_search_request(args.query)["result"]["hits"]
        if len(found) == 0 or "hit" not in found:
            self.logger.warning(f"Did not find info about {args.query}")
            return 1

        found = found["hit"][0]
        url = found["info"]["url"]
        bib = get_bib_for_url(url)

        print(bib)
        return 0
