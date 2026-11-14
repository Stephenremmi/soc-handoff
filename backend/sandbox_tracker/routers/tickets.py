"""Authenticated ticket creation, lookup and closure."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth.service import require_service
from ..database.tickets import TicketStore
from ..schemas import TicketCreate, TicketResponse

router = APIRouter(prefix="/tickets", tags=["tickets"], dependencies=[Depends(require_service)])


def ticket_store(request: Request) -> TicketStore:
    return request.app.state.tickets


Tickets = Annotated[TicketStore, Depends(ticket_store)]


@router.post("", response_model=TicketResponse)
def create_ticket(ticket: TicketCreate, store: Tickets):
    return store.create(ticket.run_id, ticket.model_dump(exclude={"run_id"}))


@router.get("/by-run/{run_id}", response_model=TicketResponse)
def find_ticket(run_id: UUID, store: Tickets):
    ticket = store.get(run_id)
    if ticket is None:
        raise HTTPException(404, "Ticket not found")
    return ticket


@router.post("/by-run/{run_id}/close", response_model=TicketResponse)
def close_ticket(run_id: UUID, store: Tickets):
    ticket = store.close(run_id)
    if ticket is None:
        raise HTTPException(404, "Ticket not found")
    return ticket
