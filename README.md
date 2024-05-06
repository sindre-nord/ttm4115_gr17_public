# ttm4115_gr17
Code base for project in TTM4115 Spring of 2024

## How to run for the first time:
After cloning the repository, navigate to the root folder of the project.
This applies for Mac OS and Linux. For Windows, use Google (and search for 
how to make and run virtual environments on Windows).

### On the PI
1. Run `cd chargerpi`
2. Run `chmod +x setup_on_pi.sh`
3. Run `./setup_on_pi.sh`
4. Run `python charger_state_machine.py`

### On the Server
1. Run `cd serverpi`
2. Run `python3 -m venv venv`
3. Run `source venv/bin/activate`
4. Run `pip install -r requirements.txt`
5. Run `python server.py`

### Can be run anywhere
1. Run `cd chargerpi`
2. Run (If not on the PI) `python3 -m venv venv`
3. Run (If not on the PI) `source venv/bin/activate`
4. Run `pip install -r requirements.txt`
5. Run `python physical_charger_interface.py`
6. Run `python queue_user_interface.py`
   
## How to run after the first time:
After the first time, you can run the code by navigating to the root folder of the project and running the following commands:
1. Navigate to the given root folder, e.g. `cd chargerpi`
2. Source the virtual environment, e.g. `source venv/bin/activate`
3. Run the desired script, e.g. `python charger_state_machine.py`

