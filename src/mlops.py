"""Reproducible run bundles, promotion gates, and a local atomic registry."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import joblib


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def code_revision() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def write_json(path: str | Path, value: object) -> None:
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify_bundle(version_dir: str | Path) -> dict:
    version_dir = Path(version_dir)
    manifest = json.loads((version_dir / "manifest.json").read_text())
    for name, expected in manifest["checksums"].items():
        path = version_dir / name
        if not path.is_file() or sha256(path) != expected:
            raise ValueError(f"Artifact checksum mismatch: {name}")
    joblib.load(version_dir / "model.joblib")
    return manifest


def evaluate_gates(
    metrics: dict,
    champion_metrics: dict | None,
    config: dict,
    quality: dict,
) -> dict:
    gates = []
    minimum_rows = int(config.get("minimum_test_rows", 100))
    gates.append({"name": "minimum_test_rows", "passed": metrics["test_rows"] >= minimum_rows})
    gates.append({"name": "both_classes", "passed": quality.get("target_classes") == 2})
    gates.append({"name": "minimum_roc_auc", "passed": metrics["roc_auc"] >= float(config.get("minimum_roc_auc", 0.5))})
    gates.append({"name": "maximum_log_loss", "passed": metrics["log_loss"] <= float(config.get("maximum_log_loss", 1.0))})
    if champion_metrics:
        tolerance = float(config.get("roc_auc_regression_tolerance", 0.01))
        gates.append({
            "name": "champion_roc_auc_tolerance",
            "passed": metrics["roc_auc"] >= champion_metrics["roc_auc"] - tolerance,
        })
    return {"passed": all(item["passed"] for item in gates), "gates": gates}


class LocalRegistry:
    """Immutable model versions with an atomically replaced champion pointer."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.versions = self.root / "versions"
        try:
            self.versions.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            # Support read-only registry mounts in containerized demos.
            if not self.versions.exists():
                raise

    @property
    def champion_file(self) -> Path:
        return self.root / "champion.json"

    def champion(self) -> dict | None:
        if not self.champion_file.exists():
            return None
        return json.loads(self.champion_file.read_text())

    def champion_dir(self) -> Path:
        champion = self.champion()
        if champion is None:
            raise RuntimeError("No champion is registered")
        return self.versions / champion["version"]

    def register(self, bundle: str | Path, version: str) -> Path:
        destination = self.versions / version
        if destination.exists():
            raise FileExistsError(f"Registry version already exists: {version}")
        shutil.copytree(bundle, destination)
        verify_bundle(destination)
        return destination

    @contextmanager
    def _lock(self):
        lock = self.root / ".promotion.lock"
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise RuntimeError("Another promotion is in progress") from exc
        os.close(fd)
        try:
            yield
        finally:
            lock.unlink(missing_ok=True)

    def _point_to(self, version: str, previous: str | None, reason: str) -> None:
        pointer = {
            "version": version,
            "previous_version": previous,
            "updated_at_utc": utc_now(),
            "reason": reason,
        }
        temporary = self.root / ".champion.json.tmp"
        write_json(temporary, pointer)
        os.replace(temporary, self.champion_file)
        with (self.root / "audit.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(pointer, sort_keys=True) + "\n")

    def promote(self, version: str, smoke_test=None) -> dict:
        verify_bundle(self.versions / version)
        with self._lock():
            prior = self.champion()
            previous = prior["version"] if prior else None
            self._point_to(version, previous, "promotion")
            try:
                if smoke_test:
                    smoke_test()
            except Exception:
                if previous:
                    self._point_to(previous, version, "automatic rollback after smoke failure")
                else:
                    self.champion_file.unlink(missing_ok=True)
                raise
        return self.champion()

    def rollback(self) -> dict:
        current = self.champion()
        if not current or not current.get("previous_version"):
            raise RuntimeError("No previous champion is available")
        target = current["previous_version"]
        verify_bundle(self.versions / target)
        with self._lock():
            self._point_to(target, current["version"], "manual rollback")
        return self.champion()
