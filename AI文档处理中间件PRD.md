# AI 文档处理中间件产品需求文档

> 工作名：DocBridge（文桥）  
> 文档版本：v1.0  
> 状态：可进入 MVP 设计与技术预研  
> 更新日期：2026-08-19  
> 目标读者：产品、设计、研发、测试、商业负责人  
> 结论：以窄场景 B2B MVP 方式推进；不做通用 Markdown/HTML 编辑器。

---

## 0. 执行摘要

### 0.1 产品定义

DocBridge 是面向 AI Agent 的文档制品发布、审阅、批准与交付中间件。它将 Agent 生成的 Markdown/HTML 保留为机器友好的源制品，同时为客户、领导和同事提供无需安装、无需理解 Markdown 的网页审阅界面，并将经人工批准的反馈以结构化协议回传给 Agent。

一句话描述：

> AI 文档的 GitHub Pull Request + Google Docs 评论 + 企业 Word/PDF 交付。

### 0.2 首个目标市场

优先服务 5～50 人、每周反复生成和审阅 AI 报告的服务型团队：咨询、市场研究、内容/广告代理、软件外包、解决方案与投标团队。

### 0.3 首个核心闭环

```text
Agent/CLI 发布 Markdown 或 HTML
→ 生成稳定阅读链接与独立审阅链接
→ 外部审阅者逐段评论并提交审阅结论
→ 文档负责人筛选反馈并形成 Revision Brief
→ Agent 只执行被负责人批准的反馈 ID
→ 发布新版本并展示 Diff
→ 批准后导出企业模板 DOCX/PDF
```

### 0.4 Go / No-Go

- **GO**：稳定文档身份、版本、段落级反馈、人工授权回写、审批、企业格式导出。
- **NO-GO**：通用富文本编辑器、知识库、博客托管、实时多人编辑、AI 写作助手。
- **商业验证条件**：10 个试点团队中，至少 3 个连续四周每周发布 ≥3 份文档，并至少 2 个愿意为团队权限、企业模板或私有部署付费。

---

## 1. 背景与问题

### 1.1 当前工作流

AI Agent 越来越擅长输出 Markdown 报告、HTML 数据报告、方案页和演示文档，但文档进入人工审阅阶段后通常出现断层：

1. Markdown 适合 Agent 和 Git，不适合多数业务审阅者。
2. HTML 适合阅读，却经常是一次性文件，修改后产生大量副本。
3. 评论散落在微信、Slack、邮件和截图中，无法定位到源内容。
4. Agent 不知道审阅者指的是哪一段、哪个版本。
5. 未经授权的外部反馈若直接进入 Agent，存在提示注入与误操作风险。
6. 正式交付仍要求 Word/PDF、企业模板、页眉页脚和审阅留痕。

### 1.2 核心问题陈述

> 当 AI 生成的文档需要多轮人工审阅时，团队缺少一个将“机器源文件、网页审阅、版本决策和正式交付”连接起来的轻量控制层。

### 1.3 已有证据与限制

