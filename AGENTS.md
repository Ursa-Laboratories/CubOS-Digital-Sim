# Repository Guidelines

## Working Standard

- Write code in a clean, organized way and favor simple, readable designs.
- Apply Clean Code principles: small focused units, clear naming, low duplication, and explicit responsibilities.
- Use test-driven development by default. Decide on the design, identify the tests needed, write tests first, then implement code.
- Run relevant tests as work progresses instead of batching verification until the end.

## Planning

- When operating in planning mode, create a plan for user review before execution.
- In planning mode, ask follow-up questions when needed to confirm scope, constraints, and expected outcomes before locking the plan.

## Progress Logs

- Maintain a dated Markdown log in `progress/` for every chat that changes or analyzes the repo.
- Create `progress/` if it does not exist.
- Append to the current date's file rather than creating multiple files for the same day unless the user asks otherwise.
- Record:
  - work completed
  - issues found
  - how issues were resolved
  - important decisions, assumptions, and follow-up items

## Documentation Expectations

- If a task introduces a fundamental workflow or product change, update both `AGENTS.md` and the relevant `README.md` files so later agents and humans have the necessary context.
- Keep documentation concise and operational. Prefer guidance that helps the next person act quickly.

## Cleanup

- Remove temporary files, one-off diagnostics, throwaway scripts, and planning artifacts that are no longer needed.
- Do not leave behind ad hoc verification files such as connectivity probes or scratch scripts unless they are intentionally part of the codebase.

## Safety

- Do not revert or delete user changes unless the user explicitly asks for it.
- Before removing files, confirm they are truly temporary or obsolete for the repository.
