#!/usr/bin/env python3

import pylacrosse
import ssl
import sys
import re
import json
import os.path
import argparse
from time import time, sleep, localtime, strftime
from collections import OrderedDict
from colorama import init as colorama_init
from colorama import Fore, Style
from configparser import ConfigParser
from unidecode import unidecode
import paho.mqtt.client as mqtt
import sdnotify
from signal import signal, SIGPIPE, SIG_DFL
signal(SIGPIPE,SIG_DFL)

project_name = 'Lacrosse MQTT Client/Daemon/Gateway'
project_url = 'https://github.com/deveth0/lacrosse-mqtt-gateway'

parameters = OrderedDict([
    ("temperature", dict(name="Temperature", name_pretty='Humidity', typeformat='%.1f', unit='°C', device_class="temperature")),
    ("humidity", dict(name="Humidity", name_pretty='Humidity', typeformat='%f', unit='%', device_class="humidity")),
    ("low_battery", dict(name="Battery", name_pretty='Sensor Battery Level Low', device_class="battery"))
])

if False:
    # will be caught by python 2.7 to be illegal syntax
    print('Sorry, this script requires a python3 runtime environment.', file=sys.stderr)

class LaCrosseSensor:
    """Implementation of a Lacrosse sensor."""

    _temperature = None
    _humidity = None
    _low_battery = None
    _new_battery = None

    def __init__(self, lacrosse, device_id, name):
        """Initialize the sensor."""
        self._name = name
        self._device_id = device_id
        self._value = None

        lacrosse.register_callback(
            int(device_id), self._callback_lacrosse, None
        )

    @property
    def device_id(self):
        """ Return the device_id of the sensor """
        return self._device_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attributes = {
            "low_battery": self._low_battery,
            "new_battery": self._new_battery,
        }
        return attributes

    def _callback_lacrosse(self, lacrosse_sensor, user_data):
        """Handle a function that is called from pylacrosse with new values."""
        self._temperature = lacrosse_sensor.temperature
        self._humidity = lacrosse_sensor.humidity
        self._low_battery = lacrosse_sensor.low_battery
        self._new_battery = lacrosse_sensor.new_battery
        print_line('Retrieving data from sensor "{}" ...'.format(self._name))
        print_line('Temperature: "{}" ...'.format(self._temperature))
        print_line('Humidity: "{}" ...'.format(self._humidity))
        print_line('Low-Battery "{}" ...'.format(self._low_battery))
        print_line('New-Battery "{}" ...'.format(self._new_battery))

        data = OrderedDict()
        data["temperature"]= self._temperature
        data["humidity"]= self._humidity
        data["low_battery"]= self._low_battery
        print_line('Result: {}'.format(json.dumps(data)))
        publish(self._name, data)


# Argparse
parser = argparse.ArgumentParser(description=project_name, epilog='For further details see: ' + project_url)
parser.add_argument('--config_dir', help='set directory where config.ini is located', default=sys.path[0])
parse_args = parser.parse_args()

# Intro
colorama_init()
print(Fore.GREEN + Style.BRIGHT)
print(project_name)
print('Source:', project_url)
print(Style.RESET_ALL)

# Systemd Service Notifications - https://github.com/bb4242/sdnotify
sd_notifier = sdnotify.SystemdNotifier()

# Logging function
def print_line(text, error = False, warning=False, sd_notify=False, console=True):
    timestamp = strftime('%Y-%m-%d %H:%M:%S', localtime())
    if console:
        if error:
            print(Fore.RED + Style.BRIGHT + '[{}] '.format(timestamp) + Style.RESET_ALL + '{}'.format(text) + Style.RESET_ALL, file=sys.stderr)
        elif warning:
            print(Fore.YELLOW + '[{}] '.format(timestamp) + Style.RESET_ALL + '{}'.format(text) + Style.RESET_ALL)
        else:
            print(Fore.GREEN + '[{}] '.format(timestamp) + Style.RESET_ALL + '{}'.format(text) + Style.RESET_ALL)
    timestamp_sd = strftime('%b %d %H:%M:%S', localtime())
    if sd_notify:
        sd_notifier.notify('STATUS={} - {}.'.format(timestamp_sd, unidecode(text)))

# Identifier cleanup
def clean_identifier(name):
    clean = name.strip()
    for this, that in [[' ', '-'], ['ä', 'ae'], ['Ä', 'Ae'], ['ö', 'oe'], ['Ö', 'Oe'], ['ü', 'ue'], ['Ü', 'Ue'], ['ß', 'ss']]:
        clean = clean.replace(this, that)
    clean = unidecode(clean)
    return clean

# Eclipse Paho callbacks - http://www.eclipse.org/paho/clients/python/docs/#callbacks
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print_line('MQTT connection established', console=True, sd_notify=True)
        print()
    else:
        print_line('Connection error with result code {} - {}'.format(str(rc), mqtt.connack_string(rc)), error=True)
        #kill main thread
        os._exit(1)


def on_publish(client, userdata, mid):
    #print_line('Data successfully published.')
    pass

def publish(sensor_name, data):
    print_line('Publishing to MQTT topic "{}/sensor/{}/state"'.format(base_topic, sensor_name.lower()))
    mqtt_client.publish('{}/sensor/{}/state'.format(base_topic, sensor_name.lower()), json.dumps(data))
    sleep(0.5) # some slack for the publish roundtrip and callback function
    print()
    print_line('Status messages published', console=False, sd_notify=True)

# Load configuration file
config_dir = parse_args.config_dir

config = ConfigParser(delimiters=('=', ), inline_comment_prefixes=('#'))
config.optionxform = str
try:
    with open(os.path.join(config_dir, 'config.ini')) as config_file:
        config.read_file(config_file)
