"""Agents module — exports all 7 agents for M2.

Router → Coordinator → 3 Workers (FieldIoT, Agronomy, Resource) → Action → Narrative
"""
from agent_core.agents.action import ActionAgent
from agent_core.agents.agronomy_agent import AgronomyAgent
from agent_core.agents.coordinator import CoordinatorAgent
from agent_core.agents.field_iot_agent import FieldIoTAgent
from agent_core.agents.narrative import NarrativeAgent
from agent_core.agents.resource_agent import ResourceAgent
from agent_core.agents.router import RouterAgent

__all__ = [
    "RouterAgent",
    "CoordinatorAgent",
    "FieldIoTAgent",
    "AgronomyAgent",
    "ResourceAgent",
    "ActionAgent",
    "NarrativeAgent",
]
