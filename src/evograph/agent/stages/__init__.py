"""Multi-stage analysis agents.

Each stage corresponds to a learning phase from CODEGRAPH_PRD:
- OverviewAgent  (Stage 1: 先看门道)
- MainFlowAgent  (Stage 2: 跑通主线)
- ShowcaseAgent  (Stage 3: 拆它绝活)
- TakeawayAgent  (Stage 4: 抄走一招)

Agents are orchestrated by AnalysisOrchestrator with explicit context-passing.
"""

from evograph.agent.stages.overview_agent import OverviewAgent
from evograph.agent.stages.mainflow_agent import MainFlowAgent
from evograph.agent.stages.showcase_agent import ShowcaseAgent
from evograph.agent.stages.takeaway_agent import TakeawayAgent

__all__ = ["OverviewAgent", "MainFlowAgent", "ShowcaseAgent", "TakeawayAgent"]
