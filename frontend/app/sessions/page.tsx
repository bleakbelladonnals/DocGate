"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Session } from "@/lib/types";
import { ErrorState } from "@/components/ErrorState";
export default function SessionsPage() {
  const [items, setItems] = useState<Session[] | null>(null);
  const [error, setError] = useState("");
  async function load() {
    setError("");
    setItems(null);
    try {
      setItems((await api<{ sessions: Session[] }>("/sessions")).sessions);
    } catch (e) {
      setError(e instanceof Error ? e.message : "未知错误");
    }
  }
  useEffect(() => {
    let active = true;
    api<{ sessions: Session[] }>("/sessions")
      .then((value) => {
        if (active) setItems(value.sessions);
      })
      .catch((caught) => {
        if (active)
          setError(caught instanceof Error ? caught.message : "未知错误");
      });
    return () => {
      active = false;
    };
  }, []);
  return (
    <main className="shell">
      <p className="eyebrow">DocGate · 本地证据链</p>
      <h1 style={{ fontSize: "clamp(34px,6vw,62px)", margin: "8px 0" }}>
        审阅会话
      </h1>
      <p className="muted">
        人的意见、Agent 声明与真实 Diff 分开呈现，最终决定始终由你完成。
      </p>
      {error && <ErrorState message={error} onRetry={load} />}{" "}
      {items === null && !error && <p role="status">正在加载会话…</p>}
      {items?.length === 0 && (
        <div className="panel" style={{ padding: 28, marginTop: 24 }}>
          <h2>还没有会话</h2>
          <p>
            运行 <code>docgate review &lt;document.md&gt;</code>{" "}
            建立第一份不可变基线。
          </p>
        </div>
      )}
      <div className="stack" style={{ marginTop: 24 }}>
        {items?.map((s) => (
          <Link
            key={s.session_id}
            href={`/sessions/${s.session_id}`}
            className="panel"
            style={{
              padding: 20,
              textDecoration: "none",
              display: "flex",
              justifyContent: "space-between",
              gap: 16,
            }}
          >
            <div>
              <strong>{s.source_path}</strong>
              <p className="muted" style={{ marginBottom: 0 }}>
                第 {s.active_round_number} 轮 · 任务 {s.task_decisions_completed}/
                {s.tasks_total} · 未声明修改 {s.unattributed_count}
              </p>
            </div>
            <span className="pill">{s.state}</span>
          </Link>
        ))}
      </div>
    </main>
  );
}
