#!/usr/bin/env python3
"""
Modernized version of filterupdate that queries IRR databases for prefix information
and applies configuration to Juniper devices. Uses pathlib, type hints, logging,
and subprocess.run for improved robustness.
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

from netmiko import ConnectHandler
from netmiko.exceptions import NetMikoAuthenticationException, NetMikoTimeoutException

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class IRRQuerier:
    """Class to query IRR databases for prefix information."""

    def __init__(self, server: str = "rr.ntt.net", port: int = 43, verbose: bool = False) -> None:
        """
        Initialize with the IRR server to query.

        Args:
            server: IRR server hostname or IP address.
            port: Port number for the IRR query.
            verbose: Enable debug output.
        """
        self.server = server
        self.port = port
        self.debug = verbose

    def _send_query(self, query: str) -> bytes:
        """Send a query to the IRR server and return the raw response."""
        if self.debug:
            logger.debug("Sending query to %s: %s", self.server, query)

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
                return response
        except Exception as exc:
            logger.error("Error querying IRR server: %s", exc)
            return b""

    def get_prefixes_for_asset(self, asset: str, ipv6: bool = False) -> List[str]:
        """Get prefixes for an AS-SET."""
        prefixes: List[str] = []
        query_type = "6" if ipv6 else "4"

        # Format 1: !4AS-SET or !6AS-SET
        query = f"!{query_type}{asset}"
        if self.debug:
            logger.debug("Trying query format 1: %s", query)
        response = self._send_query(query)
        prefixes.extend(self._parse_response(response.decode(), ipv6))

        # Format 2: !gas-set or !6as-set
        if not prefixes:
            query = f"!{query_type}as-set {asset}"
            if self.debug:
                logger.debug("Trying query format 2: %s", query)
            response = self._send_query(query)
            prefixes.extend(self._parse_response(response.decode(), ipv6))

        # Format 3: !rAS-SET or !r6AS-SET
        if not prefixes:
            query = f"!r{query_type} {asset}"
            if self.debug:
                logger.debug("Trying query format 3: %s", query)
            response = self._send_query(query)
            prefixes.extend(self._parse_response(response.decode(), ipv6))

        # Format 4: !g AS-SET (for route-set queries)
        if not prefixes:
            query_cmd = "!6g" if ipv6 else "!g"
            query = f"{query_cmd} {asset}"
            if self.debug:
                logger.debug("Trying query format 4: %s", query)
            response = self._send_query(query)
            prefixes.extend(self._parse_response(response.decode(), ipv6))

        # Format 5: !a AS-SET (for as-set queries)
        if not prefixes and asset.startswith("AS"):
            as_number = asset.replace("AS", "")
            query = f"!i {as_number}"
            if self.debug:
                logger.debug("Trying query format 5: %s", query)
            response = self._send_query(query)
            prefixes.extend(self._parse_response(response.decode(), ipv6))

        return prefixes

    def _parse_response(self, response: str, ipv6: bool = False) -> List[str]:
        """Parse the response to extract prefixes."""
        prefixes: List[str] = []
        for line in response.splitlines():
            line = line.strip()
            if not line or line.startswith("%") or line.startswith("!"):
                continue

            # Basic validation for IPv4/IPv6 prefixes
            if ipv6:
                if ":" in line and "/" in line:
                    prefixes.append(line)
            else:
                if re.match(r"^\d+\.\d+\.\d+\.\d+/\d+$", line):
                    prefixes.append(line)

        if self.debug:
            logger.debug("Found %d prefixes", len(prefixes))
            if prefixes:
                logger.debug("First few prefixes: %s", prefixes[:5])

        return prefixes

    def generate_juniper_config(self, prefixes: List[str], prefix_list_name: str, ipv6: bool = False) -> str:
        """Generate Juniper configuration for the prefix list."""
        family = "inet6" if ipv6 else "inet"
        config_lines = [
            "policy-options {",
            f"    replace:",
            f"    prefix-list {prefix_list_name} {{",
        ]

        for prefix in prefixes:
            config_lines.append(f"        {prefix};")

        config_lines.append("    }")
        config_lines.append("}")

        return "\n".join(config_lines)


def check_bgpq4_installed(verbose: bool = False) -> bool:
    """Check if bgpq4 is installed and print its version and help."""
    try:
        result = subprocess.run(
            ["bgpq4"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if result.returncode != 127:  # 127 is "command not found"
            if verbose:
                logger.info("bgpq4 seems to be installed")
            if result.stdout or result.stderr:
                logger.info("bgpq4 help output:\n%s", result.stdout or result.stderr)
            return True
        else:
            if verbose:
                logger.info("bgpq4 is not installed or not in PATH")
            return False
    except FileNotFoundError:
        if verbose:
            logger.info("bgpq4 is not installed or not in PATH")
        return False
    except Exception as exc:
        if verbose:
            logger.error("Error checking bgpq4 installation: %s", exc)
        return False


def get_config_with_whois(
    asset: str,
    prefixlist: str,
    ipv6: bool,
    irr_server: str,
    verbose: bool = False,
) -> Optional[str]:
    """Use direct whois command as a fallback."""
    logger.info("Trying direct whois query for %s on %s...", asset, irr_server)

    try:
        cmd = ["whois", "-h", irr_server, asset]
        if verbose:
            logger.debug("Running whois command: %s", " ".join(cmd))

        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0 or result.stderr.strip():
            logger.error("Error with whois command: %s", result.stderr)
            return None

        if verbose:
            logger.debug("whois output length: %d bytes", len(result.stdout))
            for i, line in enumerate(result.stdout.splitlines()[:10]):
                logger.debug("%d: %s", i + 1, line)

        prefixes: List[str] = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if ipv6:
                if line.startswith("route6:"):
                    prefix = line.replace("route6:", "").strip()
                    if ":" in prefix and "/" in prefix:
                        prefixes.append(prefix)
            else:
                if line.startswith("route:"):
                    prefix = line.replace("route:", "").strip()
                    if re.match(r"^\d+\.\d+\.\d+\.\d+/\d+$", prefix):
                        prefixes.append(prefix)

        if prefixes:
            logger.info("Found %d prefixes via whois", len(prefixes))
            family = "inet6" if ipv6 else "inet"
            config_lines = [
                "policy-options {",
                "    replace:",
                f"    prefix-list {prefixlist} {{",
            ]
            for prefix in prefixes:
                config_lines.append(f"        {prefix};")
            config_lines.append("    }")
            config_lines.append("}")
            return "\n".join(config_lines)
        else:
            logger.info("No prefixes found in whois output")
            return None
    except Exception as exc:
        logger.error("Error using whois: %s", exc)
        return None


def get_config_with_bgpq4(
    asset: str,
    prefixlist: str,
    ipv6: bool,
    irr_server: str,
    verbose: bool = False,
) -> Optional[str]:
    """Use bgpq4 to generate the configuration."""
    if not check_bgpq4_installed(verbose):
        logger.info("bgpq4 is not installed or not working correctly")
        return None

    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as outfile:
        config_file = Path(outfile.name)

    servers_to_try = [irr_server]
    if irr_server == "rr.ntt.net":
        servers_to_try.extend(["whois.radb.net", "whois.ripe.net", "whois.arin.net"])

    formats_to_try: List[str] = [asset]
    if asset.startswith("AS") and "-" not in asset:
        formats_to_try.append(f"AS-{asset[2:]}")
    elif asset.startswith("AS-"):
        formats_to_try.append(f"AS{asset[3:]}")

    if ":" not in asset and "." not in asset:
        if asset.startswith("AS"):
            formats_to_try.append(f"{asset}:AS-ALL")
            formats_to_try.append(f"{asset}.AS-ALL")

    for current_server in servers_to_try:
        for current_format in formats_to_try:
            try:
                if verbose:
                    logger.debug("Trying bgpq4 with server %s and AS-SET format %s", current_server, current_format)

                base_cmd = [
                    "bgpq4",
                    "-h",
                    current_server,
                    "-J",
                    current_format,
                ]
                if ipv6:
                    base_cmd.append("-6")

                # Try different options
                command_formats = [
                    base_cmd,
                    base_cmd + ["-l", prefixlist],
                    base_cmd + ["-f", "24", "-l", prefixlist],
                    base_cmd + ["-A", current_format],
                ]

                for i, cmd in enumerate(command_formats):
                    if verbose:
                        logger.debug("Running command format %d: %s", i + 1, " ".join(cmd))

                    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    if result.returncode != 0 or result.stderr.strip():
                        logger.debug("Error with command format %d: %s", i + 1, result.stderr)
                        continue

                    if "policy-options {" not in result.stdout and "prefix-list" not in result.stdout:
                        logger.debug("No valid configuration generated with command format %d", i + 1)
                        continue

                    if "prefix-list " in result.stdout and prefixlist not in result.stdout:
                        stdout = re.sub(
                            r"prefix-list\s+[\w-]+\s+{",
                            f"prefix-list {prefixlist} {{",
                            result.stdout,
                        )
                    else:
                        stdout = result.stdout

                    config_file.write(stdout)

                    with open(config_file, "r") as fin:
                        config_content = fin.read()

                    if verbose:
                        logger.debug("bgpq4 output length: %d bytes", len(config_content))
                        for i, line in enumerate(config_content.splitlines()[:5]):
                            logger.debug("%d: %s", i + 1, line)
                        if not config_content:
                            logger.debug("bgpq4 output is empty")
                            continue

                    config_file.unlink(missing_ok=True)
                    return config_content

            except Exception as exc:
                if verbose:
                    logger.error(
                        "Error using bgpq4 with %s and %s: %s",
                        current_server,
                        current_format,
                        exc,
                    )

    # Cleanup temp file if it exists
    if config_file.exists():
        config_file.unlink()

    logger.info("All bgpq4 attempts failed. Trying whois fallback...")
    return get_config_with_whois(asset, prefixlist, ipv6, irr_server, verbose)


def get_config_with_direct_query(
    asset: str,
    prefixlist: str,
    ipv6: bool,
    irr_server: str,
    verbose: bool = False,
) -> Optional[str]:
    """Use direct IRR query to generate the configuration."""
    irr = IRRQuerier(server=irr_server, verbose=verbose)
    prefixes = irr.get_prefixes_for_asset(asset, ipv6)

    if not prefixes:
        logger.error("Error: No prefixes found for the specified AS-SET")
        return None

    return irr.generate_juniper_config(prefixes, prefixlist, ipv6)


def startwork(
    asset: str,
    prefixlist: str,
    ipv6: bool,
    irr_server: str = "rr.ntt.net",
    use_bgpq4: bool = False,
    test_mode: bool = False,
    host_device: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    port: int = 22,
    verbose: bool = False,
) -> None:
    """Main function to update prefix filters on a Juniper device using Netmiko."""
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as outfile:
        config_file = Path(outfile.name)

    os.system("clear")
    logger.info("~ Starting bgpq4 (recommended method)...")
    config_content = get_config_with_bgpq4(asset, prefixlist, ipv6, irr_server, verbose)

    if not config_content and not use_bgpq4:
        logger.info("~ bgpq4 failed, falling back to direct IRR query...")
        config_content = get_config_with_direct_query(
            asset, prefixlist, ipv6, irr_server, verbose
        )

    if not config_content:
        logger.error("Failed to generate configuration. Please check:")
        logger.error(
            "1. Is the AS-SET format correct? Try different formats like:"
            + "\n   - AS number only: "
            + (f"{asset.replace('AS-', 'AS') if asset.startswith('AS-') else asset}")
            + "\n   - AS-SET format: "
            + (f"{'AS-' + asset[2:]}" if asset.startswith('AS') and '-' in asset else "N/A")
        )
        logger.error("2. Is bgpq4 installed? It provides better compatibility.")
        logger.error("3. Try a different IRR server with -s option:")
        logger.error("   - RADB: -s whois.radb.net")
        logger.error("   - RIPE: -s whois.ripe.net")
        logger.error("   - ARIN: -s whois.arin.net")
        config_file.unlink(missing_ok=True)
        return

    with open(config_file, "w") as f:
        f.write(config_content)

    if test_mode:
        logger.info("======[ TEST MODE - Configuration ]======")
        logger.info(config_content)
        logger.info("======[ End of configuration ]======")
        config_file.unlink(missing_ok=True)
        return

    if not host_device or not username or not password:
        logger.error("Error: Device connection parameters (host, username, password) are required for non-test mode")
        config_file.unlink(missing_ok=True)
        return

    logger.info("++ Connecting to %s", host_device)
    try:
        device = {
            "device_type": "juniper_junos",
            "host": host_device,
            "username": username,
            "password": password,
            "port": port,
        }
        net_connect = ConnectHandler(**device)
    except NetMikoTimeoutException:
        logger.error("-- Connection timed out")
        config_file.unlink(missing_ok=True)
        return
    except NetMikoAuthenticationException:
        logger.error("-- Authentication failed")
        config_file.unlink(missing_ok=True)
        return
    except Exception as exc:
        logger.error("-- Unable to connect to device: %s", exc)
        config_file.unlink(missing_ok=True)
        return

    try:
        logger.info("++ Entering configuration mode")
        net_connect.config_mode()

        logger.info("++ Locking configuration")
        lock_result = net_connect.send_command("configure exclusive")
        if "error" in lock_result.lower() or "failed" in lock_result.lower():
            logger.error("-- Unable to lock configuration: %s", lock_result)
            net_connect.disconnect()
            config_file.unlink(missing_ok=True)
            return

        logger.info("++ Loading prefixlist configuration")
        with open(config_file, "r") as f:
            config_commands = f.read().splitlines()

        logger.info("++ Loading configuration commands (%d lines)", len(config_commands))
        config_result = net_connect.send_config_set(config_commands)
        if "error" in config_result.lower() or "failed" in config_result.lower():
            logger.error("-- Unable to load configuration changes: %s", config_result)
            net_connect.exit_config_mode()
            net_connect.disconnect()
            config_file.unlink(missing_ok=True)
            return

        logger.info("++ Committing the configuration")
        commit_result = net_connect.commit(comment="Prefix filter update")
        if "error" in commit_result.lower() or "failed" in commit_result.lower():
            logger.error("-- Unable to commit configuration: %s", commit_result)
            net_connect.exit_config_mode()
            net_connect.disconnect()
            config_file.unlink(missing_ok=True)
            return

        logger.info("++ Exiting configuration mode")
        net_connect.exit_config_mode()
    except Exception as exc:
        logger.error("-- Error during configuration: %s", exc)
        try:
            net_connect.exit_config_mode()
        except Exception:
            pass
        net_connect.disconnect()
        config_file.unlink(missing_ok=True)
        return

    logger.info("++ Disconnecting from device")
    net_connect.disconnect()
    config_file.unlink(missing_ok=True)
    logger.info("++ Configuration update completed successfully")
    sys.exit(0)


def main() -> None:
    parser = argparse.ArgumentParser()

    required_args = parser.add_argument_group("required arguments")
    device_args = parser.add_argument_group("device connection arguments")

    required_args.add_argument(
        "-a",
        action="store",
        type=str,
        help="AS-SET to create prefixlist",
        dest="asset",
        required=True,
    )
    required_args.add_argument(
        "-l",
        action="store",
        type=str,
        help="prefix-list name",
        dest="prefixlist",
        required=True,
    )

    device_args.add_argument(
        "-d",
        action="store",
        type=str,
        help="Which device to use (required unless in test mode)",
        dest="host_device",
    )
    device_args.add_argument(
        "-u",
        action="store",
        type=str,
        help="Username for device login (required unless in test mode)",
        dest="username",
    )
    device_args.add_argument(
        "-p",
        action="store",
        type=str,
        help="Password for device login (required unless in test mode)",
        dest="password",
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
        "--port",
        action="store",
        type=int,
        help="SSH port (default: 22)",
        dest="port",
        default=22,
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
    parser.add_argument(
        "--test",
        action="store_true",
        default=False,
        help="Test mode: output configuration without applying to device",
        dest="test_mode",
        required=False,
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Verbose mode: show detailed debug output",
        dest="verbose",
        required=False,
    )

    args = parser.parse_args()

    if not args.test_mode and (
        not args.host_device or not args.username or not args.password
    ):
        parser.error("the arguments -d, -u, and -p are required unless --test is used")

    asset = args.asset
    prefixlist = args.prefixlist
    ipv6 = args.ipv6
    irr_server = args.irr_server
    port = args.port
    use_bgpq4 = args.use_bgpq4
    test_mode = args.test_mode
    verbose = args.verbose

    startwork(
        asset,
        prefixlist,
        ipv6,
        irr_server,
        use_bgpq4,
        test_mode,
        host_device=args.host_device,
        username=args.username,
        password=args.password,
        port=port,
        verbose=verbose,
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
