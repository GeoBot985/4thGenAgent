class RuntimeSpecError(Exception):
    pass


class CommandParseError(RuntimeSpecError):
    pass


class ManifestLoadError(RuntimeSpecError):
    pass


class ManifestValidationError(RuntimeSpecError):
    pass


class ToolRegistryError(RuntimeSpecError):
    pass


class ToolPackError(RuntimeSpecError):
    pass


class ToolPackLoadError(ToolPackError):
    pass


class ToolPackValidationError(ToolPackError):
    pass


class ToolPackHealthError(ToolPackError):
    pass


class ToolNotRegisteredError(ToolRegistryError):
    pass


class ToolArgumentError(ToolRegistryError):
    pass


class ArgumentResolutionError(RuntimeSpecError):
    pass


class ToolExecutionBlocked(RuntimeSpecError):
    pass


class ValidationEngineError(RuntimeSpecError):
    pass


class UnknownValidationTypeError(ValidationEngineError):
    pass


class CompletionGateError(RuntimeSpecError):
    pass


class PendingActionError(RuntimeSpecError):
    pass


class ToolExecutionError(RuntimeSpecError):
    pass


class RecoveryError(RuntimeSpecError):
    pass


class RecoveryAssessmentError(RecoveryError):
    pass


class RecoveryPolicyError(RecoveryError):
    pass


class DuplicateSideEffectBlocked(ToolExecutionError):
    pass


class LiveToolExecutionBlocked(ToolExecutionError):
    pass


class ToolImportError(ToolExecutionError):
    pass


class ToolFunctionError(ToolExecutionError):
    pass


class ToolResultNormalizationError(ToolExecutionError):
    pass


class EventError(RuntimeSpecError):
    pass


class EventValidationError(EventError):
    pass


class EventRoutingError(EventError):
    pass


class ManifestRouteNotFoundError(EventRoutingError):
    pass


class SchedulerError(RuntimeSpecError):
    pass


class MemoryStoreError(RuntimeSpecError):
    pass


class MemoryKeyError(MemoryStoreError):
    pass


class MemoryCommandError(RuntimeSpecError):
    pass


class LLMAdapterError(RuntimeSpecError):
    pass


class LLMCommandError(RuntimeSpecError):
    pass


class LLMToolError(RuntimeSpecError):
    pass


class LLMProviderError(LLMAdapterError):
    pass


class LLMConnectionError(LLMAdapterError):
    pass


class LLMTimeoutError(LLMAdapterError):
    pass


class LLMHTTPError(LLMAdapterError):
    pass


class LLMAdapterResponseError(LLMAdapterError):
    pass


class LLMToolNotFoundError(LLMToolError):
    pass


class LLMToolInputError(LLMToolError):
    pass


class LLMOutputSchemaError(LLMToolError):
    pass


class LLMOutputParseError(LLMAdapterError):
    pass


class LLMActionNotAllowedError(LLMCommandError):
    pass


class ConditionError(RuntimeSpecError):
    pass


class ConditionValidationError(ConditionError):
    pass


class ConditionEvaluationError(ConditionError):
    pass


class RetryPolicyError(RuntimeSpecError):
    pass


class RetryPolicyValidationError(RetryPolicyError):
    pass


class RetryExhaustedError(RetryPolicyError):
    pass


class TimingError(RuntimeSpecError):
    pass


class TimeoutPolicyError(TimingError):
    pass


class StepTimeoutExceeded(TimingError):
    pass


class PersistenceError(RuntimeSpecError):
    pass


class TaskFramePersistenceError(PersistenceError):
    pass


class RunLedgerError(PersistenceError):
    pass


class RuntimeStoreError(PersistenceError):
    pass


class RuntimeStoreValidationError(RuntimeStoreError):
    pass


class RuntimeStoreBackupError(RuntimeStoreError):
    pass


class RuntimeStoreRestoreError(RuntimeStoreError):
    pass


class RuntimeStorePolicyError(RuntimeStoreError):
    pass


class TaskFrameNotFoundError(PersistenceError):
    pass


class TaskFrameReloadError(PersistenceError):
    pass


class InspectionError(RuntimeSpecError):
    pass


class InspectionCommandError(InspectionError):
    pass


class InspectionTargetNotFoundError(InspectionError):
    pass


class RetentionPolicyError(RuntimeSpecError):
    pass


class CleanupError(RuntimeSpecError):
    pass


class CleanupPolicyError(CleanupError):
    pass


class CleanupConfirmationError(CleanupError):
    pass


class CleanupExecutionError(CleanupError):
    pass


class MaintenanceError(RuntimeSpecError):
    pass


class MaintenanceCommandError(MaintenanceError):
    pass


class MaintenancePolicyError(MaintenanceError):
    pass


class ApprovalCommandError(RuntimeSpecError):
    pass


class ApprovalCommandBlocked(RuntimeSpecError):
    pass


class LiveExecutionError(RuntimeSpecError):
    pass


class LiveExecutionBlocked(LiveExecutionError):
    pass


class LiveExecutionPolicyError(LiveExecutionError):
    pass


class LiveGuardrailError(LiveExecutionError):
    pass


class LiveExecutionNotAllowedForTool(LiveExecutionError):
    pass


class RuntimeProfilePolicyError(RuntimeSpecError):
    pass
