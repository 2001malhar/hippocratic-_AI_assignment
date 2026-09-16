# Bedtime Story Generator

## Overview
This project generates bedtime stories for children ages 5 to 10 using a small prompt-driven workflow. Instead of relying on a single large prompt, I designed a multi-step process that plans the story, writes it, evaluates it, and revises it if needed.

## System Design
The system follows this flow:

User request
  -> Story planner
  -> Storyteller
  -> Judge
  -> Revision loop
  -> Final story

## Why this design
A single prompt is often too vague for bedtime storytelling. Children’s stories need to be age-appropriate, emotionally safe, coherent, and calm by the end. I split the process into planning, generation, and evaluation so the model had a clear structure to follow. The planner creates a compact story plan with the category, characters, setting, tone, lesson, and bedtime arc. The storyteller then uses that plan to write the story. A separate judge scores the story across a rubric and provides actionable feedback if it does not meet the threshold. If needed, the story is revised and judged again.

## Prompt Strategy
I used separate prompts for different stages:
- planner prompt: structure and constraints
- storyteller prompt: warm, simple, bedtime-friendly story writing
- judge prompt: rubric-based evaluation
- revision prompt: fix specific weaknesses without changing the core idea

## Evaluation Strategy
The judge checks:
- request adherence
- age appropriateness
- story quality
- story structure
- emotional safety
- bedtime quality

I use Python to enforce pass thresholds rather than relying only on the model’s own judgment. This keeps the system more disciplined and predictable.

## Debug Mode
I included a debug option so the story plan, judge output, and revision count can be inspected during development.

## How to Run
1. Set your OpenAI API key
2. Install dependencies
3. Run:
   python main.py

## Notes
This project is intentionally lightweight and explainable. The goal is not to build a huge multi-agent platform, but to design a compact and thoughtful story-generation system with a clear evaluation loop.