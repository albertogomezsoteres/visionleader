// Prompts for the on-device VLM smoke test (Gemma 3n E2B INT4).
//
// Four focused prompts, one per scenario the production app recognises.
// Each prompt targets a single photo type so the quantised model does not
// have to decide between multiple branches.
//
//   1. Classroom door → PDDL   — initial state when user photographs a door
//   2. Directory sign → PDDL   — initial state when user photographs a sign
//   3. Elevator     → JSON     — runtime verification (open/closed)
//   4. Stairs       → JSON     — runtime verification (up/down)

class NamedPrompt {
  final String id;
  final String label;
  final String prompt;
  const NamedPrompt(this.id, this.label, this.prompt);
}

const List<NamedPrompt> kPrompts = [
  NamedPrompt(
    'door_pddl',
    'Classroom door — PDDL',
    'What room number is on the plate in this image?\n'
        '\n'
        'Read the number carefully. It contains a DOT in the middle.\n'
        'The DOT separates two digits. Keep both digits and put _ where the DOT is.\n'
        '\n'
        'Plate says 3.7 → output: (at user1 classroom_3_7)\n'
        'Plate says 0.2 → output: (at user1 classroom_0_2)\n'
        'Plate says IA  → output: (at user1 lab_ia)\n'
        '\n'
        'Output ONLY the (at user1 ...) line.',
  ),
  NamedPrompt(
    'sign_pddl',
    'Directory sign — PDDL',
    'Look at this image. It shows a large white sign on a wall inside building G.\n'
        '\n'
        'In the top-right area of the sign there are two lines of text, one above the other:\n'
        '- Top line: the building letter (G)\n'
        '- Bottom line: either a floor number (0, 1, or 2) OR the word "Agora"\n'
        '\n'
        'Read the bottom line and map it to the answer:\n'
        '- "0" → (at user1 directory_sign_g_0)\n'
        '- "1" → (at user1 directory_sign_g_1)\n'
        '- "2" → (at user1 directory_sign_g_2)\n'
        '- "Agora" → (at user1 directory_sign_g_agora)\n'
        '\n'
        'Output ONLY the (at user1 ...) line. Nothing else.',
  ),
  NamedPrompt(
    'stairs_text',
    'Stairs up/down',
    'Look at this image. It shows a staircase.\n'
        '\n'
        'Question: from the point of view of the camera, do the stairs go UP or DOWN?\n'
        '\n'
        'How to decide:\n'
        '- If the next step is higher than the camera and the stairs rise away from you → up\n'
        '- If the next step is lower than the camera and the stairs drop away from you → down\n'
        '\n'
        'Answer with exactly one of these two phrases:\n'
        'stairs up\n'
        'stairs down\n'
        '\n'
        'Output ONLY the phrase. No punctuation, no extra words.',
  ),
  NamedPrompt(
    'elevator_json_cabin',
    'Elevator open/closed',
    'Look at this image. Focus on the elevator doors.\n'
        '\n'
        'Can you see the inside of the elevator cabin?\n'
        '- YES, I can see inside the cabin → the doors are open\n'
        '- NO, I cannot see inside, the doors are a solid surface → the doors are closed\n'
        '\n'
        'Valid answers:\n'
        '{"type": "elevator", "detail": "open"}\n'
        '{"type": "elevator", "detail": "closed"}\n'
        '\n'
        'Output ONLY the JSON. Nothing else.',
  ),
];
