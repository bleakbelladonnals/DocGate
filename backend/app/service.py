from __future__ import annotations

import difflib
import json
import re
import secrets
from pathlib import Path
from string import Template
from typing import Any, Iterable

import frontmatter
from markdown_it import MarkdownIt

from .errors import DocGateError
from .models import (
    AnnotationImport,
    AnnotationSource,
    Association,
    ChangeTask,
    Check,
    Decision,
    Decisions,
    DiffHunk,
    Evidence,
    HunkDecisionInput,
    HumanStatus,
    Locator,
    LocatorStatus,
    Receipt,
    Round,
    Session,
    SessionState,
    SessionSummary,
    TaskBundle,
    TaskDecisionInput,
    now_utc,
)
from .storage import atomic_json, atomic_write, read_model, safe_markdown_path, session_lock, sha256_bytes


def _id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(10)}"


def _hunk_id(round_id: str, opcode: tuple[str, int, int, int, int]) -> str:
    digest = sha256_bytes((round_id + ":" + ":".join(map(str, opcode))).encode())[:20]
    return f"hnk_{digest}"


TRANSITIONS: dict[SessionState, set[SessionState]] = {
    SessionState.BASELINED: {SessionState.FEEDBACK_READY},
    SessionState.FEEDBACK_READY: {SessionState.AGENT_WORKING},
    SessionState.AGENT_WORKING: {SessionState.RESULT_SUBMITTED},
    SessionState.RESULT_SUBMITTED: {SessionState.VERIFYING},
    SessionState.VERIFYING: {SessionState.HUMAN_REVIEW, SessionState.RESULT_SUBMITTED},
    SessionState.HUMAN_REVIEW: {SessionState.ACCEPTED, SessionState.REWORK},
    SessionState.REWORK: {SessionState.AGENT_WORKING},
    SessionState.ACCEPTED: set(),
}


