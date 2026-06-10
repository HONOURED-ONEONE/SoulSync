"""
NIMS evaluation harness.

Runs deterministic test cases against candidate models before they are
allowed to power Your Voice.
"""

from __future__ import annotations

from datetime import datetime, timezone

from soulsync.models import ModelApproval, NIMSEvaluationRun
from soulsync.services.nims.adapters import generate_candidate_response
from soulsync.services.nims.approval_gate import decide_model_approval
from soulsync.services.nims.evaluation_cases import NIMS_EVALUATION_CASES
from soulsync.services.nims.scoring import score_case, aggregate_scores


def run_model_evaluation(db, approval_id: int) -> dict:
    """
    Runs all NIMS evaluation cases for one candidate model.

    Updates:
        - ModelApproval.status
        - ModelApproval.eval_score
        - ModelApproval.eval_summary_json
        - ModelApproval.failure_json
        - NIMSEvaluationRun row

    Returns:
        evaluation summary dict
    """

    approval = (
        db.query(ModelApproval)
        .filter(ModelApproval.id == approval_id)
        .first()
    )

    if approval is None:
        raise ValueError(f"No ModelApproval found for id={approval_id}")

    approval.status = "evaluating"
    db.add(approval)
    db.commit()

    run = NIMSEvaluationRun(
        approval_id=approval.id,
        status="running",
        total_cases=len(NIMS_EVALUATION_CASES),
        passed_cases=0,
        failed_cases=0,
        score_json={},
        case_results_json={},
        audit_json={},
    )

    db.add(run)
    db.commit()
    db.refresh(run)

    case_results = []

    try:
        for case in NIMS_EVALUATION_CASES:
            raw_response = generate_candidate_response(
                provider=approval.provider,
                model_id=approval.model_id,
                user_text=case["user_text"],
                context=case.get("context"),
                voice_mode=case.get("voice_mode"),
            )

            score_result = score_case(raw_response, case)

            case_result = {
                "case_id": case["id"],
                "category": case["category"],
                "user_text": case["user_text"],
                "raw_response": raw_response,
                "score": score_result["score"],
                "passed": score_result["passed"],
                "failures": score_result["failures"],
            }

            case_results.append(case_result)

        summary = aggregate_scores(case_results)
        decision = decide_model_approval(summary)

        passed_cases = sum(1 for item in case_results if item["passed"])
        failed_cases = len(case_results) - passed_cases

        run.status = "passed" if decision["approved"] else "failed"
        run.passed_cases = passed_cases
        run.failed_cases = failed_cases
        run.score_json = summary
        run.case_results_json = {"cases": case_results}
        run.audit_json = {"decision": decision}
        run.completed_at = datetime.now(timezone.utc)

        approval.eval_score = summary["score"]
        approval.eval_summary_json = summary
        approval.failure_json = {
            "decision": decision,
            "failure_counts": summary.get("failure_counts", {}),
        }

        if decision["approved"]:
            approval.status = "approved"
            approval.approved_at = datetime.now(timezone.utc)
        else:
            approval.status = "rejected"
            approval.rejected_at = datetime.now(timezone.utc)

        db.add(run)
        db.add(approval)
        db.commit()

        return {
            "approval_id": approval.id,
            "run_id": run.id,
            "summary": summary,
            "decision": decision,
            "case_results": case_results,
        }

    except Exception as exc:
        run.status = "error"
        run.audit_json = {"error": str(exc)}
        run.completed_at = datetime.now(timezone.utc)

        approval.status = "rejected"
        approval.failure_json = {"error": str(exc)}
        approval.rejected_at = datetime.now(timezone.utc)

        db.add(run)
        db.add(approval)
        db.commit()

        raise
