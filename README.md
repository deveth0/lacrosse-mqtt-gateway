# Lacrosse Sensor MQTT Client/Daemon/Gateway

A simple Python script to include Lacrosse Sensors using a Jeelink into an **MQTT** broker and Homeassistant.

The program can be executed in **daemon mode** to run continuously in the background, e.g., as a systemd service.

## About Lacrosse / Jeelink

* [Jeelink USB Stick](https://www.digitalsmarties.net/products/jeelink)
* [pylacrosse](https://github.com/hthiery/python-lacrosse)
* [Summary on Sensors](https://wiki.fhem.de/wiki/JeeLink#LaCrosse_Sketch)

## Features

* Highly configurable
* Data publication via MQTT
* [HomeAssistant MQTT discovery format](https://home-assistant.io/docs/mqtt/discovery/)
* MQTT authentication support
* No special/root privileges needed
* Linux daemon / systemd service, sd\_notify messages generated


### Readings

The Lacrosse sensors offer the following readings:

| Name            | Description |
|-----------------|-------------|
| `temperature`   | Air temperature, in [°C] (0.1°C resolution |
| `humidity`      | Humidity, in [%] |
| `battery`       | Lacrosse Sensors only provide a low battery warning, therefor you'll only see 100% and 0% here |

## Prerequisites

An MQTT broker is needed as the counterpart for this daemon.

## Installation

On a modern Linux system just a few steps are needed to get the daemon working.
The following example shows the installation under Debian/Raspbian below the `/opt` directory:

```shell
sudo apt install git python3 python3-pip

git clone https://github.com/deveth0/lacrosse-mqtt-gateway /opt/lacrosse-mqtt-gateway

cd /opt/lacrosse-mqtt-gateway
sudo pip3 install -r requirements.txt
```

## Configuration

To match personal needs, all operation details can be configured using the file [`config.ini`](config.ini.dist).
The file needs to be created first:

```shell
cp /opt/lacrosse-mqtt-gateway/config.{ini.dist,ini}
vim /opt/lacrosse-mqtt-gateway/config.ini
```

**Attention:**
You need to add at least one sensor to the configuration.
Scan for available Lacrosse sensors in your proximity with the command:

```shell
$> pylacrosse -d /dev/ttyS18 scan
id=63 t=21.600000 h=41 nbat=0 name=unknown
id=50 t=19.400000 h=40 nbat=0 name=unknown
id=14 t=17.300000 h=47 nbat=0 name=unknown
id=50 t=19.500000 h=40 nbat=0 name=unknown
id=3 t=22.200000 h=39 nbat=0 name=unknown
```

Note: When replacing the battery, the ID of a sensor changes. So you need to update your configuration accordingly. 

## Execution

A first test run is as easy as:

```shell
python3 /opt/lacrosse-mqtt-gateway/lacrosse-mqtt-gateway.py
```

With a correct configuration you should get the output of the configured sensors. 

Using the command line argument `--config`, a directory where to read the config.ini file from can be specified, e.g.

```shell
python3 /opt/lacrosse-mqtt-gateway/lacrosse-mqtt-gateway.py --config /opt/lacrosse-config
```

### Continuous Daemon/Service

You most probably want to execute the program **continuously in the background**.
This can be done either by using the internal daemon or cron.

**Attention:** Daemon mode must be enabled in the configuration file (default).

1. Systemd service - on systemd powered systems the **recommended** option

   ```shell
   sudo useradd lacrosse-daemon
   sudo adduser lacrosse-daemon dialout
   
   sudo cp /opt/lacrosse-mqtt-gateway/template.service /etc/systemd/system/lacrosse.service

   sudo systemctl daemon-reload

   sudo systemctl start lacrosse.service
   sudo systemctl status lacrosse.service

   sudo systemctl enable lacrosse.service
   ```

# Acknowledgement

This script is based on the great work done by [Thomas Dietrich](https://github.com/ThomDietrich) in his [miflora-mqtt-daemon](https://github.com/ThomDietrich/miflora-mqtt-daemon).
