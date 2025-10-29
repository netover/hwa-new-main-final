#!/usr/bin/env python3
"""
Performance validation script for Resync application.

This script measures key performance metrics to validate optimizations:
- RAM usage
- CPU utilization
- Startup time
- Request latency
- Throughput
"""

import asyncio
import json
import time
from datetime import datetime

import httpx
import psutil
from rich.console import Console
from rich.panel import Panel
from rich.table import Table


class PerformanceValidator:
    """Validates and measures performance metrics."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.console = Console()
        self.results: dict[str, dict[str, float]] = {}
        self.app_process = None

    async def measure_startup_time(self, startup_command: str = "uvicorn resync.main:app --host 0.0.0.0 --port 8000") -> float:
        """Measure application startup time by actually starting of application."""
        self.console.print("[yellow]Measuring startup time...[/yellow]")
        self.console.print(f"[blue]Starting application with command: {startup_command}[/blue]")

        # Record start time before launching app
        start_time = time.time()

        # Start of application as a subprocess
        process = await asyncio.create_subprocess_shell(
            startup_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Create tasks to monitor output and health
        async def read_output():
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                self.console.print(f"[dim]{line.decode().strip()}[/dim]")

        async def read_error():
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
                self.console.print(f"[red]{line.decode().strip()}[/red]")

        # Start output monitoring tasks
        output_task = asyncio.create_task(read_output())
        error_task = asyncio.create_task(read_error())

        try:
            # Wait for application to be ready
            async with httpx.AsyncClient() as client:
                for i in range(30):  # Wait up to 30 seconds
                    try:
                        response = await client.get(f"{self.base_url}/health", timeout=1.0)
                        if response.status_code == 200:
                            startup_time = time.time() - start_time
                            self.console.print(f"[green]Startup time: {startup_time:.2f}s[/green]")

                            # Cancel output monitoring tasks
                            output_task.cancel()
                            error_task.cancel()

                            # Keep process running for other tests
                            self.app_process = process
                            return startup_time
                    except httpx.RequestError:
                        pass

                    # Show progress
                    if i % 5 == 0:
                        self.console.print(f"[yellow]Waiting for application to start... ({i}/30 seconds)[/yellow]")

                    await asyncio.sleep(1)

            # If we get here, app failed to start
            try:
                process.terminate()
                await process.wait()
            except ProcessLookupError:
                # Process already terminated
                pass
            raise RuntimeError("Application failed to start within 30 seconds")

        except Exception as e:
            # Clean up process if there's an error
            try:
                process.terminate()
                await process.wait()
            except ProcessLookupError:
                # Process already terminated
                pass
            raise e

    def measure_memory_usage(self) -> dict[str, float]:
        """Measure current memory usage."""
        process = psutil.Process()
        memory_info = process.memory_info()

        # Convert to MB
        rss_mb = memory_info.rss / 1024 / 1024
        vms_mb = memory_info.vms / 1024 / 1024

        # Get system memory
        system_memory = psutil.virtual_memory()

        self.console.print(f"[green]Memory usage: RSS={rss_mb:.1f}MB, VMS={vms_mb:.1f}MB[/green]")

        return {
            "rss_mb": rss_mb,
            "vms_mb": vms_mb,
            "system_used_percent": system_memory.percent,
            "system_available_gb": system_memory.available / 1024 / 1024 / 1024
        }

    def measure_cpu_usage(self, duration: int = 10) -> float:
        """Measure CPU usage over a duration."""
        self.console.print(f"[yellow]Measuring CPU usage over {duration}s...[/yellow]")

        # Get final CPU percentage
        process = psutil.Process()
        cpu_percent = process.cpu_percent()

        # Also get system CPU
        system_cpu = psutil.cpu_percent(interval=1)

        self.console.print(f"[green]CPU usage: Process={cpu_percent:.1f}%, System={system_cpu:.1f}%[/green]")

        return cpu_percent

    async def measure_request_latency(self, endpoint: str = "/health", requests: int = 100) -> dict[str, float]:
        """Measure request latency for an endpoint."""
        self.console.print(f"[yellow]Measuring latency for {requests} requests to {endpoint}...[/yellow]")

        latencies = []

        async with httpx.AsyncClient() as client:
            for _ in range(requests):
                start_time = time.time()
                try:
                    response = await client.get(f"{self.base_url}{endpoint}", timeout=5.0)
                    if response.status_code == 200:
                        latency = (time.time() - start_time) * 1000  # Convert to ms
                        latencies.append(latency)
                except httpx.RequestError:
                    pass

        if not latencies:
            raise RuntimeError(f"No successful requests to {endpoint}")

        # Calculate statistics
        latencies.sort()
        p50 = latencies[len(latencies) // 2]
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]
        avg = sum(latencies) / len(latencies)

        self.console.print(f"[green]Latency: p50={p50:.1f}ms, p95={p95:.1f}ms, p99={p99:.1f}ms, avg={avg:.1f}ms[/green]")

        return {
            "p50_ms": p50,
            "p95_ms": p95,
            "p99_ms": p99,
            "avg_ms": avg,
            "requests": len(latencies)
        }

    async def measure_throughput(self, duration: int = 30) -> dict[str, float]:
        """Measure request throughput over a duration."""
        self.console.print(f"[yellow]Measuring throughput over {duration}s...[/yellow]")

        request_count = 0
        start_time = time.time()

        async with httpx.AsyncClient() as client:
            while time.time() - start_time < duration:
                try:
                    # Make concurrent requests
                    tasks = []
                    for _ in range(10):  # 10 concurrent requests
                        task = asyncio.create_task(
                            client.get(f"{self.base_url}/health", timeout=1.0)
                        )
                        tasks.append(task)

                    # Wait for all requests
                    responses = await asyncio.gather(*tasks, return_exceptions=True)

                    # Count successful requests
                    for response in responses:
                        if isinstance(response, httpx.Response) and response.status_code == 200:
                            request_count += 1

                    # Wait a bit before next batch
                    await asyncio.sleep(0.1)

                except Exception:
                    pass

        actual_duration = time.time() - start_time
        rps = request_count / actual_duration

        self.console.print(f"[green]Throughput: {rps:.1f} requests/second[/green]")

        return {
            "requests_per_second": rps,
            "total_requests": request_count,
            "duration": actual_duration
        }

    def save_results(self, filename: str | None = None) -> None:
        """Save results to a JSON file."""
        if filename is None:
            filename = f"performance_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2)

        self.console.print(f"[green]Results saved to {filename}[/green]")

    def display_summary(self) -> None:
        """Display a summary of all results."""
        table = Table(title="Performance Validation Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        table.add_column("Target", style="yellow")
        table.add_column("Status", style="bold")

        # Define targets
        targets = {
            "startup_time": {"target": 15.0, "unit": "s", "operator": "<"},
            "memory_rss": {"target": 2500.0, "unit": "MB", "operator": "<"},
            "cpu_idle": {"target": 50.0, "unit": "%", "operator": ">"},
            "latency_p95": {"target": 100.0, "unit": "ms", "operator": "<"},
            "throughput": {"target": 150.0, "unit": "req/s", "operator": ">"}
        }

        # Add rows for each metric
        for metric_name, result in self.results.items():
            if metric_name in targets:
                target = targets[metric_name]["target"]
                unit = targets[metric_name]["unit"]
                operator = targets[metric_name]["operator"]

                # Extract the actual value
                if metric_name == "startup_time":
                    value = result.get("startup_time", 0)
                elif metric_name == "memory_rss":
                    value = result.get("memory", {}).get("rss_mb", 0)
                elif metric_name == "cpu_idle":
                    value = 100 - result.get("cpu", 0)  # Convert usage to idle
                elif metric_name == "latency_p95":
                    value = result.get("latency", {}).get("p95_ms", 0)
                elif metric_name == "throughput":
                    value = result.get("throughput", {}).get("requests_per_second", 0)
                else:
                    value = 0

                # Determine status
                if operator == "<":
                    status = "✅ PASS" if value < target else "❌ FAIL"
                else:
                    status = "✅ PASS" if value > target else "❌ FAIL"

                table.add_row(
                    metric_name.replace("_", " ").title(),
                    f"{value:.1f} {unit}",
                    f"{target:.1f} {unit}",
                    status
                )

        self.console.print(table)

    async def run_validation(self, startup_command: str = "uvicorn resync.main:app --host 0.0.0.0 --port 8000") -> None:
        """Run complete performance validation."""
        self.console.print(Panel.fit("[bold blue]Performance Validation[/bold blue]"))

        try:
            # Measure startup time (first)
            startup_time = await self.measure_startup_time(startup_command)
            self.results["startup"] = {"startup_time": startup_time}

            # Measure memory usage
            memory = self.measure_memory_usage()
            self.results["memory"] = memory

            # Measure CPU usage
            cpu = self.measure_cpu_usage()
            self.results["cpu"] = cpu

            # Measure request latency
            latency = await self.measure_request_latency()
            self.results["latency"] = latency

            # Measure throughput
            throughput = await self.measure_throughput()
            self.results["throughput"] = throughput

            # Display summary
            self.display_summary()

            # Save results
            self.save_results()

        except Exception as e:
            self.console.print(f"[red]Error during validation: {e}[/red]")
            import traceback
            self.console.print(f"[red]Traceback: {traceback.format_exc()}[/red]")
        finally:
            # Clean up of application process
            await self.cleanup_app()

    async def cleanup_app(self) -> None:
        """Clean up the application process if it exists."""
        if self.app_process:
            try:
                self.app_process.terminate()
                await self.app_process.wait()
                self.console.print("[green]Application process terminated[/green]")
            except Exception as e:
                self.console.print(f"[yellow]Warning: Could not terminate app process: {e}[/yellow]")


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Performance validation for Resync")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL to test")
    parser.add_argument("--output", help="Output file for results")
    parser.add_argument("--startup-command",
                       default="uvicorn resync.main:app --host 0.0.0.0 --port 8000",
                       help="Command to start the application")

    args = parser.parse_args()

    validator = PerformanceValidator(args.url)

    if args.output:
        validator.save_results(args.output)

    await validator.run_validation(args.startup_command)


if __name__ == "__main__":
    asyncio.run(main())
