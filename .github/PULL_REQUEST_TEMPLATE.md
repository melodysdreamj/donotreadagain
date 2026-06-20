## What & why

Briefly: what does this change, and why?

## Checklist

- [ ] Tests added/updated and `pytest` is green locally
- [ ] No new hard model dependency in the core (dnr owns no model)
- [ ] If a new carrier: `content_hash` is invariant under embed + re-embed is byte-stable (round-trip test added)
- [ ] If agent-facing behavior changed: regenerated `SKILL.md` (`dnr skill > SKILL.md`)
- [ ] Doesn't make dnr *infer* metadata (dates/parties/topics) or do fuzzy/semantic search — that stays the agent's job
- [ ] Docs updated if needed (README / spec / qna)

## Notes

Link any relevant `qna.md` decision or spec section. Call out anything that rubs against a design principle.
