# GenGe Pipeline Maintenance Trigger

fresh_upstream_run_id: 32090231706
fresh_artifact_id: 9308603602
actions:
- remove artifact-less push/pull_request triggers from production Opportunity Discovery
- permanently switch production All-A to all_a_progress_runner
- retire duplicate sidecar workflows
- dispatch canonical Postscan against the successful Fresh All-A artifact
- persist the exact Postscan run id and terminal conclusion
