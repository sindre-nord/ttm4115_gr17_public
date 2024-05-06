'''
Description:
This file contains the state machine and helper function to realize the the logic for the workings
of a charging station (much like a gas station with several pumps). The target state is recieved over
MQTT from the server. This code contains both the state machine on the "Station Manager", and the
individual state machines for the charging units. This code is mostly responsible for handling the 
transistion between the target states. Charging is emulated by setting a pin on the Pi high.

Indicating the status of the charging station is done by setting lights on the sense hat.


Notes:
- Comments: We don't care what the line does unless its a really ugly lambda function. or
    if its a really complex line of code. We care more about WHY it is there.
- Logging: Some messages should suprisingly not be a error, if it is expected to happen,
    please don't misuse it. 
    As per now, info generally means that something is happening, debug is for showing
    all the values and stuff. Warning is for when something is not as expected, but the
    program can still run.

'''
import logging
from typing import Dict, Optional
import stmpy
import json
import paho.mqtt.client as mqtt
from threading import Thread
from enum import Enum, auto

from typing import Dict, List

# Custom imports
# import physical_charger_interface as UI
import custom_utils as custom_utils

# Constants
MQTT_BROKER = 'broker.hivemq.com'
#MQTT_BROKER = 'localhost'
MQTT_PORT = 1883
MQTT_TOPIC_RECEIVE_STATE = 'gr17/info_from_server'
AMOUNT_OF_CHARGING_UNITS = 8

MQTT_UI_RECIVE_TOPIC = 'gr17/info_from_UI'
MQTT_UI_SEND_TOPIC = 'gr17/info_to_UI'

MQTT_QUEUE_UI_SEND_TOPIC = 'gr17/info_to_queue_UI'
MQTT_QUEUE_UI_RECEIVE_TOPIC = 'gr17/info_from_queue_UI'

MQTT_UI_USER_REQUEST_CHARGE_TOPIC = 'gr17/user_requesting_to_charge'

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


running_on_pi = custom_utils.script_is_running_on_pi()

if running_on_pi:
    from sense_hat import SenseHat
    sense_hat = SenseHat()

class MqttSTMPYInterfaceHandler():

    '''
    This is a generic as I could make it. The most specific code here is the handlers
    for the topics, but at some point stuff will be case specific, this should be adaquate.

    The stucture here is as follows:
    The topic_to_action dict holds the topics and their corresponding handlers.
    Each handler is a function that takes a message and a driver as arguments.
    The handle_message method is the single point of entry for all messages, 
    and it just checks if that topic has a registered handler, and if it does, it calls it.
    '''
    def __init__(self, connected_state_machine_driver: stmpy.Driver):
        # Dict to hold the topics and their corresponding handlers
        self.topic_to_action: Dict[str, List[callable]] = {}
        self.connected_state_machine_driver = connected_state_machine_driver

    # Register a handler for a topic, the handler should take a message as an argument
    def register_topic_handler(self, topic:str, handler:callable):
        if topic not in self.topic_to_action:
            self.topic_to_action[topic] = []
        self.topic_to_action[topic].append(handler)

    # Single point of entry for all messages.
    def handle_message(self, topic:str, message:str):
        logging.info(f"Handling message for topic {topic}")
        if topic in self.topic_to_action:
            logging.debug(f"Found handler for topic {topic}")
            for handler in self.topic_to_action[topic]:
                handler(message, self.connected_state_machine_driver)
        else:
            logging.warning(f"No handler registered for topic {topic}")


###############################
# Very case specific handlers #
###############################

def handle_UI_message(message:str, stm_driver:stmpy.Driver):
    # Based on the ID in the message, we can find the corresponding charging unit
    # and send a message to it. Current format is "unit_id, state" where state is a string
    # saying either "CONNECTED" og "DISCONNECTED"
    unit_id, state = message.split(',')
    unit_id = int(unit_id)
    state = state.strip()
    logging.debug(f"UI message: Unit {unit_id} is {state}")
    if state == "CONNECTED":
        logging.debug(f"Car connected to unit {unit_id}")
        stm_driver.send('car_connected', f'charging_unit_{unit_id}')
    elif state == "DISCONNECTED":
        logging.debug(f"Car disconnected from unit {unit_id}")
        stm_driver.send('car_disconnected', f'charging_unit_{unit_id}')

