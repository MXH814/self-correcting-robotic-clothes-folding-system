# Editable system design models

These models describe the proposed product design for Assignment 2. The local simulation evidence covers the Fold Tops baseline and component probes. The UI, coordinator and adapter together still require integration. Use the English SRS for acceptance thresholds. [Control contract](../interfaces.md) · [UI contract](../ui-contract.md) · [Measured evidence](../../research/zhangmingbo/fold-experiments-20261108.md)

## Technology architecture

```mermaid
flowchart LR
  UI["Browser UI and state mapping"] <-->|"Versioned requests and status"| C["Coordinator, validation and control authority"]
  C <-->|"Commands, barrier ACK and measured feedback"| A["Isaac Python adapter"]
  A --> I["Isaac Sim 4.5 and DexGarmentLab"]
  C <-->|"Observation references and proposals"| W["Detection and recovery worker"]
  C -->|"Durable intent and lifecycle events"| L["Event store"]
  A -->|"Frames and measured traces"| F["Artifact storage"]
  L -->|"Content references and hashes"| F
  M["Approved model registry"] --> W
  T["Offline evaluation and training"] --> M
  F --> T
```

The coordinator owns authority and the durable dispatch record. The adapter enforces the current generation at admission and immediately before execution. Isaac's runtime remains isolated from the inference environment. The storage engine and cross-process transport are open decisions. The proposed resource check compares process RSS, GPU use, queue age and measured stop latency under local contention. [Logical and deployment views](../architecture-presentation-draft.md)

## Domain and ownership

```mermaid
classDiagram
  class TaskRequest {
    requestId
    idempotencyKey
    validationOrigin
  }
  class FoldingTask {
    taskId
    state
    activeSimTime
    recoveryAttempts
  }
  class FrozenProfile {
    garmentProfile
    robotProfile
    cameraProfile
    policyVersion
  }
  class ControlSession {
    generation
    authority
    stopStatus
  }
  class Observation {
    obsId
    simTime
    captureMonotonicTime
    clockDomain
  }
  class RecoveryDecision {
    decisionId
    generation
  }
  class Dispatch {
    commandId
    generation
    sequenceNo
  }
  class StopEvidence {
    requestId
    generation
    lastCommandId
    measuredSamples
  }
  class Evaluation {
    qualityOutcome
    autonomousSuccess
    reviewVersion
  }
  TaskRequest "1" --> "0..1" FoldingTask : accepted start
  FoldingTask "*" --> "1" FrozenProfile : pins
  FoldingTask "1" *-- "1" ControlSession : owns
  FoldingTask "1" *-- "*" Observation : records
  FoldingTask "1" *-- "*" RecoveryDecision : considers
  RecoveryDecision "*" --> "1" Observation : uses
  FoldingTask "1" *-- "*" Dispatch : authorizes
  RecoveryDecision "0..1" --> "0..1" Dispatch : selected prefix
  ControlSession "1" *-- "*" StopEvidence : history
  FoldingTask "1" *-- "*" Evaluation : append review
```

One accepted task pins its versions. A new control generation invalidates old authority and old rest proofs while preserving accepted dispatch accounting. A normal segment can have no recovery decision. A stop proof refers to the last command of its task and generation. An offline evaluation can append results without rewriting the terminal outcome. [Record definitions](../data-design.md)

## System API surface

| Call boundary | Required identity or payload | Observable result |
| --- | --- | --- |
| UI → Coordinator, Start | Idempotency key, selected profile, preparation checks | Rejected with reason or accepted task ID and pinned profile |
| UI → Coordinator, Pause, Resume, Terminate, Takeover, Return | Task ID, request ID, current expected generation | Current task state, stop status and permitted operations |
| Gateway → Coordinator, Observe | Observation ID, profile, frame provenance, simulation time and mapped monotonic capture time | Valid observation reference or missing/stale reason |
| Coordinator → Adapter, Dispatch | Task and command IDs, generation, sequence, bounded targets with units and frame | Receipt or rejection. Execution feedback carries measured state and the original identity |
| Coordinator ↔ Adapter, Halt and rest | Stop request ID, task, generation and last command. Reply includes samples, queue depth and active segment state | Barrier ACK separately from measured rest or timeout |
| UI → Record store through application API | Task or replay reference and cursor | Ordered events and evaluation references with read-only access |

Commands are checked both on admission and just before execution. Unsupported profile or stale observation rejects a dispatch. Invalid rest evidence preserves the execution lock. Details and existing reason codes remain in the adopted contracts. [Message fields](../interfaces.md) · [UI reasons](../ui-contract.md)

## Start, dispatch and fault ordering

```mermaid
sequenceDiagram
  participant UI as Browser UI
  participant C as Coordinator
  participant L as Event store
  participant A as Simulation adapter
  UI->>C: Start with idempotency key and profile
  alt Duplicate request
    C-->>UI: Return saved disposition
  else Validation fails
    C-->>UI: Reject with checks and no task outcome
  else Validation succeeds and initial rest proof is valid
    C->>L: Persist accepted task and frozen versions
    C-->>UI: Task ID and running status
    C->>L: Persist bounded dispatch intent
    C->>A: Send command and generation
    A->>A: Check generation and authority before execution
    A-->>C: Measured feedback for this command
  end
  UI->>C: Pause or terminate
  C->>C: Revoke authority and advance generation
  C->>A: Install barrier and request hold
  A-->>C: Barrier ACK with cancelled command IDs
  alt Fresh measured rest and queue empty
    A-->>C: Stop evidence for the current generation
    C-->>UI: Stop confirmed
  else Timeout or adapter loss
    C-->>UI: Stop unconfirmed and execution locked
  end
  A-->>C: Late feedback from revoked generation
  C->>L: Audit the rejection
```

The task outcome and execution lock are separate. Termination may become terminal while the stop remains unresolved. A transport reconnection leaves authority revoked until a current proof and the relevant validation permit a subsequent authorized action. [Stop contract](../contract-clarifications.md)

## Resume, manual return and model activation

```mermaid
sequenceDiagram
  participant UI as UI
  participant C as Coordinator
  participant A as Adapter
  participant M as Model registry
  alt Resume a paused task
    UI->>C: Resume
    C->>C: Validate fresh stop proof and saved stage
    C-->>UI: Resume or retain lock with reason
  else Return from manual control
    UI->>C: Return
    C->>A: Revoke manual generation and request new stop
    A-->>C: Current rest evidence or timeout
    C->>C: Validate pose, profile, workspace and stage
    C-->>UI: Resume or require a new takeover
  else Model activation
    UI->>C: Activate compatible model
    alt Idle with no pending start or unresolved stop
      C->>M: Validate and commit version
      M-->>C: Active version or validation failure
      C-->>UI: Report result and active version
    else Maintenance locked
      C-->>UI: Reject activation
    end
  end
```

Recovery proposal and rejection paths are specified in the recovery model. A validated normal stage and a saved recovery state follow distinct continuation rules. [Recovery sequence](../recovery-design.md)
