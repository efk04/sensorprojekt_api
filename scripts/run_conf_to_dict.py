import config.config_handler as config_handler

def conf_to_dict():
    """
    Converts the configuration file to a dictionary.

    Returns:
        dict: A dictionary containing the configuration parameters.
    """
    
    # Load the configuration file
    parser = config_handler.ISX3ConfigParser('config/config.ini')   
