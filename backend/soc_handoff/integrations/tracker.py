"""Translate the sandbox tracker HTTP contract into workflow results."""

from typing import Literal

import httpx
from pydantic import BaseModel, Field

from ..errors import NotFound, TrackerUnavailable


class TicketResult(BaseModel):
    id: str = Field(pattern=r"^TKT-(?:[0-9a-f]{32}|[0-9]+)$")
    run_id: str
    status: Literal["open", "closed"]


class TrackerClient:
    def __init__(self, client: httpx.Client, token: str | None):
        self.client = client
        self.token = token

    def _request(self, method, path, run_id, **kwargs):
        if not self.token:
            raise TrackerUnavailable("Tracker credentials are unavailable.")
        try:
            response = self.client.request(
                method, path, headers={"Authorization": f"Bearer {self.token}"}, **kwargs
            )
            if response.status_code == 404 and method == "GET":
                raise NotFound("The tracker has no ticket for this run.")
            response.raise_for_status()
            payload = response.json()
            ticket = TicketResult.model_validate(payload)
        except (httpx.HTTPError, ValueError) as error:
            raise TrackerUnavailable("Tracker did not confirm the ticket operation.") from error
        if ticket.run_id != str(run_id):
            raise TrackerUnavailable("Tracker returned a ticket for a different run.")
        return ticket, payload

    def create(self, run):
        ticket, _ = self._request("POST", "/tickets", run["_id"], json={
            "run_id": run["_id"], "title": run["title"], "alert_id": run["alert_id"], "evidence": run["evidence"],
        })
        if ticket.status != "open":
            raise TrackerUnavailable("Tracker did not confirm an open ticket.")
        return ticket.id

    def close(self, run_id, ticket_id):
        ticket, _ = self._request("POST", f"/tickets/by-run/{run_id}/close", run_id)
        if ticket.status != "closed" or ticket.id != ticket_id:
            raise TrackerUnavailable("Tracker did not confirm closure of this ticket.")

    def read(self, run_id):
        _, payload = self._request("GET", f"/tickets/by-run/{run_id}", run_id)
        return payload
