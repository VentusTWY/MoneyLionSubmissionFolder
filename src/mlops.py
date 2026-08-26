"""Reproducible run bundles, promotion gates, and a local atomic registry."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Protocol
from urllib.parse import unquote, urlparse

import joblib


TRAINING_DEPENDENCIES = (
    "joblib",
    "lightgbm",
    "pandas",
    "pyarrow",
    "PyYAML",
    "scikit-learn",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: str | Path) -> str:
    # Step 1: stream the artifact into a SHA-256 digest without loading it all at once.
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    # Step 2: return the stable hexadecimal checksum stored in manifests.
    return digest.hexdigest()


def code_revision() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def runtime_provenance(
    requirements_path: str | Path,
    dependencies: tuple[str, ...] = TRAINING_DEPENDENCIES,
) -> dict:
    """Describe the actual training runtime and its declared dependency set."""
    requirements_path = Path(requirements_path)
    return {
        "python_version": sys.version.split()[0],
        "dependencies": {
            dependency: metadata.version(dependency)
            for dependency in dependencies
        },
        "requirements_file": requirements_path.name,
        "requirements_sha256": sha256(requirements_path),
    }


def write_json(path: str | Path, value: object) -> None:
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify_bundle(version_dir: str | Path) -> dict:
    # Step 1: load the immutable bundle manifest from the selected version.
    version_dir = Path(version_dir)
    manifest = json.loads((version_dir / "manifest.json").read_text())

    # Step 2: verify that every tracked artifact exists and matches its checksum.
    for name, expected in manifest["checksums"].items():
        path = version_dir / name
        if not path.is_file() or sha256(path) != expected:
            raise ValueError(f"Artifact checksum mismatch: {name}")

    # Step 3: prove that the model payload can be deserialised by this runtime.
    joblib.load(version_dir / "model.joblib")

    # Step 4: return verified metadata to the caller.
    return manifest


def evaluate_gates(
    metrics: dict,
    champion_metrics: dict | None,
    config: dict,
    quality: dict,
) -> dict:
    # Step 1: initialise the complete list of auditable promotion decisions.
    gates = []

    # Step 2: enforce minimum evaluation population and binary-target quality.
    minimum_rows = int(config.get("minimum_test_rows", 100))
    gates.append({"name": "minimum_test_rows", "passed": metrics["test_rows"] >= minimum_rows})
    gates.append({"name": "both_classes", "passed": quality.get("target_classes") == 2})

    # Step 3: enforce absolute discrimination and calibration limits.
    gates.append({"name": "minimum_roc_auc", "passed": metrics["roc_auc"] >= float(config.get("minimum_roc_auc", 0.5))})
    gates.append({"name": "maximum_log_loss", "passed": metrics["log_loss"] <= float(config.get("maximum_log_loss", 1.0))})

    # Step 4: compare with the champion only when both used the same evaluation set.
    if champion_metrics:
        challenger_fingerprint = metrics.get("evaluation_fingerprint")
        champion_fingerprint = champion_metrics.get("evaluation_fingerprint")
        comparable = bool(
            challenger_fingerprint
            and champion_fingerprint
            and challenger_fingerprint == champion_fingerprint
        )
        comparison = {
            "name": "champion_evaluation_comparability",
            "passed": True if comparable else None,
            "applied": comparable,
        }
        if not comparable:
            comparison["reason"] = (
                "Champion-relative gate skipped because evaluation fingerprints "
                "are missing or different"
            )
        gates.append(comparison)
        if comparable:
            tolerance = float(config.get("roc_auc_regression_tolerance", 0.01))
            gates.append({
                "name": "champion_roc_auc_tolerance",
                "passed": metrics["roc_auc"] >= champion_metrics["roc_auc"] - tolerance,
                "applied": True,
            })

    # Step 5: pass only when every individual gate succeeds.
    applied_gates = [item for item in gates if item.get("applied", True)]
    return {"passed": all(item["passed"] for item in applied_gates), "gates": gates}


class ModelRegistry(Protocol):
    """Backend contract shared by training, promotion, and serving."""

    def champion(self) -> dict | None: ...

    def champion_dir(self) -> Path: ...

    def list_versions(self) -> list[dict]: ...

    def register(self, bundle: str | Path, version: str) -> Path: ...

    def promote(self, version: str, smoke_test=None, *, reason: str = "promotion", actor: str = "system") -> dict: ...

    def rollback(self, smoke_test=None, *, reason: str = "manual rollback", actor: str = "system") -> dict: ...


class RegistryBackendNotInstalled(RuntimeError):
    """Raised when a configured production registry adapter is unavailable."""


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

    def list_versions(self) -> list[dict]:
        """Return concise, non-sensitive metadata for every registered model."""
        champion = self.champion()
        active_version = champion["version"] if champion else None
        previous_version = champion.get("previous_version") if champion else None
        versions = []
        for version_dir in sorted(self.versions.iterdir(), reverse=True):
            if not version_dir.is_dir() or not (version_dir / "manifest.json").is_file():
                continue
            try:
                manifest = json.loads((version_dir / "manifest.json").read_text())
                metrics_path = version_dir / "metrics.json"
                metrics = json.loads(metrics_path.read_text()) if metrics_path.is_file() else {}
            except (OSError, json.JSONDecodeError):
                # A damaged candidate remains in storage for investigation but is not selectable.
                continue
            versions.append({
                "version": manifest.get("version", version_dir.name),
                "created_at_utc": manifest.get("created_at_utc"),
                "feature_contract_version": manifest.get("feature_contract", {}).get("name"),
                "status": manifest.get("status"),
                "metrics": {
                    key: metrics[key]
                    for key in ("roc_auc", "pr_auc", "log_loss")
                    if key in metrics
                },
                "is_active": version_dir.name == active_version,
                "is_previous": version_dir.name == previous_version,
            })
        return versions

    def register(self, bundle: str | Path, version: str) -> Path:
        # Step 1: reserve a new immutable version path and reject collisions.
        destination = self.versions / version
        if destination.exists():
            raise FileExistsError(f"Registry version already exists: {version}")

        # Step 2: copy the complete candidate bundle into the registry.
        shutil.copytree(bundle, destination)

        # Step 3: verify the stored copy before making it eligible for promotion.
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

    def _point_to(self, version: str, previous: str | None, reason: str, actor: str) -> None:
        pointer = {
            "version": version,
            "previous_version": previous,
            "updated_at_utc": utc_now(),
            "reason": reason,
            "actor": actor,
        }
        temporary = self.root / ".champion.json.tmp"
        write_json(temporary, pointer)
        os.replace(temporary, self.champion_file)
        with (self.root / "audit.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(pointer, sort_keys=True) + "\n")

    def promote(
        self, version: str, smoke_test=None, *, reason: str = "promotion", actor: str = "system"
    ) -> dict:
        # Step 1: verify the candidate bundle before touching the champion pointer.
        verify_bundle(self.versions / version)

        # Step 2: serialize promotions with an exclusive registry lock.
        with self._lock():
            # Step 3: remember the current champion for audit and rollback.
            prior = self.champion()
            previous = prior["version"] if prior else None

            # Step 4: atomically point production at the verified candidate.
            self._point_to(version, previous, reason, actor)
            try:
                # Step 5: smoke-test a model reloaded through the serving path.
                if smoke_test:
                    smoke_test()
            except Exception:
                # Step 6: restore the prior pointer when the serving smoke test fails.
                if previous:
                    self._point_to(previous, version, "automatic rollback after smoke failure", "system")
                else:
                    self.champion_file.unlink(missing_ok=True)
                raise
        return self.champion()

    def rollback(
        self, smoke_test=None, *, reason: str = "manual rollback", actor: str = "system"
    ) -> dict:
        # Step 1: resolve the current and previous champion versions.
        current = self.champion()
        if not current or not current.get("previous_version"):
            raise RuntimeError("No previous champion is available")
        target = current["previous_version"]

        # Step 2: verify the previous bundle before restoring it.
        verify_bundle(self.versions / target)

        # Step 3: serialize and atomically apply the rollback pointer update.
        with self._lock():
            self._point_to(target, current["version"], reason, actor)
            try:
                if smoke_test:
                    smoke_test()
            except Exception:
                self._point_to(
                    current["version"],
                    target,
                    "automatic restore after rollback smoke failure",
                    "system",
                )
                raise

        # Step 4: return the newly active champion record.
        return self.champion()


def create_registry(location: str | Path = "file://registry") -> ModelRegistry:
    """Create a registry from a plain path or a registry URI.

    ``file://registry`` keeps the demo self-contained. A production adapter
    should store immutable bundles in S3 and coordinate champion-pointer updates
    and promotion locks transactionally in DynamoDB (or an equivalent metadata
    store), rather than treating S3 like a local filesystem.
    """

    # Step 1: preserve direct Path injection used by tests and local callers.
    if isinstance(location, Path):
        return LocalRegistry(location)

    # Step 2: parse string locations as either plain paths or backend URIs.
    parsed = urlparse(location)
    if not parsed.scheme:
        return LocalRegistry(location)

    # Step 3: resolve supported file URIs into the tested local implementation.
    if parsed.scheme == "file":
        if parsed.query or parsed.fragment:
            raise ValueError("Registry file URI cannot contain a query or fragment")
        if parsed.netloc and parsed.path:
            if parsed.netloc != "localhost":
                raise ValueError("Remote file registry hosts are not supported")
            path = Path(unquote(parsed.path))
        elif parsed.netloc:
            # Accept the readable demo form file://registry as a relative path.
            path = Path(unquote(parsed.netloc))
        else:
            path = Path(unquote(parsed.path))
        return LocalRegistry(path)

    # Step 4: fail clearly at the documented production S3 extension point.
    if parsed.scheme == "s3":
        raise RegistryBackendNotInstalled(
            "The S3 registry backend is a production extension point and is not "
            "installed in this demo. Implement an adapter that stores immutable "
            "bundles in S3 and uses DynamoDB for champion-pointer transactions "
            "and promotion locking."
        )

    # Step 5: reject unknown backends instead of silently choosing local storage.
    raise ValueError(f"Unsupported model registry URI scheme: {parsed.scheme}")
