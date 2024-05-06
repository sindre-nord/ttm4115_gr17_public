'''
This script is intended to run in as a seperate script (process).

It's responsile for the GUI for demonstation purposes. It allows simulation
of users connecting to the charger and shows some visuals (usually through color)
i.e to indicate the state of the charger.
'''

import tkinter as tk
from datetime import timedelta
import logging
import paho.mqtt.client as mqtt

import queue
from threading import Thread
from typing import List

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Constants
MQTT_BROKER = 'broker.hivemq.com'
# MQTT_BROKER = 'localhost'
MQTT_PORT = 1883

MQTT_UI_SEND_TOPIC = 'gr17/info_from_UI'
MQTT_UI_RECEIVE_TOPIC = 'gr17/info_to_UI'

class ChargingStationUI(tk.Tk):
    '''
    This UI will recive messages by checking the queue in a polling manner useing the after()
    method that will be compatible with the blocking nature of the mainloop.

    When toggling the buttons, the UI will send a message using the mqtt_client.
    '''
    def __init__(self, queue: queue.Queue, mqtt_client: mqtt.Client) -> None:
        super().__init__()
        self.mqtt_client = mqtt_client
        self.title("Charging Station Monitor")
        self.queue = queue
        self.unit_names = ["Unit 0", "Unit 1", "Unit 2", "Unit 3", "Unit 4", "Unit 5", "Unit 6", "Unit 7"]
        self.starting_time = timedelta(minutes=0, seconds=0)
        self.time_left = [self.starting_time for _ in self.unit_names]
        # self.colors = ["green"] * 4 + ["yellow"] * 3 + ["red"]
        self.colors = ['white'] * 8
        self.labels: List[tk.Label] = []
        self.toggle_buttons: List[tk.Checkbutton] = []
        self.toggle_button_vars: List[tk.IntVar] = []

        for i, (unit_name, color) in enumerate(zip(self.unit_names, self.colors)):
            self.create_unit(i, unit_name)
        self.update_tick()
        
        self.poll_queue() # Messaging mechanism to update the UI


    def create_unit(self, id:int, unit_name:str):
        frame = tk.Frame(self)
        frame.grid(row=id//4, column=id%4, padx=10, pady=10)

        countdown_label = tk.Label(frame, text=f"{unit_name}\nTime left:\n{self.time_left[id]}", bg=self.colors[id], fg="black")
        countdown_label.pack()

        toggle_button_label = tk.Label(frame, text="Charger physically connected", fg="black")
        toggle_button_label.pack()

        var = tk.IntVar()
        var.set(0)
        self.toggle_button_vars.append(var)
        toggle_btn = tk.Checkbutton(frame, text="", variable=var, command=lambda id=id, var=var: self.on_toggle(id, var))
        toggle_btn.pack()

        self.labels.append(countdown_label)
        self.toggle_buttons.append(toggle_btn)

    def on_toggle(self, id: int, var: tk.IntVar):
        if var.get():
            self.mqtt_client.publish(MQTT_UI_SEND_TOPIC, f"{id}, CONNECTED")
        else:
            self.mqtt_client.publish(MQTT_UI_SEND_TOPIC, f"{id}, DISCONNECTED")


    # Only updates the countdown labels if the toggle is on
    # when the countdown reaches 0 
    def update_tick(self):
        # Update the countdown labels
        for i, label in enumerate(self.labels):
            if self.toggle_button_vars[i].get() and self.time_left[i] > timedelta(0):
                self.time_left[i] -= timedelta(seconds=1)
                label.config(text=f"{self.unit_names[i]}\nTime left:\n{self.time_left[i]}")
            if self.toggle_button_vars[i].get() and self.time_left[i] == timedelta(0):
                #label.config(text=f"{self.unit_names[i]}\nTime left:\n{self.time_left[i]}\nCharging complete")
                label.config(bg='gray')
        self.after(1000, self.update_tick)
    
    def process_message(self, message:str):
        '''Expected message format: "unit_id, state"'''
        logging.debug(f"Received state update: {message}")
        unit_id, state = message.split(',')
        unit_id = int(unit_id)
        state = state.strip()
        print(f"Unit {unit_id} is {state}")
        self.update_unit_state(unit_id, state)


    def update_unit_state(self, unit_id:int, state:str):
        '''
        Unit_id is just an int
        state is a string that can be:
        'CHARGING_LONG'
        'CHARGING_MEDIUM'
        'CHARGING_SHORT'
        'None'
        '''
        state_color_map = {
            'ChargingUnitDuration.CHARGING_LONG': 'red',
            'ChargingUnitDuration.CHARGING_MEDIUM': 'yellow',
            'ChargingUnitDuration.CHARGING_SHORT': 'green',
            'None': 'grey'
        }
        new_color = state_color_map.get(state, 'grey')
        # You can make local functions like this and then call it with the after().
        def update_gui():
            self.labels[unit_id].config(bg=new_color)
            self.colors[unit_id] = new_color
            # Update countdown label based on the state
            if state == 'ChargingUnitDuration.CHARGING_SHORT':
                self.time_left[unit_id] = timedelta(seconds=5)
            elif state == 'ChargingUnitDuration.CHARGING_MEDIUM':
                self.time_left[unit_id] = timedelta(seconds=10)
            elif state == 'ChargingUnitDuration.CHARGING_LONG':
                self.time_left[unit_id] = timedelta(seconds=15)
            else:
                self.time_left[unit_id] = self.starting_time

            self.labels[unit_id].config(text=f"{self.unit_names[unit_id]}\nTime left:\n{self.time_left[unit_id]}")
            # print(f"Updated unit {unit_id} to state {state}, set color to {new_color}")
        
        # If you don't do it this way, I sometimes had wierd behavior with the GUI
        # just let it do it when its ready (thread-safe)
        self.after(0, update_gui)



        
    
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
    app = ChargingStationUI(message_queue, mqtt_client.client)
    app.mainloop()
