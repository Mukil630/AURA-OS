"""Database integration tests for TaskRepository."""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.contracts.task import TaskContract
from app.core.enums import ChannelType, PriorityLevel, TaskStatus
from app.database.repositories.task_repo import TaskRepository


@pytest.mark.anyio
async def test_task_crud_lifecycle(test_db_session: AsyncSession):
    repo = TaskRepository(test_db_session)

    # 1. Create Task
    task_contract = TaskContract(
        user_id="user_test_1",
        raw_input="Check CI failures on AURA-OS",
        channel=ChannelType.VOICE,
        priority=PriorityLevel.HIGH,
    )
    saved_task = await repo.create_task(task_contract)
    assert saved_task.task_id == task_contract.task_id
    assert saved_task.status == TaskStatus.CREATED
    assert saved_task.user_id == "user_test_1"

    # 2. Get Task
    fetched = await repo.get_task(saved_task.task_id)
    assert fetched is not None
    assert fetched.task_id == saved_task.task_id
    assert fetched.raw_input == "Check CI failures on AURA-OS"

    # 3. Update Task Status
    updated = await repo.update_task_status(
        task_id=saved_task.task_id,
        status=TaskStatus.COMPLETED,
        result_summary="CI checks completed successfully.",
        result_data={"failed_runs": 0},
    )
    assert updated is not None
    assert updated.status == TaskStatus.COMPLETED
    assert updated.result_summary == "CI checks completed successfully."
    assert updated.result_data["failed_runs"] == 0
    assert updated.completed_at is not None

    # 4. List Tasks
    task_list = await repo.list_tasks(user_id="user_test_1")
    assert len(task_list) == 1
    assert task_list[0].task_id == saved_task.task_id

    # 5. Count Tasks
    count = await repo.count_tasks(user_id="user_test_1")
    assert count == 1
