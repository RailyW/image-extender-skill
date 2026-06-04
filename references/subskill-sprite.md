# Workflow: Sprite Animation

Priority: High.

Use this workflow for sprite sheets.

Use this workflow for character animation strips.

Do not hand-align frames in the model response.

Good:

```text
Generate the sheet.
Run `sprite process`.
Run `sprite package`.
```

Bad:

```text
Tell the user to align each frame manually.
```

## Inputs

Priority: High.

Collect these inputs.

- Character prompt.
- Body plan.
- Animation name.
- Optional art style.
- Optional QA fix notes.

Use one body plan.

- `biped`
- `quadruped`
- `serpent`
- `flyer`
- `blob`

Good:

```text
Use `quadruped` and `run`.
```

Bad:

```text
Use `dragon-centaur` as a body plan.
```

## Standard Flow

Priority: High.

1. Run `prompt generate --mode sprite-anchor`.
2. Generate one anchor image.
3. Run `sprite guide`.
4. Run `prompt generate --mode sprite-sheet`.
5. Generate a 4 by 2 sprite sheet.
6. Run `sprite process`.
7. Run `sprite package`.
8. Run review when a vision provider is available.

Good:

```bash
python scripts/image_extender_skill.py sprite guide --body-plan quadruped --anim run --output pose-guide.png
python scripts/image_extender_skill.py prompt generate --mode sprite-sheet --body-plan quadruped --anim run --prompt "armored wolf" --output sprite-prompt.txt
python scripts/image_extender_skill.py sprite process --sheet generated.png --body-plan quadruped --anim run --output-dir sprite
python scripts/image_extender_skill.py sprite package --input-dir sprite --output sprite.zip
```

Bad:

```bash
python scripts/image_extender_skill.py sprite process --sheet generated.png --body-plan quadruped --anim fly --output-dir sprite
```

## Alignment Rules

Priority: High.

Use stable alignment defaults.

```bash
python scripts/image_extender_skill.py sprite process \
  --sheet generated.png \
  --body-plan biped \
  --anim idle \
  --output-dir sprite \
  --vertical-anchor baseline \
  --horizontal-anchor upper-q75
```

Use `--vertical-anchor baseline` for grounded animations.

Use `--vertical-anchor none` for animations that must keep vertical motion.

Use `--horizontal-anchor upper-q75` for most right-facing characters.

Use `--horizontal-anchor bbox-center` only when the outline is stable.

Use `--alpha-floor 24` to remove weak alpha residue.

Good:

```text
Check `alignment.frames` in `manifest.json`.
Confirm stable `aligned_baseline`.
```

Bad:

```text
Ignore a moving baseline in a walk cycle.
```

## Acceptance

Priority: High.

Check these outputs.

- Eight frame PNG files exist.
- `sprite-grid.png` exists.
- `sprite-strip.png` exists.
- `manifest.json` exists.
- Grounded animations keep a stable aligned baseline.

Good:

```text
Return the ZIP path.
Report the frame size and FPS.
```

Bad:

```text
Return only a raw generated sheet.
```
