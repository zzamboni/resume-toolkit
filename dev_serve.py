#!/usr/bin/env python3
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path


IMAGE = os.environ.get("VITA_PIPELINE_IMAGE", "zzamboni/resume-toolkit:latest")
POLL_INTERVAL = float(os.environ.get("VITA_DEV_SERVE_POLL_INTERVAL", "2"))
ROOT = Path(__file__).resolve().parent


def usage() -> None:
    print(
        "Usage:\n"
        "  ./dev-serve.sh <build-resume.sh args...>\n\n"
        "Examples:\n"
        "  ./dev-serve.sh zamboni-vita-full.json --serve\n"
        "  VITA_PIPELINE_IMAGE=resume-toolkit:test ./dev-serve.sh sample/example-resume.json --serve\n\n"
        "Environment:\n"
        "  VITA_PIPELINE_IMAGE            Docker image tag to watch and run\n"
        "  VITA_DEV_SERVE_POLL_INTERVAL   Seconds between image ID checks (default: 2)"
    )


def run_capture(args: list[str]) -> str:
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def current_image_id() -> str:
    return run_capture(["docker", "image", "inspect", IMAGE, "--format", "{{.Id}}"])


def current_container_ids() -> list[str]:
    output = run_capture(
        ["docker", "ps", "--filter", f"ancestor={IMAGE}", "--format", "{{.ID}}"]
    )
    return [line for line in output.splitlines() if line]


class DevServe:
    def __init__(self, forwarded_args: list[str]) -> None:
        self.forwarded_args = list(forwarded_args)
        if "--no-it" not in self.forwarded_args:
            self.forwarded_args.insert(0, "--no-it")
        self.child: subprocess.Popen[str] | None = None
        self.container_id: str | None = None
        self.last_image_id = current_image_id()
        self.terminating = False
        self.restart_requested = False

    def start_child(self) -> None:
        print(f"→ Starting build-resume.sh using image {IMAGE}", flush=True)
        before_ids = set(current_container_ids())
        self.child = subprocess.Popen(
            ["./build-resume.sh", *self.forwarded_args],
            text=True,
            cwd=ROOT,
        )
        self.container_id = None
        for _ in range(20):
            if self.child.poll() is not None:
                return
            time.sleep(0.25)
            new_ids = set(current_container_ids()) - before_ids
            if new_ids:
                self.container_id = sorted(new_ids)[0]
                return

    def stop_child(self) -> None:
        container_id = self.container_id
        child = self.child
        self.container_id = None
        self.child = None

        if container_id:
            subprocess.run(
                ["docker", "stop", container_id],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )

        if child is not None:
            if child.poll() is None:
                child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)

    def request_stop(self, _signum: int, _frame) -> None:
        self.terminating = True
        self.stop_child()
        raise SystemExit(130)

    def run(self) -> int:
        if not self.last_image_id:
            print(f"Image not found: {IMAGE}", file=sys.stderr)
            return 1

        signal.signal(signal.SIGINT, self.request_stop)
        signal.signal(signal.SIGTERM, self.request_stop)

        self.start_child()
        try:
            while True:
                time.sleep(POLL_INTERVAL)
                new_id = current_image_id()
                if new_id and new_id != self.last_image_id:
                    print(f"→ Detected updated image {IMAGE}", flush=True)
                    self.stop_child()
                    self.last_image_id = new_id
                    if not self.terminating:
                        self.start_child()
                    continue

                if self.child is not None and self.child.poll() is not None and not self.terminating:
                    print("→ build-resume.sh exited; restarting", flush=True)
                    self.stop_child()
                    self.start_child()
        finally:
            self.stop_child()


def main(argv: list[str]) -> int:
    if not argv:
        usage()
        return 1
    return DevServe(argv).run()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