- Reddit、X、V2EX、Linux.do、小红书均出现“HTML 取代 Markdown 作为交付界面”“AI HTML 难修改”“Markdown 无法直接交付同事”等讨论。
- Linux.do 相关主题约 5,089 次浏览、321 赞、151 帖；小红书相关 HTML 编辑内容约 919 赞、137 条评论。
- [Plannotator](https://github.com/backnotprop/plannotator)、[html-anything](https://github.com/nexu-io/html-anything) 的快速增长说明开发者需求存在，也说明泛化窗口正在缩小。
- 当前证据能证明痛点与兴趣，**不能直接证明规模化付费意愿**；付费必须通过真实工作流试点验证。

---

## 2. 市场定位

### 2.1 目标用户

#### Persona A：AI 文档生产者（核心用户）

- 角色：咨询顾问、研究员、解决方案经理、产品经理、研发负责人。
- 行为：使用 Claude Code、Codex、Cursor 或内部 Agent 生成报告。
- 痛点：文件散乱、反馈无法定位、人工整理意见、重复导出。
- 成功标准：两分钟内发布；收到结构化反馈；Agent 能准确修改。

#### Persona B：业务审阅者（关键体验用户）

- 角色：客户、领导、法务/品牌审核人、项目经理。
- 特征：不愿注册新工具，不理解 Markdown/Git，不想安装软件。
- 痛点：不知道在哪里评论；不知道看的是否最新版；反馈后没有闭环。
- 成功标准：打开链接即可看、选中即可评、能明确“批准/要求修改”。

#### Persona C：团队管理员/采购者（付费决策者）

- 角色：团队负责人、IT 管理员、交付负责人。
- 痛点：敏感文件外泄、无权限记录、企业模板不统一、无法审计。
- 成功标准：成员与空间权限明确；可私有部署；有审计、模板和导出控制。

### 2.2 核心使用场景

| 场景 | 频率 | 当前替代方式 | 产品价值 | 优先级 |
|---|---:|---|---|---|
| 客户报告多轮审阅 | 每周 | HTML/PDF + 微信/邮件 | 精确评论、稳定链接、版本闭环 | P0 |
| 技术方案/Agent 计划审批 | 每日/每周 | Markdown + GitHub/聊天 | 批准后 Agent 才执行 | P0 |
| 周报/月报周期发布 | 每周/月 | 复制 Word/飞书文档 | 同一入口、历史版本、模板导出 | P0 |
| 标书/方案企业交付 | 每月 | 人工排版 Word | 企业模板、审批和审计 | P1 |
| 互动 HTML 原型审阅 | 不定期 | Vercel + 截图反馈 | 元素级评论、状态复现 | P1 |
| 知识库与实时协同写作 | 高频 | Notion/飞书/Confluence | 已有成熟替代 | 不做 |

### 2.3 不服务的人群

- 偶尔导出一次 PDF 的个人用户。
- 只需要 Markdown 预览或博客发布的开发者。
- 需要完整 Notion/飞书替代品的团队。
- 只关心 AI 写作，不存在审阅闭环的用户。

### 2.4 定位边界

DocBridge 是 **Artifact Control Plane**，不是内容创作平台。源内容由 Agent 或用户已有工具产生；DocBridge 管理制品的身份、状态、反馈、审批和交付。

---

## 3. 开源项目二开与组件选型

> GitHub Stars 为 2026-08-19 调研快照，只代表开发者关注度。许可证结论用于技术选型初筛，不替代正式法律意见；合并代码前必须保留 NOTICE、逐文件确认许可证并完成 SBOM。

### 3.1 建议直接二开的项目

| 项目 | 快照 | 许可证 | 可复用部分 | 缺口/风险 | 结论 |
|---|---:|---|---|---|---|
| [jpage / 即页](https://github.com/code2rich/jpage) | 174★ | MIT | 用户、Token、文件上传、短链、版本、访问统计、SQLite、MCP、CLI、CSP/iframe 沙箱、Docker、DOCX 初步能力 | 前端为原生 JS；现有“feedback”是产品意见箱，不是文档批注；团队空间和审批缺失 | **MVP 主骨架** |
| [PreApp Agent](https://github.com/serrendypity/preapp-agent) | 1★ | MIT | Agent-first CLI、MCP、Skill、幂等发布、反馈载荷、版本绑定、双阶段人工授权、提示注入防护文案 | 仅开放 Agent 集成层，托管服务端未开源 | **复用客户端，重建服务端协议** |
| [Plannotator](https://github.com/backnotprop/plannotator) | 7,890★ | GitHub 标记 Apache-2.0；仓库含 Apache/MIT 文件 | Markdown/HTML/计划/Diff 审阅 UI、行级批注、review-editor 组件、移动端交互、Agent 集成思路 | Monorepo 较重；逐包许可证需复核；代码审阅能力远超 MVP | **拆用审阅与 Diff 组件** |
| [html-anything](https://github.com/nexu-io/html-anything) | 8,338★ | Apache-2.0 | iframe 沙箱、HTML 技能模板、CJK 设计约束、HTML/PNG/平台导出、Agent CLI 适配方式 | 产品范围偏内容生成与分发，不含完整审批闭环 | **拆用沙箱与导出思路** |

### 3.2 建议使用的基础组件

| 能力 | 项目 | 许可证 | 使用建议 |
|---|---|---|---|
| 富文本/块编辑 | [Tiptap](https://github.com/ueberdosis/tiptap) 38,075★ | MIT（仅使用开源核心） | P1 开启负责人直接修订；P0 只做评论，不做完整编辑 |
| Markdown AST | [unified](https://github.com/unifiedjs/unified) + remark | MIT | 解析 Markdown、生成稳定 block ID、记录源行号、HTML 渲染 |
| Markdown 所见即所得备选 | [Milkdown](https://github.com/Milkdown/milkdown) 11,832★ | MIT | 若必须保持 Markdown 原文编辑，可替代 Tiptap；MVP 不同时引入两套编辑器 |
| 协同数据 | [Yjs](https://github.com/yjs/yjs) 22,369★ | MIT | P1 实时协同；P0 不需要 CRDT |
| 协同服务 | [Hocuspocus](https://github.com/ueberdosis/hocuspocus) 2,537★ | MIT | 与 Yjs/Tiptap 配合；仅在验证多人同时编辑后引入 |
| DOCX 生成 | [docx](https://github.com/dolanmiu/docx) | MIT | MVP 生成一个企业模板；已有 jpage 依赖可沿用 |
| PDF 转换 | [Gotenberg](https://github.com/gotenberg/gotenberg) 12,880★ | MIT | 独立容器，将 HTML/Office 转 PDF，降低主服务复杂度 |
| 文档导入 | [Docling](https://github.com/docling-project/docling) 65,129★ | MIT | P1 将 PDF/DOCX 转结构化内容，不进入首版关键链路 |
| 通用转换 | [Pandoc](https://github.com/jgm/pandoc) 45,936★ | GPL-2.0 | 可作为隔离的命令行/Sidecar；分发和衍生边界必须法务确认 |

### 3.3 只参考、不建议并入商业主仓库

| 项目 | 许可证/情况 | 可参考能力 | 不直接采用原因 |
|---|---|---|---|
| [Docmost](https://github.com/docmost/docmost) 21,412★ | AGPL-3.0 + 企业目录 | 评论、页面历史、空间、权限、Tiptap/Yjs 架构 | 网络服务修改分发义务；范围过大 |
| [Markra](https://github.com/markrahq/markra) 754★ | AGPL-3.0 | 本地优先、WYSIWYG/源码双模式、AI 修改预览 | AGPL；偏个人编辑器 |
| [Papermark](https://github.com/papermark/papermark) 8,953★ | AGPL-3.0 + EE | 安全分享、访问分析、自定义域名 | AGPL/EE；偏 DocSend 数据室 |
| [ONLYOFFICE DocumentServer](https://github.com/ONLYOFFICE/DocumentServer) 6,833★ | AGPL-3.0 | 高保真 DOCX 在线编辑 | 重、许可证复杂；MVP 不需要 Office 替代品 |
| [Outline](https://github.com/outline/outline) 40,237★ | BSL 1.1 | 文档协作、评论、权限、历史 | 许可证明确限制竞争性 Document Service |
| [AFFiNE](https://github.com/toeverything/AFFiNE) 71,668★ | 混合许可 | 本地优先、块模型、知识库 | 许可与架构边界复杂；产品范围过大 |
| [pandoc_docx_template](https://github.com/Achuan-2/pandoc_docx_template) 1,028★ | GitHub 未检测到许可证 | 中文 Word 标题编号、段落和模板效果 | 未获明确授权前只能学习效果，不能复制代码/模板 |

### 3.4 推荐二开组合

#### 方案 A：快速验证型（推荐）

```text
jpage MIT 主干
├── 保留：Express、SQLite、文件/版本、Token、短链、访问统计、Docker、MCP
├── 新增：workspace / artifact / review_link / annotation / approval 数据模型
├── 新增：React 审阅子应用（拆用 Plannotator 交互）
├── 新增：unified/remark block ID 与源行映射
├── 参考：PreApp CLI/MCP/反馈协议与双阶段授权
└── Sidecar：Gotenberg PDF；docx 生成 Word
```

优势：两周内能跑通首个闭环；MIT 主骨架商业友好。  
代价：后续 SaaS 化需要从 SQLite/本地文件迁移到 Postgres/S3；前端存在原生 JS 与 React 两套技术栈。

#### 方案 B：从组件新建 SaaS

Next.js/React + Tiptap + unified + Postgres + S3 + 队列，自研全部服务端，仅复用 PreApp/Plannotator/HTML Anything 的组件和协议。

优势：长期架构整洁。  
代价：首个可验证版本预计多 4～8 周，容易在基础设施上过度投入。

#### 方案 C：二开 Docmost/Outline

不建议。一个有 AGPL 与企业版边界，一个有明确竞争用途限制；同时二者是知识库，不是 Agent 文档控制层，删减成本可能高于新建。

### 3.5 最终技术决策

- MVP 采用方案 A。
- 仅把 `jpage` 作为起点，不承诺永久维持其数据库和前端结构。
- 新增业务表使用 ULID/UUID 字符串，不沿用单机自增 ID 作为外部标识。
- 所有外部反馈都被标记为 `untrusted=true`；只有负责人创建的 Revision Brief 才能成为 Agent 的可执行输入。
- 任何 Apache/MIT 源码复用必须在仓库 `THIRD_PARTY_NOTICES.md` 登记来源、版本和修改内容。

---

## 4. 闭源产品参考

| 产品 | 已验证能力 | 借鉴点 | 不照搬的部分 |
|---|---|---|---|
| [GitHub Pull Request Reviews](https://docs.github.com/en/pull-requests/reference/pull-request-reviews) | 行级评论、建议修改、Comment/Approve/Request changes、必要审批 | 审阅结论状态机；反馈与版本绑定；未批准不能合并 | 不要求审阅者理解 Git/Diff |
| [Vercel Comments](https://vercel.com/docs/comments) | 在预览页面元素或文字上直接评论；新部署提示刷新；外部邀请 | 评论覆盖在真实交付物上；版本更新提醒；与通知工具联动 | 不要求审阅者安装 Toolbar 或拥有 Vercel 账号 |
| [Google Docs](https://workspace.google.com/products/docs/) | 权限、评论、建议、版本协作 | 熟悉的选中评论、@人、已解决状态 | 不将源文件锁进专有编辑器 |
| [Notion Docs](https://www.notion.com/product/docs) | 协作编辑、评论、建议、集中反馈 | 低学习成本的侧边评论与异步协作 | 不做知识库、数据库和页面搭建 |
| [Filestage](https://filestage.io/) | 多格式集中审阅、批注、版本、批准、流程分析 | 审阅轮次、批准状态、提醒、面向客户的低摩擦体验 | MVP 不做复杂工作流编排和全媒体格式 |
| [MarkUp.io](https://www.markup.io/) | 上传/输入链接后直接可视化评论；访客无需注册 | Review Link 与 View Link 分离；外部访客无需账号 | 不扩展到任意网站、图片和视频审阅 |
| [DocSend](https://www.docsend.com/zh/) | 受保护链接、访问权限、敏感资料控制 | 密码、到期时间、撤销链接、访问记录 | 不做虚拟数据室和融资交易流程 |
| [Gamma](https://gamma.app/zh-cn) | AI 生成美观文档；链接分享；PPT/PDF/PNG/Google Slides 导出 | 开箱即美观和“一次生成，多处交付” | 不与其争夺内容生成和演示制作入口 |

### 4.1 应形成的独特组合

没有一个参考产品同时做好以下四点：

1. Markdown/HTML 作为 Agent 可持续修改的源制品。
2. 外部人员无账号、低摩擦地逐段审阅。
3. 反馈经过负责人筛选授权后结构化回到 Agent。
4. 同一制品最终按企业模板导出 DOCX/PDF。

DocBridge 的机会在于这四点的闭环，而不是任何一个单点功能。

---

## 5. 产品目标与非目标

### 5.1 MVP 目标

1. 首次从 Agent 发布到可分享链接不超过 2 分钟。
2. 审阅者无需注册即可完成评论和审阅结论。
3. 90% 的文字评论可以定位到正确源段落与正确版本。
4. Agent 不得自动执行未经负责人明确批准的外部反馈。
5. 文档可导出为一个企业 Word 模板和可打印 PDF。
6. 负责人能知道谁在何时看过、评论过、批准过哪个版本。

### 5.2 非目标

- 不提供通用 AI 写作和提示词广场。
- 不替代 Word、Notion、飞书或 Confluence。
- 不做多人实时共同写正文。
- 不执行用户上传的服务端代码。
- 不承诺任意复杂 HTML 的像素级可编辑。
- 不在 MVP 支持 PPTX、Excel、视频、设计稿等全格式审阅。

---

## 6. 信息架构与状态模型

### 6.1 信息架构

```text
组织 Organization
└── 工作区 Workspace
    ├── 成员与角色
    ├── 企业导出模板
    └── 文档制品 Artifact
        ├── 版本 Version（不可变）
        ├── 阅读链接 View Link
        ├── 审阅链接 Review Link
        ├── 评论 Annotation
        ├── 审阅轮次 Review Round
        ├── Revision Brief
        ├── 审批 Approval
        ├── 导出 Export Job
        └── 审计事件 Audit Event
```

### 6.2 文档状态

```text
DRAFT
  → IN_REVIEW
      → CHANGES_REQUESTED
          → IN_REVISION
              → IN_REVIEW
      → APPROVED
          → DELIVERED
  → ARCHIVED
```

规则：

- Version 一旦发布不可修改，只能生成下一版本。
- Artifact 的稳定链接默认指向最新可见版本。
- 评论永远绑定创建时的 `version_id`，不能自动漂移到最新版。
- 新版本发布后，旧版本未解决评论显示为“旧版本反馈”，由负责人决定迁移或关闭。
- `APPROVED` 后若发布新版本，审批自动失效并回到 `IN_REVIEW`。

### 6.3 角色与权限

| 行为 | Owner | Editor | Reviewer | Viewer/Guest |
|---|---:|---:|---:|---:|
| 发布新版本 | ✓ | ✓ | — | — |
| 创建/撤销分享链接 | ✓ | ✓ | — | — |
| 评论 | ✓ | ✓ | ✓ | 按链接能力 |
| 创建 Revision Brief | ✓ | ✓ | — | — |
| 批准/要求修改 | ✓ | 可配置 | ✓（被指定时） | — |
| 管理模板/成员 | ✓ | — | — | — |
| 查看审计记录 | ✓ | 可配置 | — | — |

---

## 7. 核心用户流程

### 7.1 流程 A：Agent 首次发布

1. 用户在工作区生成 Agent Token。
2. 安装 DocBridge CLI/Skill 或配置 MCP。
3. Agent 执行 `docbridge publish report.md --title "Q3 市场报告"`。
4. CLI 校验文件、收集本地图片、生成内容哈希和幂等键。
5. 服务端解析 Markdown AST，为块生成稳定 `block_id` 和源行映射。
6. 服务端渲染并存储不可变版本。
7. 返回 View Link、Review Link、Version Link 和反馈拉取命令。
8. 用户把 Review Link 发给客户或领导。

### 7.2 流程 B：外部审阅

1. 审阅者打开 Review Link，可按策略免登录或输入密码。
2. 页面显示文档标题、版本号、更新时间和“这是最新版/存在新版”提示。
3. 审阅者选中文字、点击图片或选择章节添加评论。
4. 审阅者提交总评：Comment / Approve / Request changes。
5. 系统记录 reviewer session、版本、目标 locator、评论和时间。
6. 文档负责人收到站内/邮件通知。

### 7.3 流程 C：反馈筛选与 Agent 修改

1. 负责人打开 Review Board，按版本查看全部反馈。
2. 负责人将反馈标记为：采纳、拒绝、需澄清、已解决。
3. 被采纳反馈组成 Revision Brief，每一项引用稳定 `feedback_id`。
4. 负责人将 Brief 标记为 `READY`。
5. Agent 拉取 Brief；原始评论仍标记为不可信上下文。
6. Agent 修改本地源文件，发布 v2，并携带 `revision_brief_id` 与序列号。
7. 服务端验证 Brief 属于 v1、未被使用、序列号未过期。
8. 发布成功后 Brief 变为 `APPLIED`，v2 可追溯到本轮修改依据。

### 7.4 流程 D：批准与交付

1. 指定审阅者对最新版点击 Approve。
2. 满足审批规则后 Artifact 进入 `APPROVED`。
3. 负责人选择企业模板导出 DOCX/PDF。
4. 导出文件记录版本、模板版本、操作者、时间与哈希。
5. Artifact 标记 `DELIVERED`，保留永久审计链。

---

## 8. 功能需求与验收标准

### 8.1 组织、工作区与身份

#### FR-AUTH-01 账号登录（P0）

- 支持邮箱密码登录；自托管允许管理员关闭公开注册。
- Agent Token 仅在创建时显示明文，服务端只保存哈希。
- **验收**：撤销 Token 后 5 秒内不能再调用发布或反馈 API。

#### FR-WORKSPACE-01 工作区（P0）

- 用户至少属于一个 Workspace。
- Artifact、模板和成员权限都归属于 Workspace。
- **验收**：不同 Workspace 的 Editor 无法通过 ID 枚举读取其他空间资源。

#### FR-RBAC-01 权限（P0）

- 支持 Owner、Editor、Reviewer 三类登录角色和 capability-link Guest。
- **验收**：每个写操作在服务端进行权限验证并产生日志。

### 8.2 发布与版本

#### FR-PUB-01 多入口发布（P0）

- Web 支持拖拽 `.md`、`.html`、静态 ZIP。
- CLI/MCP 支持创建 Artifact 或向既有 Artifact 发布新版本。
- **验收**：重复网络重试使用同一 Idempotency-Key 时只创建一个版本。

#### FR-PUB-02 文件规则（P0）

- 单次上传 ≤50MB；ZIP ≤500 个文件；解压后 ≤200MB。
- 拒绝路径穿越、符号链接、隐藏文件、可执行文件、服务端脚本。
- **验收**：恶意 ZIP 不得在制品目录外写入文件。

#### FR-VER-01 不可变版本（P0）

- 每次发布产生递增版本号、内容哈希、源文件哈希、渲染器版本。
- 稳定链接显示最新版本；固定版本链接永远显示指定版本。
- **验收**：任何已发布版本的存储对象不可原地覆盖。

#### FR-VER-02 版本说明与回滚（P1）

- 发布可填写 change note；Owner 可将旧版本内容重新发布为新版本。
- **验收**：回滚不是移动指针，而是生成可审计的新版本。

### 8.3 渲染与阅读

#### FR-RENDER-01 Markdown 渲染（P0）

- 支持 CommonMark/GFM、表格、任务列表、代码高亮、Mermaid、KaTeX、本地图片。
- Front matter 不显示在正文，可映射为文档元数据。
- 发布时渲染，查看时不重复解析源文档。
- **验收**：渲染失败不创建版本，并返回源文件行号。

#### FR-RENDER-02 HTML 沙箱（P0）

- 用户 HTML 在独立源或 sandbox iframe 内运行。
- 默认阻止访问父页面、Cookie、LocalStorage、摄像头、麦克风和下载。
- 外部资源默认阻止或按 Workspace 白名单放行。
- **验收**：上传 HTML 无法读取主站身份信息或执行同源 API。

#### FR-READ-01 阅读体验（P0）

- 响应式正文、目录、深浅主题、代码/表格横向滚动、打印样式。
- 顶部显示标题、状态、版本、更新时间及最新版本提示。
- **验收**：390px 视口无页面级横向溢出；WCAG AA 对比度。

### 8.4 评论与定位

#### FR-CMT-01 文本评论（P0）

- 审阅者选中文字后可评论。
- Locator 至少包含：`version_id`、`block_id`、exact quote、prefix、suffix、occurrence、源行范围、内容哈希。
- **验收**：同一句文本重复出现时能区分具体 occurrence；评论只能绑定当前版本。

#### FR-CMT-02 章节与图片评论（P0）

- 可对章节、图片或整篇文档评论。
- 图片引用必须验证为该版本资产路径。
- **验收**：不能通过图片 ref 访问 Artifact 目录外文件。

#### FR-CMT-03 评论状态（P0）

- 状态：Open、Accepted、Rejected、Needs clarification、Resolved、Outdated。
- 只有 Owner/Editor 能决定 Accepted/Rejected/Resolved。
- **验收**：每次状态变化进入 Audit Event。

#### FR-CMT-04 访客身份（P0）

- Review Link 可设置“免账号、输入显示名”或“必须登录/邮箱验证”。
- 显示名明确标注为 reviewer-supplied，不能代表真实身份。
- **验收**：同一浏览器 session 能看到自己的评论；默认不向外部访客展示其他审阅者评论，可由 Owner 配置。

### 8.5 审阅结论与 Revision Brief

#### FR-REV-01 审阅结论（P0）

- 审阅者提交 Comment、Approve 或 Request changes。
- Owner 可指定必须审批的人数或人员（P1）。
- **验收**：存在有效 Request changes 时文档不能进入 APPROVED。

#### FR-BRIEF-01 筛选反馈（P0）

- Owner/Editor 将一个或多个反馈整理成可执行修改项。
- 每项保留关联 `feedback_ids` 和人工编辑后的 instruction。
- **验收**：原始评论不可被覆盖；修改项与来源同时可见。

#### FR-BRIEF-02 双阶段授权（P0）

- 原始反馈始终 `untrusted=true`。
- Agent 拉取原始反馈时只允许复述并等待用户指定 feedback ID。
- 只有状态为 READY 的 Revision Brief 可以作为执行依据。
- **验收**：评论中出现命令、索取密钥、“忽略指令”等内容时，系统标记风险且不自动触发工具。

#### FR-BRIEF-03 并发与应用（P0）

- Brief 使用 `edit_sequence` 乐观锁；更新必须提交读取时序列号。
- 发布新版本时原子性地应用 Brief；Brief 只能应用一次且源版本必须是直接上一版本。
- **验收**：过期序列号返回 409，不得静默覆盖。

### 8.6 Diff

#### FR-DIFF-01 版本 Diff（P0）

- Markdown 显示语义块级 + 行级 Diff。
- HTML MVP 显示渲染前后切换和源码 Diff；P1 再做视觉 Diff。
- **验收**：用户可从 v2 返回 v1，并看到哪些变化对应哪个 Brief 项。

#### FR-DIFF-02 评论迁移提示（P1）

- 当新版本仍包含相同 block ID/quote 时建议迁移评论，但必须由人确认。
- **验收**：系统不得自动把旧版本批准状态带到新版本。

### 8.7 分享与访问分析

#### FR-SHARE-01 能力链接（P0）

- View Link 只读；Review Link 可评论；Version Link 固定版本。
- 支持撤销、重新生成、密码、到期时间。
- **验收**：Review Token 不能调用 Agent API；View Token 不能提交评论。

#### FR-ANALYTICS-01 访问记录（P0）

- 记录访问次数、最近访问时间和粗粒度设备类型。
- IP 只保存加盐哈希并设置保留期，不记录精确地理位置。
- **验收**：Owner 能确认链接是否被打开；访客隐私说明可见。

### 8.8 导出

#### FR-EXPORT-01 PDF（P0）

- 使用打印 CSS/Gotenberg 输出 PDF。
- **验收**：目录、分页、表格和中文字体可用；页内评论不进入交付版。

#### FR-EXPORT-02 DOCX（P0）

- MVP 支持一个内置企业模板：封面、自动目录、标题编号、正文、表格、图片、页眉页脚。
- 导出任务异步执行并保留模板版本与文件哈希。
- **验收**：在 Microsoft Word 与 WPS 打开无修复提示；常用标题和表格不丢失。

#### FR-TEMPLATE-01 企业模板（P1）

- Owner 可上传/配置 Workspace 模板并预览测试结果。
- **验收**：模板升级不改变历史导出文件。

### 8.9 通知与审计

#### FR-NOTIFY-01 通知（P1）

- 新评论、要求修改、批准、发布新版本通过邮件通知。
- Slack/飞书/企业微信 Webhook 后续提供。

#### FR-AUDIT-01 审计（P0）

- 记录发布、查看、评论、评论状态、Brief、批准、链接设置、导出、Token 操作。
- **验收**：审计事件 append-only，普通成员不能删除。

---

## 9. 页面与交互需求

### 9.1 页面清单

| 页面 | P0 内容 |
|---|---|
| 登录/初始化 | 登录、首次管理员、Token 引导 |
| 工作区首页 | Artifact 列表、状态、最新版本、最近活动 |
| Artifact 详情 | 版本、分享链接、审阅状态、导出、访问统计 |
| 阅读页 | 干净正文、目录、版本提示、打印 |
| 审阅页 | 正文 + 选区评论 + 评论侧栏 + 审阅结论 |
| Review Board | 按版本/状态筛选评论、创建 Brief、批准状态 |
| 版本 Diff | vN 与 vN-1 对比、关联修改项 |
| 设置 | 成员、Token、分享策略、模板、安全 |

### 9.2 审阅页布局

```text
┌────────────────────────────────────────────────────────────┐
│ Logo  文档标题  v3 · 最新  [阅读] [审阅]      提交审阅结论 │
├──────────────┬─────────────────────────────┬───────────────┤
│ 目录/章节     │ 文档正文                     │ 评论与状态     │
│              │ 选中文字 → 添加评论          │ 本人/全部过滤  │
│              │ 块边缘显示评论数量            │ 回复、解决     │
└──────────────┴─────────────────────────────┴───────────────┘
```

移动端：目录和评论侧栏改为抽屉；选中文字后出现底部评论按钮；提交审阅结论固定在底部操作栏。

### 9.3 关键体验原则

- 审阅者优先：外部访客不应先看到管理后台。
- 先阅读后操作：View Link 不加载评论控件。
- 状态显性：版本号、是否最新版、审阅结论始终可见。
- 反馈可追溯：任何“Agent 已修改”都能追溯到 Brief 和原始反馈 ID。
- 默认安全：分享是显式动作，外部反馈不能直接触发 Agent 修改。

---

## 10. 数据模型

### 10.1 核心实体

| 实体 | 关键字段 |
|---|---|
| organizations | id, name, plan, created_at |
| workspaces | id, organization_id, name, retention_policy |
| memberships | workspace_id, user_id, role |
| artifacts | id, workspace_id, slug, title, status, latest_version_id, owner_id |
| versions | id, artifact_id, number, source_format, source_path, source_hash, render_hash, artifact_hash, renderer_version, change_note, created_by, created_at |
| blocks | id, version_id, stable_key, type, heading_path, source_start_line, source_end_line, text_hash |
| review_links | id, artifact_id, permission, token_hash, password_hash, expires_at, revoked_at |
| reviewer_sessions | id, review_link_id, display_name, verified_email, session_hash |
| annotations | id, version_id, block_id, reviewer_session_id, target_type, target_json, body, untrusted, status, created_at |
| review_decisions | id, version_id, reviewer_session_id/user_id, decision, note, created_at |
| revision_briefs | id, source_version_id, state, edit_sequence, applied_version_id |
| revision_items | id, brief_id, instruction, sort_order |
| revision_item_feedback | item_id, annotation_id |
| export_templates | id, workspace_id, name, format, version, config/object_key |
| export_jobs | id, version_id, template_id, status, output_hash, object_key |
| audit_events | id, workspace_id, actor_type, actor_id, action, target_type, target_id, metadata_json, created_at |

### 10.2 Locator 数据结构

```json
{
  "type": "text",
  "versionId": "ver_01...",
  "blockId": "blk_01...",
  "quote": "年度方案可节省 20%",
  "prefix": "按年支付时，",
  "suffix": "，但需预付。",
  "occurrence": 1,
  "total": 1,
  "source": {
    "entry": "report.md",
    "startLine": 82,
    "endLine": 84,
    "headingPath": ["定价", "企业版"]
  },
  "contentHash": "sha256:..."
}
```

### 10.3 稳定块策略

1. 若 Markdown 中存在显式 `<!-- docbridge:id=... -->`，优先使用。
2. 否则根据 heading path、块类型、规范化文本和相邻块生成候选 stable key。
3. 在新版本发布时运行块匹配，仅用于辅助 Diff 和评论迁移建议。
4. 任何自动匹配都不能改变评论原始 `version_id`。

---

## 11. Agent、CLI 与 API 需求

### 11.1 CLI

```bash
docbridge login <agent-token> --base-url https://docs.example.com

docbridge publish ./report.md \
  --title "Q3 市场报告" \
  --artifact q3-market \
  --change-note "补充风险章节"

docbridge feedback get q3-market --version 1 --format markdown
docbridge revision get q3-market --version 1 --format markdown
docbridge publish ./report.md --artifact q3-market \
  --revision rbr_01... --revision-sequence 4
```

CLI 要求：

- stdout 默认输出稳定 JSON，便于 Agent 解析；人类文本用 `--format text`。
- 网络错误可重试；同次逻辑发布复用 Idempotency-Key。
- 配置文件权限为 `0600`；CI 优先使用环境变量。
- 不上传 `.git`、`.env`、`node_modules`、符号链接和无关文件。

### 11.2 MVP API

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/api/v1/artifacts/publish` | 创建 Artifact/新版本 |
| GET | `/api/v1/artifacts/{id}` | 获取状态与最新版本 |
| GET | `/api/v1/artifacts/{id}/versions` | 版本列表 |
| GET | `/api/v1/versions/{id}/feedback` | Agent/Owner 拉取结构化反馈 |
| POST | `/api/v1/review/{token}/annotations` | 审阅者提交评论 |
| POST | `/api/v1/review/{token}/decisions` | 提交批准/要求修改 |
| GET/PUT | `/api/v1/versions/{id}/revision-brief` | 读取/保存 Brief |
| POST | `/api/v1/exports` | 创建 DOCX/PDF 导出任务 |
| GET | `/api/v1/exports/{id}` | 查询导出结果 |

### 11.3 发布响应

```json
{
  "artifactId": "art_01...",
  "versionId": "ver_01...",
  "versionNumber": 2,
  "artifactHash": "sha256:...",
  "viewLink": "https://docs.example.com/s/q3-market?v=view_xxx",
  "reviewLink": "https://docs.example.com/s/q3-market/review?v=review_xxx",
  "versionLink": "https://docs.example.com/s/q3-market/v/2?v=view_xxx",
  "feedbackCommand": "docbridge feedback get q3-market --version 2",
  "warnings": []
}
```

### 11.4 MCP 工具

- `docbridge_publish`
- `docbridge_feedback_get`
- `docbridge_revision_get`
- `docbridge_revision_save`
- `docbridge_export`

MCP 工具不得将 Agent Token 作为调用参数暴露给模型；Token 从进程环境或本机配置读取。

---

## 12. 系统架构

### 12.1 MVP 部署架构

```text
Browser / CLI / MCP
        │
        ▼
Express API（基于 jpage）
├── Auth / RBAC / Capability Link
├── Artifact / Version Service
├── Review / Brief / Approval Service
├── Audit / Analytics
├── Render Pipeline（unified/remark）
└── Export Queue
        │
        ├── SQLite（MVP 单租户/小团队）
        ├── Local Object Storage
        ├── Gotenberg PDF Sidecar
        └── docx Exporter

Isolated Artifact Origin
└── sandbox iframe / 静态资源服务
```

### 12.2 SaaS 演进架构

- SQLite → PostgreSQL。
- 本地文件 → S3 兼容对象存储。
- 内存任务 → Redis/队列 Worker。
- 单域 iframe → 独立 Artifact 域名与严格 CSP。
- 单节点 → API、渲染、导出独立扩缩容。

### 12.3 关键架构原则

- 源文件与渲染结果同时保存，版本不可变。
- 用户上传内容与主应用身份域隔离。
- 评论目标使用结构化 locator，不依赖脆弱 CSS selector。
- 发布、Brief 应用、版本状态更新在一个事务中完成。
- 导出是异步任务；失败可重试但不得产生重复交付记录。

---

## 13. 非功能需求

### 13.1 性能

- 5MB Markdown：P95 发布完成 ≤8 秒（不含大型 Mermaid）。
- 普通阅读页：首屏 LCP ≤2.5 秒（国内常规宽带）。
- 新评论提交：P95 ≤800ms。
- 20MB HTML ZIP：P95 发布 ≤30 秒。

### 13.2 可用性与恢复

- MVP 目标月可用性 99.5%；正式 Team SaaS 99.9%。
- 数据库每日备份；对象存储版本化；RPO 24h、RTO 4h（MVP）。
- 发布和导出支持幂等重试。

### 13.3 安全

- 上传文件类型、数量、压缩比、路径、符号链接全面校验。
- Artifact 独立源 + iframe sandbox + CSP。
- Token 哈希存储；敏感配置不进入日志。
- 评论、显示名、locator 全部按不可信输入处理。
- Markdown/HTML 输出经过 XSS 防护；链接增加 `rel=noopener noreferrer`。
- 限流：登录、上传、评论、Token 创建分别配置。
- 关键操作进入不可变审计日志。

### 13.4 隐私

- 默认私有；创建外部链接是显式操作。
- 自托管模式不依赖第三方分析脚本。
- IP 仅做加盐哈希和反滥用，默认保留 30 天。
- 支持 Workspace 数据导出与彻底删除；删除前展示影响范围和保留策略。

### 13.5 兼容性与可访问性

- Chrome/Edge/Safari 最近两个大版本；Firefox 最近一个大版本。
- 移动端最低 360px。
- 键盘可完成评论、切换评论和提交结论。
- 颜色对比满足 WCAG 2.1 AA；状态不能只依赖颜色表达。
- 中文优先，同时预留英文文案结构。

---

## 14. 数据指标与事件

### 14.1 北极星指标

**每周完成的有效审阅闭环数**：某 Artifact 在 7 天内完成“发布 → 至少一条有效反馈/审阅结论 → 新版本或批准”。

### 14.2 激活指标

- TTFP：注册/部署后到首次成功发布的时间，目标中位数 <10 分钟。
- 首次发布成功率 >70%。
- 首份文档产生外部访问的比例 >60%。
- 首份文档产生有效评论或审阅结论的比例 >30%。

### 14.3 留存与价值指标

- 团队四周留存率。
- 每团队每周发布 Artifact 数。
- 每 Artifact 版本数、有效评论数、审阅周期时长。
- 评论被采纳进入 Brief 的比例。
- Brief 被应用并成功发布新版本的比例。
- DOCX/PDF 导出次数。
- “复制到飞书/Word 后继续审阅”的流失原因访谈。

### 14.4 埋点事件

`workspace_created`、`agent_token_created`、`publish_started`、`publish_succeeded`、`share_link_created`、`review_opened`、`annotation_created`、`decision_submitted`、`brief_ready`、`brief_applied`、`version_approved`、`export_succeeded`。

不得在埋点中上传正文、评论全文、Token 或个人敏感信息。

---

## 15. MVP 里程碑

### Week 0：技术尖峰（3～5 天）

- 跑通 jpage 本地部署、上传、版本、短链和 MCP。
- 验证 Plannotator 评论组件可独立嵌入。
- 用 unified 将 Markdown 块映射到源行。
- 用 docx/Gotenberg 导出一份中文样例。
- 完成许可证清单与 NOTICE 初稿。

退出标准：四个技术风险均有最小可运行 Demo。

### Week 1：稳定发布

- Workspace/Artifact/Version 数据模型。
- Web、CLI 发布；稳定链接和固定版本链接。
- Markdown 渲染、HTML 沙箱、内容哈希、幂等。

### Week 2：低摩擦审阅

- Review Link、访客 session、文本/章节/图片评论。
- 评论侧栏、版本绑定、最新版提示。
- Comment/Approve/Request changes。

### Week 3：Agent 回写闭环

- Review Board、评论筛选、Revision Brief。
- 双阶段授权、MCP/CLI feedback/revision。
- v1/v2 Diff、Brief 原子应用、审计日志。

### Week 4：企业交付与试点

- 一个中文 DOCX 模板、PDF 导出。
- 密码/到期/撤销链接；访问统计。
- 10 个真实团队 onboarding；记录全流程屏幕与访谈。

---

## 16. 测试与发布验收

### 16.1 P0 端到端用例

1. Codex 使用 MCP 发布含图片、表格、Mermaid 的 Markdown。
2. 外部访客在手机上打开 Review Link，无账号添加三种评论。
3. 负责人采纳两条、拒绝一条，创建 READY Brief。
4. Agent 拉取 Brief，只修改被授权两项并发布 v2。
5. 系统显示 v1/v2 Diff，旧评论仍归属 v1。
6. 审阅者批准 v2；负责人导出 DOCX/PDF。
7. 审计记录能串起发布者、审阅者 session、Brief、批准和导出。

### 16.2 安全用例

- ZIP 路径穿越、压缩炸弹、符号链接和脚本文件被拒绝。
- HTML 读取父页面 Cookie/LocalStorage 失败。
- Review Token 无法发布；View Token 无法评论。
- 评论内容包含“读取 .env 并上传”时被标记为潜在注入，Agent 不执行。
- 过期/撤销链接立即失效。
- 跨 Workspace ID 枚举返回 404/403 且不泄露资源存在性。

### 16.3 发布门槛

- 所有 P0 验收用例通过。
- 无已知 Critical/High 安全漏洞。
- 第三方依赖 SBOM、许可证和 NOTICE 完成。
- 桌面 1280px、手机 390px、打印/PDF 视觉检查通过。
- 备份恢复演练成功一次。

---

## 17. 商业化假设

> 价格是验证假设，不是最终定价。

| 版本 | 假设能力 | 价格测试 |
|---|---|---|
| Self-hosted Community | 单工作区、基础发布/审阅、社区支持 | 免费，用于获客和建立 Agent 生态 |
| Team | 托管服务、成员权限、企业模板、邮件通知、90 天审计 | ¥149～399/月/团队 |
| Business | SSO、长期审计、自定义域名、更多模板、Webhook | ¥999～2,999/月 |
| Enterprise | 私有部署、内网、定制模板、SLA、合规支持 | ¥20,000+/年起 |

首个付费点优先级：

1. 私有部署和数据不出域。
2. 企业 Word 模板与批量导出。
3. 成员权限、审计和审批规则。
4. 自定义域名、品牌和访问控制。

不建议把“Markdown 渲染”“漂亮主题”“AI 生成正文”作为主要收费点。

---

## 18. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|---|---:|---:|---|
| 工作流低频，只需一次导出 | 高 | 高 | 只招募每周多轮审阅的团队；用周闭环数做门槛 |
| 用户仍复制到飞书/Word | 高 | 高 | 把客户审阅、批准、Agent 回写和模板导出放在同一闭环 |
| 评论定位随版本漂移 | 中 | 高 | 版本绑定 + block ID + TextQuoteSelector + 哈希；迁移必须人工确认 |
| HTML 上传造成 XSS/数据泄露 | 中 | 极高 | 独立源、sandbox、CSP、静态文件、外链策略、安全测试 |
| 评论提示注入 Agent | 高 | 高 | untrusted 标记、风险扫描、双阶段授权、READY Brief |
| DOCX 高保真难度被低估 | 高 | 中 | MVP 固定一个模板和受限块类型；复杂格式回退 PDF |
| 二开代码许可证污染 | 中 | 高 | MIT 主骨架；AGPL/BSL 只参考；逐文件清单和法律复核 |
| 直接竞品快速补齐闭环 | 高 | 高 | 聚焦中文企业 Word/私有部署与服务团队模板，不打泛化功能战 |
| 两套前端技术增加维护 | 中 | 中 | MVP 隔离 Review React Bundle；验证后统一前端技术栈 |

---

## 19. 验证计划与停止条件

### 19.1 试点招募

招募 10 个团队，每类 2～3 个：咨询/研究、营销代理、软件外包、解决方案/投标。要求其当前每周至少产生 3 份 AI 文档且存在外部审阅。

### 19.2 四周实验

- 第 1 周：陪同首次发布，观察是否能在 10 分钟内完成。
- 第 2 周：要求真实客户/领导使用 Review Link，不接受内部演示替代。
- 第 3 周：完成至少一次“反馈 → Brief → Agent 修改 → v2”。
- 第 4 周：让团队选择继续付费、私有部署、回到旧流程或放弃，并记录原因。

### 19.3 继续条件

- ≥3 个团队连续四周每周发布 ≥3 份。
- ≥30% 外部打开的文档产生评论或审阅结论。
- ≥50% READY Brief 最终产生新版本。
- ≥2 个团队签署付费意向或支付试点费用。

### 19.4 停止/转向条件

- 多数用户只使用“一键导出”，不使用稳定链接和反馈回写：转向企业文档导出工具。
- 评论大量发生在飞书/微信，Review Link 无法改变习惯：转向飞书/企业微信插件。
- 只有开发者使用，业务审阅者不进入：缩窄为 Agent 计划/技术方案审批工具。
- 四周后无人愿为模板、权限或私有部署付费：停止 SaaS 化，保留开源工具。

---

## 20. 待决策问题

1. 首个垂直行业选择咨询/研究还是软件外包？建议先选能提供 5 个连续项目样本的一方。
2. MVP 是单租户自托管优先，还是托管多租户优先？建议单租户 Docker + 受控托管试点。
3. Word 模板由用户上传还是团队定制服务？建议 MVP 由团队定制，避免先造复杂模板编辑器。
4. 外部访客默认能否看到他人评论？建议默认只能看自己的，Owner 可开启公开讨论。
5. 是否支持 HTML 内脚本？建议默认静态/受限脚本；互动原型作为单独 review profile。
6. 是否需要内容级加密？MVP 先做传输/静态存储加密，企业客户再评估自持密钥。

---

## 21. 来源与调研快照

### 21.1 开源仓库

- [jpage](https://github.com/code2rich/jpage)
- [PreApp Agent](https://github.com/serrendypity/preapp-agent)
- [Plannotator](https://github.com/backnotprop/plannotator)
- [html-anything](https://github.com/nexu-io/html-anything)
- [Tiptap](https://github.com/ueberdosis/tiptap)
- [Milkdown](https://github.com/Milkdown/milkdown)
- [Yjs](https://github.com/yjs/yjs)
- [Hocuspocus](https://github.com/ueberdosis/hocuspocus)
- [Docmost](https://github.com/docmost/docmost)
- [Markra](https://github.com/markrahq/markra)
- [Papermark](https://github.com/papermark/papermark)
- [Gotenberg](https://github.com/gotenberg/gotenberg)
- [Docling](https://github.com/docling-project/docling)
- [Pandoc](https://github.com/jgm/pandoc)
- [ONLYOFFICE DocumentServer](https://github.com/ONLYOFFICE/DocumentServer)

### 21.2 闭源产品官方页面

- [GitHub Pull Request Reviews](https://docs.github.com/en/pull-requests/reference/pull-request-reviews)
- [Vercel Comments](https://vercel.com/docs/comments)
- [Google Docs](https://workspace.google.com/products/docs/)
- [Notion Docs](https://www.notion.com/product/docs)
- [Filestage](https://filestage.io/)
- [MarkUp.io](https://www.markup.io/)
- [DocSend](https://www.docsend.com/zh/)
- [Gamma](https://gamma.app/zh-cn)

### 21.3 社区需求证据

- [Reddit：HTML instead of Markdown](https://www.reddit.com/r/ClaudeCode/comments/1tkcci7/html_instead_of_markdown/)
- [Reddit：Agent reports](https://www.reddit.com/r/AgentsOfAI/comments/1towgdx/my_ai_agent_delivered_solid_reports_for_months_i/)
- [V2EX：PreApp](https://www.v2ex.com/t/1228051)
- [V2EX：jpage](https://www.v2ex.com/t/1218514)
- [Linux.do：HTML 替代 Markdown](https://linux.do/t/topic/2138856)
- [Linux.do：Word 文档讨论](https://linux.do/t/topic/2616741)
- [小红书：AI 写的 HTML 改到崩溃](https://www.xiaohongshu.com/explore/6a2631620000000021020262)
- [小红书：Markdown 转 Word Skill](https://www.xiaohongshu.com/explore/6a0999ec00000000080022c3)

---

## 22. 决策记录

| 日期 | 决策 | 理由 |
|---|---|---|
| 2026-08-19 | 采用窄场景 B2B MVP | 痛点真实但付费未验证，通用编辑器竞争拥挤 |
| 2026-08-19 | jpage 作为 MVP 主骨架 | MIT、已具备发布/版本/分享/MCP/安全基础 |
| 2026-08-19 | 不直接二开 Docmost/Outline | AGPL/BSL 风险和产品范围不匹配 |
| 2026-08-19 | 原始反馈必须双阶段授权 | 外部评论是提示注入入口，不能直接交给 Agent 执行 |
| 2026-08-19 | DOCX/PDF 属于核心闭环 | 目标客户最终交付仍依赖企业格式 |

---

**最终建议：立即开始 Week 0 技术尖峰和试点招募，但在获得真实周频使用与付费证据之前，不投入完整 SaaS 基础设施。**
