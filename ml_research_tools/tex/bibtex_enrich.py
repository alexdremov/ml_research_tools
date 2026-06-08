#!/usr/bin/env python3
import argparse
import logging

import time
import functools
import bibtexparser
import requests
from rich import print
from tqdm.auto import tqdm

from ml_research_tools.cache import RedisCache
from ml_research_tools.core.base_tool import BaseTool
from ml_research_tools.core.config import Config


def make_search_request(query, redis_cache: RedisCache | None = None, fetcher=requests.get):
    key = "dblp:" + query
    if redis_cache is not None and redis_cache.enabled and not redis_cache.recache:
        cached = redis_cache.get(key)
        if cached is not None:
            return cached
    request = fetcher("https://dblp.org/search/publ/api", dict(q=query, format="json"))
    if request.status_code != 200:
        return None

    if redis_cache is not None and redis_cache.enabled:
        redis_cache.set(key, request.json())

    return request.json()


def get_bib_for_url(url, redis_cache: RedisCache | None = None, fetcher=requests.get):
    if redis_cache is not None and redis_cache.enabled and not redis_cache.recache:
        cached = redis_cache.get("bib:" + url)
        if cached is not None:
            return cached
    request = fetcher(url + ".bib", dict(param=1))
    if request.status_code != 200:
        return None
    if redis_cache is not None and redis_cache.enabled:
        redis_cache.set("bib:" + url, request.text)
    return request.text


class BibtexEnrichTool(BaseTool):
    name = "bibtex-enrich"
    description = "Enrich bibtex file entries with publication information"

    def __init__(self, services) -> None:
        """Initialize the LaTeX grammar tool."""
        super().__init__(services)
        self.logger = logging.getLogger(__name__)
        self.last_request_time = 0

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """Add tool-specific arguments to the parser."""
        parser.add_argument("input_file", help="Path to the LaTeX file to process")
        parser.add_argument(
            "--output",
            "-o",
            help="Path to save the diff file (default: <input>_improved.bib)",
        )
        parser.add_argument(
            "--cooldown",
            type=int,
            default=30,
            help="Cooldown in seconds between API requests (default: 30)",
        )

    def throttled_get(self, url, params=None, cooldown=30):
        if time.time() - self.last_request_time < cooldown:
            time.sleep(cooldown - (time.time() - self.last_request_time))
        response = requests.get(url, params=params)
        self.last_request_time = time.time()
        return response

    def execute(self, config: Config, args: argparse.Namespace) -> int:
        args.output = args.output or f"{args.input_file}_improved.bib"

        redis_cache = self.services.get_typed("redis_cache", RedisCache)
        fetcher = functools.partial(self.throttled_get, cooldown=args.cooldown)

        with open(args.input_file, "r") as f:
            library = bibtexparser.load(f)
        result = []
        for entry in tqdm(library.entries):
            query = entry["title"]
            found = make_search_request(query, redis_cache=redis_cache, fetcher=fetcher)
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
            bib = get_bib_for_url(url, redis_cache=redis_cache, fetcher=fetcher)
            if bib is None:
                tmp_db = bibtexparser.bibdatabase.BibDatabase()
                tmp_db.entries = [entry]
                result.append(bibtexparser.dumps(tmp_db))
                self.logger.warning(f"Did not get bibtex for {query}")
                continue

            parsed = bibtexparser.loads(bib)
            parsed_entry = parsed.entries[0]

            if self.simplify_title(parsed.entries[0].get("title", None)) != self.simplify_title(
                entry["title"]
            ):
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

    def simplify_title(self, title):
        title = title.replace("{", "").replace("}", "")
        return "".join(title.lower().split())


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
