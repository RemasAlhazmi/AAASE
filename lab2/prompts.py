# Planner Prompt


PLANNER_PROMPT = """
You are an AI Research Planner.

Your task is to create a research strategy for the following AI tool.

Tool:
{tool_name}

Generate:

1. Main research objective.
2. Information that should be collected.
3. Technical topics to investigate.
4. Suggested search queries.

Return the plan in a clear format.
"""



# Analysis Prompt


ANALYSIS_PROMPT = """
You are an AI Research Analyst.

Analyze the following research about:

Tool:
{tool_name}

Research:

{research}

Generate the following sections:

1. Overview

2. Main Features

3. How It Works

4. Common Use Cases

5. Advantages

6. Limitations

Write professionally and avoid repetition.
"""



# Evaluation Prompt


EVALUATION_PROMPT = """
Evaluate the quality of the following AI tool research.

Research:

{analysis}

Evaluate based on:

- Overview completeness
- Features coverage
- Technical explanation depth
- Use cases variety
- Advantages listed
- Limitations listed
- Overall clarity and structure

You MUST return ALL of these fields:

1. score        : Integer from 1 to 10.
2. strengths    : What the research covers well (1-3 sentences).
3. weaknesses   : Where the research is thin or vague (1-3 sentences).
4. missing_information : Specific topics completely absent from the research.
                         Be precise — list topics such as:
                         "official documentation", "performance benchmarks",
                         "limitations", "comparison with alternatives",
                         "use cases", "architecture details".
5. reason       : One-sentence overall justification for the score.
"""



# Report Prompt


REPORT_PROMPT = """
Generate a professional report using the following analysis.

Tool:
{tool_name}

Analysis:

{analysis}

Return exactly in this format. Fill every section with real content.

# AI Tool Research Report: {tool_name}

## Table of Contents

1. Overview
2. Main Features
3. How It Works
4. Common Use Cases
5. Advantages
6. Limitations
7. Final Recommendation
8. References

---

## 1. Overview

## 2. Main Features

## 3. How It Works

## 4. Common Use Cases

## 5. Advantages

## 6. Limitations

## 7. Final Recommendation

The recommendation should explain who should use this tool and when.
"""
