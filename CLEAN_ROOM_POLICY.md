# Clean-room policy

1. Hudiy is treated as a black box.
2. Proprietary source code is not used as implementation input.
3. Proprietary Hudiy assets are not copied.
4. Observations are factual and reproducible.
5. Raw research evidence remains under `research/`.
6. Clean behavioral specifications and compatibility tests remain under `implementation/`.
7. Future implementation work uses `implementation/specs/` and `implementation/tests/` rather than raw reverse-engineering evidence where practical.
8. Public or documented APIs may be treated as compatibility targets.
9. Unknown behavior is marked `Unknown` rather than guessed.
10. The goal is behavioral compatibility, not copying implementation.


## Evidence limits and asset licensing

This policy describes an observation-based reimplementation, not a claim that formally isolated observation/implementation teams were used. The same development process saw reference screens and implemented the interface. Preserve the distinction between evidence of independent code and separate review of visual expression, branding, contracts and dependency licenses. A popular clone project is not legal clearance.

Fonts/icons/libraries require their own provenance and notices. Every dashboard build regenerates `public/THIRD_PARTY_NOTICES.txt` from the installed locked dependencies; Vite copies it beside the distributed browser assets. Do not crop or trace proprietary artwork, reuse original binaries/activation material, or advertise the linked GPL native program as MIT-only. The product is named coscarOS; original Hudiy references identify the historical observation target only.


## Public legal records

The [legal index](LEGAL.md), [Austrian/EU review](docs/LEGAL_REVIEW_AT_EU.md) and [asset/dependency provenance](docs/ASSET_PROVENANCE.md) record this method and its limits. Their publication does not grant third-party rights or replace the unresolved GUI, branding, entitlement and distribution review. Publish the assessment, not private source evidence or device/vehicle data.
