#!/usr/bin/env python3
import argparse
import json
import logging
import os
import pathlib
import re
import urllib

import joblib
import openreview
import tenacity

from ml_research_tools.core.base_tool import BaseTool
from ml_research_tools.core.config import Config

logger = logging.getLogger()


def get_venue_pdfs_with_metadata(venue_id, username=None, password=None):
    """
    Fetch all PDF links from an OpenReview venue along with paper metadata.

    Args:
        venue_id (str): The venue ID (e.g., "ICLR.cc/2026/Conference")
        username (str, optional): OpenReview username
        password (str, optional): OpenReview password

    Returns:
        list: A list of dictionaries containing paper metadata and PDF links
              Each dict has keys: 'title', 'authors', 'pdf_url', 'forum_url', 'number'
    """

    # Initialize the OpenReview client
    if username and password:
        client = openreview.api.OpenReviewClient(
            baseurl="https://api2.openreview.net", username=username, password=password
        )
    else:
        client = openreview.api.OpenReviewClient(baseurl="https://api2.openreview.net")

    papers = []

    try:
        # Get the venue group
        venue_group = client.get_group(venue_id)
        submission_name = venue_group.content.get("submission_name", {}).get("value", "Submission")
        submission_invitation = f"{venue_id}/-/{submission_name}"

        # Get all submissions
        print(f"Fetching submissions from {venue_id}...")
        submissions = client.get_all_notes(invitation=submission_invitation)
        print(f"Found {len(submissions)} submissions")

        # Extract metadata and PDF links
        for submission in submissions:
            pdf_value = submission.content.get("pdf", {}).get("value")

            if pdf_value:
                # Create PDF URL
                pdf_url = f"https://openreview.net/pdf?id={submission.id}"

                # Extract metadata
                paper_data = {
                    "number": submission.number,
                    "title": submission.content.get("title", {}).get("value", "No title"),
                    "authors": submission.content.get("authors", {}).get("value", []),
                    "pdf_url": pdf_url,
                    "forum_url": f"https://openreview.net/forum?id={submission.forum}",
                    "submission_id": submission.id,
                    "full": submission.content,
                }

                papers.append(paper_data)

        print(f"Successfully extracted {len(papers)} papers with metadata")

    except Exception as e:
        print(f"Error fetching papers from venue {venue_id}: {str(e)}")
        raise

    return papers


class OpenreviewLoadTool(BaseTool):
    name = "oreview-get"
    description = "Download all pdfs from openreview venue"

    def __init__(self, services) -> None:
        """Initialize the LaTeX grammar tool."""
        super().__init__(services)
        self.logger = logging.getLogger(__name__)

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """Add tool-specific arguments to the parser."""
        parser.add_argument("venue", help="Venue ID (like 'ICLR.cc/2026/Conference')")
        parser.add_argument(
            "--output",
            "-o",
            help="Path to save PDFs to",
        )
        parser.add_argument(
            "--override",
            help="Override existing PDFs",
            action="store_true",
        )
        parser.add_argument("--n-jobs", "-n", help="Number of workers", type=int)

    def execute(self, config: Config, args: argparse.Namespace) -> int:
        args.output = args.output or args.venue
        args.output = re.sub(r"[^\w_. -]", "_", args.output)
        output = pathlib.Path(args.output)
        output.mkdir(exist_ok=True)

        papers = get_venue_pdfs_with_metadata(args.venue)
        if args.n_jobs:
            process = joblib.Parallel(return_as="generator", n_jobs=args.n_jobs)(
                joblib.delayed(self._load_paper)(paper, output, override=args.override)
                for paper in papers
            )
        else:
            process = (self._load_paper(paper, output, override=args.override) for paper in papers)

        with self.create_progress(console=self.console) as progress:
            task_id = progress.add_task("Loading papers", total=len(papers))
            for file, paper in zip(process, papers):
                paper["file_name"] = file
                progress.update(task_id, advance=1, refresh=True)

            with open(output / "index.json", "w") as f:
                json.dump(papers, f)
            return 0

    @staticmethod
    @tenacity.retry(
        stop=tenacity.stop_after_attempt(10),
        wait=tenacity.wait_exponential(multiplier=1.5, min=10, max=60 * 15),
        retry=tenacity.retry_if_exception(
            lambda x: "http" in str(x).lower() or "retrieval incomplete" in str(x)
        ),
        reraise=True,
        after=tenacity.after_log(logger, logging.WARNING),
    )
    def _load_paper(paper, output: pathlib.Path, override=False):
        if "pdf_url" not in paper or "submission_id" not in paper or "title" not in paper:
            return None

        pdf_url = paper.get("pdf_url")

        file_name = f"{paper['submission_id']}_{paper['title']}.pdf"
        file_name = re.sub(r"[^\w_. -]", "_", file_name)

        result_path = output / file_name
        if not result_path.exists() or override:
            try:
                urllib.request.urlretrieve(pdf_url, result_path)
            except Exception as e:
                print(f"Failed to load {pdf_url}, {e}")
                raise

        return file_name
