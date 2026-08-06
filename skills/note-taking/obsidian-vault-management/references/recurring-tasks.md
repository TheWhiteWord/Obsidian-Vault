# Recurring tasks (cron)

Load when a user asks for recurring vault work — "every day…", "each
Monday…", "whenever X happens, note it…". The vault's *maintenance* cron
(daily sweep, weekly optimize) is installed by setup and is not this
reference's concern; this is user-requested **content** workflows.

## The pattern

1. **Pin the workflow.** What the job fetches or researches (source,
   site, query), the exact destination notes/folders, the cadence, and
   who should own the result. Write it as a self-contained prompt — a
   fresh session runs it with no conversation context.
2. **Choose the profile by grants.** A cron job runs as ONE profile with
   that profile's tools and grants. Every destination the job writes must
   be writable by that profile (`obsidian_write` grant). Rule: the profile
   whose grants cover all destinations owns the job.
3. **Split cross-owner workflows and chain them.** If no single profile
   can write every destination (each domain owner has its own), create one
   job per owner and chain them with `context_from: [<previous job id>]` —
   each run injects the previous job's latest output into the prompt, so
   the next owner consumes the artifact the previous one produced. The
   first job in the chain does the research; later jobs read and write
   within their own grants.
4. **Create the job(s)** with the `cronjob` tool: `action=create`,
   `schedule`, self-contained `prompt` (destinations as exact paths),
   `name` (the workflow, not the profile), `skills` (pin the skill the
   job needs, e.g. `obsidian-vault-management` for manager-flavoured
   jobs), `deliver` (origin if the user wants the result delivered,
   local otherwise). `attach_to_session` only when the user wants to
   converse with the job's output.
5. **Verify the first run.** `cronjob action=run` on the new job (or
   `action=list` to confirm the schedule), then check the note actually
   landed in the destination folder. A job that fails its first run is a
   job you fix now, not next week.

## Checks

- [ ] Every destination folder named in the prompt is writable by the
      job's profile (grant check — the write fails loudly if not).
- [ ] Cross-owner workflows are split into one job per owner and chained
      with `context_from`; no single job reaches outside its grants.
- [ ] The prompt is self-contained: exact paths, cadence, and output
      shape; a fresh session could run it cold.
- [ ] First run triggered and the artifacts landed where promised.
- [ ] The schedule and the vault's maintenance jobs don't collide
      meaninglessly (e.g. a heavy research job at the same minute as the
      daily sweep is fine but intentional).

## Pitfalls

- **The write grant is the guard, not the prompt.** A job whose prompt
  reaches outside its profile's grants fails the write loudly — that is
  the design working. Fix the job (or split it), never the grants, to
  accommodate it.
- **Jobs fire only while the gateway runs.** A laptop that sleeps at 05:00
  misses the job until catch-up; a stopped gateway misses it entirely.
  Say so when scheduling something time-sensitive.
- **Cron stores are per-profile.** A job created on one profile is
  invisible to `cronjob list` on another. When in doubt, list on the
  profile you created it on.
- **A manager transfer leaves the maintenance jobs behind.** After
  `--role transfer`, recreate the two maintenance jobs on the successor
  profile (`install_cron_jobs` semantics — they are keyed by name, so
  recreating is idempotent on the new profile; remove the old profile's
  copies).
- **No job prompt may touch gateway lifecycle** (restart/stop the
  gateway) — creation is blocked by the lifecycle guard by design.
