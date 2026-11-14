"""Evaluate the supplied records without performing a database or tracker write."""

ACTION = "ticket.create"
DESTINATION = "sandbox-case-tracker"
POLICY_ID = "create-sandbox-follow-up"


def check_create(run, actor, policy, finding, *, require_approval):
    if not policy or not policy["enabled"]:
        return "The Atlas policy is disabled or missing."
    if actor["role"] != policy["role"]:
        return "The analyst role is not allowed by policy."
    if run["destination"] != policy["destination"] or run["action"] != policy["action"]:
        return "The proposed action or destination is outside policy."
    if not finding or not finding.get("verified_at") or not finding.get("verified_by"):
        return "The linked finding needs human verification."
    if require_approval:
        approval = run.get("approval", {})
        if approval.get("actor") != actor["_id"]:
            return "This exact action requires explicit analyst approval."
        if approval.get("policy_version") != policy["version"]:
            return "Policy changed after approval. Stop this run and start another."
    return None


def permits_rollback(run, actor, policy):
    return bool(
        policy and policy["allow_rollback"]
        and actor["role"] == policy["role"]
        and run["destination"] == policy["destination"]
    )
