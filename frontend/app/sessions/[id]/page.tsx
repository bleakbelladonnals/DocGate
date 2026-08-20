"use client";
import Link from "next/link";
import { use, useCallback, useEffect, useMemo, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Decision, Detail, Hunk } from "@/lib/types";
import { ErrorState } from "@/components/ErrorState";
import { TaskCard } from "@/components/TaskCard";
export default function SessionPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("all");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const load = useCallback(async () => {
    setError("");
    try {
      setDetail(await api<Detail>(`/sessions/${id}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "未知错误");
    }
  }, [id]);
  useEffect(() => {
    let active = true;
    api<Detail>(`/sessions/${id}`)
      .then((value) => {
        if (active) setDetail(value);
      })
      .catch((caught) => {
        if (active)
          setError(caught instanceof Error ? caught.message : "未知错误");
      });
    return () => {
      active = false;
    };
  }, [id]);
  const decisions = useMemo(
    () =>
      new Map(
        detail?.decisions.decisions.map((d) => [
          `${d.subject_type}:${d.subject_id}`,
          d,
        ]) ?? [],
      ),
    [detail],
  );
  const taskChecks = (taskId: string) =>
    detail?.evidence?.checks.filter((c) => c.subject_id === taskId) ?? [];
  const tasks = (detail?.tasks?.tasks ?? []).filter(
    (t) =>
      filter === "all" ||
      taskChecks(t.task_id).some((c) => c.status === filter),
  );
  async function decideTask(taskId: string, decision: string, reason: string) {
    await api<Decision>(`/sessions/${id}/tasks/${taskId}/decision`, {
      method: "PUT",
      body: JSON.stringify({ decision, reason }),
    });
    await load();
  }
  async function decideHunk(hunkId: string, decision: string) {
    await api<Decision>(`/sessions/${id}/hunks/${hunkId}/decision`, {
      method: "PUT",
      body: JSON.stringify({ decision }),
    });
    await load();
  }
  async function action(name: "accept" | "rework") {
    setBusy(true);
    setNotice("");
    try {
      await api(`/sessions/${id}/${name}`, { method: "POST" });
      setNotice(
        name === "accept"
          ? "会话已接受，历史证据保持只读。"
          : "返工包已生成，并创建了不可变的新轮次。",
      );
      await load();
    } catch (e) {
      setNotice(
        e instanceof ApiError ? `${e.code}：${e.message}` : "操作失败。",
      );
    } finally {
      setBusy(false);
    }
  }
  if (error)
    return (
      <main className="shell">
        <ErrorState message={error} onRetry={load} />
      </main>
    );
  if (!detail)
    return (
      <main className="shell">
        <p role="status">正在加载验收证据…</p>
      </main>
    );
  const unattributed =
    detail.evidence?.hunks.filter((h) => h.unattributed) ?? [];
  const receiptByTask = new Map(
    detail.receipt?.tasks.map((t) => [t.task_id, t]) ?? [],
  );
  return (
    <main className="shell">
      <Link href="/sessions">← 返回会话列表</Link>
      <header className="panel" style={{ padding: 24, margin: "18px 0" }}>
        <p className="eyebrow">
          第 {detail.session.active_round_number} 轮 · {detail.session.state}
        </p>
        <h1>{detail.session.source_path}</h1>
        <p className="muted">{detail.session.session_id}</p>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <span className="pill">任务 {detail.tasks?.tasks.length ?? 0}</span>
          <span className="pill">未声明修改 {unattributed.length}</span>
          <span className="pill">
            合法动作 {detail.legal_actions.join(" / ") || "无"}
          </span>
        </div>
      </header>
      <label htmlFor="filter">筛选机器检查</label>
      <select
        id="filter"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        style={{ marginLeft: 8, padding: 8 }}
      >
        <option value="all">全部</option>
        <option value="warning">warning</option>
        <option value="fail">fail</option>
        <option value="uncertain">uncertain</option>
      </select>
      <div className="stack" style={{ marginTop: 18 }}>
        {tasks.length ? (
          tasks.map((task) => (
            <TaskCard
              key={task.task_id}
              task={task}
              receipt={receiptByTask.get(task.task_id)}
              hunks={
                detail.evidence?.hunks.filter((h) =>
                  h.associated_tasks.some((a) => a.task_id === task.task_id),
                ) ?? []
              }
              checks={taskChecks(task.task_id)}
              decision={decisions.get(`task:${task.task_id}`)}
              onDecision={(d, r) => decideTask(task.task_id, d, r)}
              disabled={detail.session.state !== "human_review"}
            />
          ))
        ) : (
          <div className="panel" style={{ padding: 20 }}>
            当前筛选没有任务。
          </div>
        )}
      </div>
      <section className="panel" style={{ padding: 24, marginTop: 24 }}>
        <p className="eyebrow">客观证据</p>
        <h2>未声明修改</h2>
        {unattributed.length === 0 ? (
          <p>没有需要单独决定的未声明修改。</p>
        ) : (
          unattributed.map((h) => (
            <Unattributed
              key={h.hunk_id}
              hunk={h}
              decision={decisions.get(`hunk:${h.hunk_id}`)}
              disabled={detail.session.state !== "human_review"}
              onDecision={(d) => decideHunk(h.hunk_id, d)}
            />
          ))
        )}
      </section>
      <section className="panel" style={{ padding: 24, marginTop: 24 }}>
        <h2>会话门槛</h2>
        <p>只有所有任务、未声明修改和阻断检查均处理完毕才能接受。</p>
        <div style={{ display: "flex", gap: 10 }}>
          <button
            className="button secondary"
            disabled={busy || detail.session.state !== "human_review"}
            onClick={() => action("rework")}
          >
            生成返工包
          </button>
          <button
            className="button"
            disabled={busy || detail.session.state !== "human_review"}
            onClick={() => action("accept")}
          >
            接受会话
          </button>
        </div>
        {notice && <p role="status">{notice}</p>}
      </section>
    </main>
  );
}
function Unattributed({
  hunk,
  decision,
  onDecision,
  disabled,
}: {
  hunk: Hunk;
  decision?: Decision;
  onDecision: (d: string) => Promise<void>;
  disabled: boolean;
}) {
  return (
    <article style={{ borderTop: "1px solid var(--line)", padding: "16px 0" }}>
      <strong>{hunk.hunk_id}</strong>
      <div className="diff">
        <pre className="before">− {hunk.before || "（空）"}</pre>
        <pre className="after">+ {hunk.after || "（空）"}</pre>
      </div>
      <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
        <button
          className="button secondary"
          disabled={disabled}
          onClick={() => onDecision("accepted")}
        >
          接受此修改
        </button>
        <button
          className="button danger"
          disabled={disabled}
          onClick={() => onDecision("revert_requested")}
        >
          要求撤销
        </button>
        {decision && <span role="status">已决定：{decision.decision}</span>}
      </div>
    </article>
  );
}
