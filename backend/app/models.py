from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, model_validator

SCHEMA_VERSION = 1
Hash = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


def validate_timestamp(value: str) -> str:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("timestamp must be a valid UTC ISO 8601 value") from exc
    return value


Timestamp = Annotated[
    str,
    StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"),
    AfterValidator(validate_timestamp),
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SessionState(StrEnum):
    BASELINED = "baselined"
    FEEDBACK_READY = "feedback_ready"
    AGENT_WORKING = "agent_working"
    RESULT_SUBMITTED = "result_submitted"
    VERIFYING = "verifying"
    HUMAN_REVIEW = "human_review"
    REWORK = "rework"
    ACCEPTED = "accepted"


class LocatorStatus(StrEnum):
    UNIQUE = "unique"
    AMBIGUOUS = "ambiguous"
    MISSING = "missing"


class HumanStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REWORK = "rework_requested"
    CLARIFICATION = "clarification_requested"


class AgentOutcome(StrEnum):
    ADDRESSED = "addressed"
    PARTIAL = "partial"
    CLARIFICATION = "clarification"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


class AnnotationSource(StrictModel):
    adapter: str
    external_id: str
    raw_type: str = "text_selection"


class Locator(StrictModel):
    exact_quote: str
    prefix: str = ""
    suffix: str = ""
    occurrence: int | None = Field(default=None, ge=1)
    start_line: int | None = Field(default=None, ge=1)
    end_line: int | None = Field(default=None, ge=1)
    heading_path: list[str] = Field(default_factory=list)
    locator_status: LocatorStatus


class TaskScope(StrictModel):
    allowed: str = "优先修改锚点段落；必要时可修改同一小节。"
    forbidden: str = "不得改动其他章节、front matter 或已接受任务。"


class ChangeTask(StrictModel):
    task_id: str = Field(pattern=r"^tsk_[a-z0-9]+$")
    instruction: str = Field(min_length=1)
    annotation_source: AnnotationSource
    locator: Locator
    scope: TaskScope = Field(default_factory=TaskScope)
    created_at: Timestamp
    human_status: HumanStatus = HumanStatus.PENDING


class TaskBundle(StrictModel):
    schema_version: Literal[1] = SCHEMA_VERSION
    session_id: str
    base_hash: Hash
    tasks: list[ChangeTask]


class Session(StrictModel):
    schema_version: Literal[1] = SCHEMA_VERSION
    session_id: str
    source_path: str
    initial_source_hash: Hash
    state: SessionState
    active_round_id: str
    active_round_number: int = Field(ge=1)
    created_at: Timestamp
    updated_at: Timestamp


class Round(StrictModel):
    schema_version: Literal[1] = SCHEMA_VERSION
    round_id: str
    number: int = Field(ge=1)
    base_hash: Hash
    result_hash: Hash | None = None
    created_at: Timestamp
    submitted_at: Timestamp | None = None


class GenericAnnotation(StrictModel):
    id: str = Field(min_length=1)
    instruction: str = Field(min_length=1)
    exact_quote: str = Field(min_length=1)
    occurrence: int | None = Field(default=None, ge=1)
    prefix: str = ""
    suffix: str = ""
    raw_type: str = "text_selection"


class AnnotationImport(StrictModel):
    schema_version: Literal[1] = SCHEMA_VERSION
    adapter: Literal["generic", "plannotator"] = "generic"
    annotations: list[GenericAnnotation] = Field(min_length=1)
    raw: dict[str, Any] | None = None


class ClaimedChange(StrictModel):
    path: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)


class ReceiptTask(StrictModel):
    task_id: str
    outcome: AgentOutcome
    summary: str = ""
    claimed_changes: list[ClaimedChange] = Field(default_factory=list)
    notes: str | None = None

    @model_validator(mode="after")
    def validate_outcome(self):
        if self.outcome == AgentOutcome.ADDRESSED and not self.claimed_changes:
            raise ValueError("addressed requires claimed_changes")
        if self.outcome != AgentOutcome.ADDRESSED and not self.notes:
            raise ValueError(f"{self.outcome.value} requires notes")
        return self


class AgentInfo(StrictModel):
    name: str
    version: str | None = None


class Receipt(StrictModel):
    schema_version: Literal[1] = SCHEMA_VERSION
    session_id: str
    round_id: str
    base_hash: Hash
    result_hash: Hash
    agent: AgentInfo
    tasks: list[ReceiptTask]
    submitted_at: Timestamp


class Association(StrictModel):
    task_id: str
    confidence: Literal["certain", "likely", "weak"]
    methods: list[str]
    reasons: list[str]


class DiffHunk(StrictModel):
    hunk_id: str
    old_start: int
    old_lines: int
    new_start: int
    new_lines: int
    before: str
    after: str
    associated_tasks: list[Association] = Field(default_factory=list)
    unattributed: bool = False


class Check(StrictModel):
    rule_id: str
    subject_type: Literal["round", "task", "hunk"]
    subject_id: str
    status: Literal["pass", "warning", "fail", "uncertain"]
    message: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class Evidence(StrictModel):
    schema_version: Literal[1] = SCHEMA_VERSION
    session_id: str
    round_id: str
    checks: list[Check]
    hunks: list[DiffHunk]
    generated_at: Timestamp


class Decision(StrictModel):
    decision_id: str
    subject_type: Literal["task", "hunk"]
    subject_id: str
    decision: Literal["accepted", "rework_requested", "clarification_requested", "revert_requested"]
    reason: str = ""
    decided_at: Timestamp
    updated_at: Timestamp


class Decisions(StrictModel):
    schema_version: Literal[1] = SCHEMA_VERSION
    decisions: list[Decision] = Field(default_factory=list)


class TaskDecisionInput(StrictModel):
    decision: Literal["accepted", "rework_requested", "clarification_requested"]
    reason: str = ""


class HunkDecisionInput(StrictModel):
    decision: Literal["accepted", "revert_requested"]
    reason: str = ""


class SessionCreateInput(StrictModel):
    source_path: str = Field(min_length=1)


class SessionSummary(StrictModel):
    session_id: str
    source_path: str
    state: SessionState
    active_round_id: str
    active_round_number: int
    updated_at: Timestamp
    tasks_total: int
    task_decisions_completed: int
    unattributed_count: int


class SessionListResponse(StrictModel):
    sessions: list[SessionSummary]


class SessionDetailResponse(StrictModel):
    session: Session
    tasks: TaskBundle | None = None
    receipt: Receipt | None = None
    evidence: Evidence | None = None
    decisions: Decisions
    legal_actions: list[str]


class HealthResponse(StrictModel):
    status: Literal["ok"] = "ok"
    version: str
    schema_version: Literal[1] = SCHEMA_VERSION


class ActionResponse(StrictModel):
    session: Session
