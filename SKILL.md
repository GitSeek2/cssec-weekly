---
name: cssec-weekly
description: 撰写《CSSEC 周报》。当用户说"写周报/CSSEC周报/本周安全动态/该发刊了"等时触发。自动抓取网络安全信息源（覆盖时间范围在步骤 0 与用户确认，默认近 10 天），给出候选头条主题供用户选定，再按五大板块产出可读的 Markdown 长文并落盘存档。目标读者是大学生技术社团学生，调性：专业但有趣、可读易读优先于全面深入。文风要求：资深报刊编辑口吻，非公众号科普体（详见 references/写作风格.md）。
license: MIT
allowed-tools: [Read, Write, Edit, Glob, Grep, Bash]
metadata:
  version: 1.0.0
  author: CSSEC
compatibility: 脚本经 `uv run python` 运行（本机 Python 由 uv 管理）；境外英文源（thn/bc/krebs/darkreading/schneier）需 HTTP 代理 127.0.0.1:7897。
---
# CSSEC 周报

> 一句话原则：**内容不在多也不在精，而在于可读、易读、有用。** 当「全面/深入」与「可读/易读」冲突时，永远优先后者。

> 文风：先进入 `references/写作风格.md` 序章「写作者人设」和 Part 0「编辑思维三原则」再动笔——它教你怎么像一个编辑那样思考和改稿，既给正向写法（简讯写作法、头条写作法），也给按思维模式分类的删除清单和格式配额。**撰写前必读 Part 0+1**，交付前必须走完 Part 1 的四步改稿流程，逐项核对 Part 4 删除清单和 Part 5 配额。

## 你在做什么

每周一发刊，覆盖用户选定的时间范围（默认近 10 天）。读者是大学生技术社团学生——有技术基础、对安全感兴趣，但不都是安全方向。专业概念要用一句类比或括注解释。

成品是一篇 Markdown 长文，结构：

```
# CSSEC 周报 第 N 期（YYYY-MM-DD ~ YYYY-MM-DD）
（1~2 句本期导读）
## 本期主题（头条，1 篇深度报道，篇幅最长）
## 五大板块（按需出现，无料的板块直接省略，绝不硬凑）
  态势感知 / 漏洞情报 / 前沿技术 / 政策法规 / 赛事活动
```

---

## 流程

### 步骤 0 — 确定时间范围与期数（先做这个：与用户确认）

**在抓取任何信息前，先与用户确认本期时间范围。** 用 AskUserQuestion 分两步问：

**第一步** —— 问覆盖天数：

> 本期覆盖多长时间？7 天 / 10 天（默认）/ 14 天 / 自定义？

**第二步** —— 问对齐方式：

> 窗口对齐方式？rolling = 当天往前推 N 天（默认）；lastweek = 上周一 ~ 今天（含今天）。选 lastweek 时，窗口起点对齐到上周一，天数以对齐为准，具体跨度随发刊日浮动。

根据用户选择跑 `issue_meta.py`：

```
# rolling + 默认 10 天（最常见的默认情况）
uv run python ${CLAUDE_SKILL_DIR}/scripts/issue_meta.py

# rolling + 指定天数
uv run python ${CLAUDE_SKILL_DIR}/scripts/issue_meta.py --mode rolling --days <天数>

# lastweek（天数自动对齐）
uv run python ${CLAUDE_SKILL_DIR}/scripts/issue_meta.py --mode lastweek
```

输出 JSON：`issue`（本期期号）、`mode`（窗口来源）、`start`/`end`/`range`（时间窗）、`days`（实际跨度天数）、`filename`（建议成品**目录名**，不含 `.md` 后缀）。期号逻辑：扫 `issues/` 已有目录/文件取最大期号 +1，空则第 1 期。

**后续步骤统一用 `start`/`end` 透传给各抓取脚本**（`--start <start> --end <end>`），确保所有脚本用同一窗口。撰写时用 `issue` 和 `range` 作标题。交付时先建 `issues/<filename>/sources/`，成品写入 `issues/<filename>/周报.md`，中间文档写入 `issues/<filename>/sources/`。

