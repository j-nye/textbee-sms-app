# Delegation

You orchestrate: plan, decide, integrate, verify. Hand off work a cheaper model can do, or that would fill
your context with output you don't need to keep.

| Work | Subagent |
|---|---|
| Finding code, tracing how something works | `Explore` (Haiku) |
| Running tests, linters, builds | `test-runner` (Haiku): returns failures only |
| Boilerplate, fixtures, test scaffolding, docstrings, doc drafts | `scaffolder` (Haiku) |
| Implementing an agreed plan across files | `implementer` (Sonnet) |
| Reviewing a non-trivial diff before calling it done | `reviewer` (Opus) |

- Do it yourself when the change is small (under ~30 lines), needs context from this conversation you'd have
  to restate at length, or you'd have to read the result in full anyway. Subagents start cold, so tiny
  hand-offs cost more than they save.
- Brief each subagent fully: goal, relevant files, constraints, how to verify, and the short report you want.
  Name known pitfalls directly (a rounding rule, an in-place-mutation risk, a same-name collision) rather
  than assuming they'll be spotted unprompted.
- Never let a subagent's report substitute for running the result. A report that a test file "looks right"
  or "should work" isn't verification — run it. Reviewing generated code (especially tests) is exactly
  where a wrong computed value or a comment that doesn't match the actual behavior slips through unnoticed.
- Run independent subagents in parallel. Don't re-read files a subagent summarized unless you must edit them.
- This project runs `opusplan`: use plan mode for multi-file work so Opus plans and Sonnet executes.
