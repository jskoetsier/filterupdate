#!/usr/bin/env python3
"""
Lightweight version of filterupdate that generates prefix lists from IRR databases
without requiring device connection libraries. Modernized with pathlib, type hints,
logging, and subprocess.run.
"""

import argparse
import logging
import os
import re
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class IRRQuerier:
    """Class to query IRR databases for prefix information."""

    def __init__(self, server: str = "rr.ntt.net", port: int = 43) -> None:
        """
        Initialize with the IRR server to query.

        Args:
            server: IRR server hostname or IP address.
            port: Port number for the IRR query.
        """
        self.server = server
        self.port = port

    def _send_query(self, query: str) -> str:
        """Send a query to the IRR server and return the response as a string."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect((self.server, self.port))
                sock.sendall(f"{query}\n".encode())
                response = b""
                while True:
                    data = sock.recv(4096)
                    if not data:
                        break
                    response += data
                return response.decode("utf-8", errors="ignore")
        except Exception as exc:
            logger.error("Error querying IRR server: %s", exc)
            return ""

    def get_prefixes_for_asset(self, asset: str, ipv6: bool = False) -> List[str]:
        """Get prefixes for an AS-SET."""
        query_type = "6" if ipv6 else "4"
        query = f"!{query_type}{asset}"
        response = self._send_query(query)
        prefixes: List[str] = []

        for line in response.splitlines():
            line = line.strip()
            if not line or line.startswith("%") or line.startswith("!"):
                continue

            if ipv6:
                if ":" in line and "/" in line:
                    prefixes.append(line)
            else:
                if re.match(r"^\d+\.\d+\.\d+\.\d+/\d+$", line):
                    prefixes.append(line)

        return prefixes

    def generate_juniper_config(self, prefixes: List[str], prefix_list_name: str, ipv6: bool = False) -> str:
        """Generate Juniper configuration for the prefix list."""
        family = "inet6" if ipv6 else "inet"
        config_lines = [
            "policy-options {",
            "    replace:",
            f"    prefix-list {prefix_list_name} {{",
        ]

        for prefix in prefixes:
            config_lines.append(f"        {prefix};")

        config_lines.append("    }")
        config_lines.append("}")

        return "\n".join(config_lines)


def get_config_with_bgpq4(
    asset: str,
    prefixlist: str,
    ipv6: bool,
    irr_server: str,
) -> Optional[str]:
    """Use bgpq4 to generate the configuration."""
    fd, temp_path = tempfile.mkstemp()
    config_file = Path(temp_path)
    os.close(fd)

    try:
        cmd = ["bgpq4", "-J", asset, "-l", prefixlist, "-h", irr_server]
        if ipv6:
            cmd.append("-6")

        with open(config_file, "w") as outfile:
            subprocess.run(cmd, stdout=outfile, check=True)
        with open(config_file, "r") as fin:
            config_content = fin.read()
        config_file.unlink(missing_ok=True)
        return config_content
    except Exception as exc:
        logger.error("Error using bgpq4: %s", exc)
        if config_file.exists():
            config_file.unlink()
        return None


def get_config_with_direct_query(
    asset: str,
    prefixlist: str,
    ipv6: bool,
    irr_server: str,
) -> Optional[str]:
    """Use direct IRR query to generate the configuration."""
    irr = IRRQuerier(server=irr_server)
    prefixes = irr.get_prefixes_for_asset(asset, ipv6)

    if not prefixes:
        logger.error("Error: No prefixes found for the specified AS-SET")
        return None

    irr_obj = IRRQuerier(server=irr_server)
    return irr_obj.generate_juniper_config(prefixes, prefixlist, ipv6)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lightweight tool to generate prefix lists from IRR databases"
    )
    parser.add_argument(
        "-a",
        action="store",
        type=str,
        help="AS-SET to create prefixlist",
        dest="asset",
        required=True,
    )
    parser.add_argument(
        "-l",
        action="store",
        type=str,
        help="prefix-list name",
        dest="prefixlist",
        required=True,
    )
    parser.add_argument(
        "-6",
        action="store_true",
        default=False,
        help="Use IPv6",
        dest="ipv6",
        required=False,
    )
    parser.add_argument(
        "-s",
        action="store",
        type=str,
        help="IRR server to query (default: rr.ntt.net)",
        dest="irr_server",
        default="rr.ntt.net",
        required=False,
    )
    parser.add_argument(
        "-o",
        action="store",
        type=str,
        help="Output file (default: stdout)",
        dest="output_file",
        default=None,
        required=False,
    )
    parser.add_argument(
        "--use-bgpq4",
        action="store_true",
        default=False,
        help="Use bgpq4 instead of direct IRR query",
        dest="use_bgpq4",
        required=False,
    )
    args = parser.parse_args()

    asset = args.asset
    prefixlist = args.prefixlist
    ipv6 = args.ipv6
    irr_server = args.irr_server
    output_file = args.output_file
    use_bgpq4 = args.use_bgpq4

    logger.info("Generating prefix list for %s...", asset)

    if use_bgpq4:
        logger.info("~ Starting bgpq4 ...")
        config_content = get_config_with_bgpq4(asset, prefixlist, ipv6, irr_server)
    else:
        logger.info("~ Starting direct IRR query ...")
        config_content = get_config_with_direct_query(asset, prefixlist, ipv6, irr_server)

    if not config_content:
        logger.error("Error: Failed to generate configuration")
        sys.exit(1)

    if output_file:
        Path(output_file).write_text(config_content)
        logger.info("Configuration written to %s", output_file)
    else:
        print("\n" + config_content)

    logger.info(
        "Note: This is a lightweight version that only generates configurations.\n"
        "To apply this configuration to a device, you need to:\n"
        "1. Save the output to a file\n"
        "2. Use the Juniper CLI or another tool to apply the configuration"
    )


if __name__ == "__main__":
    main()