**确认 Agent 工具与大模型**：从系统上下文中提取当前 Agent 工具名称和大模型名称，用 AskUserQuestion 一次性让用户确认两项：

> 检测到当前运行环境：Agent 工具 = **[检测到的工具名]**，大模型 = **[检测到的模型名]**。周报末尾的 AI 撰写说明将据此标注。确认无误？

用户确认（或修正）后，把 Agent 工具名和模型名都记录下来——步骤 4 写入 AI 撰写说明时用。

### 步骤 1 — 信息收集

依次跑这些抓取脚本（每个独立，单源失败不阻塞其他）。**可在任意目录运行（脚本路径已用 ${CLAUDE_SKILL_DIR} 绝对定位）**，用 `uv run python ${CLAUDE_SKILL_DIR}/scripts/<脚本>`（本机 Python 经 uv 管理，直接 `python` 会触发 Microsoft Store 转向器）。stdout 即为 JSON 数据（`{items:[...], errors:[...]}`）：

> **境外英文源（thn/bc/krebs/darkreading/schneier）需走代理**：运行前 `export HTTPS_PROXY=http://127.0.0.1:7897 HTTP_PROXY=http://127.0.0.1:7897`（urllib 自动识别）。这些源的 title/summary 透传英文，**撰写时再译写为中文**（套用 `references/写作风格.md` Part 2 的新闻标题与简讯规范），成品不得留英文标题原文。出处行标注英文刊名（`· BleepingComputer`/`· The Hacker News` 等），与中文源 `· 安全内参` 并列。
>
> **跨源去重（关键）**：境外源与安全内参常报道同一事件（同一 CVE/同一攻击多源都会报）。**英文源与安全内参同事件的合并为一条，优先保留英文一手链接作为出处**——这是降低单源依赖、贴近真实媒体的核心做法（详见取舍规则 5、9）。

| 脚本                                                               | 抓什么                                       |
| ------------------------------------------------------------------ | -------------------------------------------- |
| `uv run python ${CLAUDE_SKILL_DIR}/scripts/fetch_secrss.py --start <start> --end <end>`                       | 安全内参（**主内容来源**） |
| `uv run python ${CLAUDE_SKILL_DIR}/scripts/fetch_secrss.py --author 公安部网安局 --start <start> --end <end>` | 公安部网安局口径（监管/通报）                |
| `uv run python ${CLAUDE_SKILL_DIR}/scripts/fetch_ctftime_cn.py --start <start> --end <end>`                   | 国内 CTF/网安赛事                            |
| `uv run python ${CLAUDE_SKILL_DIR}/scripts/fetch_ctftime_global.py --start <start> --end <end>`               | 国际赛事                                     |
| `uv run python ${CLAUDE_SKILL_DIR}/scripts/fetch_cac.py --start <start> --end <end>`                          | 中央网信办                                   |
| `uv run python ${CLAUDE_SKILL_DIR}/scripts/fetch_miit.py --start <start> --end <end>`                         | 工信部                                       |
| `uv run python ${CLAUDE_SKILL_DIR}/scripts/fetch_thn.py --start <start> --end <end>`                         | The Hacker News（**国际事件流主力**，英文） |
| `uv run python ${CLAUDE_SKILL_DIR}/scripts/fetch_bleepingcomputer.py --start <start> --end <end>`            | BleepingComputer（国际深度+一手链接，英文） |
| `uv run python ${CLAUDE_SKILL_DIR}/scripts/fetch_krebs.py --start <start> --end <end>`                       | Krebs on Security（独家深度调查，英文）     |
| `uv run python ${CLAUDE_SKILL_DIR}/scripts/fetch_darkreading.py --start <start> --end <end>`                 | Dark Reading（企业安全视角，英文）          |
| `uv run python ${CLAUDE_SKILL_DIR}/scripts/fetch_schneier.py --start <start> --end <end>`                    | Schneier on Security（观点/趋势，英文）     |

每条 item 字段：`source / section_guess / title / url / date / summary / extra`。`section_guess` 只是初判，你可调整。

