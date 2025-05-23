#!/usr/bin/env python3
import argparse
import os
import re
import socket
import subprocess
import sys
import tempfile
import time

from netmiko import ConnectHandler
from netmiko.exceptions import NetMikoAuthenticationException, NetMikoTimeoutException

# (c) 2019 - Sebastiaan Koetsier - licensed under MIT license, see license.txt
# Modified to use Netmiko and bgpq4


class IRRQuerier:
    """Class to query IRR databases for prefix information."""

    def __init__(self, server="rr.ntt.net", port=43, verbose=False):
        """Initialize with the IRR server to query."""
        self.server = server
        self.port = port
        self.debug = verbose  # Enable debug output only in verbose mode

    def _send_query(self, query):
        """Send a query to the IRR server and return the response."""
        if self.debug:
            print(f"DEBUG: Sending query to {self.server}: {query}")

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

            decoded_response = response.decode("utf-8", errors="ignore")
            if self.debug:
                print(f"DEBUG: Received response ({len(decoded_response)} bytes):")
                # Print first few lines of response for debugging
                lines = decoded_response.splitlines()
                for i, line in enumerate(lines[:10]):
                    print(f"DEBUG: {i+1}: {line}")
                if len(lines) > 10:
                    print(f"DEBUG: ... and {len(lines) - 10} more lines")

            return decoded_response
        except Exception as e:
            print(f"Error querying IRR server: {e}")
            return ""

    def get_prefixes_for_asset(self, asset, ipv6=False):
        """Get prefixes for an AS-SET."""
        # Try different query formats
        prefixes = []

        # Format 1: !4AS-SET or !6AS-SET (original format)
        query_type = "6" if ipv6 else "4"
        query = f"!{query_type}{asset}"
        if self.debug:
            print(f"Trying query format 1: {query}")
        response = self._send_query(query)
        prefixes = self._parse_response(response, ipv6)

        # Format 2: !gas-set or !6as-set
        if not prefixes:
            query = f"!{query_type}as-set {asset}"
            if self.debug:
                print(f"Trying query format 2: {query}")
            response = self._send_query(query)
            prefixes = self._parse_response(response, ipv6)

        # Format 3: !rAS-SET or !r6AS-SET
        if not prefixes:
            query = f"!r{query_type} {asset}"
            if self.debug:
                print(f"Trying query format 3: {query}")
            response = self._send_query(query)
            prefixes = self._parse_response(response, ipv6)

        # Format 4: !g AS-SET (for route-set queries)
        if not prefixes:
            query_cmd = "!6g" if ipv6 else "!g"
            query = f"{query_cmd} {asset}"
            if self.debug:
                print(f"Trying query format 4: {query}")
            response = self._send_query(query)
            prefixes = self._parse_response(response, ipv6)

        # Format 5: !a AS-SET (for as-set queries)
        if not prefixes:
            query = f"!a {asset}"
            if self.debug:
                print(f"Trying query format 5: {query}")
            response = self._send_query(query)
            prefixes = self._parse_response(response, ipv6)

        # Format 6: !i AS-NUMBER (for direct AS number queries)
        if not prefixes and asset.startswith("AS"):
            as_number = asset.replace("AS", "")
            query = f"!i {as_number}"
            if self.debug:
                print(f"Trying query format 6: {query}")
            response = self._send_query(query)
            prefixes = self._parse_response(response, ipv6)

        return prefixes

    def _parse_response(self, response, ipv6=False):
        """Parse the response to extract prefixes."""
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

        if self.debug:
            print(f"DEBUG: Found {len(prefixes)} prefixes")
            if prefixes:
                print(f"DEBUG: First few prefixes: {prefixes[:5]}")

        return prefixes

    def generate_juniper_config(self, prefixes, prefix_list_name, ipv6=False):
        """Generate Juniper configuration for the prefix list."""
        family = "inet6" if ipv6 else "inet"
        config_lines = [
            f"policy-options {{",
            f"    replace:",
            f"    prefix-list {prefix_list_name} {{",
        ]

        for prefix in prefixes:
            config_lines.append(f"        {prefix};")

        config_lines.append("    }")
        config_lines.append("}")

        return "\n".join(config_lines)


