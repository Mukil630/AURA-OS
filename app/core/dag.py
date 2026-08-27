"""Directed Acyclic Graph (DAG) Validation and Topological Sorting Subsystem."""
from collections import defaultdict, deque
from typing import Dict, List, Set, Tuple

from app.core.contracts.task_step import TaskStepContract
from app.core.models.plan import StepDependency


class CyclicDependencyError(Exception):
    """Raised when an execution graph contains a circular/cyclic dependency."""
    pass


class InvalidDependencyError(Exception):
    """Raised when a step references a non-existent parent step ID."""
    pass


class DAGValidator:
    """
    Validates execution graphs, detects circular dependencies,
    and resolves valid topological execution sequences for parallel and sequential workflows.
    """

    @classmethod
    def validate_and_sort(
        cls,
        steps: List[TaskStepContract],
        dependencies: List[StepDependency] | None = None,
    ) -> List[TaskStepContract]:
        """
        Validate that the steps and dependencies form a valid Directed Acyclic Graph (DAG).
        Returns the steps in topological execution order.
        Raises CyclicDependencyError or InvalidDependencyError if invalid.
        """
        if not steps:
            return []

        step_map: Dict[str, TaskStepContract] = {s.step_id: s for s in steps}
        step_ids: Set[str] = set(step_map.keys())

        # Build adjacency graph and in-degree counts
        adj: Dict[str, List[str]] = defaultdict(list)
        in_degree: Dict[str, int] = {sid: 0 for sid in step_ids}

        # 1. Register dependencies declared inside TaskStepContract.dependencies
        for step in steps:
            for parent_id in step.dependencies:
                if parent_id not in step_ids:
                    raise InvalidDependencyError(
                        f"Step '{step.step_id}' ({step.name}) references non-existent dependency '{parent_id}'."
                    )
                adj[parent_id].append(step.step_id)
                in_degree[step.step_id] += 1

        # 2. Register explicit StepDependency objects if provided
        if dependencies:
            for dep in dependencies:
                if dep.parent_step_id not in step_ids:
                    raise InvalidDependencyError(f"Dependency references non-existent parent '{dep.parent_step_id}'.")
                if dep.child_step_id not in step_ids:
                    raise InvalidDependencyError(f"Dependency references non-existent child '{dep.child_step_id}'.")
                # Avoid duplicate edge count if already in step.dependencies
                if dep.child_step_id not in adj[dep.parent_step_id]:
                    adj[dep.parent_step_id].append(dep.child_step_id)
                    in_degree[dep.child_step_id] += 1

        # 3. Kahn's Algorithm for Topological Sorting & Cycle Detection
        queue: deque[str] = deque([sid for sid, deg in in_degree.items() if deg == 0])
        sorted_step_ids: List[str] = []

        while queue:
            curr = queue.popleft()
            sorted_step_ids.append(curr)

            for neighbor in adj[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # 4. If sorted count does not match total steps, a cycle exists
        if len(sorted_step_ids) != len(steps):
            unresolved = [sid for sid, deg in in_degree.items() if deg > 0]
            raise CyclicDependencyError(
                f"Circular dependency detected in execution graph involving steps: {unresolved}"
            )

        # Return steps ordered by topological order and assign updated step_index
        ordered_steps: List[TaskStepContract] = []
        for idx, sid in enumerate(sorted_step_ids):
            step = step_map[sid]
            ordered_step = step.model_copy(update={"step_index": idx})
            ordered_steps.append(ordered_step)

        return ordered_steps

    @classmethod
    def resolve_execution_batches(cls, steps: List[TaskStepContract]) -> List[List[str]]:
        """
        Group steps into parallel execution tiers.
        Steps in Tier 0 can run concurrently immediately; Tier 1 runs after Tier 0 completes, etc.
        """
        if not steps:
            return []

        step_ids = {s.step_id for s in steps}
        step_deps = {s.step_id: set(s.dependencies) for s in steps}

        completed: Set[str] = set()
        batches: List[List[str]] = []

        while len(completed) < len(steps):
            current_batch = [
                sid for sid, deps in step_deps.items()
                if sid not in completed and deps.issubset(completed)
            ]
            if not current_batch:
                raise CyclicDependencyError("Unresolvable dependency deadlock detected.")

            batches.append(current_batch)
            completed.update(current_batch)

        return batches
