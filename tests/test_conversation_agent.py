"""The finite-state dialogue, driven turn by turn as the mobile client does."""

from __future__ import annotations

import pytest

from visionleader.navigation.conversation_agent import ConversationAgent

ELEVATOR_OPEN = {
    "prompt_id": "elevator_state",
    "success": True,
    "state_type": "elevator",
    "state_detail": "open",
}


def room_plate(location_id: str) -> dict:
    return {
        "prompt_id": "room_plate",
        "success": True,
        "location_id": location_id,
        "raw_response": f"(at user {location_id})",
    }


class Session:
    """Thin helper that keeps the session id and returns the agent's reply."""

    def __init__(self, agent: ConversationAgent, session_id: str = "test") -> None:
        self.agent = agent
        self.session_id = session_id

    def say(self, message: str | None = None, photo: dict | None = None) -> dict:
        return self.agent.process_turn(self.session_id, message, photo)


@pytest.fixture
def session(agent: ConversationAgent) -> Session:
    return Session(agent)


def state(reply: dict) -> str:
    return reply["context"]["state"]


def start_route(session: Session) -> dict:
    session.say()
    session.say("I am at entrance 2 of building G")
    return session.say("take me to classroom 1.4")


def test_welcome_asks_for_the_location(session: Session) -> None:
    reply = session.say()
    assert state(reply) == "ask_knows_location"
    assert reply["next_input"] == "voice_or_photo"
    assert reply["expect_photo"] == "origin_photo_g"


def test_voice_origin_is_grounded_and_confirmed(session: Session) -> None:
    session.say()
    reply = session.say("I am at entrance 2 of building G")
    assert state(reply) == "ask_destination"
    assert "entrance 2" in reply["tts_message"]
    assert "Building G" in reply["tts_message"]


def test_destination_triggers_one_planner_call_with_the_right_problem(
    session: Session, fake_planner
) -> None:
    reply = start_route(session)
    assert len(fake_planner.problems) == 1
    problem = fake_planner.problems[0]
    assert "(at user entrance_2)" in problem
    assert "(at user classroom_g_1_4)" in problem
    assert state(reply) == "waiting_step_photo"
    assert reply["expect_photo"] == "elevator_state"
    assert reply["tts_message"].startswith("Route to Classroom 1.4, in Building G.")


def test_photo_verified_route_reaches_the_destination(session: Session) -> None:
    start_route(session)

    reply = session.say(photo=ELEVATOR_OPEN)
    assert reply["action"] == "step_after_photo_confirm"
    assert reply["expect_photo"] == "room_plate"

    reply = session.say(photo=room_plate("classroom_g_1_4"))
    assert state(reply) == "navigation_complete"
    assert "You have arrived at Classroom 1.4" in reply["tts_message"]


def test_wrong_room_plate_does_not_count_as_arrival(session: Session) -> None:
    start_route(session)
    session.say(photo=ELEVATOR_OPEN)

    reply = session.say(photo=room_plate("classroom_g_1_3"))
    assert reply["action"] == "retry_step_photo"
    assert state(reply) == "waiting_step_photo"
    assert "1.4" in reply["tts_message"]
    assert "1.3" in reply["tts_message"]


def test_photo_steps_can_be_skipped_by_voice(session: Session) -> None:
    start_route(session)
    session.say("done")
    reply = session.say("done")
    assert state(reply) == "navigation_complete"


@pytest.mark.parametrize("command", ["repeat", "say that again"])
def test_repeat_replays_the_last_instruction(session: Session, command: str) -> None:
    first = start_route(session)
    reply = session.say(command)
    assert reply["tts_message"] == first["tts_message"]
    assert state(reply) == state(first)


def test_cancel_returns_to_asking_for_a_destination(session: Session) -> None:
    start_route(session)
    reply = session.say("cancel")
    assert reply["action"] == "cancelled"
    assert state(reply) == "ask_destination"


def test_sessions_are_isolated(agent: ConversationAgent) -> None:
    alice, bob = Session(agent, "alice"), Session(agent, "bob")
    start_route(alice)
    assert state(bob.say()) == "ask_knows_location"
    assert state(alice.say("repeat")) == "waiting_step_photo"


def test_no_route_is_reported_to_the_user(session: Session, fake_planner) -> None:
    fake_planner.output = "Search stopped without finding a solution.\n"
    reply = start_route(session)
    assert state(reply) == "ask_destination"
    assert "couldn't compute a route" in reply["tts_message"]


def test_origin_can_be_grounded_from_a_photo(session: Session) -> None:
    session.say()
    reply = session.say(
        photo={
            "prompt_id": "origin_photo_g",
            "success": True,
            "location_id": "classroom_g_1_4",
            "raw_response": "(at user classroom_g_1_4)",
        }
    )
    assert state(reply) == "ask_destination"
    assert "Classroom 1.4, in Building G" in reply["tts_message"]


def test_unreadable_photos_fall_back_to_voice_questions(session: Session) -> None:
    blurry = {"prompt_id": "origin_photo_g", "success": False, "raw_response": ""}
    session.say()
    assert state(session.say("No, I do not know where I am")) == "waiting_photo_origin"
    assert session.say(photo=blurry)["action"] == "retry_photo"
    assert session.say(photo=blurry)["action"] == "retry_photo"
    assert state(session.say(photo=blurry)) == "ask_location_voice"

    assert state(session.say("I am on the first floor")) == "ask_building"
    reply = session.say("building G")
    assert state(reply) == "ask_destination"
    assert "Building G, on floor 1" in reply["tts_message"]


def test_hurry_mode_reaches_the_planner(session: Session, fake_planner) -> None:
    session.say()
    session.say("I am at entrance 2 of building G")
    reply = session.say("I'm in a hurry, take me to classroom 1.4")
    assert "(hurry_mode)" in fake_planner.problems[0]
    assert "Hurry mode on" in reply["tts_message"]


def test_named_places_resolve_to_a_planning_goal(session: Session, fake_planner) -> None:
    session.say()
    session.say("I am at entrance 2 of building G")
    reply = session.say("take me to the cafeteria")
    assert "(at user cafeteria)" in fake_planner.problems[0]
    assert reply["tts_message"].startswith("Route to the cafeteria.")
