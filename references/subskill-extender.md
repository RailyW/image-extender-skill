# 子流程：Extender 扩图

## 输入

- 原图文件。
- 扩展方向：`up`、`down`、`left`、`right`。
- 扩展比例或像素数。
- 可选自定义 prompt、art style、provider 配置。

## 标准流程

1. 调用 `extend prepare` 生成带 `#B0B0B0` 空白区域的扩展画布。
2. 调用 `prompt extend` 生成稳定扩图 prompt。
3. 如果使用 HTTP provider，调用 `extend call`；如果使用 Codex App imagegen，调用 `$imagegen`。
4. 调用 `extend apply-result` 把生成结果融合回原图，默认使用 `poisson`，速度优先可用 `feather`。
5. 如果需要 Best-of-N，调用 `extend batch`，根据 seam score 选择候选。

## 关键命令

```bash
python scripts/image_extender_skill.py extend prepare --input base.png --direction right --amount 512 --output expanded.png
python scripts/image_extender_skill.py prompt extend --input expanded.png --direction right --amount 512 --prompt "continue the forest" --output prompt.txt
python scripts/image_extender_skill.py extend apply-result --original base.png --generated generated.png --direction right --amount 512 --output final.png
```

## 验收

- 输出尺寸等于原图加扩展区域。
- 新区域不残留 `#B0B0B0`。
- 接缝评分写入 manifest。
