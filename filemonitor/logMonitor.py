#!/usr/bin/env python

'''
------------------------------------------------------------------------
Copyright 2017 David Fan

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    
    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
------------------------------------------------------------------------
'''

import threading
import logging
import socket
import time
import os
import sys
import Queue
import signal
import re, datetime

#------------------------------
#File Monitor
#-------------------------------
#

logging.basicConfig(level=logging.DEBUG)

runFlag = True

class Tail(object):
    ''' Represents a tail command. '''
    def __init__(self, tailed_file):
        ''' Initiate a Tail instance.
            Check for file validity, assigns callback function to standard out.

            Arguments:
                tailed_file - File to be followed. '''
        self.check_file_validity(tailed_file)
        self.tailed_file = tailed_file
        self.callback = sys.stdout.write
        self.flag = True

    def follow(self, s=1):
        ''' Do a tail follow. If a callback function is registered it is called with every new line.
        Else printed to standard out.

        Arguments:
            s - Number of seconds to wait between each iteration; Defaults to 1. '''
        global runFlag
        while runFlag :
            if not os.path.exists(self.tailed_file) :
                self.callback(self.tailed_file, " is not exist, try again after 1s!")
                time.sleep(s)
                continue
            
            with open(self.tailed_file) as file_:
                # Go to the end of file
                file_.seek(0,2)
                readCount = 0
                while runFlag and readCount < 15:
                    curr_position = file_.tell()
                    line = file_.readline()
                    if not line:
                        file_.seek(curr_position)
                    else:
                        self.callback(self.tailed_file, line.strip())
                    time.sleep(s)
                    readCount += 1

    def register_callback(self, func):
        ''' Overrides default callback function to provided function. '''
        self.callback = func

    def check_file_validity(self, file_):
        ''' Check whether the a given file exists, readable and is a file '''
        if not os.access(file_, os.F_OK):
            raise TailError("File '%s' does not exist" % (file_))
        if not os.access(file_, os.R_OK):
            raise TailError("File '%s' not readable" % (file_))
        if os.path.isdir(file_):
            raise TailError("File '%s' is a directory" % (file_))

class TailError(Exception):
    def __init__(self, msg):
        self.message = msg
    def __str__(self):
        return self.message
    
class LogMonitor(threading.Thread):
    def __init__(self, logName, rootPath, actionFunc):
        threading.Thread.__init__(self)
        self.logPath = rootPath + "/" + logName
        self.tailInstance = Tail(self.logPath)
        self.tailInstance.register_callback(actionFunc)
        
    def run(self):
        print("Starting monitor %s" % self.logPath)
        self.tailInstance.follow()
 
def enum(**enums):
    return type('Enum', (), enums)
       
EventType = enum(Normal=1, Error=2, Stat=3)

class Event(object):
    def __init__(self, file, line, eventType, info=""):
        self.file = file
        self.line = line
        self.ctime = time.localtime()
        self.eventType = eventType
        self.info = info

class DefaultAction(object):
    def __init__(self, queue):
        self.queue = queue
        
    def process(self, line, tailFile):
        print ("%s , %s" %(tailFile, line))
    
class ErrorAction(DefaultAction):
    def __init__(self, queue):
        self.queue =  queue
        
    def process(self, line, tailFile):
        lowerline = line.lower()
        if lowerline.find("error")>-1 or lowerline.find("exception")>-1 or lowerline.find(" fail")>-1 :
            event = Event(tailFile, line, EventType.Error, "ERROR")
            self.queue.put(event)
            
class Console(threading.Thread):
     def __init__(self, queue):
        threading.Thread.__init__(self)
        self.queue = queue
        
     def run(self):
         print "LogConsole is started!"
         while runFlag :
             time.sleep(1)
             event = queue.get()
             string = os.path.basename(event.file) + " " + " [" + event.info + "] " 
             string = string + event.line  
             print (string)

def handle (file, line) :
    for func in actionChains :
        func.process(line, file)

def loadTraceFiles(rootPath, suffixList) :
    ret = []
    files = os.listdir(rootPath)
    for f in files :
        file = f.strip()
        if file.find(".") > 0:
            suffix = file[file.find(".") + 1:]
            if suffix in suffixList :
                     ret.append(file)
    return ret

def quit(signum, frame):
    global runFlag 
    runFlag = False
    print 'Script is exited by Ctrl-C'
    sys.exit()

def help():
  helpStr = '''

script [monitorRootPath] [suffix list]
e.g :
 script . "log traces data"
'''
  print(helpStr)
  sys.exit(0)

#-----Procedure begin ------
if len(sys.argv) >= 2 :
    rootPath = sys.argv[1]
else :
    rootPath = "."
    
if len(sys.argv) == 3 :
    suffixList = sys.argv[2].split(" ")
else :
    suffixList = ["log"]
    
if len(sys.argv) >3 :
    help()

signal.signal(signal.SIGINT, quit)
signal.signal(signal.SIGTERM, quit)
queue = Queue.Queue()
threads = []
logs = loadTraceFiles(rootPath, suffixList)
actionChains = [DefaultAction(queue)]

for j in range(0, len(logs)) :
    logM = LogMonitor(logs[j], rootPath, handle)
    logM.setDaemon(True)
    threads.append(logM)
    logM.start()
    
console = Console(queue)
console.setDaemon(True)
console.start()
threads.append(console)

while True:
     alive = False
     for i in range(len(threads)):
         alive = alive or threads[i].isAlive()
     if not alive:
         break
     time.sleep(1)
