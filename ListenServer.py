#!/usr/bin/python
import socketserver
from http.server import BaseHTTPRequestHandler,HTTPServer
import time
import http.client
import subprocess
from urllib.request import urlopen
import threading
from multiping import multi_ping
import logging # Importer le module logging
from logging.handlers import RotatingFileHandler # Importer la classe RotatingFileHandler
import os
import pyaudio
from math import pi
import numpy as np

actionsList = []
runningFW = False
runningLeft = False
runningRight = False
stuckRequests = 0
silenceServer = False
setRunSpeed = False
disconnected = False
startDebugTime = 0
backTime = 7
isStop = False
PC = '192.168.0.100'
if os.path.exists("raspberry.log"): os.remove("raspberry.log")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) # Définir le niveau de sévérité à INFO
handler = RotatingFileHandler("raspberry.log", mode="w", maxBytes=10*1024*1024, backupCount=0) # Créer un objet handler pour écrire dans un fichier
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s") # Définir le format du message
handler.setFormatter(formatter) # Associer le format au handler
logger.addHandler(handler) # Associer le handler au logger

try:
    subprocess.Popen(["sudo /home/pi/SunFounder_PiCar-V/remote_control/start"], shell=True)
    print('**********************')
    logger.info("Démarrage du serveur PiCar-V") # Utiliser logger.info pour enregistrer un message
except:
    print("Error: Unable to run PiCar-V server.")
    logger.exception("Erreur lors du démarrage du serveur PiCar-V") # Utiliser logger.exception pour enregistrer une erreur

def make_sinewave(frequency, length, sample_rate=44100):
    length = int(length * sample_rate)
    factor = float(frequency) * (pi * 2) / sample_rate
    waveform = np.sin(np.arange(length) * factor)

    return waveform

def piCar(actionPiCar):
    global setRunSpeed
    if not setRunSpeed:
        urlopen("http://0.0.0.0:8001/run/?speed=54")
        setRunSpeed = True
    urlopen("http://0.0.0.0:8001/run/?action="+actionPiCar)
wave = make_sinewave(1000, 1) # Créer un signal de 1000 Hz et 1 s
def check_wifi_connection():
    global disconnected
    global startDebugTime
    global backTime
    # Ajouter une variable pour compter le nombre de fois que le PC est injoignable
    global unreachable_count
    try:
        responses, no_responses = multi_ping([PC], timeout=2, retry=0)
        # Augmenter le compteur de 1 si le PC ne répond pas
        if len(responses)==0:
            unreachable_count += 1
        # Réinitialiser le compteur à zéro si le PC répond
        else:
            unreachable_count = 0
        # Vérifier si le compteur est supérieur ou égal à 3
        if unreachable_count >= 3:
            print("Error: Pc is unreachable.")
            logger.exception("Erreur de connexion au PC")
            piCar("stop")
            result = subprocess.check_output("cat /sys/class/net/wlan0/operstate", shell=True)
            operstate = result.decode().strip()
            if operstate == "down":
                logger.exception('down down down, Je viens de perdre la connexion au réseau')
                if startDebugTime==0: startDebugTime = time.time()
                debugMode('conn')
            else:
                print("Error: I'm in Wi-Fi but PC is out of Wi-Fi.")
                logger.exception("Erreur: I'm in Wi-Fi but PC is out of Wi-Fi.")
                # Afficher le code d'erreur
                print("Error: PC is unreachable for 3 times or more.")
                # Faire beeper le robot
                p = pyaudio.PyAudio()
                stream = p.open(format=pyaudio.paFloat32, channels=1, rate=44100, output=1,)
                beeping = True
                logger.info("Beeping est activé")
                if beeping:
                    stream.write(wave.astype(np.float32).tostring())
                    time.sleep(1)
                    beeping = False
                stream.stop_stream()
                stream.close()
                p.terminate()
            disconnected = True
        # Sinon, si le PC répond, continuer normalement
        elif len(responses) > 0:
            beeping = False
            startDebugTime = 0
            backTime = 7
            if disconnected:
                logger.info("De nouveau connecté")
                disconnected = False
    except:
        print("Error: Unable to check Wi-Fi connection")
        logger.exception("Erreur lors de la vérification de la connexion Wi-Fi")
    timer = threading.Timer(3, check_wifi_connection) # Créer un objet timer qui appelle la fonction check_wifi_connection après 3 secondes
    timer.start()


