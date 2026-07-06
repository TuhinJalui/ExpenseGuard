"""
trace.py — Reasoning Trace

Captures the full internal reasoning trail across all three agents
for a single pipeline run.

This is what judges watch in the demo video to distinguish "agentic
behavior" from "one big prompt with if-statements." Each entry records:
  - Which agent ran
  - What inputs it received
  - What tools/MCP calls it made (with args + results)
  - What decision it produced and why

The trace is attached to every PipelineResult and surfaced in the
Audit Trail UI. It answers the question: "Why did the system decide X?"
"""

from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any, Optional
from datetime import datetime, UTC


class ToolCall(BaseModel):
    """A single MCP tool call made by an agent."""
    tool_name: str
    arguments: dict[str, Any]
    result: dict[str, Any]
    duration_ms: Optional[float] = None


class AgentStep(BaseModel):
    """One agent's execution record within the pipeline."""
    agent_name: str                             # "Intake Agent", "Policy Agent", etc.
    started_at: str
    inputs: dict[str, Any]                      # What the agent received
    tool_calls: list[ToolCall] = Field(default_factory=list)  # MCP calls made
    output: dict[str, Any]                      # What the agent produced
    reasoning: str                              # Plain-language explanation


class ReasoningTrace(BaseModel):
    """
    Full reasoning trace for one pipeline run.
    Immutable after the run completes.
    """
    expense_id: str
    pipeline_started_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    steps: list[AgentStep] = Field(default_factory=list)

    def add_step(self, step: AgentStep):
        self.steps.append(step)

    def summary(self) -> str:
        """One-line summary of the pipeline run for logs."""
        if not self.steps:
            return f"[{self.expense_id}] No steps recorded"
        last = self.steps[-1]
        decision = last.output.get("decision", "unknown")
        return (
            f"[{self.expense_id}] "
            + " → ".join(s.agent_name for s in self.steps)
            + f" → {decision.upper()}"
        )

    def to_display_dict(self) -> dict:
        """Serialises to a dict suitable for the Audit Trail UI."""
        return self.model_dump()
