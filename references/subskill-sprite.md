# 子流程：Sprite 动画

## 输入

- 角色 / 生物 prompt。
- 体型方案：`biped`、`quadruped`、`serpent`、`flyer`、`blob`。
- 动画：按体型选择，例如 `walk`、`run`、`slither`、`flap`、`hop`。

## 标准流程

1. 调用 `prompt generate --mode sprite-anchor` 生成 anchor prompt。
2. 用 provider 或 Codex App `imagegen` 生成单角色 anchor。
3. 调用 `sprite guide` 生成 4×2 pose guide。
4. 调用 `prompt generate --mode sprite-sheet` 生成 sheet prompt，并引用 anchor / pose guide。
5. 用 provider 或 Codex App `imagegen` 生成 4×2 sprite sheet。
6. 调用 `sprite process` 执行色键、切片、低 alpha 残边清理、鲁棒主体 bbox、脚底 baseline 对齐、水平上身锚点稳定和 grid/strip 导出。
7. 调用 `sprite package` 导出 grid、strip、单帧 PNG 和 manifest。
8. 如果启用 vision QA，调用 `prompt review --kind sprite` 与 `review call`。

## 关键命令

```bash
python3 scripts/image_extender_skill.py sprite guide --body-plan quadruped --anim run --output pose-guide.png
python3 scripts/image_extender_skill.py prompt generate --mode sprite-sheet --body-plan quadruped --anim run --prompt "armored wolf" --output sprite-prompt.txt
python3 scripts/image_extender_skill.py sprite process --sheet generated.png --body-plan quadruped --anim run --output-dir sprite
python3 scripts/image_extender_skill.py sprite package --input-dir sprite --output sprite.zip
```

## 对齐参数

`sprite process` 默认使用稳定版参数：

```bash
python3 scripts/image_extender_skill.py sprite process \
  --sheet generated.png \
  --body-plan biped \
  --anim idle \
  --output-dir sprite \
  --vertical-anchor baseline \
  --horizontal-anchor upper-q75
```

- `--vertical-anchor baseline`：用高 alpha 主体 bbox 的底边固定脚底；跳跃、飞行等需要保留垂直位移时可设为 `none`。
- `--horizontal-anchor upper-q75`：用上身像素的 75% 分位数作为水平锚点，适合多数朝右的 JRPG/平台动作角色，可减少披风、头发、裙摆、武器外摆造成的左右抖动。
- `--horizontal-anchor bbox-center`：兼容旧版整体 bbox 居中，仅在外轮廓稳定时使用。
- `--alpha-floor 24`：清理透明底图中的低 alpha 残边，避免残边被误判为脚底。
- `manifest.json` 的 `alignment.frames` 会记录每帧的 `bbox`、`baseline`、`anchor_x`、`dx`、`dy`、`aligned_baseline` 和 `aligned_anchor_x`，用于检查抖动是否来自切图坐标还是源图内部绘制不一致。

## 验收

- 8 帧 PNG 齐全。
- grid sheet、horizontal strip、manifest 齐全。
- manifest 包含 FPS、loop、frame size 和坐标。
- 对 grounded 动画，`alignment.frames[*].aligned_baseline` 应保持一致。
- 对需要稳定站位的角色，`alignment.frames[*].aligned_anchor_x` 应基本一致；若仍有脸、头发、披风内部形变，只能通过重新生成或像素修图解决。
