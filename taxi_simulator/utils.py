import json
import random
import socket
import requests
from geopy.distance import vincenty

from spade.AID import aid

REGISTER_PROTOCOL = "REGISTER"
CREATE_PROTOCOL = "CREATE"
REQUEST_PROTOCOL = "REQUEST"
TRAVEL_PROTOCOL = "INFORM"

REQUEST_PERFORMATIVE = "request"
ACCEPT_PERFORMATIVE = "accept"
PROPOSE_PERFORMATIVE = "propose"
INFORM_PERFORMATIVE = "inform"

TAXI_WAITING = 10
TAXI_MOVING_TO_PASSENGER = 11
TAXI_IN_PASSENGER_PLACE = 12
TAXI_MOVING_TO_DESTINY = 13

PASSENGER_WAITING = 20
PASSENGER_IN_TAXI = 21
PASSENGER_IN_DEST = 22
PASSENGER_LOCATION = 23


def build_aid(agent_id):
    return aid(name=agent_id + "@127.0.0.1", addresses=["xmpp://" + agent_id + "@127.0.0.1"])


coordinator_aid = build_aid("coordinator")


def random_position():
    with open("taxi_simulator/templates/data/taxi_stations.json") as f:
        stations = json.load(f)["features"]
        pos = random.choice(stations)
        coords = [pos["geometry"]["coordinates"][1], pos["geometry"]["coordinates"][0]]
        lat = float("{0:.6f}".format(coords[0]))
        lng = float("{0:.6f}".format(coords[1]))
        return [lat, lng]


def are_close(coord1, coord2, tolerance=10):
    return vincenty(coord1, coord2).meters < tolerance


def unused_port(hostname):
    """Return a port that is unused on the current host."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((hostname, 0))
    port = s.getsockname()[1]
    s.close()
    return port


def request_path(ori, dest):
    url = "http://router.project-osrm.org/route/v1/car/{src1},{src2};{dest1},{dest2}?geometries=geojson&overview=full"
    src1, src2, dest1, dest2 = ori[1], ori[0], dest[1], dest[0]
    url = url.format(src1=src1, src2=src2, dest1=dest1, dest2=dest2)
    result = requests.get(url)
    result = json.loads(result.content)
    path = result["routes"][0]["geometry"]["coordinates"]
    path = [[point[1], point[0]] for point in path]
    duration = result["routes"][0]["duration"]
    distance = result["routes"][0]["distance"]

    return path, distance, duration