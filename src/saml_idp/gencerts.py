"""CLI that generates the IdP's signing certificates (run as an init container)."""

import argparse
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from saml_idp.certs import write_certs


logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate the IdP's signing certificates: two valid for a year, one "
            "expired, and one that only becomes valid in a year."
        )
    )
    parser.add_argument(
        "directory", type=Path, help="directory to write <name>.crt/<name>.key into"
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    try:
        paths = write_certs(args.directory, datetime.now(UTC))
    except OSError as e:
        sys.exit(f"Error: cannot write certificates to {args.directory}: {e.strerror}")
    for path in paths:
        logger.info("Wrote %s", path)
