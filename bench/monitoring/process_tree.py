"""Process tree tracking utilities."""

import psutil
import docker

from bench.logging import logger


def get_process_tree(root_pid: int) -> list[int]:
    """
    Get all descendant PIDs of a root process.

    Args:
        root_pid: Root process ID

    Returns:
        List of PIDs including root and all descendants
    """
    try:
        root = psutil.Process(root_pid)
        children = root.children(recursive=True)
        return [root_pid] + [p.pid for p in children]
    except psutil.NoSuchProcess:
        logger.warning(f"Process {root_pid} not found")
        return []


def get_container_main_pid(container_name: str) -> int:
    """
    Get PID of a Docker container's main process.

    Args:
        container_name: Container name or ID

    Returns:
        Main process PID

    Raises:
        RuntimeError: If container not found or not running
    """
    try:
        client = docker.from_env()
        container = client.containers.get(container_name)

        if container.status != "running":
            raise RuntimeError(f"Container {container_name} is not running")

        return container.attrs["State"]["Pid"]
    except docker.errors.NotFound:
        raise RuntimeError(f"Container {container_name} not found")
    except Exception as e:
        raise RuntimeError(f"Failed to get container PID: {e}")