**赛事板块专用工具**：撰写「赛事活动」前，跑 `uv run python ${CLAUDE_SKILL_DIR}/scripts/format_events.py --start <start> --end <end>`，它直接输出可粘贴的 Markdown 片段（信息行式：H3 + 一句话点睛 + 竞赛时间/链接两行），已自动算好 **UTC+8 竞赛时间范围** 和 **官网 + CTFTime 双链接**。你只需润色「一句话点睛」、删掉不采纳的赛事。加 `--json` 则输出统一结构（兼容信息池记录，`extra.time_range` / `extra.ctftime_url` 可见）。

**CNVD（漏洞共享平台）需人工辅助**：它有反爬封锁，脚本无法抓。读条目池后，若"漏洞情报"偏薄，用 AskUserQuestion 问用户："是否有需要补充的选定时间范围内漏洞（CNVD/CVE）？粘贴文本或链接即可。"

**汇总**：把所有 items 合并成一个「本周信息池」。按语义去重——同一事件在多源出现的，合并为一条。

**落盘**：把信息池和去重记录写入中间文档，便于追溯（需求：记录采纳的信息链接和简要总结）：
- `issues/<filename>/sources/信息池.md`：完整信息池表格（板块/标题/来源/日期/URL/摘要/是否采纳），**含未采纳项**，未采纳括注理由（信息密度低/企业自宣/超出时间窗/与已采纳重复）。
- `issues/<filename>/sources/去重合并.md`：同一事件多源合并的记录表（合并后条目/合并的原始条目/合并理由）。

### 步骤 2 — 确定本期头条（Headline）

从信息池提炼 **2~4 个候选主题**，每个给：①事件概述 ②为什么重要 ③建议报道角度。
用 **AskUserQuestion** 让用户选 1 个做头条。选题标准：重要性高、信息量足、有延展讲解空间、与读者群体相关。

**落盘**：把候选列表和用户最终选择写入 `issues/<filename>/sources/头条候选.md`（每个候选的概述/重要性/角度，加上用户选定项、选择方式、时间）。

### 步骤 2.5 — 头条一手素材补强（仅头条，板块简讯跳过）

> 真实媒体的核心竞争力是自己的信源。本刊头条不得仅依赖安全内参的转译稿（那是二次摘要），必须有一手素材撑起纵深。这一步只针对头条主题，板块简讯用信息池即可，跳过。

用户选定头条后，针对该主题用 **WebSearch / WebFetch** 主动检索 **1~3 条一手素材**：

- **优先级**：① 厂商官方博客 / 安全公告（OpenAI / Hugging Face / Microsoft 等的官方 post）② 监管 / 法律原文（SEC 8-K、欧盟处罚决定书）③ 外媒原文深度报道（BleepingComputer / Krebs / Ars Technica）④ 论文 / 技术分析（arXiv、Project Zero）。
- **检索方式**：用「事件名 + vendor blog / official statement / original research」等查询；境外站点需走代理（同步骤 1）。境外 RSS 源（thn/bc/krebs/darkreading/schneier）里若有同主题条目，直接用其一手链接。
- **单独成档**：把一手链接 + 关键事实摘录写入 `issues/<filename>/sources/头条素材.md`（**不进信息池**——信息池是"本周发生了什么"的候选事件集，一手素材是"某个头条的纵深材料"，用途不同，混入会污染板块选材）。
- **出处**：成品「相关文献」小节把一手链接列为出处，标注 `· HF Blog` / `· OpenAI` / `· Krebs` 等，与 `· 安全内参` 并列。

### 步骤 3 — 撰写

> **撰写前必读 `references/写作风格.md`**——先读序章人设和 Part 0 编辑思维三原则（怎么想），再读 Part 1 改稿流程（怎么改），最后查 Part 4 删除清单和 Part 5 格式速查（别怎么写）。三者都是硬约束。头条写作另见 Part 3 五段骨架。

> **风格基准（黄金样本）**：参照 `issues/第3期_2026-07-29/周报.md`（成品）与同目录 `STYLE_NOTES.md`（逐条风格标注）。新期撰写前先读这两个文件，模仿其标题节奏、简讯密度、头条纵深、版面零件。注意 `STYLE_NOTES.md` 已标出第 3 期未达新规范处（新闻标题、版面零件、一手素材），新期须向新规范对齐。

