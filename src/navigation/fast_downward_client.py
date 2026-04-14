"""
Fast Downward planner client.

Runs Fast Downward inside a Docker container, parses the resulting plan,
and returns a structured result dict. Uses the standard logging module
instead of print() so callers can control verbosity.
"""

import logging
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Default search configuration — A* with landmark-cut heuristic.
_DEFAULT_SEARCH = "astar(lmcut())"

# Default timeout in seconds.  Can be overridden per-instance.
_DEFAULT_TIMEOUT = 30


class FastDownwardPlanner:
    """Runs Fast Downward in Docker and returns a parsed plan."""

    def __init__(
        self,
        docker_image: str = "fast-downward:latest",
        timeout: int = _DEFAULT_TIMEOUT,
    ):
        self.docker_image = docker_image
        self.timeout = timeout

    def plan(
        self,
        domain_path: str,
        problem_path: str,
        search_config: str = _DEFAULT_SEARCH,
    ) -> Dict:
        """
        Run Fast Downward and return the plan.

        Returns a dict with:
          success (bool)    — whether a plan was found
          plan    (List[str]) — list of PDDL action strings
          cost    (int)     — plan cost reported by Fast Downward
          steps   (int)     — number of plan steps
          error   (str|None) — error message if success is False
          output  (str)     — raw Fast Downward stdout+stderr
        """
        domain_path  = Path(domain_path).absolute()
        problem_path = Path(problem_path).absolute()

        if not domain_path.exists():
            return self._failure(f"Domain file not found: {domain_path}")
        if not problem_path.exists():
            return self._failure(f"Problem file not found: {problem_path}")

        pddl_dir       = domain_path.parent
        container_name = "fast-downward-planner"

        # Remove any leftover container from a previous run (ignore errors).
        try:
            subprocess.run(
                ["docker", "rm", "-f", container_name],
                capture_output=True, timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            pass

        cmd = [
            "docker", "run",
            "--name", container_name,
            "-v", f"{pddl_dir}:/pddl",
            self.docker_image,
            domain_path.name,
            problem_path.name,
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(pddl_dir),
            )
            output = result.stdout + result.stderr

            if result.returncode != 0:
                logger.warning(
                    "Fast Downward exited with code %d", result.returncode
                )
                return self._failure(
                    f"Fast Downward failed (exit code {result.returncode})",
                    output=output,
                )

            plan_info = self._parse_plan(output)
            if plan_info["success"]:
                logger.info(
                    "Plan found: %d steps, cost=%d",
                    plan_info["steps"], plan_info["cost"],
                )
            else:
                logger.warning("Fast Downward found no solution")

            return {
                "success": plan_info["success"],
                "plan":    plan_info["plan"],
                "cost":    plan_info["cost"],
                "steps":   plan_info["steps"],
                "output":  output,
                "error":   plan_info.get("error"),
            }

        except subprocess.TimeoutExpired:
            logger.error("Fast Downward timed out after %ds", self.timeout)
            return self._failure(
                f"Fast Downward timed out after {self.timeout}s"
            )
        except Exception as exc:
            logger.exception("Unexpected error running Fast Downward")
            return self._failure(f"Error running Fast Downward: {exc}")

    # ── parsing ───────────────────────────────────────────────────────────────

    def _parse_plan(self, output: str) -> Dict:
        """Extract plan actions, step count and cost from Fast Downward output."""
        plan:    List[str] = []
        cost  = 0
        steps = 0
        success = False

        if "Solution found" in output:
            success = True

            m = re.search(r"Plan length:\s+(\d+)\s+step", output)
            if m:
                steps = int(m.group(1))

            m = re.search(r"Plan cost:\s+(\d+)", output)
            if m:
                cost = int(m.group(1))

            in_plan = False
            for line in output.splitlines():
                if "Solution found" in line or "Actual search time" in line:
                    in_plan = True
                    continue
                if in_plan and ("Plan length" in line or "Plan cost" in line):
                    break
                if in_plan and line.strip() and not line.strip().startswith("["):
                    plan.append(line.strip())

        # Fallback: match PDDL action lines directly (some FD versions differ).
        if not plan and success:
            matches = re.findall(
                r"([a-z_]+(?:\s+[a-z0-9_]+)+)\s*\(\d+\)", output
            )
            if matches:
                plan = [m.strip() for m in matches]

        return {
            "success": success,
            "plan":    plan,
            "cost":    cost,
            "steps":   steps,
            "error":   None if success else "No solution found",
        }

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _failure(msg: str, output: str = "") -> Dict:
        return {
            "success": False,
            "error":   msg,
            "plan":    [],
            "cost":    0,
            "steps":   0,
            "output":  output,
        }
