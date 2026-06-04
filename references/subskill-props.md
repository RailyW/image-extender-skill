# 子流程：Props 装饰库

## 输入

- 生态环境 / 世界 prompt。
- 已有 prop 分类列表。
- 可选 scene brief、art style、已有 props 风格参考图。

## 标准流程

1. 调用 `props ideas` 或 `prompt prop-ideas` 获取下一批道具创意。
2. 调用 `prompt generate --mode props` 生成 4×2 props sheet prompt。
3. 用 provider 或 Codex App `imagegen` 生成 props sheet。
4. 调用 `props process` 切出 8 个透明 prop，并用 art director 名称命名。
5. 调用 `props package` 追加或导出 atlas、单个 PNG、manifest。

## 关键命令

```bash
python3 scripts/image_extender_skill.py props ideas --prompt "glowing cave" --count 8 --output ideas.json
python3 scripts/image_extender_skill.py prompt generate --mode props --prompt "glowing cave" --ideas ideas.json --output props-prompt.txt
python3 scripts/image_extender_skill.py props process --sheet generated.png --ideas ideas.json --output-dir props
python3 scripts/image_extender_skill.py props package --input-dir props --output props.zip
```

## 验收

- 每批最多 8 个透明 prop。
- manifest 记录可读名称、文件名、atlas 坐标。
- 追加批次时不能覆盖已有 prop。
