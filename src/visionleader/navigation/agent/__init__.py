"""Internal modules of the conversation agent.

These modules contain the parts of the agent that have nothing to do with
the FSM itself: text formatting, message parsing, closure logic, PDDL plan
translation, and the planner bridge. The `ConversationAgent` class itself
lives in ``src/visionleader/navigation/conversation_agent.py`` and only contains the
state machine handlers.
"""
