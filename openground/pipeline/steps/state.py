"""StateStep — fires the state machine on each packet and writes system_state."""

from __future__ import annotations

from openground.sdk.enrichment import EnrichmentContext, EnrichmentStep
from openground.services.state_machine import StateMachine


class StateStep(EnrichmentStep):
    """Calls StateMachine.on_packet_received() and writes system_state into the envelope."""

    def __init__(self, state_machine: StateMachine) -> None:
        self._state = state_machine

    async def apply(self, ctx: EnrichmentContext) -> None:
        self._state.on_packet_received()
        ctx.envelope["system_state"] = self._state.state.value

    def on_client_connected(self) -> None:
        self._state.on_client_connected()

    def on_client_disconnected(self, total_clients: int) -> None:
        self._state.on_client_disconnected(total_clients)

    def check_timeout(self) -> None:
        self._state.check_timeout()
