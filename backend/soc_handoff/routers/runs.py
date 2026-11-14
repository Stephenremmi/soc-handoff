"""HTTP routes for proposing, approving, and executing an audited ticket."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from ..auth.analyst import Analyst
from ..auth.interactive import require_interactive_action
from ..schemas import RunResponse
from ..services.workflow import HandoffWorkflow

router = APIRouter(prefix="/api/runs", tags=["handoff runs"])
mutation_guard = [Depends(require_interactive_action)]


def get_workflow(request: Request) -> HandoffWorkflow:
    return request.app.state.workflow


Workflow = Annotated[HandoffWorkflow, Depends(get_workflow)]


@router.post("", dependencies=mutation_guard, response_model=RunResponse, response_model_exclude_unset=True)
def propose(actor: Analyst, workflow: Workflow):
    return workflow.propose(actor)


@router.get("/{run_id}", response_model=RunResponse, response_model_exclude_unset=True)
def read_run(run_id: UUID, actor: Analyst, workflow: Workflow):
    return workflow.read(run_id, actor)


@router.post("/{run_id}/approve", dependencies=mutation_guard, response_model=RunResponse, response_model_exclude_unset=True)
def approve(run_id: UUID, actor: Analyst, workflow: Workflow):
    return workflow.approve(run_id, actor)


@router.post("/{run_id}/execute", dependencies=mutation_guard, response_model=RunResponse, response_model_exclude_unset=True)
def execute(run_id: UUID, actor: Analyst, workflow: Workflow):
    return workflow.execute(run_id, actor)


@router.post("/{run_id}/stop", dependencies=mutation_guard, response_model=RunResponse, response_model_exclude_unset=True)
def stop(run_id: UUID, actor: Analyst, workflow: Workflow):
    return workflow.stop(run_id, actor)


@router.post("/{run_id}/rollback", dependencies=mutation_guard, response_model=RunResponse, response_model_exclude_unset=True)
def rollback(run_id: UUID, actor: Analyst, workflow: Workflow):
    return workflow.rollback(run_id, actor)


@router.get("/{run_id}/ticket")
def ticket_status(run_id: UUID, actor: Analyst, workflow: Workflow):
    return workflow.ticket(run_id, actor)
