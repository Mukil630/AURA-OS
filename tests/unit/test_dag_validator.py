"""Unit tests for DAGValidator and Topological Sorting."""
import pytest
from app.core.contracts.task_step import TaskStepContract
from app.core.dag import CyclicDependencyError, DAGValidator, InvalidDependencyError
from app.core.enums import AgentType


def test_linear_dag_topological_sort():
    s1 = TaskStepContract(workflow_id="wf_1", step_index=0, name="s1", agent_type=AgentType.CODING, tool_name="t1")
    s2 = TaskStepContract(workflow_id="wf_1", step_index=1, name="s2", agent_type=AgentType.CODING, tool_name="t2", dependencies=[s1.step_id])
    s3 = TaskStepContract(workflow_id="wf_1", step_index=2, name="s3", agent_type=AgentType.CODING, tool_name="t3", dependencies=[s2.step_id])

    # Pass in shuffled order
    shuffled = [s3, s1, s2]
    sorted_steps = DAGValidator.validate_and_sort(shuffled)

    assert len(sorted_steps) == 3
    assert [s.step_id for s in sorted_steps] == [s1.step_id, s2.step_id, s3.step_id]
    assert sorted_steps[0].step_index == 0
    assert sorted_steps[1].step_index == 1
    assert sorted_steps[2].step_index == 2


def test_branched_dag_parallel_batches():
    # s1 -> s2, s1 -> s3, (s2, s3) -> s4
    s1 = TaskStepContract(workflow_id="wf_1", step_index=0, name="s1", agent_type=AgentType.CODING, tool_name="t1")
    s2 = TaskStepContract(workflow_id="wf_1", step_index=1, name="s2", agent_type=AgentType.CODING, tool_name="t2", dependencies=[s1.step_id])
    s3 = TaskStepContract(workflow_id="wf_1", step_index=2, name="s3", agent_type=AgentType.RESEARCH, tool_name="t3", dependencies=[s1.step_id])
    s4 = TaskStepContract(workflow_id="wf_1", step_index=3, name="s4", agent_type=AgentType.COMMUNICATION, tool_name="t4", dependencies=[s2.step_id, s3.step_id])

    batches = DAGValidator.resolve_execution_batches([s1, s2, s3, s4])
    assert len(batches) == 3
    assert batches[0] == [s1.step_id]
    assert set(batches[1]) == {s2.step_id, s3.step_id}
    assert batches[2] == [s4.step_id]


def test_cyclic_dag_rejection():
    # s1 -> s2 -> s1 (Cycle)
    s1 = TaskStepContract(workflow_id="wf_1", step_index=0, name="s1", agent_type=AgentType.CODING, tool_name="t1")
    s2 = TaskStepContract(workflow_id="wf_1", step_index=1, name="s2", agent_type=AgentType.CODING, tool_name="t2", dependencies=[s1.step_id])
    # Add backward edge
    s1_cyclic = s1.model_copy(update={"dependencies": [s2.step_id]})

    with pytest.raises(CyclicDependencyError) as exc_info:
        DAGValidator.validate_and_sort([s1_cyclic, s2])
    assert "Circular dependency" in str(exc_info.value)


def test_invalid_dependency_reference():
    s1 = TaskStepContract(workflow_id="wf_1", step_index=0, name="s1", agent_type=AgentType.CODING, tool_name="t1", dependencies=["non_existent_step_id"])

    with pytest.raises(InvalidDependencyError) as exc_info:
        DAGValidator.validate_and_sort([s1])
    assert "non-existent" in str(exc_info.value)