def check_bgpq4_installed(verbose=False):
    """Check if bgpq4 is installed and print its version and help."""
    try:
        # First try to run bgpq4 without arguments to see if it's installed
        process = subprocess.Popen(
            ["bgpq4"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        stdout, stderr = process.communicate()

        if process.returncode != 127:  # 127 is "command not found"
            if verbose:
                print("bgpq4 seems to be installed")

            # Try to get help output to understand parameters
            process = subprocess.Popen(
                ["bgpq4", "-h"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            help_stdout, help_stderr = process.communicate()

            if help_stdout or help_stderr:
                if verbose:
                    print("bgpq4 help output:")
                    print(help_stdout or help_stderr)

                    # Look for host parameter in help
                    help_text = help_stdout or help_stderr
                    if "-h" in help_text:
                        print("bgpq4 supports -h parameter")
                    else:
                        print(
                            "bgpq4 might not support -h parameter, will try alternatives"
                        )

            return True
        else:
            if verbose:
                print("bgpq4 is not installed or not in PATH")
            return False
    except FileNotFoundError:
        if verbose:
            print("bgpq4 is not installed or not in PATH")
        return False
    except Exception as e:
        if verbose:
            print(f"Error checking bgpq4 installation: {e}")
        return False


def get_config_with_whois(asset, prefixlist, ipv6, irr_server, verbose=False):
    """Use direct whois command as a fallback."""
    print(f"Trying direct whois query for {asset} on {irr_server}...")

    try:
        # Run whois command
        cmd = ["whois", "-h", irr_server, asset]
        if verbose:
            print(f"DEBUG: Running whois command: {' '.join(cmd)}")

        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        stdout, stderr = process.communicate()

        if process.returncode != 0 or stderr.strip():
            print(f"Error with whois command: {stderr}")
            return None

        if verbose:
            print(f"DEBUG: whois output length: {len(stdout)} bytes")
            if stdout:
                lines = stdout.splitlines()
                print(f"DEBUG: First few lines of whois output:")
                for i, line in enumerate(lines[:10]):
                    print(f"DEBUG: {i+1}: {line}")

        # Extract routes from whois output
        prefixes = []
        for line in stdout.splitlines():
            line = line.strip()
            if ipv6:
                # Look for IPv6 routes
                if line.startswith("route6:"):
                    prefix = line.replace("route6:", "").strip()
                    if ":" in prefix and "/" in prefix:
                        prefixes.append(prefix)
            else:
                # Look for IPv4 routes
                if line.startswith("route:"):
                    prefix = line.replace("route:", "").strip()
                    if re.match(r"^\d+\.\d+\.\d+\.\d+/\d+$", prefix):
                        prefixes.append(prefix)

        if prefixes:
            print(f"Found {len(prefixes)} prefixes via whois")
            # Generate Juniper configuration
            family = "inet6" if ipv6 else "inet"
            config_lines = [
                f"policy-options {{",
                f"    replace:",
                f"    prefix-list {prefixlist} {{",
            ]

            for prefix in prefixes:
                config_lines.append(f"        {prefix};")

            config_lines.append("    }")
            config_lines.append("}")

            return "\n".join(config_lines)
        else:
            print("No prefixes found in whois output")
            return None
    except Exception as e:
        print(f"Error using whois: {e}")
        return None


def get_config_with_bgpq4(asset, prefixlist, ipv6, irr_server, verbose=False):
    """Use bgpq4 to generate the configuration."""
    # First check if bgpq4 is installed
    if not check_bgpq4_installed(verbose):
        print("bgpq4 is not installed or not working correctly")
        return None

    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as outfile:
        config_file = outfile.name

    # Try different IRR servers if the first one fails
    servers_to_try = [irr_server]
    if irr_server == "rr.ntt.net":  # If using the default, add fallbacks
        servers_to_try.extend(["whois.radb.net", "whois.ripe.net", "whois.arin.net"])

    # Try different AS-SET formats if needed
    formats_to_try = [asset]
    if asset.startswith("AS") and not "-" in asset:
        # If it's just an AS number, try AS-SET format too
        formats_to_try.append(f"AS-{asset[2:]}")
    elif asset.startswith("AS-"):
        # If it's an AS-SET, also try just the AS number
        formats_to_try.append(f"AS{asset[3:]}")

    # Add more format variations
    if ":" not in asset and "." not in asset:
        if asset.startswith("AS"):
            formats_to_try.append(f"{asset}:AS-ALL")
            formats_to_try.append(f"{asset}.AS-ALL")

    # Try with different command formats
    for current_server in servers_to_try:
        for current_format in formats_to_try:
            try:
                if verbose:
                    print(
                        f"Trying bgpq4 with server {current_server} and AS-SET format {current_format}"
                    )

                # Try different command formats with -h parameter first
                command_formats = [
                    # Format 1: Correct format with -h first, then -J
                    ["bgpq4", "-h", current_server, "-J", current_format],
                    # Format 2: With -h first and -l for prefix list
                    [
                        "bgpq4",
                        "-h",
                        current_server,
                        "-J",
                        "-l",
                        prefixlist,
                        current_format,
                    ],
                    # Format 3: With -h first and -f (aggregate) option
                    ["bgpq4", "-h", current_server, "-J", "-f", "24", current_format],
                    # Format 4: With -h first and -A for origin AS
                    ["bgpq4", "-h", current_server, "-A", current_format],
                    # Format 5: Basic format without server specification
                    ["bgpq4", "-J", current_format],
                ]

                if ipv6:
                    for cmd in command_formats:
                        cmd.append("-6")

                for i, cmd in enumerate(command_formats):
                    if verbose:
                        print(f"DEBUG: Running command format {i+1}: {' '.join(cmd)}")

                    # Run the command and capture both stdout and stderr
                    process = subprocess.Popen(
                        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                    )
                    stdout, stderr = process.communicate()

                    # Check if there was any error
                    if process.returncode != 0 or stderr.strip():
                        if verbose:
                            print(f"Error with command format {i+1}: {stderr}")
                        continue  # Try next command format

                    # Check if output contains actual configuration
                    if "policy-options {" not in stdout and "prefix-list" not in stdout:
                        if verbose:
                            print(
                                f"No valid configuration generated with command format {i+1}"
                            )
                        continue  # Try next command format

                    # Modify the output to use the correct prefix list name if needed
                    if "prefix-list " in stdout and prefixlist not in stdout:
                        # Replace the auto-generated prefix list name with the requested one
                        stdout = re.sub(
                            r"prefix-list\s+[\w-]+\s+{",
                            f"prefix-list {prefixlist} {{",
                            stdout,
                        )

                    # Write the output to the file
                    with open(config_file, "w") as outfile:
                        outfile.write(stdout)

                    # Read the file content
                    with open(config_file, "r") as fin:
                        config_content = fin.read()

                    # Print debug info
                    if verbose:
                        print(
                            f"DEBUG: bgpq4 output length: {len(config_content)} bytes"
                        )
                        if config_content:
                            lines = config_content.splitlines()
                            print(f"DEBUG: First few lines of bgpq4 output:")
                            for i, line in enumerate(lines[:5]):
                                print(f"DEBUG: {i+1}: {line}")
                        else:
                            print("DEBUG: bgpq4 output is empty")
                            continue  # Try next command format if output is empty

                    # Success! Return the content
                    os.remove(config_file)
                    return config_content
            except Exception as e:
                if verbose:
                    print(
                        f"Error using bgpq4 with {current_server} and {current_format}: {e}"
                    )

    # If we get here, all attempts failed
    if os.path.exists(config_file):
        os.remove(config_file)

    print("\nAll bgpq4 attempts failed. Please check:")
    print(
        "1. Is bgpq4 installed correctly? Try running 'bgpq4' without arguments to see help."
    )
    print(
        "2. Does the AS-SET exist in the IRR database? Try 'whois -h whois.radb.net AS8315'"
    )
    print("3. Try running bgpq4 manually to debug: bgpq4 -h whois.radb.net -J AS8315")
    print("\nTrying whois as a fallback method...")

    # Try whois as a last resort
    return get_config_with_whois(asset, prefixlist, ipv6, irr_server, verbose)


def get_config_with_direct_query(asset, prefixlist, ipv6, irr_server, verbose=False):
    """Use direct IRR query to generate the configuration."""
    irr = IRRQuerier(server=irr_server, verbose=verbose)
    prefixes = irr.get_prefixes_for_asset(asset, ipv6)

    if not prefixes:
        print("Error: No prefixes found for the specified AS-SET")
        return None

    return irr.generate_juniper_config(prefixes, prefixlist, ipv6)


def startwork(
    asset,
    prefixlist,
    ipv6,
    irr_server="rr.ntt.net",
    use_bgpq4=False,
    test_mode=False,
    host_device=None,
    username=None,
    password=None,
    port=22,
    verbose=False,
):
    """Main function to update prefix filters on a Juniper device using Netmiko."""
    # Create a temporary file for the configuration
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as outfile:
        config = outfile.name

    os.system("clear")

    # First try with bgpq4 regardless of the use_bgpq4 flag
    print("~ Starting bgpq4 (recommended method)...")
    config_content = get_config_with_bgpq4(asset, prefixlist, ipv6, irr_server, verbose)

    # If bgpq4 fails and use_bgpq4 is False, try direct IRR query as fallback
    if not config_content and not use_bgpq4:
        print("~ bgpq4 failed, falling back to direct IRR query...")
        config_content = get_config_with_direct_query(
            asset, prefixlist, ipv6, irr_server, verbose
        )

    if not config_content:
        print("\n======[ ERROR ]======")
        print("Failed to generate configuration. Please check:")
        print("1. Is the AS-SET format correct? Try different formats like:")
        print(
            f"   - AS number only: {asset.replace('AS-', 'AS') if asset.startswith('AS-') else asset}"
        )
        print(
            f"   - AS-SET format: {'AS-' + asset[2:] if asset.startswith('AS') and not '-' in asset else asset}"
        )
        print("2. Is bgpq4 installed? It provides better compatibility.")
        print("3. Try a different IRR server with -s option:")
        print("   - RADB: -s whois.radb.net")
        print("   - RIPE: -s whois.ripe.net")
        print("   - ARIN: -s whois.arin.net")
        os.remove(config)
        return

    # Write configuration to file
    with open(config, "w") as f:
        f.write(config_content)

    # In test mode, output the configuration
    if test_mode:
        print("======[ TEST MODE - Configuration ]======")
        print(config_content)
        print("======[ End of configuration ]======")
        os.remove(config)
        return

    # Verify that device connection parameters are provided
    if not host_device or not username or not password:
        print(
            "Error: Device connection parameters (host, username, password) are required for non-test mode"
        )
        os.remove(config)
        return

    print("======[ Action log ]======")

    # Connect to the device using Netmiko
    try:
        print(f"++ Connecting to {host_device}")
        device = {
            "device_type": "juniper_junos",
            "host": host_device,
            "username": username,
            "password": password,
            "port": port,
        }

        net_connect = ConnectHandler(**device)
    except NetMikoTimeoutException:
        print("-- Connection timed out")
        os.remove(config)
        return
    except NetMikoAuthenticationException:
        print("-- Authentication failed")
        os.remove(config)
        return
    except Exception as err:
        print(f"-- Unable to connect to device: {err}")
        os.remove(config)
        return

    try:
        # Enter configuration mode
        print("++ Entering configuration mode")
        net_connect.config_mode()

        # Lock the configuration
        print("++ Locking configuration")
        lock_result = net_connect.send_command("configure exclusive")
        if "error" in lock_result.lower() or "failed" in lock_result.lower():
            print(f"-- Unable to lock configuration: {lock_result}")
            net_connect.disconnect()
            os.remove(config)
            return

        # Load the configuration
        print("++ Loading prefixlist configuration")
        with open(config, "r") as f:
            config_commands = f.read().splitlines()

        # Send configuration commands
        config_result = net_connect.send_config_set(config_commands)
        if "error" in config_result.lower() or "failed" in config_result.lower():
            print(f"-- Unable to load configuration changes: {config_result}")
            print("++ Exiting configuration mode")
            net_connect.exit_config_mode()
            net_connect.disconnect()
            os.remove(config)
            return

        # Commit the configuration
        print("++ Committing the configuration")
        commit_result = net_connect.commit(comment="Prefix filter update")
        if "error" in commit_result.lower() or "failed" in commit_result.lower():
            print(f"-- Unable to commit configuration: {commit_result}")
            print("++ Exiting configuration mode")
            net_connect.exit_config_mode()
            net_connect.disconnect()
            os.remove(config)
            return

        # Exit configuration mode
        print("++ Exiting configuration mode")
        net_connect.exit_config_mode()

    except Exception as err:
        print(f"-- Error during configuration: {err}")
        try:
            net_connect.exit_config_mode()
        except:
            pass
        net_connect.disconnect()
        os.remove(config)
        return

    # Disconnect from the device
    print("++ Disconnecting from device")
    net_connect.disconnect()

    # Clean up
    os.remove(config)
    print("++ Configuration update completed successfully")
    exit(0)


def main():
    parser = argparse.ArgumentParser()

    # Create argument groups for better organization
    required_args = parser.add_argument_group("required arguments")
    device_args = parser.add_argument_group("device connection arguments")

    # Required arguments regardless of mode
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

    # Device connection arguments (only required in non-test mode)
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

    # Optional arguments
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
        help="Test mode: output configuration to stderr without applying to device",
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

    # Check if device connection parameters are provided when not in test mode
    if not args.test_mode and (
        not args.host_device or not args.username or not args.password
    ):
        parser.error("the arguments -d, -u, and -p are required unless --test is used")

    # Extract arguments
    host_device = args.host_device
    username = args.username
    password = args.password
    asset = args.asset
    prefixlist = args.prefixlist
    ipv6 = args.ipv6
    irr_server = args.irr_server
    port = args.port
    use_bgpq4 = args.use_bgpq4
    test_mode = args.test_mode

    # Extract verbose argument
    verbose = args.verbose

    startwork(
        asset,
        prefixlist,
        ipv6,
        irr_server,
        use_bgpq4,
        test_mode,
        host_device,
        username,
        password,
        port,
        verbose,
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
