#!/bin/bash
# Entry point for running Fast Downward.

# With no arguments, show help.
if [ $# -eq 0 ]; then
    echo "Fast Downward Planner"
    echo ""
    echo "Usage:"
    echo "  docker run --rm -v \$(pwd)/pddl:/pddl fast-downward:latest <domain.pddl> <problem.pddl> [options]"
    echo ""
    echo "Example:"
    echo "  docker run --rm -v \$(pwd)/pddl:/pddl fast-downward:latest domain.pddl problem.pddl"
    echo ""
    echo "Or call fast-downward directly:"
    /fast-downward/fast-downward.py --help
    exit 0
fi

# With PDDL files, run Fast Downward.
if [ $# -ge 2 ]; then
    DOMAIN_FILE="/pddl/$1"
    PROBLEM_FILE="/pddl/$2"

    # Check that the files exist.
    if [ ! -f "$DOMAIN_FILE" ]; then
        echo "Error: domain file not found: $DOMAIN_FILE"
        exit 1
    fi

    if [ ! -f "$PROBLEM_FILE" ]; then
        echo "Error: problem file not found: $PROBLEM_FILE"
        exit 1
    fi

    echo "Running Fast Downward..."
    echo "Domain: $DOMAIN_FILE"
    echo "Problem: $PROBLEM_FILE"
    echo ""

    /fast-downward/fast-downward.py "$DOMAIN_FILE" "$PROBLEM_FILE" --search "astar(lmcut())"

    # Keep the container alive briefly so it stays visible as "Up" in docker ps.
    echo ""
    echo "Fast Downward finished. Keeping the container alive for 5 seconds..."
    sleep 5
else
    # Run with the provided arguments.
    /fast-downward/fast-downward.py "$@"
fi
