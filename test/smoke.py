# /// script
# dependencies = ["pyjwt[crypto]>=2.8", "httpx>=0.27", "rich>=13.0"]
# ///

import jwt
import httpx
from pathlib import Path
from datetime import datetime, timedelta, UTC
from rich.console import Console
from rich.table import Table

# Service configuration
SERVICES = ["service_a", "service_b", "service_c"]
ENDPOINTS = ["sentiment", "regression", "classification"]
BASE_URL = "http://localhost:9080"

# Expected permissions from the APISIX config
EXPECTED_PERMISSIONS = {
    "service_a": {"sentiment": True, "regression": True, "classification": False},
    "service_b": {"sentiment": False, "regression": False, "classification": True},
    "service_c": {"sentiment": True, "regression": False, "classification": True},
}


def generate_token(service_name: str) -> str:
    """Generate a JWT token for the specified service."""
    key_path = Path(__file__).parent / f"keys/{service_name}-private.pem"
    key = key_path.read_text()
    now = datetime.now(UTC)
    
    token = jwt.encode(
        {
            "sub": service_name,
            "key": f"iss_{service_name}",
            "nbf": now,
            "exp": now + timedelta(hours=1),
        },
        key,
        algorithm="RS256",
    )
    
    return token


def test_endpoint(service: str, endpoint: str, token: str) -> tuple[int, str, str]:
    """Test an endpoint with a service's token and return status code, status text, and response body."""
    try:
        response = httpx.post(
            f"{BASE_URL}/predict/{endpoint}",
            json={"text": "test input"},
            headers={"Authorization": token},
            timeout=5.0,
        )
        try:
            body = response.text
        except Exception:
            body = "<unable to decode response>"
        return response.status_code, response.reason_phrase, body
    except httpx.RequestError as e:
        return 0, f"Error: {type(e).__name__}", str(e)


def format_result(status_code: int, expected: bool) -> str:
    """Format the result cell with colour coding."""
    if status_code == 200:
        return f"[green]✓ {status_code}[/green]"
    elif status_code in (401, 403):
        return f"[red]✗ {status_code}[/red]"
    else:
        return f"[yellow]? {status_code}[/yellow]"


def main() -> None:
    console = Console()
    
    console.print("\n[bold cyan]APISIX consumer permission matrix validation[/bold cyan]\n")
    
    # Generate tokens for all services
    console.print("[yellow]Generating JWT tokens for all services...[/yellow]")
    tokens = {service: generate_token(service) for service in SERVICES}
    console.print("[green]✓ Tokens generated[/green]\n")
    
    # Test all combinations
    console.print("[yellow]Testing all service-endpoint combinations...[/yellow]\n")
    results: dict[str, dict[str, tuple[int, str, str]]] = {}
    
    for service in SERVICES:
        results[service] = {}
        for endpoint in ENDPOINTS:
            status_code, status_text, body = test_endpoint(service, endpoint, tokens[service])
            results[service][endpoint] = (status_code, status_text, body)
    
    # Create results table
    table = Table(title="Consumer permission matrix - test results", show_header=True, header_style="bold magenta")
    
    table.add_column("Consumer", style="cyan", width=15)
    for endpoint in ENDPOINTS:
        table.add_column(endpoint, justify="center", width=15)
    
    # Add rows for each service
    for service in SERVICES:
        row = [service]
        for endpoint in ENDPOINTS:
            status_code, _, _ = results[service][endpoint]
            expected = EXPECTED_PERMISSIONS[service][endpoint]
            row.append(format_result(status_code, expected))
        table.add_row(*row)
    
    console.print(table)
    
    # Validation summary
    console.print("\n[bold]Validation summary:[/bold]")
    
    all_correct = True
    mismatches: list[tuple[str, str, bool, int, str, str]] = []
    
    for service in SERVICES:
        for endpoint in ENDPOINTS:
            status_code, status_text, body = results[service][endpoint]
            expected = EXPECTED_PERMISSIONS[service][endpoint]
            
            is_correct = (expected and status_code == 200) or (not expected and status_code in (401, 403))
            
            if not is_correct:
                all_correct = False
                mismatches.append((service, endpoint, expected, status_code, status_text, body))
                console.print(
                    f"[red]✗[/red] {service} → {endpoint}: "
                    f"Expected {'✓' if expected else '✗'}, got status {status_code}"
                )
    
    if all_correct:
        console.print("[bold green]✓ All permissions match the expected matrix![/bold green]")
    else:
        console.print("[bold red]✗ Some permissions don't match expectations[/bold red]")
    
    # Debug section for mismatches
    if mismatches:
        console.print("\n[bold yellow]Debug information for mismatched results:[/bold yellow]\n")
        
        for service, endpoint, expected, status_code, status_text, body in mismatches:
            console.print(f"[cyan]Service:[/cyan] {service}")
            console.print(f"[cyan]Endpoint:[/cyan] /predict/{endpoint}")
            console.print(f"[cyan]Expected:[/cyan] {'Allowed (200)' if expected else 'Denied (403/401)'}")
            console.print(f"[cyan]Actual status:[/cyan] {status_code} {status_text}")
            console.print("[cyan]Response body:[/cyan]")
            console.print(f"[dim]{body}[/dim]")
            console.print()
    
    # Legend
    console.print("[bold]Legend:[/bold]")
    console.print("  [green]✓ 200[/green] = Allowed (successful)")
    console.print("  [red]✗ 403[/red] = Forbidden (consumer not in whitelist)")
    console.print("  [red]✗ 401[/red] = Unauthorised (authentication failed)")


if __name__ == "__main__":
    main()