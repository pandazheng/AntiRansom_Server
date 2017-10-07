# -*- coding: utf-8 -*-
import Queue
import SocketServer
import hashlib
import os
import sys
import threading
import datetime
import time
#import YaraGenerator
from YaraGenerator.yaraGenerator import *
from Modules.vboxauto import VBoxAuto
from Modules.arsdb import ARServerDB

BUFSIZE = 1024
queueVm = Queue.Queue()

class ItemManager:
    def __init__(self):
        self.nowItem = ""
    def SetItemName(self, item):
        self.nowItem = item
    def GetItemName(self):
        return self.nowItem

class CheckVMThread(threading.Thread):
    def __init__(self, taskId):
        threading.Thread.__init__(self)
    def run(self):
        while True:
            if not queueVm.empty():
                item = queueVm.get()
                print "[INFO] Output Queue - " + str(item)
                os.system("rm -rf ./Samples/Test/*")
                os.system("cp ./Samples/" + str(item) + " ./Samples/Test/" + str(item) + ".exe")
                g_im.SetItemName(item)

                # Start VM Test
                print '[INFO] Restore Snapshot (snapshot3)'
                g_vm.restoreSnapshot('snapshot3')
                print '[INFO] Start VM'
                g_vm.startVm()
                time.sleep(3)
                g_vm.execInGuest()
                time.sleep(10)
                for i in range(100):
                    if g_im.GetItemName() == item:
                        time.sleep(3)
                    else:
                        break
                print '[INFO] Stop VM'
                g_vm.stopVm()
                time.sleep(10)
            else:
                time.sleep(3)
        return

class MyRequestHandler(SocketServer.BaseRequestHandler):
    def handle(self):
        csock = self.request
        print '[INFO] ...connected from:', self.client_address
        hdrCommand  = csock.recv(BUFSIZE).decode()
        StrCommands = [str(x).rstrip('\x00') for x in hdrCommand.split(' ') if x.strip()]
        print StrCommands
        if StrCommands[0] == "CheckVM":
            self.RecvFile(csock, StrCommands)
        elif StrCommands[0] == "ResultVM":
            self.RecvResult(StrCommands)
        #elif StrCommands[0] == "UpdateDB":
    def RecvFile(self, csock, StrCommands):
        hashSHA = hashlib.sha256()
        dt = datetime.now()
        detected_b = 1 if str(StrCommands[2]) == "Detected" else 0
        file_type = str(StrCommands[2])
        file_size = int(StrCommands[3])
        file_name = str(dt.strftime("%y%m%d%H%M%S%f"))
        f = open("./Samples/" + file_name, 'wb')
        totalRecvBytes = 0
        while file_size > totalRecvBytes:
            buf = csock.recv(BUFSIZE);
            buflen = len(buf)
            f.write(buf)
            totalRecvBytes += buflen
            hashSHA.update(buf)
        print "[INFO] File Transfer Complete (" + str(file_name) + ")"
        f.close()
        item = g_db.AddListCheckVM(file_type, hashSHA.hexdigest(), file_name, file_size, detected_b)
        print "[INFO] Input Queue - " + str(file_name)
        queueVm.put(str(file_name))
    def RecvResult(self, StrCommands):
        if StrCommands[1] == g_im.GetItemName():
            g_im.SetItemName("")
            print "[INFO] Results Received (" + str(StrCommands[1]) + ")"
            if int(StrCommands[2]) == 1:
                # Database Update

                # Generate Yara Rule
                args = ["-r", "AR_" + str(StrCommands[1]), "-f", "exe", "./Samples/Test/"]
                generateYara(args)

def main(argv):
    global g_vm
    g_vm = VBoxAuto('Sandbox-Windows 7 x64')
    if not g_vm.check():
        print 'Error initializing'
        sys.exit()

    CheckVMTask = CheckVMThread(1)
    CheckVMTask.start()

    global g_db
    g_db = ARServerDB('antiransom')

    global g_im
    g_im = ItemManager()

    # Open Server
    host = ''
    port = 12345

    serv_sock = SocketServer.TCPServer((host, port), MyRequestHandler, bind_and_activate=False)
    serv_sock.allow_reuse_address = True
    serv_sock.server_bind()
    serv_sock.server_activate()
    print '[INFO] waiting for connection...'
    serv_sock.serve_forever()

if __name__ == '__main__':
    main(sys.argv)
