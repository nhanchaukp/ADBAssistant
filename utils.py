import os, requests, re, socket
from threading import Thread
from adbutils import adb, errors, AdbInstallError

def valid_ip(ip):
    return re.match(r"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}", ip)

class DownloadFile(Thread):
    # constructor
    def __init__(self, url, filename, label):
        # execute the base constructor
        Thread.__init__(self)
        # set a default value
        self.filename = filename
        self.url = url
        self.label=label
 
    # function executed in a new thread
    def run(self):
        if os.path.isdir("files") == False:
            os.makedirs("files")
        with open("files/{}".format(self.filename), "wb") as f:
            response = requests.get(self.url, stream=True, timeout=60000)
            total_length = response.headers.get('content-length')

            if total_length is None: # no content length header
                f.write(response.content)
            else:
                current = 0
                total_length = int(total_length)
                for data in response.iter_content(chunk_size=4096):
                    current += len(data)
                    f.write(data)
                    percent = round(current/total_length * 100, 1)
                    self.label.config(text="Downloading {}... {}%".format(self.filename, percent))

class ScanAndroidBox(Thread):
    # constructor
    def __init__(self, callback, vlan, label):
        # execute the base constructor
        Thread.__init__(self)
        # set a default value
        self.vlan = vlan
        self.label=label
        self.device_online = []
        self.function = callback
 
    # function executed in a new thread
    def run(self):
        net1 = self.vlan.split('.')
        a = '.'
        net2 = net1[0] + a + net1[1] + a + net1[2] + a

        for i in range(2, 255):
            addr = net2+str(i)
            s = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            socket.setdefaulttimeout(0.3)
            result = s.connect_ex((addr, 5555))
            print("Check {}:5555 is {}".format(addr, result))
            self.label.config(text="Scan ip {}".format(addr))
            if result == 0:
                self.device_online.append(addr)
        
        if len(self.device_online):
            self.function("List IP TVBox:\n %s \nplease copy it and Connect." % '\n - '.join(self.device_online))