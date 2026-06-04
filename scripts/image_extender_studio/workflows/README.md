# workflows 模块

`workflows` 保存面向业务的确定性流程。每个文件对应一个 Skill 子流程或一组紧密相关的后处理步骤。

## 包含文件

- `extender.py`：扩图画布准备、扩展结果融合、颜色预校正、羽化/近似梯度域融合和接缝评分。
- `tileset.py`：autotile guide 绘制、生成图切片、色键、body tileable 修正、角块调和、atlas extrude 和打包。
- `sprite.py`：pose guide、sprite sheet 切片、残边清理、主体 bbox、baseline/anchor 对齐、grid/strip 和 zip 导出。
- `props.py`：props sheet 切片、色键、稳定命名、atlas、manifest 和 zip 导出。
- `parallax.py`：四层 parallax manifest、图层色键、路径更新、自动扩图计划和打包。

## 修改规则

- 新增工作流文件时同步更新本 README、`scripts/image_extender_studio/README.md`、`SKILL.md` 和 `references/feature-map.md`。
- 工作流函数应返回 manifest 风格的 dict，CLI 层负责写出 JSON。
- 不要在 workflow 中直接拼 provider 请求体；图片或文本模型调用交给 `providers/`。

