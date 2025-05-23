#!/usr/bin/env python3
"""
Lightweight version of filterupdate that doesn't require device connection libraries.
This version can query IRR databases and generate configurations,
but cannot apply them directly to devices.
"""

import argparse
import os
import re
import socket
import subprocess
import sys
import tempfile


class IRRQuerier:
    """Class to query IRR databases for prefix information."""

    def __init__(self, server="rr.ntt.net", port=43):
        """Initialize with the IRR server to query."""
        self.server = server
        self.port = port

    def _send_query(self, query):
        """Send a query to the IRR server and return the response."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.server, self.port))
            sock.sendall(f"{query}\n".encode())

            # Receive the response
            response = b""
            while True:
                data = sock.recv(4096)
                if not data:
                    break
                response += data

            sock.close()
            return response.decode("utf-8", errors="ignore")
        except Exception as e:
            print(f"Error querying IRR server: {e}")
            return ""

    def get_prefixes_for_asset(self, asset, ipv6=False):
        """Get prefixes for an AS-SET."""
        query_type = "6" if ipv6 else "4"
        query = f"!{query_type}{asset}"

        response = self._send_query(query)
        prefixes = []

        # Parse the response to extract prefixes
        for line in response.splitlines():
            line = line.strip()
            if not line or line.startswith("%") or line.startswith("!"):
                continue

            # Basic validation for IPv4/IPv6 prefixes
            if ipv6:
                # Very basic IPv6 CIDR validation
                if ":" in line and "/" in line:
                    prefixes.append(line)
            else:
                # Very basic IPv4 CIDR validation
                if re.match(r"^\d+\.\d+\.\d+\.\d+/\d+$", line):
                    prefixes.append(line)

        return prefixes

    def generate_juniper_config(self, prefixes, prefix_list_name, ipv6=False):
        """Generate Juniper configuration for the prefix list."""
        family = "inet6" if ipv6 else "inet"
        config_lines = [
            f"policy-options {{\n",
            f"    replace:\n",
            f"    prefix-list {prefix_list_name} {{\n",
        ]

        for prefix in prefixes:
            config_lines.append(f"        {prefix};\n")

        config_lines.append("    }\n")
        config_lines.append("}\n")

        return "".join(config_lines)


def get_config_with_bgpq4(asset, prefixlist, ipv6, irr_server):
    """Use bgpq4 to generate the configuration."""
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as outfile:
        config_file = outfile.name

    try:
        cmd = ["bgpq4", "-J", asset, "-l", prefixlist, "-h", irr_server]
        if ipv6:
            cmd.append("-6")

        with open(config_file, "w") as outfile:
            subprocess.call(cmd, stdout=outfile)

        with open(config_file, "r") as fin:
            config_content = fin.read()

        os.remove(config_file)
        return config_content
    except Exception as e:
        print(f"Error using bgpq4: {e}")
        if os.path.exists(config_file):
            os.remove(config_file)
        return None


def get_config_with_direct_query(asset, prefixlist, ipv6, irr_server):
    """Use direct IRR query to generate the configuration."""
    irr = IRRQuerier(server=irr_server)
    prefixes = irr.get_prefixes_for_asset(asset, ipv6)

    if not prefixes:
        print("Error: No prefixes found for the specified AS-SET")
        return None

    return irr.generate_juniper_config(prefixes, prefixlist, ipv6)


def main():
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
    use_bgpq4 = args.use_bgpq4
    output_file = args.output_file

    print(f"Generating prefix list for {asset}...")

    # Generate configuration based on method
    if use_bgpq4:
        print("~ Starting bgpq4 ...")
        config_content = get_config_with_bgpq4(asset, prefixlist, ipv6, irr_server)
    else:
        print("~ Starting direct IRR query ...")
        config_content = get_config_with_direct_query(
            asset, prefixlist, ipv6, irr_server
        )

    if not config_content:
        print("Error: Failed to generate configuration")
        sys.exit(1)

    # Output the configuration
    if output_file:
        with open(output_file, "w") as f:
            f.write(config_content)
        print(f"Configuration written to {output_file}")
    else:
        print("\n" + config_content)

    print("\nNote: This is a lightweight version that only generates configurations.")
    print("To apply this configuration to a device, you need to:")
    print("1. Save the output to a file")
    print("2. Use the Juniper CLI or another tool to apply the configuration")


if __name__ == "__main__":
    main()
