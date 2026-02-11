"""Task-level checkpointing for resumable benchmark runs.

This module provides fault tolerance by tracking completed tasks and allowing
resumption from interruption points without repeating work.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from bench.logging import logger


class TaskID(BaseModel):
    """Unique identifier for a benchmark task."""

    suite: str
    target_id: str
    system: str
    variant: str
    msa_depth: int
    pass_index: int

    def to_key(self) -> str:
        """Convert to unique string key."""
        return f"{self.suite}|{self.target_id}|{self.system}|{self.variant}|{self.msa_depth}|{self.pass_index}"

    @classmethod
    def from_key(cls, key: str) -> "TaskID":
        """Parse from string key."""
        parts = key.split("|")
        if len(parts) != 6:
            raise ValueError(f"Invalid task key: {key}")

        return cls(
            suite=parts[0],
            target_id=parts[1],
            system=parts[2],
            variant=parts[3],
            msa_depth=int(parts[4]),
            pass_index=int(parts[5]),
        )


class CheckpointState(BaseModel):
    """Checkpoint state file format."""

    run_id: str
    checkpoint_version: int = 1
    created_at: datetime
    updated_at: datetime
    completed_tasks: set[str] = set()
    total_tasks: int = 0
    completed_count: int = 0

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            set: lambda v: list(v),
        }

    def is_completed(self, task: TaskID) -> bool:
        """Check if task is already completed."""
        return task.to_key() in self.completed_tasks

    def mark_completed(self, task: TaskID):
        """Mark task as completed."""
        self.completed_tasks.add(task.to_key())
        self.completed_count = len(self.completed_tasks)
        self.updated_at = datetime.now()

    def get_progress(self) -> tuple[int, int]:
        """Get (completed, total) task counts."""
        return self.completed_count, self.total_tasks


class CheckpointManager:
    """Manage checkpoint state for resumability."""

    def __init__(self, checkpoint_path: Path, run_id: str):
        """Initialize checkpoint manager.

        Args:
            checkpoint_path: Path to checkpoint.json file
            run_id: Unique run identifier
        """
        self.checkpoint_path = Path(checkpoint_path)
        self.run_id = run_id
        self.state: Optional[CheckpointState] = None

    def load(self) -> CheckpointState:
        """Load checkpoint from disk or create new.

        Returns:
            CheckpointState instance
        """
        if self.checkpoint_path.exists():
            logger.info(f"Loading checkpoint from {self.checkpoint_path}")
            with open(self.checkpoint_path) as f:
                data = json.load(f)

                # Convert completed_tasks back to set
                if "completed_tasks" in data:
                    data["completed_tasks"] = set(data["completed_tasks"])

                # Parse datetime strings
                if "created_at" in data:
                    data["created_at"] = datetime.fromisoformat(data["created_at"])
                if "updated_at" in data:
                    data["updated_at"] = datetime.fromisoformat(data["updated_at"])

                self.state = CheckpointState(**data)

            # Verify run_id matches
            if self.state.run_id != self.run_id:
                raise ValueError(
                    f"Checkpoint run_id mismatch: expected {self.run_id}, "
                    f"found {self.state.run_id}"
                )

            logger.info(
                f"Checkpoint loaded: {self.state.completed_count}/{self.state.total_tasks} tasks completed"
            )
        else:
            # Create new checkpoint
            logger.info("Creating new checkpoint")
            self.state = CheckpointState(
                run_id=self.run_id,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

        return self.state

    def save(self):
        """Atomic save to disk.

        Uses temporary file + rename for atomic write to prevent
        corruption on interruption.
        """
        if self.state is None:
            raise ValueError("Cannot save: checkpoint state not loaded")

        # Ensure parent directory exists
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

        # Prepare data for JSON serialization
        data = self.state.model_dump()
        data["completed_tasks"] = list(self.state.completed_tasks)
        data["created_at"] = self.state.created_at.isoformat()
        data["updated_at"] = self.state.updated_at.isoformat()

        # Atomic write via temp file
        temp_path = self.checkpoint_path.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            json.dump(data, f, indent=2)

        # Atomic rename
        temp_path.replace(self.checkpoint_path)

        logger.debug(f"Checkpoint saved: {self.state.completed_count}/{self.state.total_tasks}")

    def should_skip(self, task: TaskID) -> bool:
        """Check if task should be skipped (already completed).

        Args:
            task: Task to check

        Returns:
            True if task is already completed and should be skipped
        """
        if self.state is None:
            raise ValueError("Checkpoint state not loaded")

        return self.state.is_completed(task)

    def mark_completed(self, task: TaskID):
        """Mark task as completed and save checkpoint.

        Args:
            task: Task to mark as completed
        """
        if self.state is None:
            raise ValueError("Checkpoint state not loaded")

        self.state.mark_completed(task)
        self.save()

    def set_total_tasks(self, total: int):
        """Set total number of tasks for progress tracking.

        Args:
            total: Total task count
        """
        if self.state is None:
            raise ValueError("Checkpoint state not loaded")

        self.state.total_tasks = total
        self.save()
