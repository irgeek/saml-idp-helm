"""CLI entry point that serves the IdP with waitress."""

import argparse
import logging
import os
import sys
from pathlib import Path

from waitress import serve

from saml_idp.config import ConfigError
from saml_idp.web import create_app


DEFAULT_CONFIG_PATH = "/etc/saml-idp/config.json"
DEFAULT_CERTS_DIR = "/var/run/saml-idp/certs"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run the test SAML IdP. Reads its config file from $SAML_IDP_CONFIG "
            f"(default {DEFAULT_CONFIG_PATH}) and signing certificates from "
            f"$SAML_IDP_CERTS_DIR (default {DEFAULT_CERTS_DIR})."
        )
    )
    parser.add_argument("--host", default="0.0.0.0", help="address to listen on")
    parser.add_argument("--port", type=int, default=8080, help="port to listen on")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    config_path = Path(os.environ.get("SAML_IDP_CONFIG", DEFAULT_CONFIG_PATH))
    certs_dir = Path(os.environ.get("SAML_IDP_CERTS_DIR", DEFAULT_CERTS_DIR))
    try:
        app = create_app(config_path, certs_dir)
    except ConfigError as e:
        sys.exit(f"Error: invalid configuration: {e}")
    except (OSError, RuntimeError) as e:
        sys.exit(
            f"Error: {e}. Generate certificates with `saml-idp-gencerts {certs_dir}` "
            "or set SAML_IDP_CERTS_DIR."
        )
    serve(app, host=args.host, port=args.port)
