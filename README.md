# DocGate

DocGate 是本地 Markdown 变更验收中间件。它把人的批注、Agent 的不可信执行声明、真实文件 Diff 和人的最终决定分开呈现，让你按任务验收，而不是重读全文。

第 1 阶段只支持单用户、单工作区、单个 UTF-8 `.md` 文件；不包含团队、账号、分享、权限、导出、SaaS、模型调用或自动语义裁决。

## 1. 安装（macOS）

先确认终端位于本仓库根目录，然后逐行运行：

```bash
python3.11 --version
node --version
npm --version
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps -e .
cd frontend && npm ci && cd ..
./scripts/install-plannotator-local.sh
```

预期版本：Python `3.11.x`、Node `v22.x`、Plannotator `0.24.2`。Plannotator 安装脚本只下载到项目忽略的 `.tools/`，并校验官方 SHA-256，不修改全局 Agent 配置。

如果 Node 提示 `NODE_TLS_REJECT_UNAUTHORIZED=0`，先在当前终端运行 `unset NODE_TLS_REJECT_UNAUTHORIZED`；该宿主设置会关闭 TLS 证书校验，DocGate 不需要也不会设置它。

运行环境自检：

```bash
DOCGATE_WORKSPACE_ROOT="$PWD" .venv/bin/docgate doctor
```

若端口 8765 被占用，请先关闭本项目残留进程；不要结束不认识的其他应用。

## 2. 启动完整应用

打开两个终端，均进入仓库根目录。

终端 A（API，只监听本机）：

```bash
DOCGATE_WORKSPACE_ROOT="$PWD" .venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8765
```

终端 B（正式最小验收页）：

```bash
cd frontend
DOCGATE_API_URL=http://127.0.0.1:8765 npm run dev
```

浏览器打开 <http://127.0.0.1:3000/sessions>。API 文档位于 <http://127.0.0.1:8765/api/docs>。

## 3. 完整真实演示

1. 在工作区准备一个不超过 2 MiB 的 UTF-8 Markdown，例如 `fixtures/simple.md`。
2. 运行：

   ```bash
   DOCGATE_WORKSPACE_ROOT="$PWD" DOCGATE_PLANNOTATOR_COMMAND=.tools/plannotator \
     .venv/bin/docgate review fixtures/simple.md
   ```

3. Plannotator 打开后，选中五个段落，各写一条批注，点击 **Send Feedback**。DocGate 会建立不可变基线、导入批注、生成稳定 task、`agent-brief.md` 和 `receipt.schema.json`。
4. 在命令输出的 `.docgate/sessions/<session_id>/rounds/0001/` 中打开 `agent-brief.md`，交给 Codex、Claude Code 或其他可读写工作区的 Agent。Agent 必须修改目标文件并写出符合 `receipt.schema.json` 的回执。
5. 提交并验证：

   ```bash
   DOCGATE_WORKSPACE_ROOT="$PWD" .venv/bin/docgate submit <session_id> --receipt <receipt.json>
   DOCGATE_WORKSPACE_ROOT="$PWD" .venv/bin/docgate verify <session_id>
   DOCGATE_WORKSPACE_ROOT="$PWD" .venv/bin/docgate inspect <session_id>
   ```

6. 在任务卡逐条查看 before/after、关联 hunk、Agent 声明和机器规则，分别选择接受、返工或澄清。未声明修改必须单独接受或要求撤销。
7. 点击“生成返工包”只保留未通过项，或在所有门槛满足后点击“接受会话”。

Plannotator 不可用时的稳定回退入口：

```bash
DOCGATE_WORKSPACE_ROOT="$PWD" .venv/bin/docgate review fixtures/simple.md --no-plannotator
DOCGATE_WORKSPACE_ROOT="$PWD" .venv/bin/docgate import-annotations <session_id> fixtures/annotations/simple.json
```

这条回退路径不能替代真实 Plannotator 验收。

## 4. 常用 CLI

```text
docgate doctor
docgate review <document.md> [--no-plannotator]
docgate import-annotations <session_id> <annotations.json>
docgate brief <session_id>
docgate submit <session_id> --receipt <receipt.json>
docgate verify <session_id>
docgate inspect <session_id>
docgate rework <session_id>
docgate accept <session_id>
```

CLI 与 `/api/v1` 都调用同一后端服务；前端不计算 hash、Diff、归因或接受门槛。

## 5. 自动化验证

```bash
.venv/bin/pytest
.venv/bin/python scripts/verify-plannotator-contract.py
cd frontend
npm run typecheck
npm run lint
npm test
npm run build
npm run test:e2e
```

Playwright 首次运行前若本机没有对应浏览器：

```bash
cd frontend && npx playwright install chromium
```

FI-01 至 FI-15 位于 `backend/tests/test_failure_injection.py`，测试名保留失败注入编号。`npm run test:e2e` 每次会重建 Git 忽略的 `test-results/e2e-workspace`（结果保留供失败排查），覆盖加载/错误、证据、决策刷新、新 API 进程恢复、返工和接受门槛。

## 6. 数据、备份与恢复

运行数据位于被审阅工作区：

```text
.docgate/
├── index.json
└── sessions/<session_id>/
    ├── session.json
    ├── tasks.json
    └── rounds/0001/...
```

- 每轮 `baseline.md`、结果快照、证据和最终决定不会被下一轮覆盖。
- JSON 采用同目录临时文件、`fsync` 和原子替换；单会话写入使用文件锁。
- 备份时停止 DocGate，然后复制整个 `.docgate/` 和对应源 Markdown。
- 恢复时把两者放回原工作区相对位置，再按原 `DOCGATE_WORKSPACE_ROOT` 启动。
- `DATA_CORRUPTED` 时 DocGate 不覆盖损坏文件。先复制 `.docgate/` 作为证据，再从备份恢复；不要手改历史 Round。
- `STALE_BASELINE` / `DG-BASE-001` 表示源文件在约定时点之外变化，应重新提交回执并验证，不能强行接受。

`.docgate/`、`.env`、`.venv`、`.tools`、`node_modules`、`.next`、日志、缓存和测试产物均被 Git 忽略。

## 7. 安全与隐私

- API 固定监听 `127.0.0.1`；Host、Origin 和状态修改自定义请求头共同阻止普通跨站表单写入。
- 路径必须是工作区内普通 `.md` 文件；拒绝路径遍历、绝对外部路径、符号链接、非 UTF-8 和超限文件。
- 错误响应只含 `error.code`、`error.message` 和不敏感摘要，不返回堆栈、绝对路径或文档正文。
- P0 不调用模型、不需要 API Key；Agent receipt 永远只是不可信声明。

## 8. 第 1 阶段已知限制

- 仅验证 macOS arm64 的 Plannotator v0.24.2；发布到其他平台前需重新校验对应官方二进制和许可证通知。
- Diff 是确定性行级 Diff；章节大范围移动会明确显示低置信或未归因，不假装理解语义。
- 机器只证明 hash、文件变化、定位触达、声明范围、Markdown/front matter 和未声明修改，不判断开放式文字是否“改对”。
- 移动端只保证可读，长文档高效审阅以 1280px 桌面宽度为目标。
- `.docgate/index.json` 是可重建索引；会话目录才是事实来源。P0 没有数据库、多用户并发或完整决策审计历史。

产品经理的三份真实长文档验收步骤见 [人工验收清单](docs/产品经理三份真实文档人工验收清单.md)。开发依据与历史范围说明见 [文档总览](docs/README.md)。
