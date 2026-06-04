# 功能覆盖映射

下表把原 Web app 功能映射到 Skill 子流程和 Python 脚本入口，用于完成前后的覆盖审计。

| 原功能 | Skill 覆盖 | 固定脚本入口 |
| --- | --- | --- |
| Extender 图片扩图 | `subskill-extender.md` | `extend prepare`、`prompt extend`、`extend call`、`extend apply-result` |
| Best-of-N 候选 | Extender 子流程 | `extend batch` 生成候选 manifest |
| Poisson / 羽化接缝融合 | Extender 子流程 | `extend apply-result --blend poisson|feather` |
| 低频颜色漂移预校正 | Extender 子流程 | `extend apply-result` |
| 从文本生成起始图 | Extender / 任意子流程 | `prompt generate`、`image call` |
| Parallax 四层生成 | Parallax 子流程 | `parallax init`、`prompt generate --mode parallax` |
| Parallax 色键透明 | Parallax 子流程 | `parallax key-layer` |
| Parallax 自动扩宽 | Parallax 子流程 | `parallax auto-plan`、`extend batch` |
| Parallax tileable / harmonize | Parallax 子流程 | `parallax tileable`、`parallax harmonize` |
| Parallax ZIP + manifest | Parallax 子流程 | `parallax package` |
| Tile 结构 guide | Tileset 子流程 | `tileset guide` |
| Tile 4×4 生成 prompt | Tileset 子流程 | `prompt generate --mode tileset` |
| Tile 切片、色键、body tileable | Tileset 子流程 | `tileset extract` |
| Tile 角块调和 | Tileset 子流程 | `tileset reconcile` |
| Tile atlas extrude 导出 | Tileset 子流程 | `tileset package` |
| Tile vision QA | Tileset 子流程 | `prompt review --kind tile`、`review call` |
| Sprite anchor → sheet | Sprite 子流程 | `prompt generate --mode sprite-anchor|sprite-sheet` |
| Sprite pose guide | Sprite 子流程 | `sprite guide` |
| Sprite 色键、单帧切片 | Sprite 子流程 | `sprite process` |
| Sprite 低 alpha 残边清理 | Sprite 子流程 | `sprite process --alpha-floor` |
| Sprite 脚底 baseline 固定 | Sprite 子流程 | `sprite process --vertical-anchor baseline` |
| Sprite 水平上身锚点稳定 | Sprite 子流程 | `sprite process --horizontal-anchor upper-q75` |
| Sprite scale / baseline / center | Sprite 子流程 | `sprite process` |
| Sprite strip / grid / ZIP manifest | Sprite 子流程 | `sprite package` |
| Sprite review | Sprite 子流程 | `prompt review --kind sprite`、`review call` |
| Props art director | Props 子流程 | `props ideas` |
| Props 8 格生成 prompt | Props 子流程 | `prompt generate --mode props` |
| Props 切片、色键、命名 | Props 子流程 | `props process` |
| Props atlas / ZIP manifest | Props 子流程 | `props package` |
| BYOK / 自定义 provider | 全部子流程 | `providers validate`、`image call`、`text call`、`review call` |
| Codex App imagegen | 全部图像生成子流程 | `prompt ... --emit codex` 后调用 `$imagegen` |
| 工程化结构审计 | 全部子流程 | `audit coverage` |

审计命令：

```bash
python scripts/image_extender_skill.py audit coverage --root .
```
