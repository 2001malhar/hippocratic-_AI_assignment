import json
import os
import sys
from typing import List, TypedDict
from dotenv import load_dotenv
import openai


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

MAX_REVISIONS = 2

load_dotenv()

EVALUATION_POLICY = {
    "overall_score": 4.0,
    "request_adherence": 4,
    "age_appropriateness": 4,
    "emotional_safety": 4,
    "bedtime_quality": 4,
}

SCORE_KEYS = [
    "request_adherence",
    "age_appropriateness",
    "story_quality",
    "story_structure",
    "emotional_safety",
    "bedtime_quality",
]


# ---------------------------------------------------------
# Typed structures
# ---------------------------------------------------------

class StoryPlan(TypedDict):
    category: str
    target_age: str
    characters: List[str]
    setting: str
    tone: str
    story_arc: List[str]
    lesson: str
    bedtime_ending: str


class StoryEvaluation(TypedDict, total=False):
    request_adherence: float
    age_appropriateness: float
    story_quality: float
    story_structure: float
    emotional_safety: float
    bedtime_quality: float
    overall_score: float
    pass_: bool
    feedback: List[str]



def call_model(
    prompt: str,
    system_prompt: str = "",
    max_tokens: int = 1200,
    temperature: float = 0.7,
) -> str:
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise ValueError(
            "Please set the OPENAI_API_KEY environment variable before running this script."
        )

    client = openai.OpenAI(api_key=api_key)

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )

    return response.choices[0].message.content.strip()


# ---------------------------------------------------------
# Structured JSON handling
# ---------------------------------------------------------

def parse_json_response(raw_text: str) -> dict:
    """
    Parse JSON returned by the model.

    Supports:
    - plain JSON
    - fenced JSON
    - JSON surrounded by small amounts of explanatory text
    """

    cleaned = raw_text.strip()

    if cleaned.startswith("```"):
        cleaned = (
            cleaned
            .replace("```json", "")
            .replace("```JSON", "")
            .replace("```", "")
            .strip()
        )

    try:
        return json.loads(cleaned)

    except json.JSONDecodeError:
        pass

    # Fallback: attempt to extract a JSON object from surrounding text.
    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start != -1 and end != -1 and start < end:
        candidate = cleaned[start:end + 1]

        try:
            return json.loads(candidate)

        except json.JSONDecodeError:
            pass

    raise ValueError(
        "The model returned invalid JSON.\n\n"
        f"Raw response:\n{raw_text}"
    )


