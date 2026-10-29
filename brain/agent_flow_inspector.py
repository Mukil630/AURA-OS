"""
Agent Flow Inspector (agent_flow_inspector.py)
Utility to trace, debug, and inspect the end-to-end flow of any task through
the multi-agent swarm. Combines AgentTracer (spans + decision lineage),
AgentHealthRegistry (circuit + latency), and ExecutionSwarmController (audit log).
"""
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List

from app.observability.tracer import default_tracer
from brain.agent_health_monitor import health_registry

logger = logging.getLogger("AgentFlowInspector")


class FlowTrace:
    """
    A self-contained trace session for one task from ingress to completion.
    Captures: routing decision, agent dispatch chain, tool calls, verification,
    health metrics, and final result/error.
    """

    def __init__(self, task_id: str, user_query: str, user_id: str = "Mukil"):
        self.task_id = task_id
        self.user_query = user_query
        self.user_id = user_id
        self.started_at = datetime.now()
        self.steps: List[Dict[str, Any]] = []
        self.decisions: List[Dict[str, Any]] = []
        self._trace = default_tracer.create_trace(
            task_id=task_id,
            user_id=user_id,
            workflow_id="swarm_dispatch"
        )

    def log_step(self, stage: str, component: str, agent: str = "", action: str = "",
                 status: str = "ok", decision: Optional[str] = None, metadata: Optional[Dict] = None):
        """Log a pipeline step in the flow."""
        span = self._trace.start_span(
            name=stage,
            component=component,
            decision_rationale=decision,
            metadata=metadata or {},
        )
        step = {
            "stage": stage,
            "component": component,
            "agent": agent,
            "action": action,
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "decision": decision,
            "metadata": metadata or {},
        }
        self.steps.append(step)
        if decision:
            self._trace.record_decision(
                stage=stage,
                chosen_option=f"{agent}:{action}" if agent else action,
                why=decision,
                constraints=metadata,
            )
        span.finish(status=status)
        logger.info(f"[Flow:{self.task_id}] {stage} | {component} | {agent} | {action} | {status}")

    def log_decision(self, stage: str, chosen: str, why: str, constraints: Optional[Dict] = None):
        """Log a significant architectural decision (why this agent/tool was chosen)."""
        self._trace.record_decision(stage, chosen, why, constraints)
        self.decisions.append({
            "timestamp": datetime.now().isoformat(),
            "stage": stage,
            "decision": chosen,
            "rationale": why,
            "constraints": constraints or {},
        })

    def finalize(self, status: str = "completed", final_output: Optional[str] = None):
        self._trace.complete_trace(status=status)
        self.final_status = status
        self.final_output = final_output

    def to_report(self) -> Dict[str, Any]:
        """Generate a human-readable flow report."""
        health_snapshot = health_registry.get_snapshot()
        unhealthy = health_registry.get_unhealthy_agents()

        return {
            "task_id": self.task_id,
            "user_query": self.user_query,
            "started_at": self.started_at.isoformat(),
            "final_status": getattr(self, "final_status", "unknown"),
            "pipeline_steps": [
                {
                    "stage": s["stage"],
                    "component": s["component"],
                    "agent": s["agent"],
                    "action": s["action"],
                    "status": s["status"],
                    "decision": s["decision"],
                    "agent_health_snapshot": self._agent_health_snapshot(s["agent"]),
                }
                for s in self.steps
            ],
            "decision_lineage": self._trace.decision_lineage,
            "spans": [
                {
                    "name": sp.name,
                    "component": sp.component,
                    "status": sp.status,
                    "duration_ms": sp.duration_ms,
                    "decision_rationale": sp.decision_rationale,
                    "error_message": sp.error_message,
                }
                for sp in self._trace.spans
            ],
            "total_duration_ms": self._trace.total_duration_ms,
            "overall_status": self._trace.overall_status,
            "swarm_health": {
                "unhealthy_agents": unhealthy,
                "agent_counts": {
                    n: h["total_calls"] for n, h in health_snapshot.items()
                },
                "agent_failures": {
                    n: h["failed_calls"] for n, h in health_snapshot.items()
                },
                "agent_avg_latency_ms": {
                    n: h["avg_latency_ms"] for n, h in health_snapshot.items()
                },
            },
            "circuit_states": {
                n: h["circuit_breaker"]["state"] for n, h in health_snapshot.items()
            },
        }

    @staticmethod
    def _agent_health_snapshot(agent_name: str) -> Optional[Dict]:
        h = health_registry.get_health(agent_name)
        if h:
            return {
                "status": h.status,
                "total_calls": h.total_calls,
                "failed_calls": h.failed_calls,
                "avg_latency_ms": round(h.avg_latency_ms, 2),
                "circuit_state": h.circuit_breaker.get_metrics()["state"],
            }
        return None

    def print_report(self):
        report = self.to_report()
        print("=" * 80)
        print(f"AGENT FLOW REPORT — Task: {report['task_id']}")
        print(f"User Query: {report['user_query']}")
        print(f"Status: {report['final_status']} | Duration: {report['total_duration_ms']:.0f}ms")
        print("-" * 80)
        for span in report["spans"]:
            print(f"  [{span['duration_ms']:>7.1f}ms] {span['name']:<30} {span['component']:<25} {span['status']}")
            if span["decision_rationale"]:
                print(f"         ↳ Decision: {span['decision_rationale']}")
            if span["error_message"]:
                print(f"         ✗ Error: {span['error_message']}")
        print("-" * 80)
        print("DECISION LINEAGE:")
        for d in report["decision_lineage"]:
            print(f"  • {d['stage']}: {d['decision']} — {d['rationale']}")
        print("-" * 80)
        print("SWARM HEALTH:")
        for agent, metrics in report["swarm_health"]["agent_counts"].items():
            failures = report["swarm_health"]["agent_failures"].get(agent, 0)
            latency = report["swarm_health"]["agent_avg_latency_ms"].get(agent, 0)
            cb_state = report["circuit_states"].get(agent, "UNKNOWN")
            print(f"  {agent:<20} calls={metrics}  failures={failures}  avg_latency={latency:.1f}ms  circuit={cb_state}")
        print("=" * 80)


