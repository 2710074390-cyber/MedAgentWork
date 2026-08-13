---
name: handoff
description: Compact the current conversation into a handoff document for another agent to pick up. Use when the task needs to be passed to another agent, when the conversation context is too large, or when the user mentions "handoff", "交接", "pass to agent", or "delegate".
---

# Handoff Protocol

Compact the current conversation into a structured handoff document that another agent can pick up and execute independently — without needing the full conversation history.

## When to Trigger

- User says "handoff", "交接", "pass this to X", "delegate"
- Context window is approaching limits and the task spans multiple agents
- Complex multi-agent workflows where one agent prepares and another executes

## Handoff Document Structure

Generate a markdown document with these sections:

### 1. Task Summary
- One paragraph: what needs to be done
- Who is the target agent (PPT / web-med / 黑曜石 / etc.)

### 2. Key Decisions
- Bullet list of decisions made so far
- Rationale for each (why, not just what)

### 3. Constraints
- Hard constraints the receiving agent MUST follow
- Technical boundaries (file paths, API limits, format requirements)

### 4. Artifacts
- Reference external files by path — do NOT inline large content
- Format: `[type] path/to/file` (e.g. `[outline] ppt-output/runs/RUN001/outline.txt`)

### 5. Suggested Skills
- Which skills the receiving agent should load
- Rationale for each recommendation

### 6. Success Criteria
- Observable, verifiable conditions for "done"
- No vague "make it good" — be specific

## Rules

- **Compress, don't repeat.** Reference external files by path. If a file already exists on disk, link to it.
- **Redact sensitive info.** API keys, passwords, tokens → never in handoff.
- **Save to `handoffs/` directory** with format: `handoff-{TARGET_AGENT}-{DATE}.md`
- **Validate before sending.** Check: are all referenced paths valid? Is the target agent clearly identified? Are constraints unambiguous?

## Example

```markdown
# Handoff: Q3 销售数据 PPT → Agent-PPT
Date: 2026-06-18
Target: Agent-PPT

## Task Summary
Generate a 10-slide PPTX for Q3 2026 销售数据分析. Content research and outline completed by CherryClaw.

## Key Decisions
- 16:9 canvas, dark theme (slate blue #2C3E50 primary)
- 10 slides: 封面 → 3x 数据 → 2x 分析 → 2x 竞品 → 总结
- Data charts use matplotlib pre-rendered PNGs (not python-pptx charts)

## Constraints
- NEVER use HTML/CSS concepts — python-pptx MSO_SHAPE only
- NEVER use pixels — Inches/Emu/Pt exclusively
- Fonts: Arial + Microsoft YaHei only

## Artifacts
- [outline] ppt-output/runs/RUN042/outline.txt
- [search-brief] ppt-output/runs/RUN042/search-brief.txt
- [style] ppt-output/runs/RUN042/style.json
- [charts] ppt-output/runs/RUN042/charts/*.png

## Suggested Skills
- ppt-agent-skills: PPT generation pipeline
- code-review: Audit generated python-pptx code
- caveman: Control token usage during batch generation

## Success Criteria
- [ ] All 10 slides generated with zero Gate failures
- [ ] Visual QA score ≥ 90/100
- [ ] .pptx opens in PowerPoint without repair prompt
```
