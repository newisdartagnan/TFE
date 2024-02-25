import urllib2
import time
import threading
import sys
import subprocess

HOST = 'raspberrypi.local'
PORT = '8000'
BASE_URL = 'http://' + HOST + ':' + PORT + '/'
prevClassIndex = 0
prevClassCount = 0
detectionTime = 0
timeDiff = 0
atRight=0
atLeft=0
atForward=0
doingHTTP = False

#On demarre le script Python apres 5 secondes, le temps que la fenetre Level s'initialise dans OpenViBE
time.sleep(5)

def __request__(url, times=2):  
    for x in range(times):  
        try:
            response = urllib2.urlopen(url)
            return 0
        except:
            print("Connection error, try again")
    print("Abort")

def run_action(cmd):
    url = BASE_URL + 'run/?action=' + cmd
    __request__(url)
    print(url)
        
    return

class MyOVBox(OVBox):
    def __init__(self):
        OVBox.__init__(self)

    def initialize(self):
        # nop
        return

    def process(self):
        global prevClassCount
        global prevClassIndex
        global detectionTime
        global atRight
        global atLeft
        global atForward
        
        timeDiff = int(time.time()) - detectionTime
        #print('timeDiff = {0}'.format(timeDiff))
        
        if atRight==1 or atLeft==1 or atForward==1:
            if (timeDiff)<5:
                print('on n\'a pas encore atteint 5 secondes')
                try:
                    self.input[0].pop() #On discard le chunk qui est entrE dans le tableau, on laisse le tableau vide pour eviter d'accumuler les chunks
                except Exception as e : 
                    pass
                return # Puisqu'on n'a pas encore atteint 8 secondes, on sort de la classe, on n'execute pas la suite du code
            else : #Si on vient d'atteindre 3 secondes, on reactive les detections
                atRight=0
                atLeft=0
                atForward=0
                detectionTime = 0
                print('Detections reactivees')
                
        if True: #Si detectionTime==0
            #print('VALEUR RECHERCHEE-------------- {0}'.format(len(self.input[0])))
            try:
                for chunkIdx in range(len(self.input[0])):
                    chunk = self.input[0].pop() # chunk = l'entree de la boite python qui a l'indice 0
                    
                    maxValue = 0
                    classIndex = 0
                    
                    if (type(chunk) == OVStreamedMatrixBuffer): # Si le type de donnees recu est une matrice
                        for i in range(len(chunk)): # pour i=0...(longueur de chunk - 1)
                            if round(chunk[i], 3) >= maxValue :
                                maxValue = chunk[i]
                                classIndex = i
                        
                        maxValue *= 100
                        
                        threshold=0
                        if classIndex == 0: return #threshold=80 # Neutral
                        elif classIndex == 1: threshold=75 # Right
                        elif classIndex == 2: threshold=75 # Left
                        elif classIndex == 3: threshold=65 # Forward
                        
                        if (maxValue) >= threshold :
                            #print(maxValue)
                            #if maxValue == 100 : print('reached 100!')
                            if classIndex == prevClassIndex :
                                prevClassCount += 1
                                if prevClassCount == 3:
                                    #print('on a atteint 3 fois')
                                    prevClassCount = 0
                                    detectionTime = int(time.time())
                                    
                                    if classIndex == 1:
                                        atRight = 1
                                        t1 = threading.Thread(target=run_action,args=("fwright",))
                                        t1.start()
                                        #run_action("fwright")
                                    
                                    elif classIndex == 2:
                                        atLeft = 1
                                        t2 = threading.Thread(target=run_action,args=("fwleft",))
                                        t2.start()
                                        #run_action("fwleft")
                                        
                                    elif classIndex == 3:
                                        atForward = 1
                                        t3 = threading.Thread(target=run_action,args=("forward",))
                                        t3.start()
                                        #run_action("forward")
                                    
                            else:
                                prevClassCount = 0
                                prevClassIndex = classIndex                                   
                    else:
                        print('Received chunk of type ', type(chunk), " looking for OVStreamedMatrixBuffer")
            except Exception as e:
                print(e)
            return

    def uninitialize(self):
        # nop
        return

box = MyOVBox()
