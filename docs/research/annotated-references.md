# Annotated references for Assignment 2 — Ma workstream

Status: AI-assisted draft for owner and team review. These annotations explain proposed design influence; they do not claim experiments or joint approval. Each English annotation body is separately checked against the required 200–300 words. Bibliographic headings and source links are excluded from the count.

## L05 — Yuan, J., Wu, Y., and Bajcsy, A. When to Act, Ask, or Learn: Uncertainty-Aware Policy Steering. RSS, 2026.

Source: [version 2](https://arxiv.org/html/2602.22474v2). CAAI A (2024 catalogue); not listed in CCF 2026.

<!-- annotation:L05:start -->
UPS examines how a robot should respond when its action verifier is uncertain. It distinguishes unclear task intent from an underlying policy that cannot generate a suitable action, combining calibrated verification with clarification and corrective learning. Its conclusion explicitly depends on accurate predicted outcomes and complete behavior narrations. We therefore use the paper as a design reference rather than as evidence that a verifier can certify cloth manipulation.

For this project, its most useful influence is the separation between proposing an action, assessing its usefulness, and authorizing execution. The proposed recovery contract permits an empty candidate set and records why a decision was rejected. The task coordinator retains control of dispatch, time limits, and human handoff. A model prediction cannot substitute for measured stop evidence. Because the garment goal is fixed in the MVP, language clarification is not introduced solely to imitate the paper's architecture.

The study also motivates checking whether uncertainty originates in the goal, the available candidates, or insufficient physical observations. This distinction shapes H1 and the candidate coverage diagnostic. However, our current documents do not establish a new uncertainty method or reproduce UPS's coverage guarantee. Before adopting its calibration machinery, we would need to verify calibration assumptions, input distributions, and recalibration after policy changes. Its role in the Design submission is to justify explicit rejection paths and bounded autonomy while making upstream prediction assumptions visible.
<!-- annotation:L05:end -->

## L07 — Ahmed, R., and Begum, M. TAIL-Safe: Task-Agnostic Safety Monitoring for Imitation Learning Policies. RSS, 2026.

Source: [version 2](https://arxiv.org/html/2605.01195v2). CAAI A (2024 catalogue); not listed in CCF 2026.

<!-- annotation:L07:start -->
TAIL-Safe studies runtime monitoring and action correction for a pretrained imitation policy. It combines visibility, recognizability, and graspability signals with a learned safety value function, then uses action gradients for recovery. The paper explicitly characterizes its assurances as empirical and identifies limitations involving training coverage, deterministic policies, and digital twin fidelity. These boundaries prevent us from treating a positive learned score as a formal safety certificate.

The design implication for our folding system is that useful recovery assessment must support decisions, not merely classify a state as abnormal. Nevertheless, the three generic criteria do not directly define the required final folding quality. We preserve separate records for runtime completion, local recovery, offline landmark quality, human assistance, and autonomous success. This separation makes it possible to investigate H2 without assuming that a successful grasp guarantees a successful fold.

We also separate value semantics from probability semantics. TAIL-Safe's safety value cannot be inserted into the SRS probability threshold through arbitrary normalization. A deployed scorer must document its meaning, applicable controller and budget, and validation calibration. Any gradient controller would still pass through the same action and authority checks as other candidates.

The paper informs our proposed scoring boundary and validation risks, not a commitment to reproduce its controller. Before adapting it, we would inspect finite step behavior, projection at action limits, contact failures, and the consistency of reported dimensions and trial counts. Those checks remain open implementation work.
<!-- annotation:L07:end -->

## L08 — Yan, Z., et al. RedFlow: Redirect Failure into Action-level Corrections for Flow-Matching VLA Policies. Preprint, 2026.

Source: [version 2](https://arxiv.org/html/2607.27782v2). No confirmed conference acceptance or conference category assigned in this record.

<!-- annotation:L08:start -->
RedFlow constructs action-level corrective references from a fixed buffer of mixed-quality robot rollouts. It matches chunks using estimated progress and proprioception, then combines quality-weighted imitation, suppression, and correction during offline post-training. Its evaluation includes real clothes folding, making it a direct neighbor of our recovery proposal rather than merely a generic robotics reference. The manuscript acknowledges that comparable execution contexts do not establish identical object or contact states.

This observation motivates a precise question for our project: when do progress and robot configuration fail to identify a transferable garment recovery? Our H1 diagnostic compares current observations, stage conditions, and observed execution history while holding the candidate pool and evaluation budget constant. We must demonstrate mismatches and downstream consequences before claiming that a richer representation is necessary. RedFlow already uses visual history within its progress estimation, so simply saying that our method uses history would not establish novelty.

For the software design, offline target construction is isolated from online dispatch. Retrospective quality labels and future trajectory information may support training, but cannot enter the deployed observation interface. A retrieved or averaged corrective reference must still satisfy the current action profile and authority checks. Unsupported contexts should remain rejectable.

The paper therefore influences data provenance, matching diagnostics, and the proposed interchangeable recovery interface. Full VLA post-training is not a prerequisite for this Design deliverable. Its feasibility, resource costs, and effectiveness in our environment require subsequent measurement, and the publication status remains explicitly recorded as a preprint.
<!-- annotation:L08:end -->

## L01 — Wang, Y., et al. DexGarmentLab: Dexterous Garment Manipulation Environment with Generalizable Policy. NeurIPS, 2025.

Source: [version 3](https://arxiv.org/html/2505.11032v3), [conference record](https://papers.nips.cc/paper_files/paper/2025/hash/c20ac0df6c213db6d3a930fe9c7296c8-Abstract-Conference.html). CCF A (2026 catalogue); CAAI A (2024 catalogue). Author project identifies a Spotlight presentation.

<!-- annotation:L01:start -->
DexGarmentLab combines a garment simulation environment, automated demonstration collection, and the hierarchical HALO policy. It provides a relevant starting point for the fixed tabletop garment profile in our SRS. Its contribution is broader than a folding controller: structural correspondence supports demonstration transfer, while affordance localization and trajectory generation address variation across garments. The paper also distinguishes real-world data collection from policy transfer out of simulation.

Our design treats the platform as a candidate behind a simulation adapter. The public paper and repository do not establish that its assets, robot configuration, observations, and action interfaces are already compatible with our implementation. The environment gate therefore requires a reproducible manipulation, documented units and coordinates, sensor provenance, and an assessment of stop feedback and snapshot fidelity. Platform-specific details must not leak into the recovery scorer's public contract.

The stated simulation limitations also affect evaluation design. Penetration, jitter, or unrealistic contact cannot be hidden by reporting only successful runs. We distinguish method-induced failures from independently demonstrated environment faults, retaining evidence and replacement records. Hidden garment geometry can support offline quality assessment, but cannot be mislabeled as camera-derived input to an online policy.

For research, the environment offers a way to investigate recovery needs, not proof that the proposed gap exists. We must first measure the normal controller's behavior under the registered disturbances. Only then can history or continuation scoring be evaluated against a stable common baseline. These considerations inform the adapter boundary, data isolation decision, and environment validation plan.
<!-- annotation:L01:end -->
