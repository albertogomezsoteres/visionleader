"""Per-state handlers for the navigation FSM.

Each module in this package implements one phase of the conversation
flow and exports free functions of the form
``handle_<state>(agent, ctx, ...)``. The agent's ``process_turn``
dispatches to the right handler based on ``ctx.state``.
"""