- **本期主题** → 1 篇深度报道（头条），独立成段、篇幅最长、比板块条目深得多。
- **其余信息** → 按五大板块分类。**单条目结构**（便于扫读）：
  1. **标题**（H3）：一句话点明事件，含关键名词（厂商/CVE/赛事名）。
  2. **一句话摘要**：发生了什么 + 影响谁。
  3. **正文（2~4 句）**：背景 + 关键细节 + 必要时 1 句具体影响点评（点评密度见 `references/写作风格.md` 第 5 章）。
  4. **出处链接**：行内 Markdown 链接附在条目末尾。
- **无料的板块直接省略**，不要硬凑。

### 步骤 4 — 自查与交付

对照下方「质量清单」逐项过。然后落盘（期号、日期区间、目录名都来自步骤 0 的 `issue_meta.py` 输出）：

- **写入** `issues/<filename>/周报.md`（如 `issues/第7期_2026-07-29/周报.md`），用 Write 工具。中间文档已在步骤 1、2 写入 `issues/<filename>/sources/`。

---

## 取舍规则（贯穿全程，质量把关关键）

1. **政府信息极度克制**：网信办/工信部/公安部多数政策普通人难以直观感知。**只取**影响极远/极深/极快、存在争议、确实有趣的。其余一律舍弃——宁可政策法规板块空着。
2. **剔除企业自宣**：安全内参上的产品宣传/企业文化/企业活动一律忽略。
3. **社区甄别真伪**：CTFtime 等社区信息，赛事状态含 `POSTPONED`（延期）的需特别标注。来自 CTFTime 的国际赛事，链接同时给「官网 + CTFTime」两个（CTFTime 链接由 `format_events.py` / `fetch_ctftime_global.py` 从 `比赛ID` 自动推出，形如 `https://ctftime.org/event/<id>`）；国内赛事无 CTFTime ID，只给官网。
4. **时间窗**：所有信息发布/赛事时间在**选定时间范围内**（脚本已过滤，撰写时再核一遍）。
5. **去重（跨源）**：同一事件在多源（含安全内参与境外英文源）出现的，合并为一条。**英文一手源与安全内参同事件的，优先保留英文一手链接作为出处**，降低对单一中文聚合源的依赖。
6. **可读优先**：非安全方向学生也能读懂，无未加说明的术语。
7. **板块节制**：无料的板块已省略，未硬凑。
8. **头条突出**：本期主题是当期最重要事件，篇幅与深度明显高于板块条目。
9. **头条有一手素材**：头条至少引用 1 条一手素材（厂商官方/监管原文/外媒原文/论文），不得仅依赖安全内参转译稿——这是从"二次摘要"走向"独立媒体"的硬要求（见步骤 2.5）。

## 输出格式规范

本节只规定**文档结构**（标题层级、条目要素、链接形式）。**文风、Markdown 标记配额、标点、点评密度等全部约束见 `references/写作风格.md`（撰写前必读，交付前按其自查清单逐项核对）。**

- **标题层级**：期数 H1；板块 H2；条目标题 H3；条目内不再深层嵌套。
- **导读/摘要**：开篇 1~2 句「本期导读」；每条目开篇 1 句摘要。
- **链接**：原文以行内 Markdown 链接给出，关键来源附条目末尾。
- **CVE 等编号**：用行内代码格式 `` `CVE-2026-xxxx` `` 便于检索。
- **配图**：以中性可移植 Markdown 为主；赛事条目可引用 `extra.logo`（比赛标志 URL）。

### 报刊零件（出版物仪式感）

除板块内容外，每期成品必须包含以下固定零件（措辞规范见 `references/写作风格.md` Part 7）：

| 零件 | 位置 | 说明 |
|---|---|---|
| 期数与日期 | H1 `# CSSEC 周报 第 N 期（YYYY-MM-DD ~ YYYY-MM-DD）` | 标题自带 |
| 本期导读 | H1 下，1~2 句 | 具体事实钩子，禁"本周动态频繁"式开门 |
| 发刊电头 | 导读末尾，单独一行 | `发刊：YYYY-MM-DD` |
| 下期预告 | 文末（赛事板块之后），1~2 句 | 基于已知事件的具体预告；无已知事件则省略 |
| 反馈入口 | 文末最后一行 | `反馈与勘误：[提交 issue](url)`，中性陈述不喊话 |
| AI 撰写说明 | 文末最后（反馈入口之后），以 `---` 分隔 | Agent 工具和模型名来自步骤 0 用户确认；模板见下方小节 |

