"""
World Model Store - FTI Feature Pipeline for TAHI

Implements versioned world model storage following FTI (Feature/Training/Inference)
MLOps patterns. This is the "Feature Pipeline" analog for TAHI's coprocessor
architecture.

Reference: https://www.hopsworks.ai/post/mlops-to-ml-systems-with-fti-pipelines
"""

import gzip
import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .world_state import WorldModel


@dataclass
class WorldModelManifest:
    """Metadata for a versioned world model"""

    source: str
    version: str
    domain: str
    build_date: str
    num_nodes: int
    num_edges: int
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "version": self.version,
            "domain": self.domain,
            "build_date": self.build_date,
            "num_nodes": self.num_nodes,
            "num_edges": self.num_edges,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorldModelManifest":
        return cls(
            source=data["source"],
            version=data["version"],
            domain=data["domain"],
            build_date=data["build_date"],
            num_nodes=data["num_nodes"],
            num_edges=data["num_edges"],
            metadata=data.get("metadata", {}),
        )


class WorldModelStore:
    """
    Versioned world model storage following FTI Feature Pipeline pattern.

    Structure:
        store_path/
            {source}/
                {version}/
                    manifest.json
                    {db_id}.json.gz (or {db_id}.json)
                    ...

    Example:
        store = WorldModelStore("~/.tahi/world-models/")

        # Build and save
        world = build_dea_world_model(source="federal-register")
        store.save(
            world,
            source="dea-scheduling",
            version="v1.0.0",
            db_id="california_schools",
            metadata={"enrichment": "csv_metadata"}
        )

        # Load
        world = store.load("dea-scheduling", "v1.0.0", model_id="analogues")
    """

    def __init__(self, base_path: str | Path, compress: bool = True):
        """
        Args:
            base_path: Root directory for world model storage
            compress: Use gzip compression (default True)
        """
        self.base_path = Path(base_path).expanduser()
        self.compress = compress
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _version_path(self, source: str, version: str) -> Path:
        """Get path to version directory"""
        return self.base_path / source / version

    def _manifest_path(self, source: str, version: str) -> Path:
        """Get path to manifest file"""
        return self._version_path(source, version) / "manifest.json"

    def _model_path(self, source: str, version: str, model_id: str) -> Path:
        """Get path to world model file"""
        version_dir = self._version_path(source, version)
        ext = ".json.gz" if self.compress else ".json"
        return version_dir / f"{model_id}{ext}"

    def save(
        self,
        world_model: WorldModel,
        source: str,
        version: str,
        model_id: str,
        metadata: dict | None = None,
    ) -> None:
        """
        Save a world model with versioning.

        Args:
            world_model: WorldModel instance to save
            source: Source identifier (e.g., "dea-scheduling", "hotpotqa-wiki")
            version: Semantic version (e.g., "v1.0.0")
            model_id: Model identifier (e.g., db_id, schema_name)
            metadata: Optional build metadata
        """
        version_dir = self._version_path(source, version)
        version_dir.mkdir(parents=True, exist_ok=True)

        # Save world model
        model_path = self._model_path(source, version, model_id)
        model_data = json.dumps(world_model.to_dict(), indent=2)

        if self.compress:
            with gzip.open(model_path, 'wt', encoding='utf-8') as f:
                f.write(model_data)
        else:
            model_path.write_text(model_data, encoding='utf-8')

        # Update manifest
        manifest = self._load_or_create_manifest(source, version, world_model.domain)
        manifest.num_nodes = max(manifest.num_nodes, len(world_model.nodes))
        manifest.num_edges = max(manifest.num_edges, len(world_model.edges))
        if metadata:
            manifest.metadata.setdefault("models", {})[model_id] = metadata

        self._save_manifest(manifest, source, version)

    def load(
        self,
        source: str,
        version: str,
        model_id: str,
    ) -> WorldModel:
        """
        Load a versioned world model.

        Args:
            source: Source identifier
            version: Semantic version
            model_id: Model identifier

        Returns:
            WorldModel instance

        Raises:
            FileNotFoundError: If model doesn't exist
        """
        model_path = self._model_path(source, version, model_id)

        if not model_path.exists():
            raise FileNotFoundError(
                f"World model not found: {source}:{version}/{model_id}\n"
                f"Path: {model_path}"
            )

        if self.compress:
            with gzip.open(model_path, 'rt', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = json.loads(model_path.read_text(encoding='utf-8'))

        return WorldModel.from_dict(data)

    def exists(self, source: str, version: str, model_id: str) -> bool:
        """Check if a world model exists"""
        return self._model_path(source, version, model_id).exists()

    def list_versions(self, source: str) -> list[str]:
        """List all versions for a source"""
        source_path = self.base_path / source
        if not source_path.exists():
            return []
        return sorted([v.name for v in source_path.iterdir() if v.is_dir()])

    def list_models(self, source: str, version: str) -> list[str]:
        """List all model IDs in a version"""
        version_path = self._version_path(source, version)
        if not version_path.exists():
            return []

        ext = ".json.gz" if self.compress else ".json"
        return sorted([
            p.stem.replace('.json', '') if self.compress else p.stem
            for p in version_path.glob(f"*{ext}")
            if p.name != "manifest.json"  # Exclude manifest
        ])

    def get_manifest(self, source: str, version: str) -> WorldModelManifest | None:
        """Get manifest for a version"""
        manifest_path = self._manifest_path(source, version)
        if not manifest_path.exists():
            return None

        data = json.loads(manifest_path.read_text(encoding='utf-8'))
        return WorldModelManifest.from_dict(data)

    def build_and_save(
        self,
        builder: Callable[..., WorldModel],
        source: str,
        version: str,
        model_id: str,
        metadata: dict | None = None,
        **builder_kwargs,
    ) -> WorldModel:
        """
        Build a world model and save it.

        Args:
            builder: Function that builds WorldModel (e.g., build_dea_world_model)
            source: Source identifier
            version: Semantic version
            model_id: Model identifier
            metadata: Optional build metadata
            **builder_kwargs: Arguments passed to builder function

        Returns:
            Built WorldModel
        """
        world_model = builder(**builder_kwargs)
        self.save(world_model, source, version, model_id, metadata)
        return world_model

    def get_or_build(
        self,
        builder: Callable[..., WorldModel],
        source: str,
        version: str,
        model_id: str,
        metadata: dict | None = None,
        force_rebuild: bool = False,
        **builder_kwargs,
    ) -> WorldModel:
        """
        Load existing world model or build if doesn't exist.

        Args:
            builder: Function that builds WorldModel
            source: Source identifier
            version: Semantic version
            model_id: Model identifier
            metadata: Optional build metadata
            force_rebuild: Force rebuild even if exists
            **builder_kwargs: Arguments passed to builder function

        Returns:
            WorldModel instance
        """
        if not force_rebuild and self.exists(source, version, model_id):
            return self.load(source, version, model_id)

        return self.build_and_save(builder, source, version, model_id, metadata, **builder_kwargs)

    def _load_or_create_manifest(
        self,
        source: str,
        version: str,
        domain: str,
    ) -> WorldModelManifest:
        """Load existing manifest or create new one"""
        manifest_path = self._manifest_path(source, version)

        if manifest_path.exists():
            data = json.loads(manifest_path.read_text(encoding='utf-8'))
            return WorldModelManifest.from_dict(data)

        return WorldModelManifest(
            source=source,
            version=version,
            domain=domain,
            build_date=datetime.now().isoformat(),
            num_nodes=0,
            num_edges=0,
        )

    def _save_manifest(
        self,
        manifest: WorldModelManifest,
        source: str,
        version: str,
    ) -> None:
        """Save manifest to disk"""
        manifest_path = self._manifest_path(source, version)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest.to_dict(), indent=2),
            encoding='utf-8'
        )

    def delete_version(self, source: str, version: str) -> None:
        """Delete an entire version"""
        version_path = self._version_path(source, version)
        if version_path.exists():
            shutil.rmtree(version_path)

    def delete_model(self, source: str, version: str, model_id: str) -> None:
        """Delete a specific model"""
        model_path = self._model_path(source, version, model_id)
        if model_path.exists():
            model_path.unlink()
