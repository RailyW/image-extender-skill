# 子流程：Tileset 自动瓦片

## 输入

- 材质 prompt。
- 可选 scene brief、art style、tile fix notes。

## 标准流程

1. 调用 `tileset guide` 生成 8×8 结构参考图。
2. 调用 `prompt generate --mode tileset` 生成图生图 prompt。
3. 用 HTTP provider 或 Codex App `imagegen` 生成 restyled guide。
4. 调用 `tileset extract` 从固定采样格切出 13 个角色。
5. 调用 `tileset reconcile` 调和角块和边缘。
6. 调用 `tileset package` 生成带 2px extrude 的 atlas、单块 PNG 和 manifest。
7. 如果启用 vision QA，调用 `prompt review --kind tile` 与 `review call`，失败时把 fix notes 传回第 2 步。

## 关键命令

```bash
python3 scripts/image_extender_skill.py tileset guide --output tile-guide.png
python3 scripts/image_extender_skill.py prompt generate --mode tileset --prompt "mossy stone with small roots" --output tile-prompt.txt
python3 scripts/image_extender_skill.py tileset extract --sheet generated.png --output-dir tileset
python3 scripts/image_extender_skill.py tileset package --input-dir tileset --output tileset.zip
```

## 验收

- 13 个角色文件齐全。
- atlas 有 4×4 布局和 2px extrude。
- manifest 记录 role、文件名、坐标、tile size。
