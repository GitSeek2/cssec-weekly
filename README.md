# CSSEC Weekly

CSSEC 网安周报，一个由 Agent Skill 驱动的安全周刊。

## 结构

- `skills/cssec-weekly/` —— SKILL 定义（`SKILL.md` + `references/` + `scripts/`）
- `issues/` —— 每期成品 + 中间文档存档（仓库根）
- `HISTORY.md` —— 发刊史（逐期记录刊号 / 日期 / 头条，Release Note 数据源）
- `.github/workflows/release.yml` —— 发刊 CI：打上刊号 tag 后自动发布 GitHub Releases

## 存档

每期成品（`CSSEC 周报 · 第 N 期.md` + 自包含 HTML `.html` + PDF `.pdf`）归档于 `issues/CSYY-MMWW-TP/`（`CS`=CSSEC 前缀，`YYMMWW`=发刊年 / 月 / 当月第几周，`TP`=中图分类）+ 中间文档。

打上刊号 tag（如 `CS26-0801-TP`）并推送后，GitHub Actions 自动把该期 md / html / pdf 与 `sources/` 中间稿发布为 [GitHub Releases](https://github.com/GitSeek2/cssec-weekly/releases)，Release Note 取自 `HISTORY.md`。发布前先用 `skills/cssec-weekly/scripts/append_history.py` 追加本期发刊史条目（详见 `skills/cssec-weekly/SKILL.md` 步骤 7）。

## 致谢

以下信息源为本刊提供了持续、高质量的报道，在此致谢：

- [安全内参](https://www.secrss.com/)（奇安信）—— 主内容来源，七年未断更
- [The Hacker News](https://thehackernews.com/) —— 国际事件流主力
- [BleepingComputer](https://www.bleepingcomputer.com/) —— 深度报道与一手链接
- [Krebs on Security](https://krebsonsecurity.com/) —— 独家深度调查
- [Dark Reading](https://www.darkreading.com/) —— 企业安全视角
- [Schneier on Security](https://www.schneier.com/) —— 安全趋势与隐私分析
- [Hello-CTFtime](https://github.com/ProbiusOfficial/Hello-CTFtime) —— 国内外 CTF 赛事信息
- 相关监管机构与漏洞共享平台

## 许可

[MIT](LICENSE)
