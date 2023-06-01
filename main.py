from tkinter import *
import os, subprocess, re, sys, requests, pathlib, queue, platform
from datetime import datetime
import tkinter as tk
from tkinter import filedialog
from tkinter import ttk
import tkinter.messagebox
import utils
from threading import Thread, Event
from time import sleep
from multiprocessing.pool import ThreadPool
from adbutils import adb, errors, AdbInstallError

run_success = False


# def check_before():
#     if utils.tool_exist('adb') == 0:
#         tkinter.messagebox.showerror("Error",  "Cannot detect adb tool!")
#         # return False
    
#     config_name = 'adb'

#     # determine if application is a script file or frozen exe
#     if getattr(sys, 'adb', False):
#         application_path = os.path.dirname(sys.executable)
#     elif __file__:
#         application_path = os.path.dirname(__file__)

#     config_path = os.path.join(application_path, config_name)
#     os.chdir(config_path)
#     print(application_path)

class App:
    def __init__(self, parent):
        self.parent = parent
        self.path = os.path.dirname(__file__)
        print("work dir: "+self.path)

        self.selected_device = None
        self.device = None
        self.model = None

        top_frame = Frame(parent)
        top_frame.pack(anchor=W, fill=X, pady=10, padx=10)

        scan_frame = Frame(parent)
        scan_frame.pack(anchor=W, fill=X, pady=[0, 10])

        drop_frame = Frame(parent)
        drop_frame.pack(anchor=W, fill=X)


        button_frame = Frame(parent)
        button_frame.config(pady=10)
        button_frame.pack(anchor=W, fill=X)

        console_frame = Frame(parent)
        console_frame.config(pady=10)
        console_frame.pack(anchor=W, fill=X)


        footer_frame = Frame(parent)
        footer_frame.config(pady=10)
        footer_frame.pack(anchor=W, fill=X, side=BOTTOM)

        def push_console(text):
            console.insert(END, "%s\n" % text)

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
            return None
        
        def load_device_info(device):
            try:
                self.device = adb.device(serial=self.selected_device)
                self.device.root()
                product = self.device.prop.model
                self.model = product
                lbDeviceConnected.config(text=product)
            except errors.AdbError as e:
                load_device()
            return None
        
        def download_file(filename):
            if os.path.exists("files") == False:
                os.makedirs("files")
                lbStatus.config(text="Create files dir")
            print("Download file: "+filename)
            url = "https://aliasesurl.tgdd.vn/ADBServer/{}".format(filename)
            t = utils.DownloadFile(url=url, filename=filename, label=lbStatus)
            t.start()
            # t.join()
            return t

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
            push_console("Installing curl...")
            mount_system()
            try:
                self.device.sync.push("./files/curl-arm", "/system/bin/curl")
                self.device.shell("chmod 777 /system/bin/curl")
                push_console("Push and Chmod curl binary")
            except errors.AdbError as e:
                push_console("Push and Chmod curl fail")
            unmount_system()

            # test
            output = self.device.shell("ls /system/bin | grep curl")
            if "curl" in output:
                push_console("SUCCESS.\n\n")
            else:
                push_console("FAIL\n\n")
            
        def install_app_http():
            push_console("Installing app_http...")
            mount_system()
            # make dir
            try:
                output = self.device.shell("mkdir /data/app_http && mkdir /data/app_http_web_root", timeout=1)
                push_console("Create dir /data/app_http success")

                # push file
                self.device.sync.push("./files/app_http", "/system/bin/app_http")
                self.device.sync.push("./files/key.pem", "/system/bin/key.pem")
                self.device.sync.push("./files/cert.pem", "/system/bin/cert.pem")
                push_console("Upload file success")

                self.device.shell("chmod 777 /system/bin/app_http && chmod 777 /system/bin/key.pem && chmod 777 /system/bin/cert.pem")
                push_console("Chmod file success")

                # settings [--user 0] put global package_verifier_enable 0  
                self.device.shell("settings put global package_verifier_enable 0")
                push_console("Skip check install new app success")

                output = self.device.shell("cat /system/bin/install-recovery.sh | grep app_http")
                if "app_http" not in output:
                    push_console("Installing app_http as system service...")
                    self.device.shell("echo \"sh -c \'export APP_HTTP_WEB_ROOT=/data/app_http_web_root && cd /system/bin && ./app_http &\'\" >> /system/bin/install-recovery.sh")
                else:
                    push_console("app_http already installed")

                
                push_console("ALL DONE.\n\n")
            except errors.AdbError as e:
                push_console("FAIL: {}\n\n".format(e))   
            # unmount
            unmount_system()

        def connect(address):
            try:
                output = adb.connect("{}:5555".format(address), timeout=10.0)
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

        def onBtnInstAdbServerClick(*args):
            if self.selected_device is None:
                tkinter.messagebox.showerror("Error",  "No device selected!")
                return False
            pool = ThreadPool(processes=1)
            if os.path.exists("files/curl-arm") == False:
                download_file("curl-arm")
            if os.path.exists("files/app_http") == False:
                download_file("app_http")
            if os.path.exists("files/key.pem") == False:
                download_file("key.pem")
            if os.path.exists("files/cert.pem") == False:
                download_file("cert.pem")


            async_result = pool.apply_async(install_curl)
            async_result = pool.apply_async(install_app_http)
            # tkinter.messagebox.showinfo("Congratulation",  "Install app_http successfully")
            return True
        
        def takescreenshoot():
            if os.path.isdir("screenshoots") == False:
                os.makedirs("screenshoots")
            lbStatus.config(text="Wait for take screenshoot...")
            now = datetime.now()
            timestr = now.strftime("%d-%m-%Y-%H-%M-%S")
            filename = "screenshoots/{}-{}.png".format(self.model, timestr)
            self.device.shell("screencap -p /sdcard/screenshot.png")
            self.device.sync.pull("/sdcard/screenshot.png", filename)
            openfile(filename)

        def onBtnCaptureClick(*args):
            if self.selected_device is None:
                tkinter.messagebox.showerror("Error",  "No device selected!")
                return False
            pool = ThreadPool(processes=1)
            async_result = pool.apply_async(takescreenshoot)
            return None
        
        def onBtnRebootClick(*args):
            if self.selected_device is None:
                tkinter.messagebox.showerror("Error",  "No device selected!")
                return False
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

        def onBtnInstallApkClick():
            file_path = filedialog.askopenfilename(title="Select APK", parent=self.parent, filetypes=[("APK File", "*.apk")])
            if file_path != "":
                try:
                    output = self.device.install(file_path)
                    print(output)
                except AdbInstallError as e:
                    print(e)

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
        txtIp = Entry(top_frame, width=20, textvariable=ipValue)
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
        txtVlan = Entry(scan_frame, width=20, textvariable=vlanValue)
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
        

        btnInstAdbServer = Button(button_frame, text="Install ADBServer", command=onBtnInstAdbServerClick)
        btnInstAdbServer.grid(row=0, column=0, padx=10, sticky='w')

        btnInstallApk = Button(button_frame, text="Install Apk", command=onBtnInstallApkClick)
        btnInstallApk.grid(row=0, column=1, padx=[0, 10], sticky='w')

        btnCapture = Button(button_frame, text="Take Screenshoot", command=onBtnCaptureClick)
        btnCapture.grid(row=0, column=2, padx=[0, 10], sticky='w')

        btnReboot = Button(button_frame, text="Reboot", command=onBtnRebootClick)
        btnReboot.grid(row=0, column=3, padx=[0, 10], sticky='w')

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
w = Tk()
w.title("ADBServer Installer")
w.geometry("600x500")
w.minsize(600, 500)
w.maxsize(600, 500)
App(w)
w.mainloop()