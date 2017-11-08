# -*- coding: utf-8 -*-

"""Main module."""
import json
import faker
import logging

from spade.ACLMessage import ACLMessage
from spade.Agent import Agent
from spade.Behaviour import Behaviour, ACLTemplate, MessageTemplate

from taxi import TaxiAgent
from passenger import PassengerAgent
from utils import random_position, coordinator_aid, CREATE_PROTOCOL, PASSENGER_IN_DEST, REQUEST_PROTOCOL, \
    REQUEST_PERFORMATIVE

logger = logging.getLogger("CoordinatorAgent")


class CoordinatorAgent(Agent):
    def __init__(self, agentjid, password, debug):
        self.taxi_agents = {}
        self.passenger_agents = {}

        self.faker = faker.Factory.create()

        Agent.__init__(self, agentjid=agentjid, password=password, debug=debug)

    def _setup(self):
        logger.info("Coordinator agent running")
        self.wui.setPort(9000)
        self.wui.start()
        logger.info("Web interface running at http://127.0.0.1:{}/app".format(self.wui.port))

        self.wui.setTemplatePath("taxi_simulator/templates")

        self.wui.registerController("app", self.index_controller)
        self.wui.registerController("entities", self.entities_controller)
        self.wui.registerController("generate", self.generate_controller)
        self.wui.registerController("clean", self.clean_controller)

        tpl = ACLTemplate()
        tpl.setProtocol(CREATE_PROTOCOL)
        template = MessageTemplate(tpl)
        self.addBehaviour(CreateAgentBehaviour(), template)

        tpl = ACLTemplate()
        tpl.setProtocol(REQUEST_PROTOCOL)
        template = MessageTemplate(tpl)
        self.addBehaviour(DelegateRequestTaxiBehaviour(), template)

    def index_controller(self):
        return "index.html", {}

    def entities_controller(self):
        result = {
            "taxis": [taxi.to_json() for taxi in self.taxi_agents.values()],
            "passengers": [passenger.to_json() for passenger in self.passenger_agents.values()],
        }
        return None, result

    def generate_controller(self, taxis=1, passengers=1):
        logger.info("Creating taxis.")
        self.create_agent("taxi", number=int(taxis))
        logger.info("Creating passengers.")
        self.create_agent("passenger", number=int(passengers))
        return None, {"status": "done"}

    def clean_controller(self):
        self.stop_agents()
        self.taxi_agents = {}
        self.passenger_agents = {}
        return None, {"status": "done"}

    def stop_agents(self):
        for name, agent in self.taxi_agents.items():
            logger.info("Stopping taxi {}".format(name))
            agent.stop()
        del self.taxi_agents
        for name, agent in self.passenger_agents.items():
            logger.info("Stopping passenger {}".format(name))
            agent.stop()
        del self.passenger_agents

    def create_agent(self, type_, number=1):
        msg = ACLMessage()
        msg.addReceiver(coordinator_aid)
        msg.setProtocol(CREATE_PROTOCOL)
        msg.setPerformative(REQUEST_PERFORMATIVE)
        content = {
            "type": type_,
            "number": number
        }
        msg.setContent(json.dumps(content))
        self.send(msg)


class CreateAgentBehaviour(Behaviour):
    def _process(self):
        msg = self._receive(block=True)
        content = json.loads(msg.content)
        type_ = content["type"]
        number = content["number"]
        if type_ == "taxi":
            for _ in range(number):
                position = random_position()
                name = self.myAgent.faker.user_name()
                password = self.myAgent.faker.password()
                jid = name + "@127.0.0.1"
                taxi = TaxiAgent(jid, password, debug=[])
                taxi.set_id(name)
                taxi.set_position(position)
                self.myAgent.taxi_agents[jid] = taxi
                taxi.start()
                logger.info("Created taxi {} at position {}".format(name, position))
        elif type_ == "passenger":
            for _ in range(number):
                position = random_position()
                name = self.myAgent.faker.user_name()
                password = self.myAgent.faker.password()
                jid = name + "@127.0.0.1"
                passenger = PassengerAgent(jid, password, debug=[])
                passenger.set_id(name)
                passenger.set_position(position)
                self.myAgent.passenger_agents[jid] = passenger
                passenger.start()
                logger.info("Created passenger {} at position {}".format(name, position))


class CoordinatorStrategyBehaviour(Behaviour):
    pass


class DelegateRequestTaxiBehaviour(CoordinatorStrategyBehaviour):
    def _process(self):
        msg = self._receive(block=True)
        msg.removeReceiver(coordinator_aid)
        for taxi in self.myAgent.taxi_agents.values():
            msg.addReceiver(taxi.getAID())
            self.myAgent.send(msg)
            logger.info("Coordinator sent request to taxi {}".format(taxi.getAID().getName()))