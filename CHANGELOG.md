# Changelog

## 1.1.0 (2026-11-12)

Engineering release after the thesis defence. The system's behaviour and the
reported results are unchanged, except for the parsing fix below.

- Backend packaged as `visionleader` (`pyproject.toml`, `uv.lock`, `make` targets).
- Fast Downward pinned to `release-24.06.1`; the planner benchmark solves the frozen
  problem files and reproduces the published CSV exactly.
- Test suite (dialogue, PDDL generation, VLM grounding, HTTP API, data and results)
  and CI on Python 3.10 to 3.12, including the planner reproduction in Docker.
- Fixed: building names were matched inside other words ("building CD" resolved to
  building G, "I'm" to building M).

## 1.0.0 (2026-05-23)

The system as submitted and defended as a bachelor's thesis at Universidad Francisco
de Vitoria: on-device Whisper STT, Gemma 4 E4B-it grounding, Fast Downward planning
over the campus PDDL domain, the Flutter client, and the five experiment suites.
