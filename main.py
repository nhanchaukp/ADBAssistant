from tkinter import *
import os, subprocess, platform, urllib, requests
from datetime import datetime
import tkinter as tk
from tkinter import filedialog
import tkinter.messagebox
import utils
from multiprocessing.pool import ThreadPool
from threading import Thread, Lock
from time import sleep
from adbutils import adb, errors, AdbInstallError
import concurrent.futures

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ADBServer Installer")
        self.geometry("600x500")
        self.minsize(600, 500)
        self.maxsize(600, 500)

        self.POLLING_DELAY = 250  # ms
        self.lock = Lock()  # Lock for shared resources.
        self.finished = False
        self.download_success = True
        self.path = os.path.dirname(__file__)
        print("work dir: "+self.path)

        self.selected_device = None
        self.device = None
        self.model = None

        top_frame = Frame(self)
        top_frame.pack(anchor=W, fill=X, pady=10, padx=10)

        scan_frame = Frame(self)
        scan_frame.pack(anchor=W, fill=X, pady=[0, 10])

        drop_frame = Frame(self)
        drop_frame.pack(anchor=W, fill=X, pady=[0, 10])

        staticip_frame = Frame(self)
        staticip_frame.pack(anchor=W, fill=X)


        button_frame = Frame(self)
        button_frame.config(pady=10)
        button_frame.pack(anchor=W, fill=X)

        console_frame = Frame(self)
        console_frame.config(pady=10)
        console_frame.pack(anchor=W, fill=X)


        footer_frame = Frame(self)
        footer_frame.config(pady=10)
        footer_frame.pack(anchor=W, fill=X, side=BOTTOM)

        def push_console(text, newline = "\n"):
            console.insert(END, "{}{}".format(text, newline))

        def openfile(filepath):
            if platform.system() == 'Darwin':       # macOS
                subprocess.call(('open', filepath))
            elif platform.system() == 'Windows':    # Windows
                os.startfile(filepath)
            else:                                   # linux variants
                subprocess.call(('xdg-open', filepath))

        def load_device():
            devices = []
            for d in adb.list():
                if d.state == "device":
                    devices.append(d.serial)
                else:
                    adb.disconnect(d.serial)
            loadOptionMenu(devices)
            if self.selected_device:
                btnInstAdbServer.config(state=NORMAL)
                btnCapture.config(state=NORMAL)
                btnReboot.config(state=NORMAL)
                btnBlinkLed.config(state=NORMAL)
                btnInstallApk.config(state=NORMAL)
                btnSetStaticIp.config(state=NORMAL)
                btnDhcp.config(state=NORMAL)
            else:
                btnInstAdbServer.config(state=DISABLED)
                btnCapture.config(state=DISABLED)
                btnReboot.config(state=DISABLED)
                btnBlinkLed.config(state=DISABLED)
                btnInstallApk.config(state=DISABLED)
                btnSetStaticIp.config(state=DISABLED)
                btnDhcp.config(state=DISABLED)
            return None
        
        def load_device_info(device):
            try:
                self.device = adb.device(serial=self.selected_device)
                self.device.root()
                product = self.device.prop.model
                self.model = product
                lbDeviceConnected.config(text=product)
                staticIpValue.set(value=str(self.selected_device).split(":")[0])
                # print(self.selected_device)
            except errors.AdbError as e:
                load_device()
            return None
        
        # def download_file(filename):
        #     if os.path.exists("files") == False:
        #         os.makedirs("files")
        #         lbStatus.config(text="Create files dir")
        #     url = "https://aliasesurl.tgdd.vn/ADBServer/{}".format(filename)
        #     t = utils.DownloadFile(url=url, filename=filename, label=lbStatus, callback=push_console)
        #     t.start()
        #     # t.join()

        

        def on_selected(*args):
            self.selected_device=selected.get()
            load_device_info(self.selected_device)
        
        def mount_system():
            push_console("Mount system")
            try:
                self.device.shell("mount -o remount,rw /system && busybox chmod o+w /system/bin")
            except errors.AdbError as e:
                push_console("mount fail")
            
        def unmount_system():
            push_console("Unmount system")
            try:
                self.device.shell("busybox chmod o-w /system/etc && mount -o remount,ro /system")
            except errors.AdbError as e:
                push_console("unmount fail")

        def install_curl():
            push_console("Installing lib...")
            mount_system()
            try:
                self.device.sync.push("./files/ipconfigstore", "/system/bin/ipconfigstore")
                self.device.shell("chmod 777 /system/bin/ipconfigstore")
                push_console("Installing ipconfigstore...")

                self.device.sync.push("./files/curl-arm", "/system/bin/curl")
                self.device.shell("chmod 777 /system/bin/curl")
                push_console("Installing curl...")

                push_console("DONE.\n\n")
            except errors.AdbError as e:
                print(e)
                push_console("FAIL\n\n")
            unmount_system()
            
        def install_app_http():
            push_console("Installing app_http...")
            mount_system()
            # make dir
            try:
                push_console("Create dir /data/app_http...", "")
                output = self.device.shell("mkdir /data/app_http && mkdir /data/app_http_web_root", timeout=1)
                push_console("done.")

                # push file
                push_console("Upload file...")
                self.device.sync.push("./files/app_http", "/system/bin/app_http")
                self.device.sync.push("./files/key.pem", "/system/bin/key.pem")
                self.device.sync.push("./files/cert.pem", "/system/bin/cert.pem")
                push_console("done.")

                push_console("Chmod file...")
                self.device.shell("chmod 777 /system/bin/app_http && chmod 777 /system/bin/key.pem && chmod 777 /system/bin/cert.pem")
                push_console("done.")

                # settings [--user 0] put global package_verifier_enable 0  
                push_console("Skip check install new app...")
                self.device.shell("settings put global package_verifier_enable 0")
                push_console("done.")

                output = self.device.shell("cat /system/bin/install-recovery.sh | grep app_http")
                if "app_http" not in output:
                    push_console("Installing app_http as system service...")
                    self.device.shell("echo \"sh -c \'export APP_HTTP_CERT_DIR=/system/bin && export APP_HTTP_WEB_ROOT=/data/app_http_web_root && cd /system/bin && ./app_http &\'\" >> /system/bin/install-recovery.sh")
                else:
                    push_console("app_http already installed")

                
                push_console("ALL DONE.\n\n")
            except errors.AdbError as e:
                print(e)
                push_console("FAIL: {}\n\n".format(e))   
            # unmount
            unmount_system()

        def connect(address):
            try:
                output = adb.connect(address, timeout=10.0)
                print("connect output: %s" % output)
                lbMsg.config(text="Connected")
                load_device()
            except errors.AdbTimeout as e:
                tkinter.messagebox.showerror("Error",  "Connect timeout")

        def onBtnConnectClick(*args):
            if ipValue.get() is None or ipValue.get() == "":
                tkinter.messagebox.showerror("Error",  "Please input IP")
                return None
            if utils.valid_ip(ipValue.get()) == None:
                tkinter.messagebox.showerror("Error",  "IP incorrect!")
                return None
            connect(ipValue.get())

        def download_files(filename, timeout):
            baseurl = "https://aliasesurl.tgdd.vn/ADBServer/"
            dl_url = "http://ipv4.download.thinkbroadband.com/5MB.zip" #baseurl+filename
            try:
                with requests.get(dl_url, stream=True, timeout=timeout) as r:
                    with open("files/{}".format(filename), "wb") as f:
                        total_size = int(r.headers.get('content-length'))
                        chunk_size = 1
                        for i, chunk in enumerate(r.iter_content(chunk_size=chunk_size)):
                            percent = round(i * chunk_size / total_size * 100, 1)
                            f.write(chunk)
                            lbStatus.config(text="Downloading {}... {}%".format(filename, percent))
                    return True
            except Exception as e:
                print(e)
                return False
                
        
        def update_finish(val):
            self.finished = val
        def update_download_status(val):
            self.download_success = val

        def onBtnInstAdbServerClick(*args):
            if not os.path.isdir("files"):
                os.makedirs("files")
            miss_files = []
            if os.path.exists("files/curl-arm") == False:
                miss_files.append("curl-arm")
            if os.path.exists("files/app_http") == False:
                miss_files.append("app_http")
            if os.path.exists("files/key.pem") == False:
                miss_files.append("key.pem")
            if os.path.exists("files/cert.pem") == False:
                miss_files.append("cert.pem")
            if os.path.exists("files/ipconfigstore") == False:
                miss_files.append("ipconfigstore")
            
            dl_complete = True
            if miss_files:
                push_console("Missing file(s):")

                with self.lock:
                    self.finished = False

                download_thread = utils.DownloadFile(filelist=miss_files, label=lbStatus, 
                                                     update_download_status = update_download_status, 
                                                     update_finish=update_finish, 
                                                     callback=push_console)
                download_thread.daemon = True
                self.after(self.POLLING_DELAY, monitor_download)
                download_thread.start()

        def monitor_download():
            with self.lock:
                if not self.finished:
                    self.after(self.POLLING_DELAY, monitor_download)  # Keep polling.
                else:
                    if self.download_success:
                        # download success => install file
                        pool = ThreadPool(processes=1)
                        async_result = pool.apply_async(install_curl)
                        async_result = pool.apply_async(install_app_http)
                    else:
                        push_console("Error while download file!.")
                    

        def monitor(self, thread):
            if thread.is_alive():
            # check the thread every 100ms
                self.after(100, lambda: monitor(self, thread))
            else:
                return True

        def takescreenshoot():
            if os.path.isdir("screenshoots") == False:
                os.makedirs("screenshoots")
            push_console("Taking screenshoot...", "")
            now = datetime.now()
            timestr = now.strftime("%d-%m-%Y-%H-%M-%S")
            filename = "screenshoots/{}-{}.png".format(self.model, timestr)
            self.device.shell("screencap -p /sdcard/screenshot.png")
            self.device.sync.pull("/sdcard/screenshot.png", filename)
            push_console("saved %s" % filename)
            openfile(filename)

        def onBtnCaptureClick(*args):
            pool = ThreadPool(processes=1)
            async_result = pool.apply_async(takescreenshoot)
            return None
        
        def onBtnRebootClick(*args):
            self.device.shell("reboot")
            lbStatus.config(text="Device rebooting...")
            return None
        
        def onBtnRefreshClick(*args):
            load_device()
        
        def onBtnDebugClick(*args):
            str = "List devices\n"
            for d in adb.list():
                str += "  " + d.serial + " - " + d.state + "\n"
            push_console(str)

        def onBtnScanClick(*args):
            if utils.valid_ip(vlanValue.get()) == None:
                tkinter.messagebox.showerror("Error",  "Vlan IP incorrect!")
                return None
            t = utils.ScanAndroidBox(callback=push_console, vlan=vlanValue.get(), label=lbStatus)
            t.start()

        def led_blink():
            push_console("Led blinking...", "")
            self.device.shell("i=0; while [ $((i)) -le 10 ]; do i=$(($i+1)); echo $(($i%2)) > /sys/class/leds/green/brightness; sleep 0.5; done")
            push_console("done.")

        def onBtnBlinkLedClick(*args):
            t = Thread(target=led_blink)
            t.start()

        def set_static_ip():
            push_console("Set static IP %s (WiFi)" % staticIpValue.get())
            data = """ipAssignment: STATIC
linkAddress: {}/24
gateway: 192.168.2.1
dns: 8.8.8.8
proxySettings: NONE
id: 836156484""".format(staticIpValue.get())
            fout = open("files/ipconfig.conf", "wt")
            fout.write(data)
            fout.close()
            try:
                # up file
                push_console("Upload ipconfig.conf...")
                self.device.sync.push("./files/ipconfig.conf", "/data/misc/wifi/ipconfig.conf")
                # pack ipconfig
                push_console("Packing...")
                self.device.shell("ipconfigstore -p 2 < /data/misc/wifi/ipconfig.conf > /data/misc/wifi/ipconfig.txt")

                # restart wifi
                push_console("Restart wifi...")
                self.device.shell("svc wifi disable && sleep 3 && svc wifi enable")

                push_console("DONE.\n\n")
            except errors.AdbError as e:
                print(e)
                push_console("FAIL\n\n")

        def enable_dhcp():
            try:
                # up file
                push_console("Enable DHCP...", "")
                self.device.shell("rm /data/misc/wifi/ipconfig.txt")
                push_console("done.")
            except errors.AdbError as e:
                print(e)
                push_console("FAIL\n\n")
            
        def onBtnSetStaticIpClick(*args):
            if utils.valid_ip(staticIpValue.get()) == None:
                tkinter.messagebox.showerror("Error",  "Static IP incorrect!")
                return None
            pool = ThreadPool(processes=1)
            async_result = pool.apply_async(set_static_ip)

        def onBtnDhcpClick(*args):
            enable_dhcp()

        def install_apk(file_path):
            lbStatus.config(text="Wait for install apk...")
            try:
                output = self.device.install(file_path)
                push_console("Install {} success.".format(file_path))
            except AdbInstallError as e:
                push_console("Error install apk! %s" % e)

        def onBtnInstallApkClick():
            file_path = filedialog.askopenfilename(title="Select APK", parent=self.parent, filetypes=[("APK File", "*.apk")])
            if file_path != "":
                pool = ThreadPool(processes=1)
                async_result = pool.apply_async(install_apk, [file_path])

        def loadOptionMenu(new_choices):
            # Reset var and delete all old options
            selected.set('')
            drop_devices['menu'].delete(0, 'end')

            # Insert list of new options (tk._setit hooks them up to var)
            # print(new_choices)
            if len(new_choices): 
                for choice in new_choices:
                    drop_devices['menu'].add_command(label=choice, command=tk._setit(selected, choice, on_selected))
                selected.set(new_choices[0])
                self.selected_device = new_choices[0]
                load_device_info(self.selected_device)

        # frame IP
        lbIp = Label(top_frame, text="Device IP")
        lbIp.grid(row=0,column=0, sticky='we')
        ipValue = StringVar()
        txtIp = Entry(top_frame, width=20, textvariable=ipValue, justify=CENTER)
        txtIp.grid(row=0, column=1, sticky='w')
        btnConnect = Button(top_frame, text="Connect", command=onBtnConnectClick)
        btnConnect.grid(row=0, column=2, padx=10, sticky='w')
        lbMsg = Label(top_frame, text="")
        lbMsg.grid(row=0,column=3, padx=10, sticky='we')

        # frame scann IP
        lbVlan = Label(scan_frame, text="VLAN")
        lbVlan.grid(row=0,column=0, padx=10, sticky='we')
        vlanValue = StringVar()
        vlanValue.set(value="192.168.2.1")
        # vlanValue.set(value="10.100.120.1")
        txtVlan = Entry(scan_frame, width=20, textvariable=vlanValue, justify=CENTER)
        txtVlan.grid(row=0, column=1, sticky='w')
        btnScan = Button(scan_frame, text="Scan", command=onBtnScanClick)
        btnScan.grid(row=0, column=2, padx=10, sticky='w')
        

        # Dropdown menu options
        selected = StringVar()
        drop_devices = OptionMenu( drop_frame , selected , None, command=on_selected)
        drop_devices.config(width=20)
        drop_devices.grid(row=0, column=0, padx=10)

        btnRefresh = Button(drop_frame, text="Refresh", command=onBtnRefreshClick)
        btnRefresh.grid(row=0, column=1, padx=[0, 10], sticky='w')
        btnDebug = Button(drop_frame, text="Debug", command=onBtnDebugClick)
        btnDebug.grid(row=0, column=2, padx=[0, 10], sticky='w')

        lbDeviceConnected = Label( drop_frame, text="")
        lbDeviceConnected.grid(row=0, column=3, padx=10)
        
        # frame set static IP
        lbStaticIp = Label(staticip_frame, text="Set static IP for WiFi")
        lbStaticIp.grid(row=0,column=0, padx=10, sticky='we')
        staticIpValue = StringVar()
        staticIpValue.set(value="")
        txtStaticIp = Entry(staticip_frame, width=20, textvariable=staticIpValue, justify=CENTER)
        txtStaticIp.grid(row=0, column=1, sticky='w')
        btnSetStaticIp = Button(staticip_frame, text="Set", command=onBtnSetStaticIpClick)
        btnSetStaticIp.grid(row=0, column=2, padx=10, sticky='w')
        btnDhcp = Button(staticip_frame, text="Enable DHCP", command=onBtnDhcpClick)
        btnDhcp.grid(row=0, column=3, padx=[0,10], sticky='w')

        # frame button
        btnInstAdbServer = Button(button_frame, text="Install ADBServer", command=onBtnInstAdbServerClick)
        btnInstAdbServer.grid(row=0, column=0, padx=10, sticky='w')

        btnInstallApk = Button(button_frame, text="Install Apk", command=onBtnInstallApkClick)
        btnInstallApk.grid(row=0, column=1, padx=[0, 10], sticky='w')

        btnCapture = Button(button_frame, text="Take Screenshoot", command=onBtnCaptureClick)
        btnCapture.grid(row=0, column=2, padx=[0, 10], sticky='w')

        btnReboot = Button(button_frame, text="Reboot", command=onBtnRebootClick)
        btnReboot.grid(row=0, column=3, padx=[0, 10], sticky='w')

        btnBlinkLed = Button(button_frame, text="LED Blink", command=onBtnBlinkLedClick)
        btnBlinkLed.grid(row=1, column=0, padx=10, sticky='w')

        console = Text(console_frame, width=82, height=16)
        console.pack(side=tk.LEFT, fill=X, padx=10)

        lbStatus = Label(footer_frame, text="")
        lbStatus.grid(row=0,column=3, padx=10, sticky='we')

        
        load_device()
        # try:
        #     # output = self.device.shell("mkdir /data/app_http && mkdir /data/app_http_web_root", timeout=1)
        #     output = self.device.sync.push(pathlib.Path("files/app_http"), "/data/app_http/app_http")
        #     print(output)
        # except errors.AdbError as e:
        #     print(e)
        # print(self.device.shell("ls /system/bin | grep curl"))
        # print(adb.list())

# Check adb exist
# if check_before() == False:
#     exit(1)

# Create windows
# w = Tk()
# w.title("ADBServer Installer")
# w.geometry("600x500")
# w.minsize(600, 500)
# w.maxsize(600, 500)
# App(w)
# w.mainloop()
if __name__ == "__main__":
    app = App()
    app.mainloop()