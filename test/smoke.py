# /// script
# dependencies = ["httpx>=0.27", "mohawk>=1.1.0", "pyjwt[crypto]>=2.8", "rich>=13.0", "typer>=0.12"]
# ///

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

import httpx
import jwt
import typer
from mohawk import Sender
from rich.console import Console
from rich.table import Table

SERVICES = ["service_a", "service_b", "service_c"]
ENDPOINTS = ["sentiment", "regression", "classification"]
APISIX_BASE_URL = "http://localhost:9080"
HAWK_BASE_URL = "http://localhost:9081"
REQUEST_CONTENT_TYPE = "application/json"

EXPECTED_PERMISSIONS = {
    "service_a": {"sentiment": True, "regression": True, "classification": False},
    "service_b": {"sentiment": False, "regression": False, "classification": True},
    "service_c": {"sentiment": True, "regression": False, "classification": True},
}

HAWK_CREDENTIALS = {
    "service_a": {"id": "service_a_id", "env": "SERVICE_A_HAWK_KEY"},
    "service_b": {"id": "service_b_id", "env": "SERVICE_B_HAWK_KEY"},
    "service_c": {"id": "service_c_id", "env": "SERVICE_C_HAWK_KEY"},
}

ProxyMode = Literal["apisix", "hawk"]

app = typer.Typer(add_completion=False, no_args_is_help=False)


@dataclass
class EndpointResult:
    status_code: int
    status_text: str
    body: str


def create_request_body() -> bytes:
    """Create a canonical JSON request body for smoke tests."""
    return json.dumps({"text": "test input"}, separators=(",", ":")).encode("utf-8")


def generate_jwt_token(service_name: str) -> str:
    """Generate a JWT token for a service."""
    key_path = Path(__file__).parent / f"keys/{service_name}-private.pem"
    key = key_path.read_text()
    now = datetime.now(UTC)

    return jwt.encode(
        {
            "sub": service_name,
            "key": f"iss_{service_name}",
            "nbf": now,
            "exp": now + timedelta(hours=1),
        },
        key,
        algorithm="RS256",
    )


def validate_hawk_key_env() -> list[str]:
    """Return the missing HAWK key environment variables."""
    missing: list[str] = []
    for service in SERVICES:
        env_var = HAWK_CREDENTIALS[service]["env"]
        if not os.getenv(env_var):
            missing.append(env_var)
    return missing


def load_hawk_keys_from_env_file() -> int:
    """Load HAWK keys from test/keys/.env when not already exported."""
    env_file = Path(__file__).parent / "keys/.env"
    if not env_file.exists():
        return 0

    loaded = 0
    required_vars = {HAWK_CREDENTIALS[service]["env"] for service in SERVICES}
    for line in env_file.read_text().splitlines():
        if "=" not in line:
            continue

        key, raw_value = line.split("=", 1)
        key = key.strip()
        if key not in required_vars or os.getenv(key):
            continue

        value = raw_value.strip()
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]

        os.environ[key] = value
        loaded += 1

    return loaded


def build_hawk_headers(service: str, path: str, method: str, body: bytes) -> dict[str, str]:
    """Build HAWK Authorization header for a request."""
    credentials = HAWK_CREDENTIALS[service]
    hawk_key = os.getenv(credentials["env"])
    if not hawk_key:
        missing_var = credentials["env"]
        raise RuntimeError(
            f"Missing HAWK key in environment variable: {missing_var}"
        )

    sender = Sender(
        {"id": credentials["id"], "key": hawk_key, "algorithm": "sha256"},
        path,
        method,
        content=body,
        content_type=REQUEST_CONTENT_TYPE,
    )
    auth_header = sender.request_header
    if not isinstance(auth_header, str):
        raise RuntimeError("Unable to generate HAWK authorisation header")

    return {"Authorization": auth_header}


def test_endpoint(
    mode: ProxyMode,
    service: str,
    endpoint: str,
    jwt_token: str | None = None,
) -> EndpointResult:
    """Send a smoke-test request and return status details."""
    path = f"/predict/{endpoint}"
    body = create_request_body()
    headers = {"Content-Type": REQUEST_CONTENT_TYPE}

    if mode == "apisix":
        if jwt_token is None:
            raise RuntimeError("JWT token is required for APISIX requests")
        headers["Authorization"] = jwt_token
        base_url = APISIX_BASE_URL
    else:
        headers.update(build_hawk_headers(service=service, path=path, method="POST", body=body))
        base_url = HAWK_BASE_URL

    try:
        response = httpx.post(
            f"{base_url}{path}",
            content=body,
            headers=headers,
            timeout=5.0,
        )
        return EndpointResult(
            status_code=response.status_code,
            status_text=response.reason_phrase,
            body=response.text,
        )
    except httpx.RequestError as error:
        return EndpointResult(
            status_code=0,
            status_text=f"Error: {type(error).__name__}",
            body=str(error),
        )


def result_matches_expectation(status_code: int, expected_allowed: bool) -> bool:
    """Check whether a status code matches expected allow/deny behaviour."""
    if expected_allowed:
        return status_code == 200
    return status_code in (401, 403)


