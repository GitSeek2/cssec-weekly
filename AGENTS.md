# CSSEC Weekly — 仓库层工作流约定

本文件记录仓库层面的项目结构与 GitHub 发布（发刊）工作流。**报刊内容的撰写流程见 `skills/cssec-weekly/SKILL.md`**（内容创作），本文件只管项目 / GitHub 侧。

## 仓库结构

- `skills/cssec-weekly/` —— Agent Skill：报刊内容创作（`SKILL.md` + `references/` + `scripts/` 内容脚本：fetch_all / fetch_* / format_events / issue_meta / lint / check_facts / md2html / html2pdf）
- `scripts/` —— 发刊脚本（`release_notes.py` / `append_history.py`）
- `issues/<刊号>/` —— 每期成品 + `sources/` 中间稿存档（`<刊号>` 形如 `CS26-0801-TP`）
- `HISTORY.md` —— 发刊史（逐期记录刊号 / 日期 / 头条，Release Note 数据源）
- `.github/workflows/release.yml` —— 发刊 CI
- `README.md` —— 项目说明

## 发刊（发布）工作流

内容三格式成品（`issues/<刊号>/CSSEC 周报 · 第 N 期.{md,html,pdf}`）齐全后：

1. **追加发刊史**（幂等，把本期刊号 / 发刊日期 / 头条标题记入 `HISTORY.md`）：

   ```bash
   uv run python scripts/append_history.py --dirname <刊号>
   ```

   不传 `--dirname` 时自动定位最新一期；`HISTORY.md` 已有该期条目则跳过。
2. **打刊号 tag 并推送**（tag 即期目录刊号）：

   ```bash
   git tag <刊号> && git push origin <刊号>
   ```
3. **GitHub Actions 自动发布 Release**：把该期 md / html / pdf 三份成品 + `sources/` 中间稿的整期 zip 挂到 Release，Release Note 由 `scripts/release_notes.py` 依据 `HISTORY.md` 生成。

### 发布约束

- **tag = 期目录刊号**（如 `CS26-0802-TP`），与 `issues/` 目录一一对应，无需映射。
- **Release 资产用已提交成品**，不在 CI 重建（PDF 与本地一致，CI 无需装浏览器 / 中文字体）。
- **Release 资产命名**：三份成品以刊号重命名上传（`<刊号>.md` / `.html` / `.pdf`，纯 ASCII，下载名清晰），另附整期 zip `CSSEC-Weekly-<刊号>.zip`（含 `sources/`）。
- `HISTORY.md` 缺该期条目时发刊 CI 会失败并提示 —— 先跑 `append_history.py` 再打 tag。

## HISTORY.md 格式

每期一个 `## 第 N 期（YYYY-MM-DD 发刊）` 小节，含 `- 刊号：` 与 `- 头条：` 两行（由 `append_history.py` 统一追加，保证与期 md 一致）：

```markdown
## 第 1 期（2026-08-09 发刊）
- 刊号：CS26-0801-TP
- 头条：AI 安全测试失控，三巨头接连越界
```

## 发刊脚本说明

- `scripts/release_notes.py` —— 从 `HISTORY.md` 生成某期 Release Note。`--dirname <刊号>` 必填；`--issue-only` 只打期号数字（供 workflow 拼 Release 标题）。
- `scripts/append_history.py` —— 从期 md 提取 `刊号：` / `发刊：` / `## 本期主题：` 冒号后文本作为头条，幂等追加进 `HISTORY.md`。

脚本均为 Python 标准库，本地用 `uv run python` 运行（本机 Python 由 uv 管理）；GitHub ubuntu runner 用内置 `python3`。
