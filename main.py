from tkinter import *
import os, subprocess, re, sys, requests, pathlib, queue
import tkinter as tk
from tkinter import ttk
import tkinter.messagebox
import utils
from threading import Thread
from time import sleep
from multiprocessing.pool import ThreadPool
from adbutils import adb, errors

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
        device = None

        top_frame = Frame(parent)
        top_frame.pack(anchor=W, fill=X)

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

        def call_adb(command):
            # command = str(command)
            # if command.startswith("adb") == False:
            #     command = "adb -s {} {}".format(self.selected_device, command)
            # output = os.popen(command).read()

            # print(command)
            # print(output)

            return None
        
        def load_device():
            devices = []
            for d in adb.device_list():
                devices.append(d.serial)
            loadOptionMenu(devices)
            return None
        
        def load_device_info(device):
            self.device = adb.device(serial=self.selected_device)
            self.device.root()
            # serial = device.shell("getprop ro.serial")
            product = self.device.prop.model
            version = self.device.shell("getprop ro.build.version.release").rstrip()
            lbDeviceConnected.config(text="{} (Android: {})".format(product,version))
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
            # make dir
            try:
                output = self.device.shell("mkdir /data/app_http && mkdir /data/app_http_web_root", timeout=1)
                push_console("Create dir /data/app_http success")
            except errors.AdbError as e:
                push_console("Create dir /data/app_http FAIL")

            # push file
            try:
                self.device.sync.push("./files/app_http", "/data/app_http/app_http")
                self.device.sync.push("./files/key.pem", "/data/app_http/key.pem")
                self.device.sync.push("./files/cert.pem", "/data/app_http/cert.pem")
                push_console("Upload file success")
            except errors.AdbError as e:
                push_console("Upload file FAIL")
            
            try:
                self.device.shell("chmod 777 /data/app_http/app_http && chmod 777 /data/app_http/key.pem && chmod 777 /data/app_http/cert.pem")
                push_console("Chmod file success")
            except errors.AdbError as e:
                push_console("Chmod file FAIL")
            
            mount_system()
            output = self.device.shell("cat /system/bin/install-recovery.sh | grep app_http")
            if "app_http" not in output:
                push_console("Installing app_http as system service...")
                self.device.shell("echo \"sh -c \'export APP_HTTP_WEB_ROOT=/data/app_http_web_root && cd /data/app_http && ./app_http &\'\" >> /system/bin/install-recovery.sh")
            else:
                push_console("app_http already installed")
            unmount_system()

            # test
            output = self.device.shell("cat /system/bin/install-recovery.sh | grep app_http")
            if "app_http" in output:
                push_console("SUCCESS.\n\n")
            else:
                push_console("FAIL !!!\n\n")
            
            
        def onBtnConnectClick(*args):
            if ipValue.get() is None or ipValue.get() == "":
                tkinter.messagebox.showerror("Error",  "Please input IP")
                return None
            match = re.match(r"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}", ipValue.get())

            if match == None:
                tkinter.messagebox.showerror("Error",  "IP incorrect!")
                return None
            
            
            try:
                output = adb.connect("{}:5555".format(ipValue.get()), timeout=3.0)
                lbMsg.config(text="Connected")
                load_device()
            except errors.AdbTimeout as e:
                tkinter.messagebox.showerror("Error",  "Connect timeout")
                

        def onBtnInstAdbServerClick(*args):
            pool = ThreadPool(processes=1)

            if os.path.exists("files/curl-arm") == False:
                download_file("curl-arm")
            if os.path.exists("files/app_http") == False:
                download_file("app_http")
            if os.path.exists("files/key.pem") == False:
                download_file("key.pem")
            if os.path.exists("files/cert.pem") == False:
                download_file("cert.pem")


            # async_result = pool.apply_async(install_curl)
            # async_result = pool.apply_async(install_app_http)
            # tkinter.messagebox.showinfo("Congratulation",  "Install app_http successfully")
            return True

        def loadOptionMenu(new_choices):
            # Reset var and delete all old options
            selected.set('')
            drop_devices['menu'].delete(0, 'end')

            # Insert list of new options (tk._setit hooks them up to var)
            for choice in new_choices:
                drop_devices['menu'].add_command(label=choice, command=tk._setit(selected, choice, on_selected))
            if new_choices: 
                selected.set(new_choices[0])
                self.selected_device = new_choices[0]
                load_device_info(self.selected_device)

        lbIp = Label(top_frame, text="IP")
        lbIp.grid(row=0,column=0, padx=10, sticky='we')

        ipValue = StringVar()
        txtIp = Entry(top_frame, width=20, textvariable=ipValue)
        txtIp.grid(row=0, column=1, pady=10, sticky='w')

        btnConnect = Button(top_frame, text="Connect", command=onBtnConnectClick)
        btnConnect.grid(row=0, column=2, padx=10, sticky='w')

        lbMsg = Label(top_frame, text="")
        lbMsg.grid(row=0,column=3, padx=10, sticky='we')
        

        # Dropdown menu options
        selected = StringVar()
        drop_devices = OptionMenu( drop_frame , selected , None, command=on_selected)
        drop_devices.config(width=20)
        drop_devices.grid(row=0, column=0, padx=10)
        lbDeviceConnected = Label( drop_frame, text="")
        lbDeviceConnected.grid(row=0, column=2, padx=10)

        btnInstAdbServer = Button(button_frame, text="Install ADBServer", command=onBtnInstAdbServerClick)
        btnInstAdbServer.grid(row=0, column=1, padx=10, sticky='w')

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

# Check adb exist
# if check_before() == False:
#     exit(1)

# Create windows
w = Tk()
w.title("ADBServer Installer")
w.geometry("600x400")
w.minsize(600, 400)
w.maxsize(600, 400)
App(w)
w.mainloop()