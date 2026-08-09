# Revision 4 transient evidence registration retry

- Revision: 4
- Implementation commit: `3591112`
- Error: the running process retained the pre-commit evidence path `evidence/autonomous-review/revision-4.json` and manager rejected it because block paths must remain under `blocks/`.
- Recovery: resume revision 4 with the committed launcher, which uses `blocks/evidence/autonomous-review/revision-4.json`.
- Tests and verification commands: not run.