def debugMode(a):
    global actionsList
    global silenceServer
    global backTime
    global startDebugTime

    silenceServer = True
    print("Entering debug mode...")
    logger.info("Entrée en mode debug") # Utiliser logger.info pour enregistrer un message
    piCar('stop')
    piCar('fwstraight')
    #for i in range(0, 3):
    if actionsList[-1][0] == 'forward':
        piCar('backward')
    #elif actionsList[-1][0] == 'backward':
    #    piCar('forward')
    elif actionsList[-1][0] == 'fwleft':
        piCar('fwleft')
        piCar('backward')
        time.sleep(4)
        piCar('fwstraight')
        backTime = 7
        startDebugTime -= 7
    elif actionsList[-1][0] == 'fwright':
        piCar('fwright')
        piCar('backward')
        time.sleep(4)
        piCar('fwstraight')
        backTime = 7
        startDebugTime -= 7
    if a=='conn' and actionsList[-1][0] == 'forward':
        logger.info("Fin du mode debug connexion")
        time.sleep(backTime) #( int(actionsList[-1][1] - actionsList[-2][1]) )
        startDebugTime -= backTime # for the next back, if it ever have to happen

        if backTime < 7 : actionsList.pop() # si le robot est revenu en arriere pendant moins de 7 secondes, alors on enleve le dernier objet de la liste
        if ( startDebugTime - actionsList[-1][1] ) < 7 :
            backTime = startDebugTime - actionsList[-1][1]
        else: backTime = 7
    elif a=='unstuck':
        logger.info("Fin du mode debug unstuck")
        time.sleep(10)
    piCar('stop')
    piCar('fwstraight')
    logger.info("Sortie du mode debug")
    silenceServer = False

class MyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        global silenceServer, runningFW, runningLeft, runningRight, stuckRequests, isStop
        if silenceServer: return

        if self.path == '/run/?action=fwleft':
            if not stuckRequests: # Ajouter une condition pour vérifier si stuckRequests est False
                actionsList.append(['fwleft',time.time()])
                runningLeft = silenceServer = True
                piCar('fwleft')
                piCar('forward')
                time.sleep(7)
                piCar('fwstraight')
                actionsList.append(['forward',time.time()])
                runningLeft = silenceServer = False
                runningFW = True
                isStop = False # Mettre isStop à False
                logger.info("Requête GET /run/?action=fwleft reçue et exécutée") # Utiliser logger.info pour enregistrer un message
        elif self.path == '/run/?action=forward':
            if not stuckRequests: # Ajouter une condition pour vérifier si stuckRequests est False
                if runningFW:
                    piCar('stop')
                    runningFW = False
                else:
                    actionsList.append(['forward',time.time()])
                    runningFW = silenceServer = True
                    piCar('forward')
                    #time.sleep(3)
                    silenceServer = False
                isStop = False # Mettre isStop à False
                logger.info("Requête GET /run/?action=forward reçue et exécutée") # Utiliser logger.info pour enregistrer un message
        elif self.path == '/run/?action=fwright':
            if not stuckRequests: # Ajouter une condition pour vérifier si stuckRequests est False
                actionsList.append(['fwright',time.time()])
                runningRight = silenceServer = True
                piCar('fwright')
                piCar('forward')
                time.sleep(7)
                piCar('fwstraight')
                actionsList.append(['forward',time.time()])
                runningRight = silenceServer = False
                runningFW = True
                isStop = False # Mettre isStop à False
                logger.info("Requête GET /run/?action=fwright reçue et exécutée") # Utiliser logger.info pour enregistrer un message
        elif self.path == '/run/?action=fwstraight':
            if not stuckRequests: # Ajouter une condition pour vérifier si stuckRequests est False
                piCar('fwstraight')
                isStop = False # Mettre isStop à False
                logger.info("Requête GET /run/?action=fwstraight reçue et exécutée") # Utiliser logger.info pour enregistrer un message
        elif self.path == '/run/?action=backward': # Ne sera jamais appelE
            #actionsList.append(['backward',time.time()])
            silenceServer = True
            piCar('backward')
            time.sleep(7)
            silenceServer = False
            isStop = False # Mettre isStop à False
            logger.info("Requête GET /run/?action=backward reçue et exécutée") # Utiliser logger.info pour enregistrer un message
        elif self.path == '/run/?action=stop':
            piCar('stop')
            print('receive stop')
            #time.sleep(7)
            isStop = True # Mettre isStop à True
            stuckRequests = False # Mettre stuckRequests à False
            logger.info("Requête GET /run/?action=stop reçue et exécutée") # Utiliser logger.info pour enregistrer un message
        elif self.path == '/run/?action=checkStuck':
            if not isStop: # Ajouter une condition pour vérifier si isStop est False
                if (runningFW or runningLeft or runningRight):
                    # Mettre stuckRequests à True
                    stuckRequests = True
                    print('The robot is stucked.')
                    debugMode('unstuck')
                    #time.sleep(20)
                    runningFW = runningLeft = runningRight = False
                else:
                    # Mettre stuckRequests à False
                    stuckRequests = False
                    print('The robot is not stucked.')
            logger.info("Requête GET /run/?action=checkStuck reçue et traitée")

httpd = socketserver.TCPServer(("", 8000), MyHandler)

check_wifi_connection()
try:
    httpd.serve_forever()
except KeyboardInterrupt:
    print("Shutting down the server...")
    httpd.shutdown()