def handle_charging_state_update(message, stm_driver):
    stm_driver.send('new_state_received_from_server', 'charging_manager', 
                    args=[message])
    
def handle_user_requesting_to_charge(message, stm_driver):
    stm_driver.send('user_requesting_to_charge', 'charging_manager',
                    args=[message])
    
#################################
# End of case specific handlers #
#################################
    
# Define MQTT Client
class MQTTClient:
    '''
    As generic as I could make it, ref the interface. 
    '''
    def __init__(self, mqtt_stmpy_interface_handler: MqttSTMPYInterfaceHandler):
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        self.mqtt_stmpy_interface_handler = mqtt_stmpy_interface_handler
    
    def on_connect(self, client, userdata, flags, rc):
        logging.info("Connected to MQTT Broker")
        
    def on_message(self, client, userdata, msg:mqtt.MQTTMessage):
        logging.debug("Received message: {}".format(msg.payload.decode()))
        self.mqtt_stmpy_interface_handler.handle_message(msg.topic, msg.payload.decode())

    def start(self, broker_address, port=1883, keepalive=60):
        self.client.connect(broker_address, port, keepalive)
        try:
            thread = Thread(target=self.client.loop_forever) # Keeps the client running in a separate thread
            thread.start()
        except KeyboardInterrupt: # This is really unfortunate, but this never seems to be called
            print("Interrupted")
            self.client.disconnect()
    
    def stop(self):
        self.client.disconnect()
    
    def register_topic(self, topic:str, handler:callable):
        self.mqtt_stmpy_interface_handler.register_topic_handler(topic, handler)
        self.client.subscribe(topic)
                                                        

# Made with an enum because the __member__ attribute can
# return the name of the enum value which paried well
# with the way strings are used a lot in this code.
class ChargingUnitDuration(Enum):
    CHARGING_SHORT = 0
    CHARGING_MEDIUM = 1
    CHARGING_LONG = 2

# Possible alternative
# CHARGING_SHORT = "CHARGING_SHORT"
# CHARGING_MEDIUM = "CHARGING_MEDIUM"
# CHARGING_LONG = "CHARGING_LONG"


DEFAULT_CHARGING_UNIT_DURATION = ChargingUnitDuration.CHARGING_SHORT
class ChargingUnitState:
    def __init__ (self, unit_id):
        self.unit_id = unit_id
        self.current_duration = None
        self.target_duration = DEFAULT_CHARGING_UNIT_DURATION # Does not really relate to a unit, so it should not be there.
        self.current_user = None


LONG_CHARGE_TIME = 15
MEDIUM_CHARGE_TIME = 10
SHORT_CHARGE_TIME = 5

