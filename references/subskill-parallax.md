# Workflow: Parallax Background

Priority: High.

Use this workflow for side-view parallax backgrounds.

Build four layers.

Do not merge all layers into one image.

Good:

```text
Create `near`, `mid`, `far`, and `sky`.
Package the manifest.
```

Bad:

```text
Generate one flat background and stop.
```

## Inputs

Priority: High.

Collect these inputs.

- World prompt.
- Optional art style.
- Target width.
- Layer roles: `near`, `mid`, `far`, and `sky`.

Good:

```text
Use `near` as the first visual anchor.
```

Bad:

```text
Skip the shared scene brief.
```

## Standard Flow

Priority: High.

1. Run `parallax init`.
2. Generate a shared scene brief.
3. Generate layer prompts in this order: `near`, `mid`, `far`, `sky`.
4. Run `parallax key-layer` for non-sky layers.
5. Run `parallax auto-plan` when more width is needed.
6. Use the Extender workflow for planned extensions.
7. Run `parallax tileable`.
8. Run `parallax harmonize`.
9. Run `parallax package`.

Good:

```bash
python scripts/image_extender_skill.py parallax init --output parallax.json
python scripts/image_extender_skill.py prompt generate --mode parallax --layer near --prompt "crystal forest" --scene-brief brief.txt --output near-prompt.txt
python scripts/image_extender_skill.py parallax key-layer --input near-raw.png --role near --output near.png
python scripts/image_extender_skill.py parallax package --manifest parallax.json --output parallax.zip
```

Bad:

```bash
python scripts/image_extender_skill.py parallax package --manifest missing.json --output parallax.zip
```

## Layer Rules

Priority: High.

Keep `sky` opaque.

Key `far`, `mid`, and `near`.

Use pure `#FF00FF` as the removable background for non-sky layers.

Good:

```text
Run `parallax key-layer` for `near`.
Do not run it for `sky`.
```

Bad:

```text
Make the sky transparent.
```

## Acceptance

Priority: High.

Check these outputs.

- `sky` is opaque.
- `far`, `mid`, and `near` have transparent backgrounds.
- The ZIP includes generated layers.
- The ZIP includes `parallax.json`.

Good:

```text
Return `parallax.zip` and `parallax.json`.
```

Bad:

```text
Return only one layer image.
```
