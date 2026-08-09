# CSSEC 周报 · HTML 版式设计规格（设计存档）

> 本文档是《CSSEC 周报》**HTML 版交付物**的设计规格：说明「Markdown 周报 → 自包含报刊风格 HTML」的版式从哪里来、按什么规则映射、刻意不做什么。
>
> **执行以 `../SKILL.md`（流程，见「步骤 5 — HTML 版生成」「步骤 6 — PDF 版生成」）+ `scripts/md2html.py` / `scripts/html2pdf.py`（转换器，样式唯一实现方）+ `CHECKLIST.md`（交付自查「六、HTML / PDF 版自查」）为准。** 本文档不作执行依据；转换器实际输出与本文档冲突时，以脚本为准并回改本文档。

## 1. 定位

- **是什么**：把每期成品 `<filename>.md` 渲染为同目录的自包含 HTML 版 `<filename>.html`——单文件、CSS 全内嵌、零外部资源、离线可看、可打印为 PDF。成品三格式共用人类可读文件名 `CSSEC 周报 · 第 N 期`（不补零），归档在自封刊号目录 `CSYY-MMWW-TP/`（见 `../SKILL.md`「成品命名规范」）。
- **单一事实源**：Markdown 仍是唯一事实源；HTML 是它的版式渲染，两版内容必须一致（发刊时按 `CHECKLIST.md` 六节核对）。
- **读者**：浏览器打开 / 打印 / 分享 PDF 的人。目标调性沿用正文原则——**可读、易读**，但版式语言刻意「报刊 + 极简」：像一份严谨的定期出版物，而非公众号推文。

## 2. 转换机制

- 转换器：`scripts/md2html.py`（stdlib-only、离线、确定性——无时间戳/随机，同一输入逐字节可复现）。
- 命令（发刊时自动执行，见 `../SKILL.md` 步骤 5）：

  ```
  uv run python ${CLAUDE_SKILL_DIR}/scripts/md2html.py ${CLAUDE_SKILL_DIR}/../../issues/<dirname>/<filename>.md
  ```

- 输出路径规则：默认输入同目录同名 `.html`（`<filename>.md` → `<filename>.html`）；可用 `-o` 指定、`--title` 覆盖 `<title>`（默认取 H1 刊名）。
- PDF：`scripts/html2pdf.py` 用无头浏览器（Win11 自带 Edge，其次 Chrome）`--print-to-pdf` 打印，A4、去默认页眉页脚，`@page` 边距由 HTML 控制。

## 3. 借鉴自 opencode.ai 的设计元素（及不借清单）

opencode.ai 文档站（Astro + Starlight）的极简/严谨/美观来自一套可迁移的纪律：暖单色、发丝线、直角、mono 数据、克制的链接、真实 print 样式。本刊借鉴如下，主题色换成 `#016737`：

| 借鉴 | 落地 |
|---|---|
| 暖白纸面 + 墨色 + 暖灰发丝线 | `--bg:#FCFCFD` / `--ink:#1E1E1C` / `--hairline:#D9D9D8` |
| 直角（border-radius:0） | `*{border-radius:0}`，全站无圆角 = 严谨信号 |
| 发丝线分隔取代填充/阴影 | 版眉、条目、表格、分隔线全部 1px 线 |
| 大写 + letter-spacing 的微标签 | `.kicker`、`.preview .label`、表头 th |
| mono 数据质感 | 期号/刊号/电头/出处/竞赛时间/链接/CVE/表格数字一律 mono |
| 链接保持暗色、不加色变化 | `a{color:inherit; underline}`，绿永远不上链接 |
| 真正的 print 样式 | `@media print`（见 §9） |

**明确不借**（屏幕交互/站点骨架，与「出版物单页」调性相反）：左侧导航栏、右侧「本页内容」TOC 栏、顶栏搜索与主题切换、hover/点击动效、阴影堆叠、弹窗动画、蓝紫色强调色（换成 `#016737`）。

## 4. 配色表

| Token | 值 | 用途 |
|---|---|---|
| `--bg` | `#FCFCFD` | 页面背景（暖白纸面） |
| `--ink` | `#1E1E1C` | 刊名、版眉、条目标题、表头（墨色） |
| `--ink-soft` | `#55554F` | 正文 |
| `--ink-faint` | `#8A8A84` | 电头、出处、赛事数据、报尾（弱字） |
| `--hairline` | `#D9D9D8` | 发丝线（条目/表格底/面板边） |
| `--hairline-strong` | `#CFCECB` | 强线（版眉尾随线/分隔线/引文左边线） |
| `--panel` | `#F7F7F5` | 面板底（导读框/引文/代码/预告框） |
| `--panel-strong` | `#F0F0EE` | 面板底（文献块） |
| `--accent` | `#016737` | 主题绿：版眉竖条、kicker、电头标记、导读/预告左绿边、赛事项目符、`§` 小节符 |
| `--accent-soft` | `#E5F0EA` | 绿浅底（kicker 背景） |