class ChargingUnitStateMachine:
    '''
    State machine for the individual chargers on a station. In this realization it's
    more coupled with the UI than the specification intended for.

    Current issue: The timer that controls the charging duration is not properly implemented. 
    It's just the one static timer. 

    Could be nice to add some effects to the lights to indicate different states. 
    '''
    def __init__(self, id, connected_state_machine_driver: stmpy.Driver, mqtt_client: mqtt.Client):
        self.unit_id = id
        self.connected_state_machine_driver = connected_state_machine_driver
        self.state = None # ChargingUnitDuration, can't decide on a meaningful default value
                            # the light will be turned off in this case.
        self.stm = self.create_state_machine()
        self.mqtt_client = mqtt_client

    def create_state_machine(self):
        state_transitions = [
            {'trigger': 'init', 
                'source': 'initial', 'target': 'waiting_for_state', 
                'effect': 'request_state_from_station_manager()'},
            {'trigger': 'recived_state', 
                'source': 'waiting_for_state', 'target': 'available_to_charge', 
                'effect': 'update_state(*); update_sense_hat_matrix(); update_UI()'},
            {'trigger': 'car_connected', 
                'source': 'available_to_charge', 'target': 'charging', 
                'effect': 'update_sense_hat_matrix(); start_timer_for_x_seconds()'},
            {'trigger': 'charge_complete', 
                'source': 'charging', 'target': 'waiting_for_disconnect', 
                'effect': 'update_sense_hat_matrix()'},
            {'trigger': 'car_disconnected', 
                'source': 'waiting_for_disconnect', 'target': 'waiting_for_state', 
                'effect': 'request_state_from_station_manager; update_sense_hat_matrix()'},
            # Happens when the car is disconnected before the charge is complete
            {'trigger': 'car_disconnected', 
                'source': 'charging', 'target': 'waiting_for_state', 
                'effect': 'request_state_from_station_manager; update_sense_hat_matrix(); stop_timer("charge_complete")'} 
        ]
        machine = stmpy.Machine(name=f'charging_unit_{self.unit_id}', transitions=state_transitions, obj=self)
        return machine

    # Needs to update the corresponding pixel of the sense hat.
    def update_sense_hat_matrix(self):
        logging.debug(f"Updating display for unit {self.unit_id}.")
        if not running_on_pi:
            # Show a log message for the debugging
            if self.state == ChargingUnitDuration.CHARGING_LONG:
                logging.info(f"Unit {self.unit_id} is charging long.")
            elif self.state == ChargingUnitDuration.CHARGING_MEDIUM:
                logging.info(f"Unit {self.unit_id} is charging medium.")
            elif self.state == ChargingUnitDuration.CHARGING_SHORT:
                logging.info(f"Unit {self.unit_id} is charging short.")
            else:
                logging.info(f"Unit {self.unit_id} is in an unknown state.")
            logging.debug("Not running on a Pi, skipping sense hat update.")
            return
        # This sets the x'th row with the corresponding color
        # That would be the top row with the usb ports pointing to the right
        # and power pointing down.
        if self.state == ChargingUnitDuration.CHARGING_LONG:
            sense_hat.set_pixel(self.unit_id, 0, (255, 0, 0)) # Red
        elif self.state == ChargingUnitDuration.CHARGING_MEDIUM:
            sense_hat.set_pixel(self.unit_id, 0, (255, 255, 0)) # Yellow
        elif self.state == ChargingUnitDuration.CHARGING_SHORT:
            sense_hat.set_pixel(self.unit_id, 0, (0, 255, 0)) # Green
        else:
            sense_hat.set_pixel(self.unit_id, 0, (0, 0, 0)) # Off
            

    def request_state_from_station_manager(self):
        logging.debug(f"Unit {self.unit_id} requesting state.")
        self.connected_state_machine_driver.send(f'chargin_unit_requests_charge_state', 'charging_manager', 
                                                    args=[self.unit_id])

    def update_state(self, new_state:ChargingUnitDuration):
        logging.debug(f"Unit {self.unit_id} changing state to {new_state}.")
        self.state = new_state

    def update_UI(self):
        logging.info("Updating UI...")
        self.mqtt_client.publish(MQTT_UI_SEND_TOPIC, f"{self.unit_id}, {self.state}")

    def start_timer_for_x_seconds(self):
        if self.state == ChargingUnitDuration.CHARGING_LONG:
            self.stm.start_timer('charge_complete', LONG_CHARGE_TIME * 1000)
        elif self.state == ChargingUnitDuration.CHARGING_MEDIUM:
            self.stm.start_timer('charge_complete', MEDIUM_CHARGE_TIME * 1000)
        elif self.state == ChargingUnitDuration.CHARGING_SHORT:
            self.stm.start_timer('charge_complete', SHORT_CHARGE_TIME * 1000)
        else:
            logging.error(f"Unknown state {self.state} for unit {self.unit_id}")

    # Mock of a charge of payment based on the time spent charging
    def charge_user(self):
        pass 

