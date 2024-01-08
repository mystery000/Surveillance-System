#!/bin/bash

port="1-1.1" # Replace with the actual bus and port number of your USB device

unbind_usb() {
 echo "$1" >/sys/bus/usb/drivers/usb/unbind
}

bind_usb() {
 echo "$1" >/sys/bus/usb/drivers/usb/bind
}

unbind_usb "$port"
# sleep 1 # Add a delay here if needed
# bind_usb "$port"