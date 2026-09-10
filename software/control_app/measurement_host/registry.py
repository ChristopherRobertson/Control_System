"""Deterministic optional-package discovery; no central feature import list."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
from pathlib import Path
from typing import Iterable

from .contracts import ContractError, ModuleDescriptor, TabHandle, validate_descriptor, validate_handles


@dataclass(frozen=True)
class RegistrationIssue:
    module: str
    stage: str
    message: str


@dataclass(frozen=True)
class DiscoveryResult:
    descriptors: tuple[ModuleDescriptor, ...]
    issues: tuple[RegistrationIssue, ...]


@dataclass(frozen=True)
class TabCreationResult:
    handles: tuple[TabHandle, ...]
    issues: tuple[RegistrationIssue, ...]


def discover_modules(*, package_name: str = "control_app.measurement_modules") -> DiscoveryResult:
    """Import only registration.py files; defer widget construction to the host.

    Registration files must not import optional SDKs or access instruments. If a
    module violates its import contract, report it without removing working tabs.
    Namespace package paths are supported; duplicate IDs across paths are errors.
    """
    issues, descriptors = [], []
    try:
        package = importlib.import_module(package_name)
        roots = tuple(Path(path) for path in package.__path__)
    except (Exception, SystemExit) as exc:
        return DiscoveryResult((), (RegistrationIssue(package_name, "discovery", f"{type(exc).__name__}: {exc}"),))
    candidates = sorted(
        ((child.name, child / "registration.py") for root in roots for child in root.iterdir()
         if child.is_dir() and (child / "registration.py").is_file()),
        key=lambda item: (item[0], str(item[1])),
    )
    seen = set()
    for directory_id, path in candidates:
        module_name = f"{package_name}.{directory_id}.registration"
        try:
            if directory_id in seen:
                raise ContractError(f"Duplicate experiment ID {directory_id!r} at {path}")
            seen.add(directory_id)
            module = importlib.import_module(module_name)
            descriptor = validate_descriptor(getattr(module, "DESCRIPTOR", None), directory_id=directory_id)
            descriptors.append(descriptor)
        except (Exception, SystemExit) as exc:
            issues.append(RegistrationIssue(module_name, "registration", f"{type(exc).__name__}: {exc}"))
    return DiscoveryResult(tuple(sorted(descriptors, key=lambda item: (item.display_order, item.experiment_id))), tuple(issues))


def create_registered_tabs(
    discovery: DiscoveryResult | Iterable[ModuleDescriptor], context_factory, *, existing_titles: Iterable[str] = (),
    existing_instance_ids: Iterable[str] = (),
) -> TabCreationResult:
    """Construct valid pairs on the Qt thread; isolate a failing optional pair."""
    descriptors = discovery.descriptors if isinstance(discovery, DiscoveryResult) else tuple(discovery)
    issues = list(discovery.issues) if isinstance(discovery, DiscoveryResult) else []
    titles = {title.strip().casefold() for title in existing_titles}
    instances = set(existing_instance_ids)
    experiments = {instance.rsplit(":", 1)[0] for instance in instances}
    accepted = []
    for descriptor in sorted(descriptors, key=lambda item: (item.display_order, item.experiment_id)):
        pair = ()
        module_name = getattr(descriptor, "experiment_id", repr(descriptor))
        try:
            validate_descriptor(descriptor)
            if descriptor.experiment_id in experiments:
                raise ContractError(f"Duplicate experiment ID {descriptor.experiment_id!r}")
            experiments.add(descriptor.experiment_id)
            context = context_factory.for_experiment(descriptor.experiment_id, constructing=True)
            pair = tuple(descriptor.create_tabs(context))
            pair = validate_handles(descriptor, pair)
            for handle in pair:
                if handle.instance_id in instances:
                    raise ContractError(f"Duplicate instance ID {handle.instance_id!r}")
                if handle.title.strip().casefold() in titles:
                    raise ContractError(f"Duplicate top-level tab title {handle.title!r}")
            instances.update(handle.instance_id for handle in pair)
            titles.update(handle.title.strip().casefold() for handle in pair)
            accepted.extend(pair)
            context._activate()
        except (Exception, SystemExit) as exc:
            issues.append(RegistrationIssue(module_name, "construction", f"{type(exc).__name__}: {exc}"))
            # Failed optional widgets have never been published or activated.
            for handle in pair:
                widget = getattr(handle, "widget", None)
                if callable(getattr(widget, "deleteLater", None)):
                    widget.deleteLater()
    return TabCreationResult(tuple(accepted), tuple(issues))
