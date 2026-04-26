"""
Kubernetes Job 樣板：每個 shard 一個 Job，跨 pod 平行跑 ``--shard i/N``。
Render Kubernetes ``batch/v1 Job`` manifests for shard-parallel runs. Each
Job sets ``--shard <i>/<total>`` so the existing CLI does the actual work
inside the container.

The manifest is dict-only; callers can ``yaml.safe_dump`` or stream the
JSON form into ``kubectl create``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class K8sRunnerError(WebRunnerException):
    """Raised when a config produces an invalid manifest."""


_RFC1123_RE = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")


@dataclass
class ShardJobConfig:
    """Inputs for a single batch of shard Jobs."""

    name_prefix: str
    image: str
    total_shards: int
    actions_dir: str
    namespace: str = "default"
    command: Sequence[str] = field(default_factory=lambda: ["python", "-m", "je_web_runner"])
    env: Dict[str, str] = field(default_factory=dict)
    resources: Dict[str, Dict[str, str]] = field(default_factory=lambda: {
        "requests": {"cpu": "500m", "memory": "1Gi"},
        "limits": {"cpu": "1", "memory": "2Gi"},
    })
    backoff_limit: int = 1
    parallelism: int = 1
    completions: int = 1
    labels: Dict[str, str] = field(default_factory=dict)
    extra_args: Sequence[str] = field(default_factory=tuple)


def _validate(config: ShardJobConfig) -> None:
    if not _RFC1123_RE.match(config.name_prefix):
        raise K8sRunnerError(
            f"name_prefix {config.name_prefix!r} must be RFC-1123 (lowercase, dashes)"
        )
    if not config.image:
        raise K8sRunnerError("image required")
    if config.total_shards <= 0:
        raise K8sRunnerError("total_shards must be > 0")
    if not isinstance(config.actions_dir, str) or not config.actions_dir:
        raise K8sRunnerError("actions_dir must be non-empty")


def render_job_manifests(config: ShardJobConfig) -> List[Dict[str, Any]]:
    """Produce one ``batch/v1`` Job dict per shard."""
    _validate(config)
    manifests: List[Dict[str, Any]] = []
    base_labels = {
        "app.kubernetes.io/name": "webrunner",
        "app.kubernetes.io/component": "shard",
        "webrunner/run": config.name_prefix,
    }
    base_labels.update(config.labels)
    for index in range(1, config.total_shards + 1):
        job_name = f"{config.name_prefix}-shard-{index}-of-{config.total_shards}"
        labels = dict(base_labels)
        labels["webrunner/shard"] = f"{index}-of-{config.total_shards}"
        manifests.append(_render_one(config, index, job_name, labels))
    return manifests


def _render_one(
    config: ShardJobConfig,
    shard_index: int,
    job_name: str,
    labels: Dict[str, str],
) -> Dict[str, Any]:
    args = [
        "--execute_dir", config.actions_dir,
        "--shard", f"{shard_index}/{config.total_shards}",
    ]
    args.extend(str(arg) for arg in config.extra_args)
    env = [{"name": name, "value": value} for name, value in config.env.items()]
    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": job_name,
            "namespace": config.namespace,
            "labels": labels,
        },
        "spec": {
            "backoffLimit": config.backoff_limit,
            "parallelism": config.parallelism,
            "completions": config.completions,
            "template": {
                "metadata": {"labels": labels},
                "spec": {
                    "restartPolicy": "Never",
                    "containers": [
                        {
                            "name": "webrunner",
                            "image": config.image,
                            "command": list(config.command),
                            "args": args,
                            "env": env,
                            "resources": config.resources,
                        }
                    ],
                },
            },
        },
    }


def render_yaml_documents(manifests: List[Dict[str, Any]]) -> str:
    """Render to a multi-doc YAML string (basic dumper, no PyYAML dependency)."""
    pieces: List[str] = []
    for index, manifest in enumerate(manifests):
        if index > 0:
            pieces.append("---")
        pieces.append(_dump_yaml(manifest, indent=0))
    return "\n".join(pieces) + "\n"


def _dump_yaml(value: Any, indent: int = 0) -> str:
    pad = "  " * indent
    if isinstance(value, dict):
        if not value:
            return f"{pad}{{}}"
        lines = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{pad}{key}:")
                lines.append(_dump_yaml(item, indent + 1))
            else:
                lines.append(f"{pad}{key}: {_scalar(item)}")
        return "\n".join(lines)
    if isinstance(value, list):
        if not value:
            return f"{pad}[]"
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{pad}-")
                lines.append(_dump_yaml(item, indent + 1))
            else:
                lines.append(f"{pad}- {_scalar(item)}")
        return "\n".join(lines)
    return f"{pad}{_scalar(value)}"


def _scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if any(ch in text for ch in (":", "#", "\n", "{", "}", "[", "]", ",", "&", "*", "!")):
        return f'"{text}"'
    return text


def render_job_yaml(config: ShardJobConfig) -> str:
    """End-to-end: render manifests then YAML-encode."""
    return render_yaml_documents(render_job_manifests(config))
