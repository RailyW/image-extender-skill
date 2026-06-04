# 子流程：Parallax 视差背景

## 输入

- 世界 / 场景 prompt。
- 可选 art style。
- 目标宽度。
- 四层：`near`、`mid`、`far`、`sky`。

## 标准流程

1. 调用 `parallax init` 创建四层 manifest。
2. 用 `text call` 或 `prompt scene-brief` 生成共享 scene brief。
3. 按 `near → mid → far → sky` 生成图层 prompt。
4. 非 sky 图层调用 `parallax key-layer` 进行洋红色透明化。
5. 需要更宽时调用 `parallax auto-plan` 规划多次横向扩图，再用 Extender 子流程执行。
6. 调用 `parallax tileable` 修复水平循环点。
7. 调用 `parallax harmonize` 平滑多次扩展造成的面板色漂。
8. 调用 `parallax package` 导出 ZIP 和 `parallax.json`。

## 关键命令

```bash
python3 scripts/image_extender_skill.py parallax init --output parallax.json
python3 scripts/image_extender_skill.py prompt generate --mode parallax --layer near --prompt "crystal forest" --scene-brief brief.txt --output near-prompt.txt
python3 scripts/image_extender_skill.py parallax key-layer --input near-raw.png --role near --output near.png
python3 scripts/image_extender_skill.py parallax package --manifest parallax.json --output parallax.zip
```

## 验收

- `sky` 保持不透明。
- `far` / `mid` / `near` 透明背景来自色键处理。
- ZIP 包含所有已生成图层和 `parallax.json`。
