'''
This script is intended to run in as a seperate script (process).

This is a GUI for showing the queue to the users to interact with. It also has buttons to
add someone to the queue instead of a phone app for demonstration purposes.
'''

import tkinter as tk
import logging
import paho.mqtt.client as mqtt
from enum import Enum, auto
from typing import Dict, Optional, List
import random
import string
import json
import queue
from threading import Thread

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Constants
MQTT_BROKER = 'broker.hivemq.com'
# MQTT_BROKER = 'localhost'
MQTT_PORT = 1883

MQTT_UI_SEND_TOPIC = 'gr17/info_from_queue_UI'
MQTT_UI_RECEIVE_TOPIC = 'gr17/info_to_queue_UI'

class ChargingUnitDuration(Enum):
    CHARGING_SHORT = 0
    CHARGING_MEDIUM = 1
    CHARGING_LONG = 2


class WaitingQueueUI(tk.Tk):
    '''
    This UI will recive messages by checking the queue in a polling manner useing the after()
    method that will be compatible with the blocking nature of the mainloop.

    When toggling the buttons, the UI will send a message using the mqtt_client.
    '''
    def __init__(self, queue: queue.Queue, mqtt_client: mqtt.Client) -> None:
        super().__init__()
        self.mqtt_client = mqtt_client
        self.title("Charging Queue")
        self.queue = queue
        self.estimated_wait_times = [0, 0, 0]
        self.estimated_wait_times_labels = [tk.StringVar(), tk.StringVar(), tk.StringVar()]

        # This dosent differentiate between if a person is charging or could start charging, like the
        # system at McDonalds, the display will show when the food is ready, but only goes away when the
        # food is actually picked up (and here the user has completed the charge)
        self.users_that_can_go_to_charging: Dict[ChargingUnitDuration, List[str]] = {
            ChargingUnitDuration.CHARGING_LONG: [],
            ChargingUnitDuration.CHARGING_MEDIUM: [],
            ChargingUnitDuration.CHARGING_SHORT: []
        }
        self.users_waiting_for_charging: Dict[ChargingUnitDuration, List[str]] = {
            ChargingUnitDuration.CHARGING_LONG: [],
            ChargingUnitDuration.CHARGING_MEDIUM: [],
            ChargingUnitDuration.CHARGING_SHORT: []
        }

        self.setup_ui() 
        self.poll_queue() # Messaging mechanism to update the UI

    def setup_ui(self):
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.columnconfigure(2, weight=1)
        
        # Frames for each column
        queue_selection_and_wait_time_frame = tk.Frame(self)
        waiting_frame = tk.Frame(self)
        can_charge_frame = tk.Frame(self)

        queue_selection_and_wait_time_frame.grid(row=0, column=0, sticky='nswe')
        waiting_frame.grid(row=0, column=1, sticky='nswe')
        can_charge_frame.grid(row=0, column=2, sticky='nswe')
        
        # Setup Listboxes and labels for both columns
        self.waiting_listboxes = {}
        self.can_charge_listboxes = {}
        for i, state in enumerate(ChargingUnitDuration):
            self.create_listbox(waiting_frame, self.waiting_listboxes, state, "Waiting")
            self.create_listbox(can_charge_frame, self.can_charge_listboxes, state, "Can Charge")

        # Setup the queue selection and wait time frame
        self.queue_wait_time_label = tk.Label(queue_selection_and_wait_time_frame, text="Estimated wait time:")

        self.queue_selection_label = tk.Label(queue_selection_and_wait_time_frame, text="Select queue:")
        # 3 buttons for selecting the queue
        self.enter_long_queue_button = tk.Button(queue_selection_and_wait_time_frame, text="Enter Long Queue", command=self.enter_long_queue)
        self.enter_medium_queue_button = tk.Button(queue_selection_and_wait_time_frame, text="Enter Medium Queue", command=self.enter_medium_queue)
        self.enter_short_queue_button = tk.Button(queue_selection_and_wait_time_frame, text="Enter Short Queue", command=self.enter_short_queue)

        # Wait time labels
        self.estimated_wait_time_short_label = tk.Label(queue_selection_and_wait_time_frame, textvariable=self.estimated_wait_times_labels[0], fg="white")
        self.estimated_wait_time_medium_label = tk.Label(queue_selection_and_wait_time_frame, textvariable=self.estimated_wait_times_labels[1], fg="white")
        self.estimated_wait_time_long_label = tk.Label(queue_selection_and_wait_time_frame, textvariable=self.estimated_wait_times_labels[2], fg="white")

        # Grid layout for better control
        self.enter_short_queue_button.grid(row=1, column=0, padx=10, pady=10, sticky='ew')
        self.estimated_wait_time_short_label.grid(row=2, column=0, padx=10, pady=2, sticky='ew')

        self.enter_medium_queue_button.grid(row=3, column=0, padx=10, pady=10, sticky='ew')
        self.estimated_wait_time_medium_label.grid(row=4, column=0, padx=10, pady=2, sticky='ew')

        self.enter_long_queue_button.grid(row=5, column=0, padx=10, pady=10, sticky='ew')
        self.estimated_wait_time_long_label.grid(row=6, column=0, padx=10, pady=2, sticky='ew')

        # Make the column widths within the frame equal
        queue_selection_and_wait_time_frame.columnconfigure(0, weight=1)
        queue_selection_and_wait_time_frame.columnconfigure(1, weight=1)
        queue_selection_and_wait_time_frame.columnconfigure(2, weight=1)

        self.update_ui()



    def enter_long_queue(self):
        print("Entered long queue")
        # Generate a random user id 8 chars long
        random_user_string = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        json_formatted_message = json.dumps({random_user_string : "CHARGING_LONG"})
        self.mqtt_client.publish(MQTT_UI_SEND_TOPIC, json_formatted_message)
        # pass

    def enter_medium_queue(self):
        print("Entered medium queue")
        random_user_string = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        json_formatted_message = json.dumps({random_user_string : "CHARGING_MEDIUM"})
        self.mqtt_client.publish(MQTT_UI_SEND_TOPIC, json_formatted_message)
        # pass

    def enter_short_queue(self):
        print("Entered short queue")
        random_user_string = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        json_formatted_message = json.dumps({random_user_string : "CHARGING_SHORT"})
        self.mqtt_client.publish(MQTT_UI_SEND_TOPIC, json_formatted_message)
        # pass

    
    def create_listbox(self, parent_frame, listbox_dict, state, prefix):
        frame = tk.Frame(parent_frame)
        frame.pack(fill='both', expand=True)
        label = tk.Label(frame, text=f"{prefix} - {state.name}")
        label.pack()
        listbox = tk.Listbox(frame, height=10, fg='black')
        listbox.pack(fill='both', expand=True)
        listbox_dict[state] = listbox
        if state == ChargingUnitDuration.CHARGING_LONG:
            listbox.configure(bg='#e8847d')
        elif state == ChargingUnitDuration.CHARGING_MEDIUM:
            listbox.configure(bg='#ede887')
        elif state == ChargingUnitDuration.CHARGING_SHORT:
            listbox.configure(bg='#7de88c')

    def update_ui(self):
        # Update waiting listboxes
        for state, listbox in self.waiting_listboxes.items():
            listbox.delete(0, tk.END)  # Clear existing items
            for implicit_queue_number, user_id in enumerate(self.users_waiting_for_charging[state]):
                listbox.insert(tk.END,f"{implicit_queue_number+1}. {user_id}")

        # Update can charge listboxes
        for state, listbox in self.can_charge_listboxes.items():
            listbox.delete(0, tk.END)  # Clear existing items
            for user_id in self.users_that_can_go_to_charging[state]:
                listbox.insert(tk.END, user_id)

        # Update estimated wait times
        if self.estimated_wait_times[0] == "No unit serving at the moment.":
            self.estimated_wait_times_labels[0].set(self.estimated_wait_times[0])
        else:
            self.estimated_wait_times_labels[0].set(f"Short: 00:{self.estimated_wait_times[0]:02d}:00")

        if self.estimated_wait_times[1] == "No unit serving at the moment.":
            self.estimated_wait_times_labels[1].set(self.estimated_wait_times[1])
        else:
            self.estimated_wait_times_labels[1].set(f"Medium: 00:{self.estimated_wait_times[1]:02d}:00")

        if self.estimated_wait_times[2] == "No unit serving at the moment.":
            self.estimated_wait_times_labels[2].set(self.estimated_wait_times[2])
        else:
            self.estimated_wait_times_labels[2].set(f"Long: 00:{self.estimated_wait_times[2]:02d}:00")


    def process_message(self, message):
        try:
            data = json.loads(message)
            for key, users in data["users_that_can_go_to_charging"].items():
                self.users_that_can_go_to_charging[ChargingUnitDuration[key]] = users

            for key, users in data["users_waiting_for_charging"].items():
                self.users_waiting_for_charging[ChargingUnitDuration[key]] = users

            self.estimated_wait_times[0] = data["estimated_wait_times"][0]
            self.estimated_wait_times[1] = data["estimated_wait_times"][1]
            self.estimated_wait_times[2] = data["estimated_wait_times"][2]

            self.update_ui()
        except json.JSONDecodeError:
            # Handle malformed data
            logging.error("Data not as expected, data was: %s", message)

    def poll_queue(self):
        try:
            # Try to get a message from the queue
            message = self.queue.get_nowait()
            self.process_message(message)
        except queue.Empty:
            # No message in the queue
            pass
        finally:
            # Schedule the next poll
            self.after(100, self.poll_queue)

class MQTTClientForUI:
    def __init__(self, queue: queue.Queue):
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.queue = queue

    def on_connect(self, client, userdata, flags, rc):
        logging.info("Connected to MQTT Broker")
        
    def on_message(self, client, userdata, msg):
        logging.debug("Received message: {}".format(msg.payload.decode()))
        self.queue.put(msg.payload.decode())

    def start(self, broker_address, topic, port=1883, keepalive=60):
        self.client.connect(broker_address, port, keepalive)
        self.client.subscribe(topic)
        try:
            thread = Thread(target=self.client.loop_forever) # Keeps the client running in a separate thread
            thread.start()
        except KeyboardInterrupt: # This is really unfortunate, but this never seems to be called
            print("Interrupted")
            self.client.disconnect()

# Create and run the application
if __name__ == "__main__": # Can no longer create the app without the stm_driver
    message_queue = queue.Queue()
    mqtt_client = MQTTClientForUI(message_queue)
    mqtt_client.start(MQTT_BROKER, MQTT_UI_RECEIVE_TOPIC, MQTT_PORT) # Spawns in a sparate thread.
    app = WaitingQueueUI(message_queue, mqtt_client.client)
    app.mainloop()
