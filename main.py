### IMPORTS ###
from html import parser
from logging import config
import time
import serial
import configparser
import struct
import pprint

from src.TEST_ISX3 import ISX3
import src.command_functions as command

from src.helper_functions import *

import config.config_transmitter as config_transmitter
from config.config_handler import ISX3ConfigParser
### FUNCTIONS ###

### MAIN ###
def main():
    # 1. Initialize the parser with the path to your config file
    parser = ISX3ConfigParser("config/config.ini")
    
    try:
        # 2. Get the configuration as a nested dictionary
        config_dict = parser.parse_as_flat_dict()
        
        print("\n--- Full Dictionary Structure ---")
        print(config_dict)
        
    except FileNotFoundError as e:
        print(e)

if __name__ == "__main__":
    main()