# Workflow: Tileset

Priority: High.

Use this workflow for 2D platformer autotiles.

Do not crop autotiles manually.

Use the guide image.

Good:

```text
Generate a guide.
Restyle the guide.
Extract tiles with the runner.
```

Bad:

```text
Ask the model to describe tile coordinates.
```

## Inputs

Priority: High.

Collect these inputs.

- Material prompt.
- Optional art style.
- Optional scene brief.
- Optional QA fix notes.

Good:

```text
Use `mossy stone with roots` as the material prompt.
```

Bad:

```text
Use a vague prompt such as `nice tiles`.
```

## Standard Flow

Priority: High.

1. Run `tileset guide`.
2. Run `prompt generate --mode tileset`.
3. Generate or edit the guide image.
4. Run `tileset extract`.
5. Run `tileset reconcile`.
6. Run `tileset package`.
7. Run review when a vision provider is available.

Good:

```bash
python scripts/image_extender_skill.py tileset guide --output tile-guide.png
python scripts/image_extender_skill.py prompt generate --mode tileset --prompt "mossy stone with small roots" --output tile-prompt.txt
python scripts/image_extender_skill.py tileset extract --sheet generated.png --output-dir tileset
python scripts/image_extender_skill.py tileset package --input-dir tileset --output tileset.zip
```

Bad:

```bash
python scripts/image_extender_skill.py tileset package --input-dir empty --output tileset.zip
```

## Tile Rules

Priority: High.

Keep the guide silhouette.

Keep pure `#FF00FF` for transparent regions.

Avoid pink material colors.

Make the body tile repeatable.

Good:

```text
Use gray guide pixels as material.
Preserve magenta pixels for keying.
```

Bad:

```text
Paint magenta flowers inside the material.
```

## Acceptance

Priority: High.

Check these outputs.

- Tile PNG files exist.
- `tileset.json` exists.
- `manifest.json` exists.
- `tileset-atlas.png` exists.
- The ZIP includes the atlas and manifest.

Good:

```text
Return `tileset.zip`.
List the atlas path.
```

Bad:

```text
Return only the generated sheet.
```
