"""Small shared host for independent measurement pairs; no SDK imports."""

from .contracts import API_VERSION, ContractError, ModuleDescriptor, TabHandle
from .context import ContextFactory, MeasurementContext, OperationSnapshot, PlanSnapshot, ScopedPreferences
from .registry import DiscoveryResult, RegistrationIssue, TabCreationResult, create_registered_tabs, discover_modules

__all__ = [
    "API_VERSION", "ContractError", "ModuleDescriptor", "TabHandle", "ContextFactory",
    "MeasurementContext", "OperationSnapshot", "PlanSnapshot", "ScopedPreferences",
    "DiscoveryResult", "RegistrationIssue", "TabCreationResult", "create_registered_tabs", "discover_modules",
]
