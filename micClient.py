#!/usr/bin/env python

import pyaudio
import socket
import sys
import time
#from multiping import multi_ping

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 8000
CHUNK = 512
SERVER = 'raspberrypi.local'
PORT = 4444

pingResult = False

while True:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    while not pingResult:  # Modifiez la condition de la boucle
        try:
            result = s.connect_ex((SERVER,PORT))
            if result==0:
                print('Server is up')
                #s.connect((SERVER, PORT))
                pingResult = True
                
            else:
                print("Client connection failed, retrying in 5 sec...")
                time.sleep(5) # wait for 5 seconds before trying again
        except Exception:
            print("Exception: Client connection failed, retrying in 5 sec...")
            time.sleep(5) # wait for 5 seconds before trying again

    audio = pyaudio.PyAudio()
    stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, output=True, frames_per_buffer=CHUNK)

    try:
        while True:
            try:
                data = s.recv(CHUNK)
                stream.write(data)
                if data=="":
                    print("Connection lost. Waiting for the server to restart.")
                    pingResult = False
                    s.close()
                    break
            except Exception:
                print("Connection lost.\nWaiting for connection.")
    except KeyboardInterrupt:
        break

print('Shutting down')
s.close()
stream.close()
audio.terminate()