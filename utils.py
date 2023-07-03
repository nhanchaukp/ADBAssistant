import os, requests, re, socket, json, platform, subprocess
from threading import Thread

def openfile(filepath):
    if platform.system() == 'Darwin':       # macOS
        subprocess.Popen(['open', filepath])
    elif platform.system() == 'Windows':    # Windows
        subprocess.Popen(['start', filepath], shell=True)

def valid_ip(ip):
    return re.match(r"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}", ip)

def get_update_json():
    url_json = "https://aliasesurl.tgdd.vn/ADBServer/update.json"
    try:
        with requests.get(url_json, stream=True, timeout=2) as r:
            return json.loads(r.content)
    except:
        return None
    
def recheck_version(ip):
    url = "https://{}/version".format(ip).replace(':5555', ':8443')
    print(url)
    try:
        with requests.post(url, verify=False, timeout=3, headers={
            "Authorization": "Basic YWRtaW46bXdnMjAyNDMqQCghKik=",
            "Content-Type": "text/plain"
        }) as r:
            return r.text
    except:
        return None
    
def send_cmd(ip, cmd, cb):
    url = "https://{}/sh?timeout=3".format(ip).replace(':5555', ':8443')
    print(url)
    try:
        with requests.post(url, data=cmd, verify=False, timeout=3, headers={
            "Authorization": "Basic YWRtaW46bXdnMjAyNDMqQCghKik=",
            "Content-Type": "text/plain"
        }) as r:
            cb(r.text)
    except:
        return None
        
class DownloadFile(Thread):
    # constructor
    def __init__(self, filelist, label, update_download_status, update_finish, callback):
        # execute the base constructor
        Thread.__init__(self)
        # set a default value
        self.filelist = filelist
        self.baseurl = "https://aliasesurl.tgdd.vn/ADBServer/"
        self.label=label
        self.callback = callback
        self.update_download_status = update_download_status
        self.update_finish = update_finish
 
    # function executed in a new thread
    def run(self):
        if os.path.isdir("files") == False:
            os.makedirs("files")
        for filename in self.filelist:
            dl_url = self.baseurl+filename
            # dl_url="http://ipv4.download.thinkbroadband.com/5MB.zip"
            self.callback("Downloading %s..." % filename, "")
            try:
                with requests.get(dl_url, stream=True, timeout=3) as r:
                    with open("files/{}".format(filename), "wb") as f:
                        total_size = int(r.headers.get('content-length'))
                        chunk_size = 1
                        for i, chunk in enumerate(r.iter_content(chunk_size=chunk_size)):
                            percent = round(i * chunk_size / total_size * 100, 1)
                            f.write(chunk)
                            self.label.config(text="Downloading {}... {}%".format(filename, percent))
                    self.callback("done.")
                    self.update_download_status(True)
            except:
                self.callback("fail.")
                self.update_download_status(False)
                self.update_finish(True)
                break
            self.update_finish(True)

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

        for i in range(1, 255):
            addr = net2+str(i)
            s = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            socket.setdefaulttimeout(0.3)
            result = s.connect_ex((addr, 5555))
            print("Check {}:5555 is {}".format(addr, result))
            self.label.config(text="Scan {}".format(addr))
            if result == 0:
                self.device_online.append(addr)
        
        if len(self.device_online):
            self.function("List IP TVBox:\n - %s \nplease copy it and Connect." % '\n - '.join(self.device_online))