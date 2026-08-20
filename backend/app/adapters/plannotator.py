from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from ..errors import DocGateError
from ..models import AnnotationImport, GenericAnnotation

PLANNOTATOR_VERSION = "v0.24.2"


def parse_feedback(feedback: str) -> list[GenericAnnotation]:
    """Parse the v0.24.2 JSON envelope's structured Markdown feedback."""
    sections = re.split(r"(?m)^##\s+\d+\.\s+", feedback)[1:]
    annotations: list[GenericAnnotation] = []
    for index, section in enumerate(sections, 1):
        lines = section.strip().splitlines()
        if not lines:
            continue
        title = lines[0].strip()
        body = "\n".join(lines[1:])
        fenced = re.search(r"```(?:\w+)?\n(.*?)\n```", body, re.S)
        inline = re.search(r"`([^`]+)`", body)
        titled = re.search(r'Feedback on:\s*[“\"](.+?)[”\"]', title)
        quote = (fenced.group(1) if fenced else inline.group(1) if inline else titled.group(1) if titled else "").strip()
        comments = [re.sub(r"^>\s?", "", line).strip() for line in lines[1:] if line.lstrip().startswith(">")]
        instruction = "\n".join(item for item in comments if item).strip()
        if title.lower().startswith("remove") and not instruction:
            instruction = title
        if not quote or not instruction:
            raise DocGateError("PLANNOTATOR_CONTRACT_ERROR", "Plannotator 输出缺少可定位的选中文本或批注意见。")
        annotations.append(GenericAnnotation(id=f"plannotator-{index}", instruction=instruction, exact_quote=quote))
    if not annotations:
        raise DocGateError("PLANNOTATOR_CONTRACT_ERROR", "Plannotator 未返回可导入的文本批注。")
    return annotations


def parse_stdout(payload: str) -> AnnotationImport:
    try:
        value: dict[str, Any] = json.loads(payload.strip())
    except json.JSONDecodeError as exc:
        raise DocGateError("PLANNOTATOR_CONTRACT_ERROR", "Plannotator 未返回合法 JSON。") from exc
    if set(value) - {"decision", "feedback"} or value.get("decision") not in {"approved", "annotated", "dismissed"}:
        raise DocGateError("PLANNOTATOR_CONTRACT_ERROR", "Plannotator JSON 决策契约不兼容。")
    if value["decision"] != "annotated":
        raise DocGateError("NO_ANNOTATIONS", "本次 Plannotator 审阅没有发送批注。")
    feedback = value.get("feedback")
    if not isinstance(feedback, str):
        raise DocGateError("PLANNOTATOR_CONTRACT_ERROR", "Plannotator annotated 决策缺少 feedback。")
    return AnnotationImport(adapter="plannotator", annotations=parse_feedback(feedback), raw={"decision": "annotated"})


def run(command: str, document: Path) -> AnnotationImport:
    try:
        completed = subprocess.run(
            [command, "annotate", str(document), "--gate", "--json"],
            check=False,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError as exc:
        raise DocGateError("PLANNOTATOR_UNAVAILABLE", "未找到已锁定的 Plannotator v0.24.2；请先运行本地安装脚本。") from exc
    if completed.returncode != 0:
        raise DocGateError("PLANNOTATOR_FAILED", "Plannotator 运行失败；请检查本地窗口和版本。")
    return parse_stdout(completed.stdout)

