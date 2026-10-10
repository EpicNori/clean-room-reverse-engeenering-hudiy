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