async def trace_dispatch(task_id: str, user_query: str, orchestrator, cognitive_route) -> FlowTrace:
    """
    End-to-end traced dispatch:
    1. Log the routing decision (which track/agent chosen)
    2. Dispatch to orchestrator with flow tracing
    3. Capture result, health, circuit state
    4. Return the complete FlowTrace
    """
    flow = FlowTrace(task_id, user_query)

    # Step 1: Routing decision
    flow.log_step(
        stage="routing",
        component="CognitiveRouter",
        action=cognitive_route.track,
        decision=f"Selected track={cognitive_route.track}, agent={cognitive_route.target_swarm_agent}",
        metadata={"confidence": cognitive_route.confidence, "goal": cognitive_route.goal_summary},
    )
    flow.log_decision(
        stage="agent_selection",
        chosen=cognitive_route.target_swarm_agent or "NONE",
        why=f"Confidence {cognitive_route.confidence:.2f} based on intent classification",
    )

    # Step 2: Dispatch
    result = await orchestrator.dispatch(
        target_agent=cognitive_route.target_swarm_agent,
        action=cognitive_route.track,
        payload={"description": cognitive_route.goal_summary},
    )

    flow.log_step(
        stage="agent_execution",
        component="SwarmOrchestrator",
        agent=cognitive_route.target_swarm_agent or "N/A",
        action=cognitive_route.track,
        status=result.status,
        decision=f"Agent returned status={result.status}",
        metadata={"error": result.error} if result.error else {},
    )

    if result.status == "FAILED":
        flow.log_decision(
            stage="error_handling",
            chosen="failover_attempted" if result.result and result.result.get("backup_delegated_from") else "no_recovery",
            why=result.error or "Unknown failure",
        )

    # Step 3: Finalize
    flow.finalize(status=result.status, final_output=result.result.get("summary", "") if result.result else "")
    return flow