def format_result(status_code: int, expected_allowed: bool) -> str:
    """Format a table cell for status result."""
    if status_code == 0:
        return "[yellow]? ERR[/yellow]"
    if result_matches_expectation(status_code, expected_allowed):
        return f"[green]✓ {status_code}[/green]"
    return f"[red]✗ {status_code}[/red]"


def run_mode(console: Console, mode: ProxyMode) -> bool:
    """Run smoke tests for one proxy mode and return overall pass/fail."""
    mode_label = "APISIX" if mode == "apisix" else "HAWK"
    console.print(f"\n[bold cyan]{mode_label} consumer permission matrix validation[/bold cyan]\n")

    tokens: dict[str, str] = {}
    if mode == "apisix":
        console.print("[yellow]Generating JWT tokens...[/yellow]")
        tokens = {service: generate_jwt_token(service) for service in SERVICES}
        console.print("[green]✓ JWT tokens generated[/green]\n")
    else:
        loaded_count = load_hawk_keys_from_env_file()
        if loaded_count:
            console.print(
                f"[yellow]Loaded {loaded_count} HAWK key(s) from test/keys/.env[/yellow]"
            )
        missing_vars = validate_hawk_key_env()
        if missing_vars:
            console.print("[bold red]✗ Missing HAWK key environment variables:[/bold red]")
            for missing_var in missing_vars:
                console.print(f"[red]- {missing_var}[/red]")
            return False
        console.print("[yellow]Using HAWK credentials from environment...[/yellow]")
        console.print("[green]✓ HAWK credentials loaded[/green]\n")

    console.print("[yellow]Testing all service-endpoint combinations...[/yellow]\n")
    results: dict[str, dict[str, EndpointResult]] = {}

    for service in SERVICES:
        results[service] = {}
        for endpoint in ENDPOINTS:
            token = tokens.get(service)
            result = test_endpoint(mode=mode, service=service, endpoint=endpoint, jwt_token=token)
            results[service][endpoint] = result

    table = Table(
        title=f"{mode_label} consumer permission matrix - test results",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Consumer", style="cyan", width=15)
    for endpoint in ENDPOINTS:
        table.add_column(endpoint, justify="center", width=15)

    for service in SERVICES:
        row = [service]
        for endpoint in ENDPOINTS:
            status_code = results[service][endpoint].status_code
            expected_allowed = EXPECTED_PERMISSIONS[service][endpoint]
            row.append(format_result(status_code, expected_allowed))
        table.add_row(*row)

    console.print(table)
    console.print("\n[bold]Validation summary:[/bold]")

    mismatches: list[tuple[str, str, bool, EndpointResult]] = []
    for service in SERVICES:
        for endpoint in ENDPOINTS:
            endpoint_result = results[service][endpoint]
            expected_allowed = EXPECTED_PERMISSIONS[service][endpoint]
            if not result_matches_expectation(endpoint_result.status_code, expected_allowed):
                mismatches.append((service, endpoint, expected_allowed, endpoint_result))

    if not mismatches:
        console.print(f"[bold green]✓ {mode_label} permissions match the expected matrix[/bold green]")
        return True

    console.print(f"[bold red]✗ {mode_label} permissions do not match expectations[/bold red]")
    for service, endpoint, expected_allowed, endpoint_result in mismatches:
        console.print(
            f"[red]✗[/red] {service} → {endpoint}: "
            f"Expected {'200' if expected_allowed else '401/403'}, "
            f"got {endpoint_result.status_code}"
        )

    console.print("\n[bold yellow]Debug information for mismatches:[/bold yellow]\n")
    for service, endpoint, expected_allowed, endpoint_result in mismatches:
        console.print(f"[cyan]Service:[/cyan] {service}")
        console.print(f"[cyan]Endpoint:[/cyan] /predict/{endpoint}")
        console.print(f"[cyan]Expected:[/cyan] {'Allowed (200)' if expected_allowed else 'Denied (401/403)'}")
        console.print(f"[cyan]Actual status:[/cyan] {endpoint_result.status_code} {endpoint_result.status_text}")
        console.print("[cyan]Response body:[/cyan]")
        console.print(f"[dim]{endpoint_result.body}[/dim]")
        console.print()

    return False


@app.command()
def main(
    context: typer.Context,
    apisix: bool = typer.Option(
        False,
        "--apisix",
        help="Run smoke tests against APISIX at http://localhost:9080.",
    ),
    hawk: bool = typer.Option(
        False,
        "--hawk",
        help="Run smoke tests against HAWK proxy at http://localhost:9081.",
    ),
) -> None:
    """Run smoke tests for one or both proxy modes."""
    if not apisix and not hawk:
        typer.echo(context.get_help(), err=True)
        typer.echo("\nError: pass --apisix and/or --hawk.", err=True)
        raise typer.Exit(code=2)

    console = Console()
    overall_success = True

    if apisix:
        overall_success = run_mode(console=console, mode="apisix") and overall_success

    if hawk:
        overall_success = run_mode(console=console, mode="hawk") and overall_success

    if not overall_success:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
