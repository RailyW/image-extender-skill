# Workflow: Props

Priority: High.

Use this workflow for transparent prop libraries.

Use this workflow for standalone decoration sprites.

Do not generate characters in this workflow.

Good:

```text
Generate eight standalone props.
Process the sheet.
Package the atlas.
```

Bad:

```text
Generate a scene with a character and props.
```

## Inputs

Priority: High.

Collect these inputs.

- World or biome prompt.
- Optional art style.
- Optional scene brief.
- Optional existing prop categories.
- Desired prop count.

Good:

```text
Use `glowing cave`.
Exclude existing `mushroom`.
```

Bad:

```text
Request eight copies of the same crate.
```

## Standard Flow

Priority: High.

1. Run `props ideas`.
2. Run `prompt generate --mode props`.
3. Generate a 4 by 2 prop sheet.
4. Run `props process`.
5. Run `props package`.

Good:

```bash
python scripts/image_extender_skill.py props ideas --prompt "glowing cave" --count 8 --output ideas.json
python scripts/image_extender_skill.py prompt generate --mode props --prompt "glowing cave" --ideas ideas.json --output props-prompt.txt
python scripts/image_extender_skill.py props process --sheet generated.png --ideas ideas.json --output-dir props
python scripts/image_extender_skill.py props package --input-dir props --output props.zip
```

Bad:

```bash
python scripts/image_extender_skill.py props package --input-dir props --output props.zip
```

## Prop Rules

Priority: High.

Keep one prop per cell.

Use pure `#FF00FF` as the removable background.

Avoid labels.

Avoid shadows.

Avoid complete scenes.

Good:

```text
Cell 1 contains one lantern.
Cell 2 contains one crystal cluster.
```

Bad:

```text
Cell 1 contains a full cave scene with text labels.
```

## Acceptance

Priority: High.

Check these outputs.

- Individual prop PNG files exist.
- `props-atlas.png` exists.
- `manifest.json` exists.
- The ZIP includes the atlas and manifest.

Good:

```text
Return `props.zip`.
List the prop names.
```

Bad:

```text
Return only the raw sheet.
```
