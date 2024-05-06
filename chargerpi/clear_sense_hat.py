'''
Simple utility script to clear the pixels on the sense hat.
'''
from sense_hat import SenseHat

sense_hat = SenseHat()

def clear_sense_hat():
    sense_hat.clear()
    return

if __name__ == '__main__':
    clear_sense_hat()
    print("Sense hat cleared.")
