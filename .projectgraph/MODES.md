# Modes

| Mode | Phases | Gates | Agents active |
|---|---|---|---|
| mvp | Discover → Build → Verify | Release | Maya, Forge, Sentinel |
| research | Discover → Validate | None | Maya, Nova |
| ai-rag | Discover → Validate → Design → Build → Verify | Design + Release | Maya, Nova, Atlas, Forge, Sentinel |
| saas | Discover → Validate → Design → Build → Verify | Design + Release | Maya, Nova, Atlas, Forge, Sentinel |
| repo-rescue | Design → Build → Verify | Recovery plan | Atlas, Forge, Sentinel |

## Notes
- This file is reference only. Agents do not load it during normal execution.
- Maya selects the mode; the human may confirm or override.
- Mode changes are made only by editing `Mode:` in `.projectgraph/CONTEXT.md`.

