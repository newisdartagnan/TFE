#!/usr/bin/env python

import pyaudio
import socket
import sys
import time
from multiping import multi_ping
#from subprocess import call

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 8000
CHUNK = 512
SERVER = '192.168.0.100'
PORT = 4445

print('####### ------- CLIENT STARTING ------- ######')
pingResult = False

while True:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    while not pingResult:  # Modifiez la condition de la boucle
        try:
            #responses, no_responses = multi_ping([SERVER], timeout=2, retry=0)
            #op = subprocess.check_output(["ping",SERVER,"-c","5"])
            #print(op)
            s.settimeout(2)
            s.connect((SERVER,PORT))
            
            if True:#len(responses)==1:
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
                print("Exception: Connection lost.\nWaiting for connection.")
                pingResult = False
                s.close()
                break
            #print('boucle')
    except KeyboardInterrupt:
        break

print('Shutting down')
s.close()
stream.close()
audio.terminate()
