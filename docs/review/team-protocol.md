# Team protocol (developer / reviewer / tester)

Repository: /home/hermesbot/workspace/uk-accent-stt-eval
Authoritative spec: docs/implementation-plan.md. Do NOT open or print .env, .env.local, .env.sample.

Subagents cannot write files in this environment (Zed over ACP denies writes). The orchestrator saves code
and runs pytest, then relays real output.

File return format (developer only). For each file created or changed, return its COMPLETE content framed as:

  =====FILE: relative/path/from/repo/root=====
  (the whole file content here, no markdown fences)
  =====END FILE=====

followed by NOTES and QUESTIONS sections.
