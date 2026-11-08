# Assignment 2 system design handoff

This handoff records evidence and proposed design text for Zhang Mingbo's sections. The owner still needs to confirm personal decisions, work performed independently and any time estimates before submitting the individual statement.

| Section | Material to integrate | Review owner |
| --- | --- | --- |
| A2-02 and A2-03 | Use the logical and deployment views from the architecture draft and the editable technology, domain and interaction models. The current deployment baseline is one simulation workstation. The cross-process transport and persistent store are open design choices. | Zhang with Ma for recovery boundaries and Hu for UI authority |
| A2-05 | Verify that Pause, Terminate and Return show a separate stop state. Manual control requires current measured rest and an explicit takeover. | Hu with Zhang |
| A2-06 | Retain the platform and integration risks below. Compare them with the research risk register before final sign-off. | Zhang with Ma and Hu |
| A2-07 to A2-09 | Use the source annotations, evidence links and reflection draft below. Obtain owner confirmation before adding personal effort or submission claims. | Zhang and team reviewers |

[Architecture draft](architecture-presentation-draft.md) · [Editable system models](models/zhang-system-models.md) · [Research risk register](ma-risks-and-validation.md)

## Part III validation

| Risk and consequence | Smallest useful check | Decision if evidence fails |
| --- | --- | --- |
| Cloth reset variability compromises candidate comparisons. | Recreate a fixed mid-task failure with the same pose, garment, velocity and contact conditions. Compare mesh, measured joint state and visible patch motion before executing each branch. Record unavailable state and the predeclared tolerance. | Keep dissimilar branches exploratory. Reject identical-start claims and revisit state restoration or paired design. |
| Resource contention delays feedback and stop proof. | Run the adapter and worker at a fixed load. Record memory, GPU use, capture age, queue length and actual stop time. Check the one-second wall deadline on each stop. | Retain the lock on timeout. Separate inference from simulation or reduce its concurrency, then repeat measurements. |
| Disconnect or late replies restore stale authority. | Cut the real coordinator–adapter link after accepting a queued command. Test restart and reconnect separately, replay the old ID, verify no motion and require a new generation and measured rest. | Keep execution locked, retain the failed trace and revise the barrier or transport. |
| Protected simulator data reach the runtime detector. | Tag each source and inspect runtime features. Inject a privileged mesh field into a development observation and verify that validation rejects it. | Restrict privileged geometry to offline evaluation and rebuild affected data. |
| The product profile lacks an asset or upstream dependency. | Start from the recorded commit, verify local asset hashes and run the small baseline before candidate trials. Check the license terms before sharing asset files. | Pin the last validated profile, store hashes and official download references, and reopen platform review if blocked. |

## Slide handoff

- Logical view. Show how a recovery proposal reaches the coordinator and how measured execution returns through the adapter. Describe why only the coordinator can authorize motion.
- Deployment and technology. Show the workstation, isolated Isaac runtime, versioned messages and evidence storage. State which links are proposed.
- Evidence and open risks. Present the 77 checked folding frames, 60 measured joint channels and the 31.7 mm settled reset discrepancy. Describe why branch comparability and external transport matter for Part III.

[Team presentation plan](presentation-plan.md) · [Fold Tops evidence](../research/zhangmingbo/fold-experiments-20261108.md)

## Contribution and AI reflection for owner confirmation

The submitted Zhang workstream includes platform setup and version records, normal trajectory handoff, measured runtime I/O, camera diagnosis, stop evidence, reset measurements and editable architecture sources. Codex helped implement and review collection code, recalculate metrics and prepare handoff documentation. Two mistakes show why the underlying evidence matters. Initial RGB data were black until a lighting comparison isolated the cause. The original launchers could accept a zero exit without new output until a per-run completion marker and regression fixture were added. Reviewers can reconstruct both corrections from the linked PRs and raw records. Individual effort, decisions made independently, and personal evaluation remain for Zhang to confirm. No hours, slide upload or presentation attendance are inferred.

[Architecture PR](https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/pull/6) · [Runtime PR](https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/pull/10) · [Adapter fault PR](https://github.com/MXH814/self-correcting-robotic-clothes-folding-system/pull/11)

## L02 · Learning Efficient Robotic Garment Manipulation with Standardization

<!-- annotation:L02:start -->
Zhou and colleagues study how to prepare a garment for a downstream folding procedure. Their method combines unfolding with standardization. A fling can spread fabric quickly, while a pick and place action can refine its alignment. Spatial action maps select feasible operations, and detected landmarks support a separate folding procedure. The study illustrates why coverage alone can miss important differences between garments that look broadly flat. Sleeve and shoulder alignment still affect whether a fixed folding sequence can be applied.

For our design, this supports a preparation gate that checks garment type, workspace occupancy and readiness for a pinned fold profile. The evaluation record should preserve the initial garment configuration and the controller version. A visually wide garment with one curled sleeve can remain a useful counterexample even if a coverage measure looks favorable. This also supports showing concrete preparation checks to the operator and documenting the reason when an attempt is rejected.

The paper's use of simulation particles for some evaluations and image masks for real experiments motivates a separation between runtime inputs and offline evidence. Our runtime detector should use only the allowed, timestamped observations. Mesh vertices can help inspect a simulated failure afterward. The source does not provide a validation result for our grasp offset or partial slippage cases on a partly folded shirt. We use its distinction between readiness and downstream folding to design the preparation flow and test cases. We retain the project SRS thresholds and validate them on the registered profile.
<!-- annotation:L02:end -->

[ICML paper](https://proceedings.mlr.press/v267/zhou25q.html) · [Reading notes](../research/zhangmingbo/02_APS-Net.md)

## L06 · From Reaction to Anticipation

<!-- annotation:L06:start -->
Xu and colleagues represent manipulation through a graph of subgoals and action transitions. Their framework anticipates failures associated with normal transitions, prepares recovery branches and monitors execution for relevant triggers. The study separates graph construction and motion compilation from online monitoring. This makes the intended return point explicit and helps explain when a recovery step can advance a task rather than restarting the whole procedure. Its simulation uses privileged state in some experiments, and its real experiments include towel folding.

Our design adopts the useful distinction between an observed deviation, a recovery proposal and an authorized continuation. A decision record therefore identifies the current stage, the observed history, the generation and the intended normal controller version. The coordinator applies the action, time and authority gates after it receives a proposal. An unavailable or stale result can be audited without changing who controls the robot. In the interaction models, cancellation and measured rest are separate events because they answer different questions.

The paper informs the design of monitoring and return paths. Its graph cost and real towel result provide no direct estimate of our shirt fold quality or the probability of recovery from slippage. For evaluation we retain local recovery, terminal task outcome and offline quality as separate fields. We also keep unclear contact states visible. This allows a later reviewer to distinguish a successful local movement from a verified continuation under the registered fold policy and budget.
<!-- annotation:L06:end -->

[RSS paper](https://roboticsproceedings.org/rss22/p180.html) · [Reading notes](../research/zhangmingbo/03_AgentChord.md) · [Existing DexGarmentLab annotation](../research/annotated-references.md#l01--wang-y-et-al-dexgarmentlab-dexterous-garment-manipulation-environment-with-generalizable-policy-neurips-2025)