except IOError:
    print_line('No configuration file "config.ini"', error=True, sd_notify=True)
    sys.exit(1)

used_adapter = config['General'].get('adapter', '/dev/ttyUSB0')
datarate = config['General'].get('datarate')
toggle_mask  = config['General'].get('toggle_mask')
toggle_interval  = config['General'].get('toggle_interval')

daemon_enabled = config['Daemon'].getboolean('enabled', True)

base_topic = config['MQTT'].get('base_topic', "homeassistant").lower()
device_id = config['MQTT'].get('homie_device_id', 'lacrosse-mqtt-daemon').lower()

# Check configuration
if not config['Sensors']:
    print_line('No sensors found in configuration file "config.ini"', error=True, sd_notify=True)
    sys.exit(1)

print_line('Configuration accepted', console=False, sd_notify=True)

# MQTT connection
print_line('Connecting to MQTT broker ...')
mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_publish = on_publish

if config['MQTT'].getboolean('tls', False):
    # According to the docs, setting PROTOCOL_SSLv23 "Selects the highest protocol version
    # that both the client and server support. Despite the name, this option can select
    # “TLS” protocols as well as “SSL”" - so this seems like a resonable default
    mqtt_client.tls_set(
        ca_certs=config['MQTT'].get('tls_ca_cert', None),
        keyfile=config['MQTT'].get('tls_keyfile', None),
        certfile=config['MQTT'].get('tls_certfile', None),
        tls_version=ssl.PROTOCOL_SSLv23
    )

mqtt_username = os.environ.get("MQTT_USERNAME", config['MQTT'].get('username'))
mqtt_password = os.environ.get("MQTT_PASSWORD", config['MQTT'].get('password', None))

if mqtt_username:
    mqtt_client.username_pw_set(mqtt_username, mqtt_password)

try:
    mqtt_client.connect(os.environ.get('MQTT_HOSTNAME', config['MQTT'].get('hostname', 'localhost')),
                        port=int(os.environ.get('MQTT_PORT', config['MQTT'].get('port', '1883'))),
                        keepalive=config['MQTT'].getint('keepalive', 60))
except:
    print_line('MQTT connection error. Please check your settings in the configuration file "config.ini"', error=True, sd_notify=True)
    sys.exit(1)

sd_notifier.notify('READY=1')

# Initialize Lacrosse sensors
try:
    lacrosse = pylacrosse.LaCrosse(used_adapter, 57600)
    lacrosse.open()
except SerialException as exc:
    print_line("Unable to open serial port: %s".format(exc), error=True, sd_notify=True)
    sys.exit(1)

if toggle_interval is not None:
    print_line("Setting interval")
    lacrosse.set_toggle_interval(toggle_interval)
if toggle_mask is not None:
    lacrosse.set_toggle_mask(toggle_mask)
if datarate is not None:
    lacrosse.set_datarate(datarate)

lacrosse.start_scan()

sensors = OrderedDict()
for [name, device_id] in config['Sensors'].items():
    if not re.match("[0-9]{1,2}", device_id.lower()):
        print_line('The Device-ID "{}" seems to be in the wrong format. Please check your configuration'.format(device_id), error=True, sd_notify=True)
        sys.exit(1)

    if '@' in name:
        name_pretty, location_pretty = name.split('@')
    else:
        name_pretty, location_pretty = name, ''
    name_clean = clean_identifier(name_pretty)
    location_clean = clean_identifier(location_pretty)

    print('Adding sensor to device list')
    print('Name:          "{}"'.format(name_pretty))
    print('DeviceId:          "{}"'.format(device_id))

    sensors[name_clean] = LaCrosseSensor(lacrosse, device_id, name)

print_line('Announcing Lacrosse devices to MQTT broker for auto-discovery ...')
for [sensor_name, lacrosse] in sensors.items():
    state_topic = '{}/sensor/{}/state'.format(base_topic, sensor_name.lower())
    for [sensor, params] in parameters.items():
        discovery_topic = 'homeassistant/sensor/{}/{}/config'.format(sensor_name.lower(), sensor)
        payload = OrderedDict()
        payload['name'] = "{} {}".format(sensor_name, sensor.title())
        payload['unique_id'] = "{}-{}".format(sensor_name.lower(), sensor)
        if 'unit' in params:
            payload['unit_of_measurement'] = params['unit']
        if 'device_class' in params:
            payload['device_class'] = params['device_class']
        payload['state_topic'] = state_topic
        payload['value_template'] = "{{{{ value_json.{} }}}}".format(sensor)
        payload['device'] = {
                'identifiers' : ["Lacrosse{}".format(lacrosse.device_id.lower().replace(":", ""))],
                'connections' : [["device_id", lacrosse.device_id.lower()]],
                'manufacturer' : 'Lacrosse',
                'name' : sensor_name,
                'model' : 'Lacrosse Sensor',
        }
        print_line('Payload: {}'.format(json.dumps(payload)))
        mqtt_client.publish(discovery_topic, json.dumps(payload), 1, True)

print_line('Initialization complete, starting MQTT publish loop', console=False, sd_notify=True)

sleep_period = 300

# Sensor data retrieval and publication
while True:
    print_line('Status messages published', console=False, sd_notify=True)

    if daemon_enabled:
        print_line('Sleeping ({} seconds) ...'.format(sleep_period))
        sleep(sleep_period)
        print()
    else:
        print_line('Execution finished in non-daemon-mode', sd_notify=True)
        if reporting_mode == 'mqtt-json':
            mqtt_client.disconnect()
        break