def call_model_for_json(
    prompt: str,
    system_prompt: str,
    max_tokens: int,
    temperature: float,
) -> dict:
    """
    Call the model expecting JSON.

    If parsing fails, retry once with stricter output instructions.
    """

    retry_instruction = """

IMPORTANT OUTPUT REQUIREMENT:
Return exactly one valid JSON object.
Do not use Markdown code fences.
Do not include explanations.
Do not include text before or after the JSON object.
"""

    attempts = [
        prompt,
        prompt + retry_instruction,
    ]

    last_error = None

    for current_prompt in attempts:
        response = call_model(
            current_prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        try:
            return parse_json_response(response)

        except ValueError as exc:
            last_error = exc

    raise ValueError(
        "The model failed to return valid JSON after one retry."
    ) from last_error


# ---------------------------------------------------------
# Story planning
# ---------------------------------------------------------

def create_story_plan(
    user_request: str,
    style: str,
) -> StoryPlan:
    """
    Create a lightweight story plan.

    The planner is intentionally simple: enough structure to improve
    consistency, but not a full orchestration framework.
    """

    system_prompt = """
You are a careful planner for children's bedtime stories.

Your task is to convert a user's request into a short structured plan
for a bedtime story appropriate for children ages 5 to 10.

The plan should improve consistency and story structure without becoming elaborate.

Do not write the full story.

Return valid JSON only.
"""

    prompt = f"""
User request:
"{user_request}"

Requested style:
"{style}"

Create a short JSON story plan using exactly these keys:

{{
    "category": "one short category such as animal_adventure, fantasy, friendship, everyday_life, or bedtime_magic",
    "target_age": "a reasonable age range within ages 5 to 10",
    "characters": ["2 to 4 important characters"],
    "setting": "short description of where the story happens",
    "tone": "short description matching the requested style",
    "story_arc": [
        "setup",
        "mild problem",
        "meaningful action taken by the characters",
        "resolution"
    ],
    "lesson": "a subtle lesson or kindness theme",
    "bedtime_ending": "short note describing how the story becomes calm and reassuring"
}}

Planning guidelines:
- Follow all important details in the user's request.
- Keep the plan concise.
- Give the main character something meaningful to do.
- Use a mild, age-appropriate challenge.
- Mild worry or suspense is allowed.
- Avoid graphic violence, cruelty, intense fear, death, or unresolved distress.
- The ending should feel warm, emotionally complete, and suitable for bedtime.
- The lesson should emerge naturally rather than feel preachy.

Return JSON only.
"""

    plan = call_model_for_json(
        prompt=prompt,
        system_prompt=system_prompt,
        max_tokens=700,
        temperature=0.35,
    )

    return plan  # type: ignore


# ---------------------------------------------------------
# Story generation
# ---------------------------------------------------------

def write_story_from_plan(
    user_request: str,
    style: str,
    plan: StoryPlan,
) -> str:
    """
    Generate the initial bedtime story.
    """

    system_prompt = """
You are a gifted children's bedtime storyteller.

Write stories for children ages 5 to 10 that are imaginative, warm,
easy to follow, and pleasant to hear aloud.

A strong story should:
- hook the child quickly
- establish memorable characters
- introduce a clear but mild problem
- give the main character agency
- include concrete imagery and natural dialogue
- build toward a satisfying resolution
- gradually reduce emotional intensity near the end
- finish with a peaceful, reassuring bedtime feeling

Avoid writing that feels generic, repetitive, or overly moralizing.

Return only the title and story.
"""

    prompt = f"""
Original user request:
"{user_request}"

Requested style:
"{style}"

Story plan:
{json.dumps(plan, indent=2)}

Write a complete bedtime story that follows both the original request
and the story plan.

Requirements:
- Appropriate for children ages 5 to 10.
- Aim for approximately 400 to 700 words.
- Put a short title on the first line.
- Use simple but vivid language.
- Include a clear beginning, middle, and ending.
- Give the main character meaningful choices or actions.
- Include at least a small amount of sensory detail or dialogue.
- Use a mild challenge that creates interest without becoming frightening.
- Mild suspense or worry is allowed when age appropriate.
- Avoid graphic violence, cruelty, intense fear, death, or unresolved distress.
- Resolve the challenge clearly and kindly.
- Do not force a moral into the story.
- Gradually make the final section quieter and calmer.
- End with a warm, comforting final paragraph suitable for bedtime.
- Follow the requested style consistently.

Return only the title and story.
"""

    return call_model(
        prompt,
        system_prompt=system_prompt,
        max_tokens=1300,
        temperature=0.8,
    )


# ---------------------------------------------------------
# Story evaluation
# ---------------------------------------------------------

def judge_story(
    user_request: str,
    style: str,
    plan: StoryPlan,
    story: str,
) -> StoryEvaluation:
    """
    Ask the LLM to provide subjective evaluation scores and feedback.

    The LLM evaluates qualitative dimensions.
    Python calculates the final average and pass/fail result.
    """

    system_prompt = """
You are a strict but fair evaluator of children's bedtime stories.

Judge the story against:
1. the original request
2. the requested style
3. the story plan
4. the rubric below

Be critical enough to distinguish acceptable work from excellent work.

Do not calculate the overall score.
Do not decide whether the story passes.

Return valid JSON only.
"""

    prompt = f"""
Original user request:
"{user_request}"

Requested style:
"{style}"

Story plan:
{json.dumps(plan, indent=2)}

Story to evaluate:
--- STORY START ---
{story}
--- STORY END ---

Score every category from 1 to 5.

Use these anchors:

1 = poor
2 = weak
3 = acceptable but clearly improvable
4 = strong
5 = excellent

Evaluate:

1. request_adherence
5 = follows all important requested details naturally
3 = follows the main idea but misses or weakens some details
1 = substantially ignores or contradicts the request

2. age_appropriateness
5 = vocabulary, ideas, and emotional complexity fit ages 5-10 very well
3 = mostly suitable but occasionally too advanced, confusing, or simplistic
1 = clearly unsuitable for the target age

3. story_quality
5 = vivid, imaginative, emotionally engaging, and memorable
3 = understandable but predictable, flat, or generic
1 = confusing, dull, repetitive, or incoherent

4. story_structure
5 = strong setup, meaningful challenge, character action, resolution, and ending
3 = complete story but pacing or transitions are weak
1 = lacks a coherent narrative arc

5. emotional_safety
5 = mild, appropriate conflict with reassuring resolution
3 = some moments may be unnecessarily tense or uncomfortable
1 = contains intense fear, graphic harm, cruelty, or unresolved distress

6. bedtime_quality
5 = emotional intensity settles naturally and the ending feels peaceful and comforting
3 = ending is acceptable but not especially calming
1 = ending feels abrupt, stimulating, unsettling, or unresolved

Return exactly this JSON shape:

{{
    "request_adherence": 1,
    "age_appropriateness": 1,
    "story_quality": 1,
    "story_structure": 1,
    "emotional_safety": 1,
    "bedtime_quality": 1,
    "feedback": [
        "specific actionable improvement",
        "specific actionable improvement"
    ]
}}

Feedback rules:
- Give 2 to 4 short notes.
- Focus on the weakest areas.
- Make every note actionable.
- Do not praise the story unless that praise directly explains what should be preserved.
- If the story is already strong, suggest only small refinements.

Return valid JSON only.
"""

    evaluation = call_model_for_json(
        prompt=prompt,
        system_prompt=system_prompt,
        max_tokens=900,
        temperature=0.15,
    )

    return calculate_evaluation(evaluation)  # type: ignore


def calculate_evaluation(
    evaluation: dict,
) -> StoryEvaluation:
    """
    Validate scores, calculate the average, and apply the evaluation policy.
    """

    scores = []

    for score_name in SCORE_KEYS:
        raw_score = evaluation.get(score_name, 1)

        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            score = 1.0

        # Rubric is defined from 1 to 5.
        score = max(1.0, min(5.0, score))

        evaluation[score_name] = score
        scores.append(score)

    evaluation["overall_score"] = round(
        sum(scores) / len(scores),
        2,
    )

    feedback = evaluation.get("feedback")

    if not isinstance(feedback, list):
        evaluation["feedback"] = [
            "Improve the weakest scoring dimensions while preserving strong parts of the story."
        ]

    evaluation["pass_"] = passes_evaluation(evaluation)

    return evaluation  # type: ignore


def passes_evaluation(
    evaluation: StoryEvaluation,
) -> bool:
    """
    Apply centralized acceptance rules.
    """

    return all(
        evaluation.get(metric, 0) >= threshold
        for metric, threshold in EVALUATION_POLICY.items()
    )


# ---------------------------------------------------------
# Revision
# ---------------------------------------------------------

def revise_story(
    user_request: str,
    style: str,
    plan: StoryPlan,
    story: str,
    feedback: List[str],
) -> str:
    """
    Revise the story using judge feedback while preserving strong sections.
    """

    system_prompt = """
You are an expert editor for children's bedtime stories.

Revise the story based on evaluator feedback.

Preserve everything that already works well.
Do not rewrite sections unnecessarily.

Keep the original characters, story identity, and user intent unless
the feedback specifically requires a change.

The revised story should feel like a better version of the same story,
not a completely different story.

Return only the revised title and story.
"""

    feedback_text = "\n".join(
        f"- {item}"
        for item in feedback
    )

    prompt = f"""
Original user request:
"{user_request}"

Requested style:
"{style}"

Story plan:
{json.dumps(plan, indent=2)}

Current story:
--- STORY START ---
{story}
--- STORY END ---

Evaluator feedback:
{feedback_text}

Revise the story.

Requirements:
- Preserve strong parts of the current version.
- Address each useful feedback item.
- Continue following the original request.
- Preserve the main characters and core idea.
- Keep the language suitable for ages 5 to 10.
- Improve engagement without making the story overstimulating.
- Keep any challenge mild and emotionally safe.
- Avoid graphic violence, cruelty, intense fear, death, or unresolved distress.
- Maintain a clear story arc.
- Keep the requested style.
- End peacefully and reassuringly.
- Return only the title and revised story.
"""

    return call_model(
        prompt,
        system_prompt=system_prompt,
        max_tokens=1300,
        temperature=0.6,
    )


# ---------------------------------------------------------
# Main generation loop
# ---------------------------------------------------------

def create_bedtime_story(
    user_request: str,
    style: str,
) -> tuple[str, StoryPlan, StoryEvaluation, int]:
    """
    Run the full story generation and evaluation pipeline.
    """

    plan = create_story_plan(
        user_request,
        style,
    )

    story = write_story_from_plan(
        user_request,
        style,
        plan,
    )

    evaluation: StoryEvaluation = {}
    revisions_used = 0

    for attempt in range(MAX_REVISIONS + 1):

        evaluation = judge_story(
            user_request,
            style,
            plan,
            story,
        )

        if evaluation["pass_"]:
            break

        if attempt == MAX_REVISIONS:
            break

        story = revise_story(
            user_request,
            style,
            plan,
            story,
            evaluation.get("feedback", []),
        )

        revisions_used += 1

    return story, plan, evaluation, revisions_used


def get_style_choice() -> str:
    """
    Let the user optionally choose the storytelling style.
    """

    print("\nChoose a story style:")
    print("1. Cozy")
    print("2. Funny")
    print("3. Magical")
    print("4. Adventure")
    print("5. Surprise me")

    choice = input("Style [default: Surprise me]: ").strip()

    styles = {
        "1": "cozy and gentle",
        "2": "playful and funny",
        "3": "magical and imaginative",
        "4": "adventurous but bedtime-friendly",
        "5": "choose the style that best fits the request",
        "": "choose the style that best fits the request",
    }

    return styles.get(
        choice,
        "choose the style that best fits the request",
    )

# ---------------------------------------------------------
# Debug output
# ---------------------------------------------------------

def print_debug_info(
    plan: StoryPlan,
    evaluation: StoryEvaluation,
    revisions_used: int,
) -> None:
    """
    Print planner and evaluator information when running with --debug.
    """

    print("\n" + "=" * 60)
    print("DEBUG INFO")
    print("=" * 60)

    print("\nSTORY PLAN:")
    print(json.dumps(plan, indent=2))

    print("\nFINAL EVALUATION:")
    print(json.dumps(evaluation, indent=2))

    print(f"\nRevisions used: {revisions_used}")
    print(f"Maximum automatic revisions: {MAX_REVISIONS}")


# ---------------------------------------------------------
# Program entry point
# ---------------------------------------------------------

def main():
    user_request = input(
        "What kind of bedtime story do you want? (Default : A tiny fox helps a lost bunny in a moonlit garden.) "
    ).strip()

    if not user_request:
        user_request = (
            "A tiny fox helps a lost bunny in a moonlit garden."
        )

    style = get_style_choice()

    try:
        story, plan, evaluation, revisions_used = create_bedtime_story(
            user_request,
            style,
        )

        print("\n" + "=" * 60)
        print("FINAL STORY")
        print("=" * 60)
        print()
        print(story)

        if "--debug" in sys.argv:
            print_debug_info(
                plan,
                evaluation,
                revisions_used,
            )


    except Exception as exc:
        print(f"\nError: {exc}")


if __name__ == "__main__":
    main()