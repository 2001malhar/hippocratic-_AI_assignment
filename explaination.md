## 1. Planning: how I designed it

I broke the problem into small, deliberate steps so I could divide the work across different functions instead of putting everything into one large function.

- I asked the user for a bedtime story request
- I added an optional style choice to give the story a bit more personality
- I created a planner that turns the request into a compact story plan
- I used a storyteller to write the story from that plan
- I added a judge to score the result
- If the story failed the evaluation, I revised it
- I returned the final story to the user

This matters because a single prompt is often too vague or too loose. For a children’s bedtime story, I needed:
- the right age fit
- emotional safety
- a calm ending
- a clear story arc
- a gentle tone

So my design was:

User request -> plan -> write story -> evaluate -> revise if needed -> final story

This gave me structure, consistency, and a better chance of producing a story that felt thoughtful instead of random.

---

## 2. What functions I created and why

### 2.1 `call_model(...)`
Purpose:
- sends the prompt to the OpenAI model
- sets the system prompt, token count, and temperature
- returns the model output

Why:
- this is the central reusable API wrapper
- every other function uses it
- it keeps the code clean and consistent

---

### 2.2 `parse_json_response(...)`
Purpose:
- converts model output into Python dictionaries
- handles normal JSON and fenced JSON blocks

Why:
- the planner and judge are expected to return JSON
- LLMs often add formatting or extra text
- this function makes the system more robust

---

### 2.3 `call_model_for_json(...)`
Purpose:
- calls the model while expecting structured JSON
- retries once if parsing fails

Why:
- JSON output is critical for the planner and judge
- this reduces failed runs and makes the system more reliable

---

### 2.4 `create_story_plan(...)`
Purpose:
- turns the request into a small structured plan
- includes:
  - category
  - target age
  - characters
  - setting
  - tone
  - story arc
  - lesson
  - bedtime ending

Why:
- this gives the storyteller a blueprint instead of asking it to create everything from scratch
- better structure leads to better story quality
- this also makes the story more consistent with the user request

This was one of the most important design choices.

---

### 2.5 `write_story_from_plan(...)`
Purpose:
- writes the actual bedtime story using the plan

Why:
- the plan makes the story more focused
- the prompt can instruct the model to write warm, gentle stories for ages 5–10
- the story is less likely to drift or become generic

This function is the creative step.

---

### 2.6 `judge_story(...)`
Purpose:
- reviews the generated story
- scores it on:
  - request adherence
  - age appropriateness
  - story quality
  - story structure
  - emotional safety
  - bedtime quality
- also returns feedback to improve it

Why:
- a story is subjective
- I needed a rubric to judge quality
- I did not want the model to simply say “good” or “bad”
- the judge made the process more intentional and measurable

This became the system’s quality-control layer.

---

### 2.7 `calculate_evaluation(...)`
Purpose:
- validates the judge scores
- calculates the overall score
- determines whether the story passes

Why:
- LLM evaluations are helpful but not always perfect
- Python should enforce the rules
- this keeps the system from accepting weak stories just because the model sounded confident

This was a strong engineering decision.

---

### 2.8 `passes_evaluation(...)`
Purpose:
- checks whether the story meets the pass threshold

Why:
- I wanted objective rules instead of relying only on subjective output
- it kept the project disciplined and predictable

Example rules:
- the overall score must be high enough
- safety must be high enough
- request adherence must be high enough
- age fit must be high enough

This was the final gate before acceptance.

---

### 2.9 `revise_story(...)`
Purpose:
- rewrites the story using the judge’s feedback
- keeps the same core idea but fixes weak spots

Why:
- first drafts are rarely perfect
- a revision step improves quality without starting from scratch
- it makes the system feel more like an agent than a one-shot prompt

---

### 2.10 `create_bedtime_story(...)`
Purpose:
- orchestrates the full flow:
  - plan story
  - generate story
  - judge it
  - revise if needed
  - stop after the allowed number of revisions

Why:
- this is the main workflow function
- it ties the pipeline together
- it makes the system easy to explain and run

---

### 2.11 `get_style_choice()`
Purpose:
- lets the user optionally choose a broad style
- examples:
  - cozy
  - funny
  - magical
  - adventurous

Why:
- it adds a small creative touch
- it helps tailor the story without adding complexity
- it keeps the experience user-friendly

This is a lightweight custom feature.

---

### 2.12 `print_debug_info(...)`
Purpose:
- prints the story plan, evaluation, and revision count when `--debug` is used

Why:
- it is useful for debugging and explaining the workflow
- it helps show that the system is doing real evaluation rather than just generating text

This is useful in a demo or interview.

---

## 3. How the flow works from start to finish

This was the exact flow:

1. I asked the user for a bedtime story prompt
2. I optionally selected a style
3. `create_story_plan(...)` created a structured plan
4. `write_story_from_plan(...)` wrote a story from that plan
5. `judge_story(...)` evaluated the story
6. `calculate_evaluation(...)` computed the final scores
7. `passes_evaluation(...)` decided if the story passed
8. If not:
   - `revise_story(...)` improved it
   - then the judge ran again
9. The final story was printed

So the process was:

User request -> story plan -> story generation -> evaluation -> revision -> final output

---

## 4. Why this generates a nice bedtime story

The story quality came from a few deliberate choices.

### 4.1 The planner made the story more focused
Instead of writing “a random story,” I first decided:
- who the characters were
- where it happened
- what problem they faced
- what lesson was naturally present
- how it should end

This improved coherence.

---

### 4.2 The storyteller prompt was designed for ages 5–10
I told the model to:
- use simple but vivid language
- include a mild challenge
- keep the ending calm
- avoid fear, violence, or confusion
- end with a warm bedtime feeling

This mattered more than simply saying “be child-friendly.”

---

### 4.3 The judge checked the right dimensions
The system did not just ask “is this good?” It checked:
- Did it match the request?
- Is it age-appropriate?
- Is it clear and well structured?
- Is it emotionally safe?
- Does it feel like a bedtime story?

These are exactly the things that matter for a bedtime story for young children.

---

### 4.4 The revision loop improved weak stories
I did not treat the first draft as final.
If the judge said the story was too flat, too generic, too scary, or too weakly structured, I revised it based on those specific issues.

This improved the output quality without making the system too complicated.

---

## 5. Why this is a strong design

I think this design is strong because it reflects real engineering principles:

- separation of responsibilities
- structured prompts instead of one giant prompt
- objective scoring in Python
- iterative improvement
- age-targeted constraints
- user-centered bedtime story output

This is the kind of design that looks good in an assignment or interview because it shows:
- I understand prompt design
- I understand evaluation
- I understand how to improve generated outputs
- I know how to make a system feel intentional rather than random

If you want, I can next turn this into:
- a polished README section
- a 5-minute verbal explanation for a review call
- or a cleaner final summary paragraph for submission.