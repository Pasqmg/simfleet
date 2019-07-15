import json

from .fleetmanager import CoordinatorStrategyBehaviour
from .customer import PassengerStrategyBehaviour
from .transport import TaxiStrategyBehaviour
from .utils import TRANSPORT_WAITING, TRANSPORT_WAITING_FOR_APPROVAL, CUSTOMER_WAITING, TRANSPORT_MOVING_TO_CUSTOMER, \
    CUSTOMER_ASSIGNED
from .protocol import REQUEST_PERFORMATIVE, ACCEPT_PERFORMATIVE, REFUSE_PERFORMATIVE, PROPOSE_PERFORMATIVE, \
    CANCEL_PERFORMATIVE, REGISTER_PROTOCOL, DEREGISTER_PROTOCOL
from .helpers import PathRequestException


################################################################
#                                                              #
#                     FleetManager Strategy                    #
#                                                              #
################################################################
class DelegateRequestTaxiBehaviour(CoordinatorStrategyBehaviour):
    """
    The default strategy for the FleetManager agent. By default it delegates all requests to all transports.
    """

    async def run(self):
        msg = await self.receive(timeout=5)
        self.logger.debug("Manager received message: {}".format(msg))
        if not msg:
            return
        performative = msg.get_metadata("performative")
        if performative == REGISTER_PROTOCOL:
            content = json.loads(msg.body)
            self.add_transport(content)
            return
        elif performative == DEREGISTER_PROTOCOL:
            name = msg.body
            self.get_out_transport(name)
            return
        if msg:
            for transport in self.get_transport_agents().values():
                msg.to = str(transport["jid"])
                self.logger.debug("Manager sent request to transport {}".format(transport["name"]))
                await self.send(msg)


################################################################
#                                                              #
#                     Transport Strategy                       #
#                                                              #
################################################################
class AcceptAlwaysStrategyBehaviour(TaxiStrategyBehaviour):
    """
    The default strategy for the Taxi agent. By default it accepts every request it receives if available.
    """

    async def run(self):
        if not self.agent.registration:
            await self.send_registration()

        msg = await self.receive(timeout=5)
        if not msg:
            return
        self.logger.debug("Transport received message: {}".format(msg))
        content = json.loads(msg.body)
        performative = msg.get_metadata("performative")

        self.logger.debug("Transport {} received request protocol from customer {}.".format(self.agent.name,
                                                                                        content["customer_id"]))
        if performative == REQUEST_PERFORMATIVE:
            if self.agent.status == TRANSPORT_WAITING:
                await self.send_proposal(content["customer_id"], {})
                self.agent.status = TRANSPORT_WAITING_FOR_APPROVAL

        elif performative == ACCEPT_PERFORMATIVE:
            if self.agent.status == TRANSPORT_WAITING_FOR_APPROVAL:
                self.logger.debug("Transport {} got accept from {}".format(self.agent.name,
                                                                      content["customer_id"]))
                try:
                    self.agent.status = TRANSPORT_MOVING_TO_CUSTOMER
                    await self.pick_up_customer(content["customer_id"], content["origin"], content["dest"])
                except PathRequestException:
                    self.logger.error("Transport {} could not get a path to customer {}. Cancelling..."
                                      .format(self.agent.name, content["customer_id"]))
                    self.agent.status = TRANSPORT_WAITING
                    await self.cancel_proposal(content["customer_id"])
                except Exception as e:
                    self.logger.error("Unexpected error in transport {}: {}".format(self.agent.name, e))
                    await self.cancel_proposal(content["customer_id"])
                    self.agent.status = TRANSPORT_WAITING
            else:
                await self.cancel_proposal(content["customer_id"])

        elif performative == REFUSE_PERFORMATIVE:
            self.logger.debug("Transport {} got refusal from {}".format(self.agent.name,
                                                                   content["customer_id"]))
            if self.agent.status == TRANSPORT_WAITING_FOR_APPROVAL:
                self.agent.status = TRANSPORT_WAITING


################################################################
#                                                              #
#                       Customer Strategy                      #
#                                                              #
################################################################
class AcceptFirstRequestTaxiBehaviour(PassengerStrategyBehaviour):
    """
    The default strategy for the Customer agent. By default it accepts the first proposal it receives.
    """

    async def run(self):
        if self.agent.status == CUSTOMER_WAITING:
            await self.send_request(content={})

        msg = await self.receive(timeout=5)

        if msg:
            performative = msg.get_metadata("performative")
            transport_id = msg.sender
            if performative == PROPOSE_PERFORMATIVE:
                if self.agent.status == CUSTOMER_WAITING:
                    self.logger.debug("Customer {} received proposal from transport {}".format(self.agent.name,
                                                                                           transport_id))
                    await self.accept_transport(transport_id)
                    self.agent.status = CUSTOMER_ASSIGNED
                else:
                    await self.refuse_transport(transport_id)

            elif performative == CANCEL_PERFORMATIVE:
                if self.agent.transport_assigned == str(transport_id):
                    self.logger.warning("Customer {} received a CANCEL from Transport {}.".format(self.agent.name, transport_id))
                    self.agent.status = CUSTOMER_WAITING

