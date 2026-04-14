"""
Fast Downward planner client.

Runs Fast Downward inside a Docker container and parses the resulting plan.
"""

import subprocess
import re
from pathlib import Path
from typing import List, Dict


class FastDownwardPlanner:
    """Runs Fast Downward in Docker and returns a parsed plan."""

    def __init__(self, docker_image: str = "fast-downward:latest", timeout: int = 30):
        self.docker_image = docker_image
        self.timeout = timeout

    def plan(
        self,
        domain_path: str,
        problem_path: str,
        search_config: str = "astar(lmcut())",
    ) -> Dict:
        """
        Run Fast Downward and return the plan.

        Returns a dict with:
          success (bool), plan (List[str]), cost (int), steps (int), error (str|None)
        """
        domain_path = Path(domain_path).absolute()
        problem_path = Path(problem_path).absolute()

        if not domain_path.exists():
            return {"success": False, "error": f"Domain file not found: {domain_path}", "plan": [], "cost": 0, "steps": 0}

        if not problem_path.exists():
            return {"success": False, "error": f"Problem file not found: {problem_path}", "plan": [], "cost": 0, "steps": 0}

        pddl_dir = domain_path.parent
        container_name = "fast-downward-planner"

        try:
            subprocess.run(
                ["docker", "rm", "-f", container_name],
                capture_output=True,
                timeout=5,
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
                return {
                    "success": False,
                    "error": f"Fast Downward failed with exit code {result.returncode}",
                    "output": output,
                    "plan": [],
                    "cost": 0,
                    "steps": 0,
                }

            plan_info = self._parse_plan(output)
            return {
                "success": plan_info["success"],
                "plan": plan_info["plan"],
                "cost": plan_info["cost"],
                "steps": plan_info["steps"],
                "output": output,
                "error": plan_info.get("error"),
            }

        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Fast Downward timed out after {self.timeout}s", "plan": [], "cost": 0, "steps": 0}
        except Exception as e:
            return {"success": False, "error": f"Error running Fast Downward: {e}", "plan": [], "cost": 0, "steps": 0}

    def _parse_plan(self, output: str) -> Dict:
        """Extract plan actions, step count, and cost from Fast Downward stdout."""
        plan: List[str] = []
        cost = 0
        steps = 0
        success = False

        if "Solution found" in output:
            success = True

            m = re.search(r"Plan length:\s+(\d+)\s+step\(s\)", output)
            if m:
                steps = int(m.group(1))

            m = re.search(r"Plan cost:\s+(\d+)", output)
            if m:
                cost = int(m.group(1))

            in_plan = False
            for line in output.split("\n"):
                if "Solution found" in line or "Actual search time" in line:
                    in_plan = True
                    continue
                if in_plan and ("Plan length" in line or "Plan cost" in line):
                    break
                if in_plan and line.strip():
                    action = line.strip()
                    if action and not action.startswith("["):
                        plan.append(action)

        # Fallback: match PDDL action lines directly
        if not plan:
            matches = re.findall(r"([a-z_]+(?:\s+[a-z0-9_]+)+)\s*\(\d+\)", output)
            if matches:
                plan = [m.strip() for m in matches]
                success = True

        return {"success": success, "plan": plan, "cost": cost, "steps": steps}