**绿色纪律**：`#016737` 只做**状态与强调**（版眉、标记、左缘），绝不做装饰、绝不上链接。其余全部停留在暖单色——这样整页在「绿」出现前先给人报刊的克制感，绿作为本刊标识少量点睛。链接永远 `color:inherit` 的墨色下划线。

## 5. 字体决策与字栈（混搭）

用户既定：**刊头/版眉衬线（报刊身份）+ 正文无衬线（现代可读）+ 数据 mono（质感）**。中文优先系统字体栈，不加载外部字体（离线/打印/网络受限环境都能看）：

```
--serif:"Noto Serif SC","Songti SC","STSong","SimSun",Georgia,"Times New Roman",serif;
--sans:"PingFang SC","Microsoft YaHei","Noto Sans SC","Segoe UI",system-ui,-apple-system,"Helvetica Neue",Arial,sans-serif;
--mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,"Cascadia Mono",Consolas,"Courier New",monospace;
```

| 元素 | 字栈 |
|---|---|
| 刊名、版眉 H2、条目标题 H3、头条小标题、文献头、报尾 label | `--serif` |
| 正文段落、列表、导读正文 | `--sans` |
| 期号/日期、刊号、电头、出处、`code`、赛事「竞赛时间/链接」、表格数字、预告/反馈/报尾 | `--mono` |

字号基调：正文 `16px / line-height 1.75`（CJK 舒展节奏）；标题 `line-height ~1.2`；微标签 `.8125rem` 大写 + 字距。

## 6. 报刊零件 → HTML 映射表

`md2html.py` 按下面规则识别成品 Markdown（`<filename>.md`）里的报刊零件（正则容忍全角/半角 `：:（）()~～`，H1 期号容忍空格），渲染为固定元素：

| 零件 | 检测规则 | HTML 元素 / class |
|---|---|---|
| 期数与日期（H1） | 首个 `#`，正则拆 刊名/期号/区间 | `<header class="masthead">`：`h1.publication-name` + `p.issue-meta` |
| 刊号 | H1 后首段 `^刊号[：:]` | 提升进 `<header class="masthead">`：`p.publication-no`（mono 小字，报头刊号行，不留在导读框） |
| 本期导读 | H1 与首个 H2 间的段落 | `<section class="lede">` 面板框（左绿边） |
| 发刊电头 | `^发刊[：:] YYYY-MM-DD` | `p.dateline`（mono 右对齐，绿连续破折线标记，放导读框末） |
| 板块 H2 | 任意 `##` | `<section class="section"><h2 class="section-head">`（绿竖条 + 尾随发丝线） |
| 本期主题（头条） | H2 以 `本期主题` 开头 | `section.headline`：字号加大 + `p.kicker`「头条深度报道」；内部 H3 → `h3.subsection-head`（`§ ` 前缀） |
| 条目标题（H3） | `###`（板块内） | `<article class="story"><h3 class="story-title">`，衬线 |
| 引文 | `>` 引用块；末行 `——` | `<blockquote>` + `footer.quote-attribution` |
| 相关文献 | 剥离行内后等于 `相关文献` 的段 + 后随编号列表；前导 `---` 吞掉 | `<div class="literature">`：`div.literature-head` + `ol.literature-list` |
| 出处 | `^出处[：:]` | `p.source`（mono 小字，链接保持墨色） |
| 赛事数据行 | `- 竞赛时间/链接[：:]` 列表项 | `ul.event-meta > li.data-line`（mono，绿 `•` 项目符） |
| 下期预告 | `^下期预告[：:]` | `div.preview`：`span.label` + 正文 |
| 反馈入口 | `^反馈与勘误[：:]` | `p.feedback`（右对齐 mono） |
| AI 撰写说明 | `^\*\*AI 撰写说明\*\*[：:]`（或「末段 + `---` 后」回退）；尾部 `---` 吞掉 | `footer.colophon`（双线报尾；Agent 工具名/模型名主题绿突出） |

映射关系的措辞模板（下期预告/反馈/AI 说明）以 `写作风格.md` Part 7 与 `../SKILL.md` 为准——HTML 只是换载体，不换措辞。