class DocGateService:
    def __init__(self, workspace_root: Path, *, max_bytes: int = 2_097_152):
        self.root = workspace_root.resolve()
        self.max_bytes = max_bytes
        self.data = self.root / ".docgate"
        self.sessions_dir = self.data / "sessions"

    def _session_dir(self, session_id: str) -> Path:
        if not re.fullmatch(r"ses_[a-z0-9]+", session_id):
            raise DocGateError("SESSION_NOT_FOUND", "会话不存在。", status=404)
        return self.sessions_dir / session_id

    def _round_dir(self, session: Session) -> Path:
        return self._session_dir(session.session_id) / "rounds" / f"{session.active_round_number:04d}"

    def _load_session(self, session_id: str) -> Session:
        try:
            return read_model(self._session_dir(session_id) / "session.json", Session)
        except DocGateError as exc:
            if exc.code == "NOT_FOUND":
                raise DocGateError("SESSION_NOT_FOUND", "会话不存在。", status=404) from exc
            raise

    def _save_session(self, session: Session) -> None:
        session.updated_at = now_utc()
        atomic_json(self._session_dir(session.session_id) / "session.json", session)
        self._rebuild_index()

    @staticmethod
    def _transition(session: Session, target: SessionState) -> None:
        if target not in TRANSITIONS[session.state]:
            raise DocGateError("INVALID_STATE_TRANSITION", "当前会话状态不允许此操作。", status=409)
        session.state = target

    def _rebuild_index(self) -> None:
        items: list[dict[str, Any]] = []
        if self.sessions_dir.exists():
            for path in sorted(self.sessions_dir.glob("ses_*/session.json")):
                try:
                    session = read_model(path, Session)
                    items.append(session.model_dump(mode="json"))
                except DocGateError:
                    continue
        atomic_json(self.data / "index.json", {"schema_version": 1, "sessions": items})

    def create_session(self, source_path: str) -> Session:
        _, relative, content = safe_markdown_path(self.root, source_path, self.max_bytes)
        for existing in self.list_sessions():
            if existing.source_path == relative and existing.state != SessionState.ACCEPTED:
                raise DocGateError("ACTIVE_SESSION_EXISTS", "该文件已有活跃审阅会话。", status=409, details={"session_id": existing.session_id})
        session_id, round_id, timestamp = _id("ses"), _id("rnd"), now_utc()
        digest = sha256_bytes(content)
        session = Session(
            session_id=session_id,
            source_path=relative,
            initial_source_hash=digest,
            state=SessionState.BASELINED,
            active_round_id=round_id,
            active_round_number=1,
            created_at=timestamp,
            updated_at=timestamp,
        )
        directory = self._session_dir(session_id)
        round_dir = directory / "rounds" / "0001"
        with session_lock(directory):
            atomic_write(round_dir / "baseline.md", content)
            atomic_json(round_dir / "round.json", Round(round_id=round_id, number=1, base_hash=digest, created_at=timestamp))
            atomic_json(round_dir / "decisions.json", Decisions())
            self._save_session(session)
        return session

    def list_sessions(self) -> list[Session]:
        if not self.sessions_dir.exists():
            return []
        result: list[Session] = []
        for path in sorted(self.sessions_dir.glob("ses_*/session.json")):
            result.append(read_model(path, Session))
        return sorted(result, key=lambda item: item.updated_at, reverse=True)

    def list_session_summaries(self) -> list[SessionSummary]:
        summaries: list[SessionSummary] = []
        for session in self.list_sessions():
            detail = self.get_detail(session.session_id)
            tasks = detail["tasks"].tasks if detail["tasks"] else []
            decisions = detail["decisions"].decisions
            evidence = detail["evidence"]
            summaries.append(SessionSummary(
                session_id=session.session_id,
                source_path=session.source_path,
                state=session.state,
                active_round_id=session.active_round_id,
                active_round_number=session.active_round_number,
                updated_at=session.updated_at,
                tasks_total=len(tasks),
                task_decisions_completed=sum(1 for item in decisions if item.subject_type == "task"),
                unattributed_count=sum(1 for hunk in evidence.hunks if hunk.unattributed) if evidence else 0,
            ))
        return summaries

    @staticmethod
    def _headings(lines: list[str], line_number: int) -> list[str]:
        stack: list[tuple[int, str]] = []
        for line in lines[:line_number]:
            match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
            if match:
                level, title = len(match.group(1)), match.group(2)
                stack = [item for item in stack if item[0] < level]
                stack.append((level, title))
        return [title for _, title in stack]

    def import_annotations(self, session_id: str, payload: AnnotationImport) -> TaskBundle:
        directory = self._session_dir(session_id)
        with session_lock(directory):
            session = self._load_session(session_id)
            if session.state not in {SessionState.BASELINED, SessionState.FEEDBACK_READY}:
                raise DocGateError("INVALID_STATE_TRANSITION", "当前状态不能导入批注。", status=409)
            round_dir = self._round_dir(session)
            round_data = read_model(round_dir / "round.json", Round)
            base = (round_dir / "baseline.md").read_text("utf-8")
            lines = base.splitlines()
            external_ids: set[str] = set()
            tasks: list[ChangeTask] = []
            for annotation in payload.annotations:
                if annotation.id in external_ids:
                    raise DocGateError("DUPLICATE_ANNOTATION", "批注外部 ID 重复。")
                external_ids.add(annotation.id)
                positions = [m.start() for m in re.finditer(re.escape(annotation.exact_quote), base)]
                occurrence = annotation.occurrence
                if not positions:
                    status, position = LocatorStatus.MISSING, None
                elif occurrence is not None and occurrence <= len(positions):
                    status, position = LocatorStatus.UNIQUE, positions[occurrence - 1]
                elif len(positions) == 1:
                    status, position, occurrence = LocatorStatus.UNIQUE, positions[0], 1
                else:
                    status, position, occurrence = LocatorStatus.AMBIGUOUS, None, None
                start_line = base[:position].count("\n") + 1 if position is not None else None
                end_line = start_line + annotation.exact_quote.count("\n") if start_line else None
                tasks.append(ChangeTask(
                    task_id=_id("tsk"),
                    instruction=annotation.instruction,
                    annotation_source=AnnotationSource(adapter=payload.adapter, external_id=annotation.id, raw_type=annotation.raw_type),
                    locator=Locator(
                        exact_quote=annotation.exact_quote,
                        prefix=annotation.prefix or (base[max(0, (position or 0) - 40):(position or 0)] if position is not None else ""),
                        suffix=annotation.suffix or (base[(position or 0) + len(annotation.exact_quote):(position or 0) + len(annotation.exact_quote) + 40] if position is not None else ""),
                        occurrence=occurrence,
                        start_line=start_line,
                        end_line=end_line,
                        heading_path=self._headings(lines, start_line or 0),
                        locator_status=status,
                    ),
                    created_at=now_utc(),
                ))
            bundle = TaskBundle(session_id=session_id, base_hash=round_data.base_hash, tasks=tasks)
            atomic_json(directory / "tasks.json", bundle)
            atomic_json(round_dir / "annotations.raw.json", payload)
            self._write_receipt_schema(round_dir)
            self._write_brief(session, round_data, bundle, round_dir, rework=False)
            if session.state == SessionState.BASELINED:
                self._transition(session, SessionState.FEEDBACK_READY)
            self._transition(session, SessionState.AGENT_WORKING)
            self._save_session(session)
            return bundle

    def _write_receipt_schema(self, round_dir: Path) -> None:
        schema = Receipt.model_json_schema()
        atomic_json(round_dir / "receipt.schema.json", schema)

    def _write_brief(self, session: Session, round_data: Round, bundle: TaskBundle, round_dir: Path, *, rework: bool, protected: list[str] | None = None) -> None:
        task_text = "\n\n".join(
            f"## Task {task.task_id}\n\nInstruction: {task.instruction}\n\nAnchor: {task.locator.exact_quote}\n\nAllowed scope: {task.scope.allowed}\n\nForbidden: {task.scope.forbidden}"
            for task in bundle.tasks
        )
        template_name = "rework-brief.md.tmpl" if rework else "agent-brief.md.tmpl"
        template = Template((Path(__file__).parent / "templates" / template_name).read_text("utf-8"))
        rendered = template.substitute(
            session_id=session.session_id,
            round_id=round_data.round_id,
            source_path=session.source_path,
            base_hash=round_data.base_hash,
            receipt_path=(round_dir / "receipt.json").relative_to(self.root).as_posix(),
            tasks=task_text or "No active tasks.",
            protected="\n".join(f"- {item}" for item in (protected or [])) or "- None",
        )
        atomic_write(round_dir / ("rework-brief.md" if rework else "agent-brief.md"), rendered.encode())

    def submit_receipt(self, session_id: str, receipt: Receipt) -> Round:
        directory = self._session_dir(session_id)
        with session_lock(directory):
            session = self._load_session(session_id)
            if session.state != SessionState.AGENT_WORKING:
                raise DocGateError("INVALID_STATE_TRANSITION", "当前状态不能提交回执。", status=409)
            round_dir = self._round_dir(session)
            round_data = read_model(round_dir / "round.json", Round)
            bundle = read_model(directory / "tasks.json", TaskBundle)
            _, _, source = safe_markdown_path(self.root, session.source_path, self.max_bytes)
            actual = sha256_bytes(source)
            if receipt.session_id != session_id or receipt.round_id != round_data.round_id:
                raise DocGateError("RECEIPT_TARGET_MISMATCH", "回执不属于当前会话或轮次。")
            if receipt.base_hash != round_data.base_hash:
                raise DocGateError("STALE_BASELINE", "回执基线与当前轮次不一致。", status=409)
            if receipt.result_hash != actual:
                raise DocGateError("RESULT_HASH_MISMATCH", "回执结果 hash 与源文件不一致。", details={"rule_id": "DG-HASH-002"})
            expected = {task.task_id for task in bundle.tasks}
            actual_tasks = [task.task_id for task in receipt.tasks]
            if len(actual_tasks) != len(set(actual_tasks)) or set(actual_tasks) != expected:
                raise DocGateError("RECEIPT_TASK_MISMATCH", "回执必须恰好覆盖所有活跃任务。")
            for item in receipt.tasks:
                for claimed in item.claimed_changes:
                    if claimed.path != session.source_path or claimed.end_line < claimed.start_line:
                        raise DocGateError("INVALID_CLAIMED_RANGE", "回执声明范围无效。")
            atomic_write(round_dir / "result.md", source)
            atomic_json(round_dir / "receipt.json", receipt)
            round_data.result_hash = actual
            round_data.submitted_at = now_utc()
            atomic_json(round_dir / "round.json", round_data)
            self._transition(session, SessionState.RESULT_SUBMITTED)
            self._save_session(session)
            return round_data

    @staticmethod
    def _diff_hunks(round_id: str, before: str, after: str) -> list[DiffHunk]:
        old, new = before.splitlines(), after.splitlines()
        matcher = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
        hunks: list[DiffHunk] = []
        for opcode in matcher.get_opcodes():
            tag, i1, i2, j1, j2 = opcode
            if tag == "equal":
                continue
            hunks.append(DiffHunk(
                hunk_id=_hunk_id(round_id, opcode),
                old_start=i1 + 1,
                old_lines=i2 - i1,
                new_start=j1 + 1,
                new_lines=j2 - j1,
                before="\n".join(old[i1:i2]),
                after="\n".join(new[j1:j2]),
            ))
        return hunks

    @staticmethod
    def _overlap(start: int, length: int, target_start: int, target_end: int) -> bool:
        effective_end = start + max(length, 1) - 1
        return start <= target_end and effective_end >= target_start

    def verify(self, session_id: str) -> Evidence:
        directory = self._session_dir(session_id)
        with session_lock(directory):
            session = self._load_session(session_id)
            if session.state not in {SessionState.RESULT_SUBMITTED, SessionState.VERIFYING, SessionState.HUMAN_REVIEW}:
                raise DocGateError("INVALID_STATE_TRANSITION", "当前状态不能生成证据。", status=409)
            round_dir = self._round_dir(session)
            round_data = read_model(round_dir / "round.json", Round)
            bundle = read_model(directory / "tasks.json", TaskBundle)
            receipt = read_model(round_dir / "receipt.json", Receipt)
            before = (round_dir / "baseline.md").read_text("utf-8")
            after = (round_dir / "result.md").read_text("utf-8")
            was_review = session.state == SessionState.HUMAN_REVIEW
            if not was_review:
                self._transition(session, SessionState.VERIFYING)
                self._save_session(session)
            hunks = self._diff_hunks(round_data.round_id, before, after)
            receipt_by_task = {item.task_id: item for item in receipt.tasks}
            for hunk in hunks:
                associations: list[Association] = []
                for task in bundle.tasks:
                    loc = task.locator
                    if loc.locator_status == LocatorStatus.UNIQUE and loc.start_line and loc.end_line and self._overlap(hunk.old_start, hunk.old_lines, loc.start_line, loc.end_line):
                        associations.append(Association(task_id=task.task_id, confidence="certain", methods=["base_range_overlap", "unique_quote"], reasons=["hunk 与唯一锚点的基线行区间重叠"])); continue
                    distance = min(abs(hunk.old_start - (loc.start_line or -1000)), abs(hunk.old_start - (loc.end_line or -1000)))
                    if loc.locator_status == LocatorStatus.UNIQUE and distance <= 3:
                        associations.append(Association(task_id=task.task_id, confidence="likely", methods=["near_unique_quote"], reasons=["hunk 距离唯一锚点不超过 3 行"])); continue
                    claimed = receipt_by_task[task.task_id].claimed_changes
                    if any(self._overlap(hunk.new_start, hunk.new_lines, item.start_line, item.end_line) for item in claimed):
                        associations.append(Association(task_id=task.task_id, confidence="weak", methods=["agent_claimed_range"], reasons=["只有不可信的 Agent 声明范围支持关联"]))
                hunk.associated_tasks = associations
                hunk.unattributed = not associations or all(item.confidence == "weak" for item in associations)
            checks: list[Check] = []
            def add(rule: str, subject_type: str, subject_id: str, status: str, message: str, **evidence: Any) -> None:
                checks.append(Check(rule_id=rule, subject_type=subject_type, subject_id=subject_id, status=status, message=message, evidence=evidence))
            add("DG-HASH-001", "round", round_data.round_id, "pass" if receipt.base_hash == round_data.base_hash else "fail", "回执基线 hash 与轮次基线一致。" if receipt.base_hash == round_data.base_hash else "回执基线 hash 不一致。")
            add("DG-HASH-002", "round", round_data.round_id, "pass" if receipt.result_hash == sha256_bytes(after.encode()) else "fail", "回执结果 hash 与结果快照一致。" if receipt.result_hash == sha256_bytes(after.encode()) else "回执结果 hash 与结果快照不一致。")
            addressed = any(item.outcome.value == "addressed" for item in receipt.tasks)
            add("DG-DIFF-001", "round", round_data.round_id, "fail" if addressed and not hunks else "pass", "存在真实文件变化。" if hunks else "Agent 声称完成，但文件没有变化。")
            add("DG-TASK-001", "round", round_data.round_id, "pass", "回执恰好覆盖每个活跃任务。")
            for task in bundle.tasks:
                related = [assoc for h in hunks for assoc in h.associated_tasks if assoc.task_id == task.task_id and assoc.confidence in {"certain", "likely"}]
                outcome = receipt_by_task[task.task_id].outcome.value
                status = "pass" if outcome != "addressed" or related else ("uncertain" if task.locator.locator_status != LocatorStatus.UNIQUE else "fail")
                add("DG-TASK-002", "task", task.task_id, status, "任务有客观 hunk 支持。" if related else "任务没有 certain/likely hunk 支持。")
                loc_status = "pass" if task.locator.locator_status == LocatorStatus.UNIQUE else "uncertain"
                add("DG-LOC-001", "task", task.task_id, loc_status, f"定位状态：{task.locator.locator_status.value}。")
                for claimed in receipt_by_task[task.task_id].claimed_changes:
                    touched = any(self._overlap(h.new_start, h.new_lines, claimed.start_line, claimed.end_line) for h in hunks)
                    add("DG-CLAIM-001", "task", task.task_id, "pass" if touched else "fail", "声明范围触达真实 hunk。" if touched else "声明范围没有真实 Diff。")
            try:
                MarkdownIt("commonmark").parse(after)
                md_status = "pass"
            except Exception:
                md_status = "fail"
            add("DG-MD-001", "round", round_data.round_id, md_status, "Markdown 可以解析。" if md_status == "pass" else "Markdown 解析失败。")
            fm_status = "pass"
            if before.startswith("---"):
                try:
                    parsed = frontmatter.loads(after)
                    if not after.startswith("---") or not isinstance(parsed.metadata, dict): fm_status = "fail"
                except Exception:
                    fm_status = "fail"
            add("DG-FM-001", "round", round_data.round_id, fm_status, "front matter 保持可解析。" if fm_status == "pass" else "原有 front matter 已损坏。")
            unattributed = [h for h in hunks if h.unattributed]
            add("DG-SCOPE-001", "round", round_data.round_id, "warning" if unattributed else "pass", "存在未归因修改，需要人工决定。" if unattributed else "所有 hunk 均有客观任务关联。", hunk_ids=[h.hunk_id for h in unattributed])
            _, _, current = safe_markdown_path(self.root, session.source_path, self.max_bytes)
            stable = sha256_bytes(current) == round_data.result_hash
            add("DG-BASE-001", "round", round_data.round_id, "pass" if stable else "fail", "源文件与结果快照一致。" if stable else "验证后源文件继续发生了变化。")
            evidence = Evidence(session_id=session_id, round_id=round_data.round_id, checks=checks, hunks=hunks, generated_at=now_utc())
            atomic_json(round_dir / "diff.json", {"schema_version": 1, "hunks": [h.model_dump(mode="json") for h in hunks]})
            atomic_json(round_dir / "evidence.json", evidence)
            if not was_review:
                self._transition(session, SessionState.HUMAN_REVIEW)
            self._save_session(session)
            return evidence

    def get_detail(self, session_id: str) -> dict[str, Any]:
        session = self._load_session(session_id)
        directory, round_dir = self._session_dir(session_id), self._round_dir(session)
        result: dict[str, Any] = {"session": session, "tasks": None, "receipt": None, "evidence": None, "decisions": Decisions(), "legal_actions": self.legal_actions(session)}
        for key, path, model in [
            ("tasks", directory / "tasks.json", TaskBundle),
            ("receipt", round_dir / "receipt.json", Receipt),
            ("evidence", round_dir / "evidence.json", Evidence),
            ("decisions", round_dir / "decisions.json", Decisions),
        ]:
            if path.exists(): result[key] = read_model(path, model)
        return result

    @staticmethod
    def legal_actions(session: Session) -> list[str]:
        return {
            SessionState.BASELINED: ["import_annotations"], SessionState.AGENT_WORKING: ["submit_receipt"],
            SessionState.RESULT_SUBMITTED: ["verify"], SessionState.VERIFYING: ["verify"],
            SessionState.HUMAN_REVIEW: ["decide", "rework", "accept"], SessionState.ACCEPTED: [],
        }.get(session.state, [])

    def decide_task(self, session_id: str, task_id: str, value: TaskDecisionInput) -> Decision:
        return self._decide(session_id, "task", task_id, value.decision, value.reason)

    def decide_hunk(self, session_id: str, hunk_id: str, value: HunkDecisionInput) -> Decision:
        return self._decide(session_id, "hunk", hunk_id, value.decision, value.reason)

    def _decide(self, session_id: str, subject_type: str, subject_id: str, decision: str, reason: str) -> Decision:
        directory = self._session_dir(session_id)
        with session_lock(directory):
            session = self._load_session(session_id)
            if session.state != SessionState.HUMAN_REVIEW:
                raise DocGateError("INVALID_STATE_TRANSITION", "当前状态不能保存人工决定。", status=409)
            round_dir = self._round_dir(session)
            if subject_type == "task":
                valid = {t.task_id for t in read_model(directory / "tasks.json", TaskBundle).tasks}
            else:
                valid = {h.hunk_id for h in read_model(round_dir / "evidence.json", Evidence).hunks if h.unattributed}
            if subject_id not in valid:
                raise DocGateError("SUBJECT_NOT_FOUND", "决策对象不存在。", status=404)
            decisions = read_model(round_dir / "decisions.json", Decisions)
            existing = next((d for d in decisions.decisions if d.subject_type == subject_type and d.subject_id == subject_id), None)
            timestamp = now_utc()
            if existing:
                existing.decision, existing.reason, existing.updated_at = decision, reason, timestamp
                saved = existing
            else:
                saved = Decision(decision_id=_id("dec"), subject_type=subject_type, subject_id=subject_id, decision=decision, reason=reason, decided_at=timestamp, updated_at=timestamp)
                decisions.decisions.append(saved)
            atomic_json(round_dir / "decisions.json", decisions)
            return saved

    def _acceptance_gaps(self, session: Session) -> list[str]:
        directory, round_dir = self._session_dir(session.session_id), self._round_dir(session)
        bundle, evidence, decisions = read_model(directory / "tasks.json", TaskBundle), read_model(round_dir / "evidence.json", Evidence), read_model(round_dir / "decisions.json", Decisions)
        by_subject = {(d.subject_type, d.subject_id): d for d in decisions.decisions}
        gaps = [t.task_id for t in bundle.tasks if by_subject.get(("task", t.task_id), None) is None or by_subject[("task", t.task_id)].decision != "accepted"]
        gaps += [h.hunk_id for h in evidence.hunks if h.unattributed and (by_subject.get(("hunk", h.hunk_id), None) is None or by_subject[("hunk", h.hunk_id)].decision != "accepted")]
        blocking = {"DG-HASH-001", "DG-HASH-002", "DG-MD-001", "DG-FM-001", "DG-BASE-001"}
        gaps += [c.rule_id for c in evidence.checks if c.rule_id in blocking and c.status == "fail"]
        _, _, current = safe_markdown_path(self.root, session.source_path, self.max_bytes)
        round_data = read_model(round_dir / "round.json", Round)
        if sha256_bytes(current) != round_data.result_hash: gaps.append("DG-BASE-001")
        return sorted(set(gaps))

    def accept(self, session_id: str) -> Session:
        directory = self._session_dir(session_id)
        with session_lock(directory):
            session = self._load_session(session_id)
            if session.state != SessionState.HUMAN_REVIEW:
                raise DocGateError("INVALID_STATE_TRANSITION", "当前状态不能接受会话。", status=409)
            gaps = self._acceptance_gaps(session)
            if gaps:
                raise DocGateError("ACCEPTANCE_BLOCKED", "仍有未接受的任务、修改或阻断检查。", status=409, details={"pending": gaps})
            self._transition(session, SessionState.ACCEPTED)
            self._save_session(session)
            return session

    def rework(self, session_id: str) -> Session:
        directory = self._session_dir(session_id)
        with session_lock(directory):
            session = self._load_session(session_id)
            if session.state != SessionState.HUMAN_REVIEW:
                raise DocGateError("INVALID_STATE_TRANSITION", "当前状态不能生成返工包。", status=409)
            old_round_dir = self._round_dir(session)
            bundle, evidence, decisions = read_model(directory / "tasks.json", TaskBundle), read_model(old_round_dir / "evidence.json", Evidence), read_model(old_round_dir / "decisions.json", Decisions)
            by_subject = {(d.subject_type, d.subject_id): d for d in decisions.decisions}
            active = [t.model_copy(update={"human_status": HumanStatus.PENDING}) for t in bundle.tasks if by_subject.get(("task", t.task_id)) and by_subject[("task", t.task_id)].decision in {"rework_requested", "clarification_requested"}]
            reverted = [h.hunk_id for h in evidence.hunks if by_subject.get(("hunk", h.hunk_id)) and by_subject[("hunk", h.hunk_id)].decision == "revert_requested"]
            if not active and not reverted:
                raise DocGateError("NO_REWORK_ITEMS", "没有需要返工的项目。", status=409)
            protected = [t.task_id for t in bundle.tasks if by_subject.get(("task", t.task_id)) and by_subject[("task", t.task_id)].decision == "accepted"]
            old_result = (old_round_dir / "result.md").read_bytes()
            old_round_hashes = {p.name: sha256_bytes(p.read_bytes()) for p in old_round_dir.iterdir() if p.is_file()}
            self._transition(session, SessionState.REWORK)
            self._save_session(session)
            session.active_round_number += 1
            session.active_round_id = _id("rnd")
            new_round_dir = self._round_dir(session)
            timestamp, digest = now_utc(), sha256_bytes(old_result)
            new_round = Round(round_id=session.active_round_id, number=session.active_round_number, base_hash=digest, created_at=timestamp)
            atomic_write(new_round_dir / "baseline.md", old_result)
            atomic_json(new_round_dir / "round.json", new_round)
            atomic_json(new_round_dir / "decisions.json", Decisions())
            new_bundle = TaskBundle(session_id=session_id, base_hash=digest, tasks=active)
            atomic_json(directory / "tasks.json", new_bundle)
            self._write_receipt_schema(new_round_dir)
            self._write_brief(session, new_round, new_bundle, new_round_dir, rework=True, protected=protected + [f"revert hunk {x}" for x in reverted])
            for name, digest_before in old_round_hashes.items():
                if sha256_bytes((old_round_dir / name).read_bytes()) != digest_before:
                    raise DocGateError("IMMUTABILITY_VIOLATION", "历史轮次发生意外变化。", status=500)
            self._transition(session, SessionState.AGENT_WORKING)
            self._save_session(session)
            return session
