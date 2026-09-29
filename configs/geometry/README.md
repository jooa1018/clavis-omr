# geometry

Owner: W5.

`constants.yaml` and `rules.yaml` use JSON-subset YAML so the runtime needs no YAML
parser. W5 owns these registries. Values are provisional conventions, frozen
contract defaults, or dimensionless unit conversions; they are not Dev fits.
Rule flags are represented by `GeometryConfig.enabled`; remove an ID to ablate.
G2 ablation is required under the Orchestrator's 2026-09-29 initial-component ruling.

`jitter.yaml` is an empirical **synthetic-v0** joint error table, conditional on
matched detection. Resample a whole row within the target-interline slice to
preserve correlations; do not independently Gaussian-fit its columns. Line-y
and endpoint offsets are in true staff-spaces, interline error is relative,
slope error is dy/dx. Misses are separate slice counts, never zero-error samples.
These are four W2 smoke scores × three fonts at 16/10/8 px, not SYN-Val or real
Dev. Do not infer a real deployment distribution from it. Replace/update the
artifact when Dev v0 is available. The runtime detector does not read jitter.