## 7. Markdown 子集 → 样式映射表

转换器支持以下受控子集；未列出的 Markdown 语法按通用降级处理（见 §10）：

| Markdown | 渲染 |
|---|---|
| `**粗体**` | `<strong>`（墨色；句中可用，如 `**141,006 次**`） |
| `*斜体*` | `<em>`（`_下划线_` 刻意不支持，避免文件名/`keyv@6.0.0` 误伤） |
| `` `代码` `` | `<code>`（mono，浅面板底；CVE 编号即用此） |
| `[文本](链接)` | `<a>` 墨色下划线；**scheme 白名单** http/https/mailto，`javascript:` 等一律降级为纯文本 |
| 裸 `https://…` | 保守 autolink（去掉尾部收尾符号） |
| `#`~`####` | 刊头 / 版眉 / 条目标题 / 小标题（见 §6） |
| 无序/有序列表（2 层嵌套） | `<ul>/<ol>`；无序列表＝主题绿小圆点 `•`（嵌套层空心圈 `◦`），有序列表＝mono 墨色数字；全为「竞赛时间/链接」的 ul 变 `event-meta`（绿点数据行） |
| `> 引用` | `<blockquote>`（面板底 + 强线左缘） |
| GFM 表格 | `table`：th 大写 + `.5px` 字距 + 发丝线，**无斑马纹** |
| `---` | 发丝线分隔（文献前、报尾前的 `---` 自动吞掉，由各自块自带顶线） |
| ``` 代码围栏 ``` | `<pre>`（mono，面板底，可换行） |
| `![alt](图片)` | `<img src alt>`（scheme 白名单；周报当前不配图，属通用能力） |

## 8. 明确「不做」清单

单页出版物的克制，靠主动放弃功能维持：

- **无侧边栏 / 无目录栏 / 无搜索 / 无主题切换**——不是文档站，是单篇报刊。
- **无 JS、无外部字体、无 CDN**——单文件自包含，`file://` 打开零请求，打印/离线/邮件转发都成立。
- **无暗色模式**——报刊是纸，纸是浅色的；深浅切换属于应用，不属于出版物。
- **无装饰性动效 / 无阴影堆叠 / 无圆角**——直角 + 发丝线即全部「装饰」。
- **绿色不上链接**——纪律见 §4。

## 9. 打印样式说明

`@media print` 是这份 HTML 的「出刊」，不是配角。规则直接借鉴 opencode 站点自带 print 样式：

- 底色转纯白、清除阴影；`.report` 取消宽度限制与内边距。
- `break-inside:avoid`：导读框、文献块、引文、表格、代码、预告框不跨页断块。
- `break-after:avoid`：标题不孤行（标题与下段正文同页）。
- `orphans:2; widows:2`：段落不出现孤行。
- 代码 `white-space:pre-wrap`：长行在打印中换行而非溢出截断。
- 链接保持墨色下划线（打印可读），刊头/报尾双线转纯黑。
- `@page{size:A4;margin:18mm 16mm}`：A4 纸张、统一页边距。

发刊时 `scripts/html2pdf.py` 用无头浏览器（Edge/Chrome）自动打印为 A4 PDF（已去浏览器默认页眉页脚）；浏览器手工 `Ctrl+P → 另存为 PDF` 得到同一版式。

## 10. 设计边界与回退

- **未知 Markdown 块**：转换器对未识别的块做中性通用渲染（普通段落/列表/表格/分隔线），保证**任意** Markdown 报告都能转，只是缺少报刊零件的特殊版式。
- **报刊零件缺失**：缺刊号/导读/电头/预告/反馈时，对应元素不输出，不报错（各期版式可不同）。
- **措辞冲突**：HTML 不重写措辞，只换载体。AI 撰写说明的 Agent 工具名与模型名、信息源列表，仍以 `../SKILL.md` 步骤 0 确认 + 本期实际使用为准。
- **内容对等**：发刊时按 `CHECKLIST.md`「六、HTML 版自查」核对 HTML 与 Markdown 逐项一致。

## 交叉引用

- 流程与命令：`../SKILL.md`「步骤 5 — HTML 版生成」「步骤 6 — PDF 版生成」
- 交付自查：`CHECKLIST.md`「六、HTML / PDF 版自查」
- 成品命名：`../SKILL.md`「成品命名规范」
- 报刊零件措辞：`写作风格.md` Part 7
- 发布渠道待决项：`设计规格.md` §3（本 HTML/PDF 版即「发布渠道落地」的第一步：通用、可打印的网页版）
