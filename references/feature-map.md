# Feature Coverage Map

Priority: High.

Use this file for coverage audits.

Check that each original workflow has a skill path.

Check that each fixed step has a runner command.

Good:

```text
Run `python scripts/image_extender_skill.py audit coverage --root .`.
Compare missing entries before reporting completion.
```

Bad:

```text
Assume coverage is complete without running the audit.
```

## Coverage Table

Priority: High.

Use this table as the source of expected workflow coverage.

| Original feature | Skill coverage | Fixed runner entry |
| --- | --- | --- |
| Extender outpainting | `subskill-extender.md` | `extend prepare`, `prompt extend`, `extend call`, `extend apply-result` |
| Best-of-N candidates | Extender workflow | `extend batch` |
| Poisson or feather seam blending | Extender workflow | `extend apply-result --blend poisson|feather` |
| Low-frequency color correction | Extender workflow | `extend apply-result` |
| Text-to-starting-image | Any image workflow | `prompt generate`, `image call` |
| Four parallax layers | Parallax workflow | `parallax init`, `prompt generate --mode parallax` |
| Parallax chroma key | Parallax workflow | `parallax key-layer` |
| Parallax auto widen | Parallax workflow | `parallax auto-plan`, `extend batch` |
| Parallax repeat and harmonize | Parallax workflow | `parallax tileable`, `parallax harmonize` |
| Parallax ZIP and manifest | Parallax workflow | `parallax package` |
| Tile structure guide | Tileset workflow | `tileset guide` |
| Tile 4 by 4 prompt | Tileset workflow | `prompt generate --mode tileset` |
| Tile slicing and keying | Tileset workflow | `tileset extract` |
| Tile corner reconciliation | Tileset workflow | `tileset reconcile` |
| Tile atlas extrude | Tileset workflow | `tileset package` |
| Tile vision QA | Tileset workflow | `prompt review --kind tile`, `review call` |
| Sprite anchor image | Sprite workflow | `prompt generate --mode sprite-anchor` |
| Sprite sheet prompt | Sprite workflow | `prompt generate --mode sprite-sheet` |
| Sprite pose guide | Sprite workflow | `sprite guide` |
| Sprite slicing and keying | Sprite workflow | `sprite process` |
| Sprite low alpha cleanup | Sprite workflow | `sprite process --alpha-floor` |
| Sprite baseline alignment | Sprite workflow | `sprite process --vertical-anchor baseline` |
| Sprite upper-body anchor | Sprite workflow | `sprite process --horizontal-anchor upper-q75` |
| Sprite grid and strip | Sprite workflow | `sprite process` |
| Sprite ZIP manifest | Sprite workflow | `sprite package` |
| Sprite review | Sprite workflow | `prompt review --kind sprite`, `review call` |
| Props art direction | Props workflow | `props ideas` |
| Props 8-cell prompt | Props workflow | `prompt generate --mode props` |
| Props slicing and keying | Props workflow | `props process` |
| Props atlas and ZIP | Props workflow | `props package` |
| BYOK providers | All workflows | `providers validate`, `image call`, `text call`, `review call` |
| Codex App imagegen | All image workflows | `prompt ... --emit codex`, then `$imagegen` |
| Structure audit | All workflows | `audit coverage` |

Good:

```text
When adding a new workflow, add a row here.
Add a runner entry for each deterministic step.
```

Bad:

```text
Add a new command without updating this table.
```

## Audit Command

Priority: High.

Run this command from the skill root.

```bash
python scripts/image_extender_skill.py audit coverage --root .
```

Good:

```text
Report `ok: true`.
Report missing files when `ok` is false.
```

Bad:

```text
Hide missing coverage from the user.
```