class ChargingManagerStateMachine:
    '''
    Handles the target state from the server, and passes them out to the units per request.

    The data from the server contains some info we don't really care about. The server does not
    dictate which unit gets a state, it only cares for the amount of each state. However, having
    the same structure on both target and current state was easier to handle.

    '''
    def __init__(self, station_id,connected_state_machine_driver: stmpy.Driver, mqtt_client: mqtt.Client):
        self.station_id = station_id
        self.mqtt_client = mqtt_client
        # Contains a list of users waiting for a certain state
        self.waiting_queue = {
            ChargingUnitDuration.CHARGING_SHORT: [],
            ChargingUnitDuration.CHARGING_MEDIUM: [],
            ChargingUnitDuration.CHARGING_LONG: []
        }
        self.charging_unit_states = {unit_id: ChargingUnitState(unit_id) for unit_id in range(AMOUNT_OF_CHARGING_UNITS)}

        self.stm = self.create_state_machine()
        self.connected_state_machine_driver = connected_state_machine_driver

    def create_state_machine(self):
        t0 = {'trigger': 'init', 'source': 'initial', 'target': 'idle'}
        t1 = {'trigger': 'chargin_unit_requests_charge_state', 
                'source': 'idle', 
                'target': 'idle', 
                'effect': 'handle_state_request_from_chargin_unit(*)'}
        t2 = {'trigger': 'new_state_received_from_server',
                'source': 'idle', 
                'target': 'updating_info', 
                'effect': 'update_state_with_data_from_server(*)'}
        t3 = {'trigger': 'info_updated',
                'source': 'updating_info',
                'target': 'idle',
                'effect': 'print_unit_states()'}
        t4 = {'trigger': 'user_requesting_to_charge',
                'source': 'idle',
                'target': 'idle',
                'effect': 'handle_user_requesting_to_charge(*)'}
        
        machine = stmpy.Machine(name='charging_manager', transitions=[t0, t1, t2, t3, t4], obj=self)
        return machine

    def handle_state_request_from_chargin_unit(self, unit_id : int):
        """
        As mentioned in the ChargingManagerStateMachine, the server does not dictate which unit gets a state,
        it only cares for the amount of each state. We assign the states per amount, and prioritize the states
        in the following order: SHORT, MEDIUM, LONG.

        This beeing triggered implies that the unit is ready for a new user.
        """
        logging.debug(f"Handling state request for Unit {unit_id}.")

        # Count the amount of each state in the target states and the current states
        target_state_counts = {
            ChargingUnitDuration.CHARGING_SHORT: 0,
            ChargingUnitDuration.CHARGING_MEDIUM: 0,
            ChargingUnitDuration.CHARGING_LONG: 0
        }
        current_state_counts = {
            ChargingUnitDuration.CHARGING_SHORT: 0,
            ChargingUnitDuration.CHARGING_MEDIUM: 0,
            ChargingUnitDuration.CHARGING_LONG: 0
        }
        for unit in self.charging_unit_states.values():
            target_state_counts[unit.target_duration] += 1 # There will always be a default target state
            try:
                current_state_counts[unit.current_duration] += 1
            except KeyError:
                # If the current state is not set, it will be None
                pass

        logging.debug(f"Target state counts: {target_state_counts}")
        logging.debug(f"Current state counts: {current_state_counts}")

        # Prioritize SHORT, then MEDIUM, then LONG
        # This dynamic allocation skrews up the target, so target should not be updated here.
        # It might be better to move it out of the individual unit states as we allocate them here.
        # Target states make more sense do save by the count.
        if target_state_counts[ChargingUnitDuration.CHARGING_SHORT] > current_state_counts[ChargingUnitDuration.CHARGING_SHORT]:
            self.charging_unit_states[unit_id].current_duration = ChargingUnitDuration.CHARGING_SHORT
            self.connected_state_machine_driver.send('recived_state', f'charging_unit_{unit_id}', args=[ChargingUnitDuration.CHARGING_SHORT])
        elif target_state_counts[ChargingUnitDuration.CHARGING_MEDIUM] > current_state_counts[ChargingUnitDuration.CHARGING_MEDIUM]:
            self.charging_unit_states[unit_id].current_duration = ChargingUnitDuration.CHARGING_MEDIUM
            self.connected_state_machine_driver.send('recived_state', f'charging_unit_{unit_id}', args=[ChargingUnitDuration.CHARGING_MEDIUM])
        elif target_state_counts[ChargingUnitDuration.CHARGING_LONG] > current_state_counts[ChargingUnitDuration.CHARGING_LONG]:
            self.charging_unit_states[unit_id].current_duration = ChargingUnitDuration.CHARGING_LONG
            self.connected_state_machine_driver.send('recived_state', f'charging_unit_{unit_id}', args=[ChargingUnitDuration.CHARGING_LONG])
        else:
            # Target and current state are the same (just the amount of each state is equal)
            self.connected_state_machine_driver.send('recived_state', f'charging_unit_{unit_id}', args=[self.charging_unit_states[unit_id].current_duration])
        
        # There can't be a user assigned to this unit, as it requested a state. They are assigned when this is requested, 
        # or when a user requests to charge.
        self.charging_unit_states[unit_id].current_user = None 
        self.check_queue_and_assign_users(unit_id)

    # Expected format: {"IDSTRING123": "CHARGING_LONG"}
    def handle_user_requesting_to_charge(self, mqtt_message:str):
        logging.info(f"Handling user requesting to charge: {mqtt_message}")
        try:
            data = json.loads(mqtt_message)
        except json.JSONDecodeError:
            logging.error("Couldnt parse mqtt message to enlist user in queue.")
            return

        for user_id_string, state_string in data.items():
            state = ChargingUnitDuration[state_string]
            self.waiting_queue[state].append(user_id_string)
            logging.info(f"Added user {user_id_string} to queue for state {state}.")
        self.show_queue_for_debugging()
        self.show_current_unit_states()
        self.check_queue_and_assign_users()
        self.show_queue_for_debugging()
        
    def show_queue_for_debugging(self):
        logging.info(f"Queue for SHORT: {self.waiting_queue[ChargingUnitDuration.CHARGING_SHORT]}")
        logging.info(f"Queue for MEDIUM: {self.waiting_queue[ChargingUnitDuration.CHARGING_MEDIUM]}")
        logging.info(f"Queue for LONG: {self.waiting_queue[ChargingUnitDuration.CHARGING_LONG]}")

    def show_current_unit_states(self):
        for unit_id, unit in self.charging_unit_states.items():
            logging.info(f"Unit {unit_id} is in state {unit.current_duration}, with target {unit.target_duration} and is serving user {unit.current_user}.")

    def check_queue_and_assign_users(self, unit_id:int=None):
        ''' There are two scenarios here:
        1. A user has entered the queue and does not have to wait. It should be assigned to a unit.
        2. A user has entered the queue and has to wait.'''
        logging.info(f"Trying to assign users to units.")
        if unit_id: 
            # The charging unit requested a state (and can take a new user)
            # Check if there are any users in the queue for the state of the unit
            if self.waiting_queue[self.charging_unit_states[unit_id].current_duration]: # There are users in the queue
                user_id_string = self.waiting_queue[self.charging_unit_states[unit_id].current_duration].pop(0)
                self.charging_unit_states[unit_id].current_user = user_id_string
                logging.info(f"Assigned user {user_id_string} to unit {unit_id}.")
            else:
                logging.info(f"No users in queue for unit {unit_id}.")
        else:
            # This means that a user has requested to charge, but does not mean there is an available unit.
            # check, and if not, do nothing, they have been added to the waiting queue.
            for unit_id, unit in self.charging_unit_states.items():
                if not unit.current_user and unit.current_duration:
                    # Check if we have any users waiting for a unit of this state
                    if len(self.waiting_queue[unit.current_duration]): # Will return False if the list is empty
                        # logging.info(f"The queue is not empty for duration:{unit.target_duration}")
                        user_id_string = self.waiting_queue[unit.current_duration].pop(0)
                        unit.current_user = user_id_string
                        logging.info(f"Assigned user {user_id_string} to unit {unit_id} with target duration {unit.target_duration}.")
                    else:
                        logging.info(f"No users in queue for unit {unit_id}.")
                else:
                    logging.info(f"Unit {unit_id} is already serving a user.")
                # if not unit.current_user and len(self.waiting_queue[unit.target_duration]):
                #     user_id_string = self.waiting_queue[unit.target_duration].pop(0)
                #     unit.current_user = user_id_string
                #     logging.info(f"Assigned user {user_id_string} to unit {unit_id}.")

            # Add the person to the queue if there are no available units
            #logging.info("No available units for new users.")

        self.show_queue_for_debugging()

        self.update_queue_ui()


    # Update the charging unit target states. Ignore the message if station id is not the same as this station
    # expected format:
    # {
    # "Station ID": 1,
    # "Units": {
    #     "0": "CHARGING_LONG",
    #     "1": "CHARGING_MEDIUM",
    #     "2": "CHARGING_MEDIUM"
    #     [...]
    #     }
    # }
    def update_state_with_data_from_server(self, *args):
        # args[0] is expected to be the JSON string
        json_string = args[0]
        try:
            data = json.loads(json_string)  # Data is now a dictionary
        except json.JSONDecodeError:
            logging.error("Could not parse JSON string to update state.")
            return
        logging.debug(f"Updating state with data from server: {data}")
        # Check if the station ID matches
        if data["Station ID"] == self.station_id:
            # Update the charging unit target states
            for unit_id_str, state_str in data["Units"].items():
                unit_id = int(unit_id_str)  # Convert string keys to integer
                # Convert the state string to an enum value
                if state_str in ChargingUnitDuration.__members__:
                    # self.charging_unit_target_states[unit_id] = ChargingUnitDuration[state_str]
                    self.charging_unit_states[unit_id].target_duration = ChargingUnitDuration[state_str]
                    logging.debug(f"Unit {unit_id} is set to {state_str}.")
                    logging.debug(f"Unit {unit_id} is set to {self.charging_unit_states[unit_id].target_duration}.")
                else:
                    logging.error(f"Unknown state {state_str} for unit {unit_id}")
            self.connected_state_machine_driver.send('info_updated', 'charging_manager')
        else:
            # Perhaps should be a warning, it is expected behavior on a lot of messages.
            logging.warning(f"Ignoring message for station ID {data['Station ID']}. This station is ID {self.station_id}.")
        #self.print_unit_states() # Only for debugging, it was a bit too much
                                    # to have alongside normal debug statements.

    # Just a helper for debugging
    def print_unit_states(self):
        # for unit_id, state in self.charging_unit_target_states.items():
        for unit_id, state in self.charging_unit_states.items():
            logging.info(f"Unit {unit_id} is set to {state.target_duration} and is {state.current_duration}.")

    # This is the data structure on the other end:
    # {
    #     "users_that_can_go_to_charging": {
    #         "CHARGING_LONG": ["User 1", "User 2", "User 3", "User 4"],
    #         "CHARGING_MEDIUM": ["User 5", "User 6", "User 7"],
    #         "CHARGING_SHORT": ["User 8", "User 9", "User 10"]
    #     },
    #     "users_waiting_for_charging": {
    #         "CHARGING_LONG": ["User 11", "User 12", "User 13", "User 14"],
    #         "CHARGING_MEDIUM": ["User 15", "User 16", "User 17"],
    #         "CHARGING_SHORT": ["User 18", "User 19", "User 20"]
    #     }
    # }
    def update_queue_ui(self):
        # Prepare data structures for users currently charging and those waiting
        users_charging = {duration.name: [] for duration in ChargingUnitDuration}
        users_waiting = {duration.name: list(queue) for duration, queue in self.waiting_queue.items()}
        
        # Print all users currently charging
        for unit_id, unit in self.charging_unit_states.items():
            if unit.current_user:
                users_charging[unit.current_duration.name].append(f"Unit {unit_id}: {unit.current_user}")  # Added unit ID to the f-string
            
        
        # Calculated estimated wait time for a new user:
        # Find the amount of users in the queue for the target state of each unit

        estimated_wait_time = [0, 0, 0] # List of expected wait time for each queue. It just a count of how many users are in each queue,
                                    # multiplied by the time it takes to charge for that state.
        for duration, queue in self.waiting_queue.items():
            chargers_serving_queue = 0
            if duration == ChargingUnitDuration.CHARGING_SHORT:
                # Take into account how many chargers are serving the queue
                for unit in self.charging_unit_states.values():
                    if unit.current_duration == ChargingUnitDuration.CHARGING_SHORT:
                        chargers_serving_queue += 1
                if chargers_serving_queue == 0:
                    estimated_wait_time[0] = "No unit serving at the moment."
                else:
                    estimated_wait_time[0] = ((len(queue) // chargers_serving_queue)+1) * SHORT_CHARGE_TIME
            elif duration == ChargingUnitDuration.CHARGING_MEDIUM:
                for unit in self.charging_unit_states.values():
                    if unit.current_duration == ChargingUnitDuration.CHARGING_MEDIUM:
                        chargers_serving_queue += 1
                if chargers_serving_queue == 0:
                    estimated_wait_time[1] = "No unit serving at the moment."
                else:
                    estimated_wait_time[1] = ((len(queue) // chargers_serving_queue)+1) * MEDIUM_CHARGE_TIME
            elif duration == ChargingUnitDuration.CHARGING_LONG:
                for unit in self.charging_unit_states.values():
                    if unit.current_duration == ChargingUnitDuration.CHARGING_LONG:
                        chargers_serving_queue += 1
                if chargers_serving_queue == 0:
                    estimated_wait_time[2] = "No unit serving at the moment."
                else:
                    estimated_wait_time[2] = ((len(queue) // chargers_serving_queue)+1) * LONG_CHARGE_TIME

        data_to_send = {
            "users_that_can_go_to_charging": users_charging,
            "users_waiting_for_charging": users_waiting,
            "estimated_wait_times": estimated_wait_time
        }
        logging.debug(f"Data to send to UI: {data_to_send}")
        # Convert the data structure to a JSON string
        json_message = json.dumps(data_to_send)
        
        # Publish the message to the MQTT topic for UI updates
        logging.info("Updating UI with current charging and waiting queues.")
        self.mqtt_client.publish(MQTT_QUEUE_UI_SEND_TOPIC, json_message)


# Create the stmpy driver and add state machines
stmpy_driver = stmpy.Driver()

# Initialize the interface handler
mqtt_stmpy_interface_handler = MqttSTMPYInterfaceHandler(stmpy_driver)

# Initialize and add the MQTT Client
mqtt_client = MQTTClient(mqtt_stmpy_interface_handler)
mqtt_client.start(MQTT_BROKER)

# Connect the handlers
mqtt_client.register_topic(MQTT_UI_RECIVE_TOPIC, handle_UI_message)
mqtt_client.register_topic(MQTT_TOPIC_RECEIVE_STATE, handle_charging_state_update)
mqtt_client.register_topic(MQTT_QUEUE_UI_RECEIVE_TOPIC, handle_user_requesting_to_charge)

# Initialize and add the Charging Manager State Machine
charging_manager_stm = ChargingManagerStateMachine(1, stmpy_driver, mqtt_client.client).stm # 1 is station id.
stmpy_driver.add_machine(charging_manager_stm)

# Initialize and add Charging Unit State Machines
for unit_id in range(AMOUNT_OF_CHARGING_UNITS):
    charging_unit_stm = ChargingUnitStateMachine(unit_id, stmpy_driver, mqtt_client.client).stm
    stmpy_driver.add_machine(charging_unit_stm)


# Start the driver
try:
    stmpy_driver.start()
except KeyboardInterrupt:
    pass
    # # This does not work, as Threading does not have a neat way to hadle KeyboardInterrupt
    # # Its a know issue and an existing feature request. A possible fix is to use a signaling 
    # # mechanism to signal the threads to stop. Here is an example of someone doing that:
    # # https://alexandra-zaharia.github.io/posts/how-to-stop-a-python-thread-cleanly/

    # logging.debug("Interrupted")
    # stmpy_driver.stop()
    # mqtt_client.client.disconnect()
    # logging.debug("Driver stopped and MQTT disconnected.")
    # # Clear the sense hat
    # sense_hat.clear()
    # logging.debug("Sense hat cleared.")