'''
Description:
This file contains the state machine and helper function to realize the server logic on the car
charging project in TTM4115. The optimization algorith is simply mocked by a constrained
randomization of the system state. 
'''

import logging
import random
import stmpy 
import json
from threading import Thread
from enum import Enum, auto
import paho.mqtt.client as mqtt

# Constants:
MQTT_BROKER = 'broker.hivemq.com'
# MQTT_BROKER = 'localhost'
MQTT_PORT = 1883

MQTT_TOPIC_INPUT = 'gr17/info_from_stations'
MQTT_TOPIC_OUTPUT = 'gr17/info_from_server'

MOCK_ALGORITHM_DELAY = 200

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Replace direct print with logging.info or logging.debug
logging.debug("STMPY Version installed: {}".format(stmpy.__version__))

# Example usage:
def example_debug_function():
    logging.debug("Debugging information here")
    logging.info("General info")
    logging.warning("This is a warning")
    logging.error("This is an error message")
    logging.critical("Critical issue")

# Define data structures for the charging station and charging units:
class ChargingUnitStates(Enum):
    CHARGING_LONG = auto()
    CHARGING_MEDIUM = auto()
    CHARGING_SHORT = auto()

class ChargingUnit:
    def __init__(self, id, state=None):
        self.id = id
        self.state = state
        self.charge_time = 0

MAX_AMOUNT_OF_CHARGING_UNITS = 8 # Amount of rows on the sense hat we are visualizing on
class ChargingStation:
    def __init__(self, id, amout_of_units_in_station):
        self.max_amount_of_units = MAX_AMOUNT_OF_CHARGING_UNITS
        self.station_id = id
        self.amounts_of_units_in_station = amout_of_units_in_station
        self.units = [ChargingUnit(i) for i in range(amout_of_units_in_station)]
    
    def calculate_new_state(self):
        # Define the upper bounds for long and medium
        long_units_indecies    = random.randint(0,2)
        medium_units_indecies  = random.randint(0,3) + long_units_indecies
        # short_units   = self.amounts_of_units_in_station - long_units - medium_units

        # Assign states
        for i, unit in enumerate(self.units):
            if i < long_units_indecies:
                unit.state = ChargingUnitStates.CHARGING_LONG
            elif i < medium_units_indecies:
                unit.state = ChargingUnitStates.CHARGING_MEDIUM
            else:
                unit.state = ChargingUnitStates.CHARGING_SHORT

        # Logging the new state for debugging
        for unit in self.units:
            logging.debug(f"Unit {unit.id} state: {unit.state.name}")



    # This is just to make the message compatible with the MQTT protocol that I use in MQTTX
    def create_and_format_new_state_message(self) -> str:
        # Create a dictionary structure for the message
        message_dict = {
            "Station ID": self.station_id,
            "Units": {unit.id: unit.state.name for unit in self.units}
        }
        # Convert the dictionary to a JSON string
        message_json = json.dumps(message_dict, indent=4)
        return message_json


    def print_instance(self):
        # Print the current state of the charging station
        logging.debug(f"Station ID: {self.station_id}")
        logging.debug(f"Amount of units in station: {self.amounts_of_units_in_station}")
        for unit in self.units:
            logging.debug(f"Unit {unit.id} state: {unit.state.name}")

# Define MQTT Client
class MQTTClient:
    def __init__(self, connected_state_machine_driver: stmpy.Driver):
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.connected_state_machine_driver = connected_state_machine_driver
    
    def on_connect(self, client, userdata, flags, rc):
        #logging.debug("Connected with result code {}".format(str(rc)))
        logging.debug("Connected to MQTT Broker")
        
    # We are just going to mock that we receive new information
    # from the chargin stations, so we just print a mock message
    # and trigger the mock algorithm.
    def on_message(self, client, userdata, msg):
        logging.debug("Received message: {}".format(msg.payload.decode()))
        # logging.debug(f'Payload: {msg.payload.decode("utf-8")}')  
        self.connected_state_machine_driver.send('new_info_received', 'server_state_machine')

    def start(self, broker_address, topic, port=1883, keepalive=60):
        self.client.connect(broker_address, port, keepalive)
        self.client.subscribe(topic)
        try:
            # line below should not have the () after the function!
            thread = Thread(target=self.client.loop_forever)
            thread.start()
        except KeyboardInterrupt:
            print("Interrupted")
            self.client.disconnect()

class ServerStateMachine:
    def __init__(self, mqtt_client: MQTTClient, charging_station: ChargingStation):
        self.mqtt_client = mqtt_client
        self.charging_station = charging_station
        self.stm = self.create_state_machine()

    def create_state_machine(self):

        # Define the state machine by its transitions:
        t0 = {'source': 'initial',
                'target': 'idle'}

        t1 = {'trigger': 'new_info_received',
                'source': 'idle',
                'target': 'calculating_new_state',
                'effect': f'start_timer("t_new_state_calculated", {MOCK_ALGORITHM_DELAY})'}

        t2 = {'trigger': 't_new_state_calculated',
                'source': 'calculating_new_state',
                'target': 'idle',
                'effect': 'deploy_new_state_effect()'}

        stm = stmpy.Machine(name='server_state_machine', transitions=[t0, t1, t2], obj=self)            
        return stm
    
    def deploy_new_state_effect(self):
        self.charging_station.calculate_new_state()
        message = self.charging_station.create_and_format_new_state_message()
        self.mqtt_client.client.publish(MQTT_TOPIC_OUTPUT, message)

station = ChargingStation(1, 8)
station.calculate_new_state()

stm_driver = stmpy.Driver()

mqtt_client = MQTTClient(stm_driver)
mqtt_client.start(MQTT_BROKER, MQTT_TOPIC_INPUT)

stm_driver.add_machine(ServerStateMachine(mqtt_client, station).stm)
stm_driver.start()