### AI 撰写说明（报刊零件）

每期成品末尾（反馈入口之后、全文最后）必须以分隔线 `---` 引出 AI 撰写说明。**Agent 工具名和模型名均使用步骤 0 用户确认的名称**。措辞模板：

---
**AI 撰写说明**：本文由 [步骤 0 确认的 Agent 工具名] 调用 [步骤 0 确认的模型名] 基于安全内参、BleepingComputer、The Hacker News、Krebs on Security、Dark Reading、Schneier on Security、中央网信办、工信部、Hello-CTFtime 等公开权威信息源整理撰写。内容经人工审核，力求准确可靠。

**约束**：
- Agent 工具名和模型名严格使用步骤 0 用户确认的名称，不得自行更改或编造。
- 信息源列表以**本期实际使用的源**为准（未使用的源不列）。
- 文案保持此模板的中性陈述语气，不加「敬请谅解」「欢迎指正」等客套话。
- 不允许用 emoji、箭头、直角引号。

### 赛事条目（信息行式）

「赛事活动」板块每条用结构化信息行，便于扫读时间与链接（由 `format_events.py` 自动生成，撰写时只润色一句话点睛、删不采纳项）：

```
### <比赛名>[（已延期）]

<一句话点睛：主办/赛制/权重/面向人群等>。

- 竞赛时间：<YYYY-MM-DD ~ YYYY-MM-DD（UTC+8）>（同日起止写单日）
- 链接：[官网](<比赛链接>) · [CTFtime](https://ctftime.org/event/<id>)
```

- **竞赛时间**一律标 `（UTC+8）`（数据源 `Global.json` 本身带 UTC+8；国内赛事默认 UTC+8）。
- **链接**：国际赛事给「官网 + CTFTime」两个行内链接；国内赛事只给 `[官网](…)`。
- 延期赛事标题加「（已延期）」，正文说明新日期未公布。
- 时间/链接用无序列表，不计入正文「叙述优先」的克制——它是结构化信息，属合理用途（详见 `references/写作风格.md` Part 5）。

### 头条相关文献（头条专属）

「本期主题」末尾附一个「相关文献」小节，列出头条正文引用过的**全部出处**（含多源合并的各篇、外部官方博客/公告等），便于溯源。板块简讯不列。

```
### <最后一个头条小节，如「余波与影响」>

（头条正文……）

---

**相关文献**

1. [OpenAI 失控模型在互联网游荡 4 天](https://www.secrss.com/articles/92621) · 安全内参
2. [越狱一周才被发现](https://www.secrss.com/articles/92499) · 安全内参
3. [Hugging Face 事后复盘](https://…) · HF Blog
```

编号列表，每条「标题 + 行内链接 + 来源标注（· 安全内参 / · HF Blog 等）」。分隔线 `---` 与板块分隔一致。

## 质量清单（交付前自查）

交付前逐项核对 **`CHECKLIST.md`**——它是结构 + 配额 + 删除清单三组合并去重的速查卡（含本次新增的「跨源去重」「头条至少 1 条一手素材」「新闻标题抽检」「报刊零件齐全」等条目）。文风自查的具体判据见 `references/写作风格.md` Part 0~5。

## 深度参考

- `references/写作风格.md`——撰写前**必读**，是文风硬约束。序章人设 + Part 0 思维三原则 + Part 1 改稿流程为必读；Part 2~7 为写作与自查参考。
- `CHECKLIST.md`——交付前逐项核对的速查卡（结构 + 配额 + 删除清单三组合并去重版）。
- `references/信息源.md`——全部信息源（含境外英文源）地址、字段与取用规则（需要时再读）。
- `references/设计规格.md`——设计意图存档（项目定位 + 取用规则理由，需要时再读）。
