from tkinter import *
import os, subprocess, re, sys, requests
import tkinter as tk
from tkinter import ttk
import tkinter.messagebox
import utils
from threading import Thread
from time import sleep
from multiprocessing.pool import ThreadPool

run_success = False


def check_before():
    if utils.tool_exist('adb') == 0:
        tkinter.messagebox.showerror("Error",  "Cannot detect adb tool!")
        # return False
    
    config_name = 'myapp.cfg'

    # determine if application is a script file or frozen exe
    if getattr(sys, 'adb', False):
        application_path = os.path.dirname(sys.executable)
    elif __file__:
        application_path = os.path.dirname(__file__)

    config_path = os.path.join(application_path, config_name)
    os.chdir(application_path)
    print(application_path)
    cwd = os.getcwd()

class App:
    def __init__(self, parent):
        self.parent = parent

        self.selected_device = None
        list_devices = []

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
            command = str(command)
            if command.startswith("adb") == False:
                command = "adb -s {} {}".format(self.selected_device, command)
            output = os.popen(command).read()

            print(command)
            print(output)
            return output
        
        def load_device():
            output = call_adb("adb devices")
            if output is None:
                return None
            devices = []
            for line in output.split("\n"):
                if "{}".format(line).endswith("device"):
                    devices.append("{}".format(line).split("\t")[0])
            loadOptionMenu(devices)
            return None
        def load_device_info(device):
            call_adb("root")
            product = call_adb("shell getprop ro.product.device".format(device)).rstrip()
            version = call_adb("shell getprop ro.build.version.release".format(device)).rstrip()
            lbDeviceConnected.config(text="{} (Android: {})".format(product, version))
            return None
        
        def download_file(filename):
            if os.path.isdir("files") == False:
                os.makedirs("files")
            url = "https://aliasesurl.tgdd.vn/ADBServer/{}".format(filename)
            t = utils.DownloadFile(url=url, filename=filename, label=lbStatus)
            t.start()
            t.join()
                        

        def on_selected(*args):
            self.selected_device=selected.get()
            load_device_info(self.selected_device)
        
        def mount_system():
            push_console("Mount system")
            call_adb("shell \"mount -o remount,rw /system && busybox chmod o+w /system/bin\"")
        def unmount_system():
            push_console("Unmount system")
            call_adb("shell \"busybox chmod o-w /system/etc && mount -o remount,ro /system\"")

        def install_curl():
            push_console("Installing curl...")
            mount_system()
            call_adb("push ./files/curl-arm /system/bin/curl")
            call_adb("shell \"chmod 777 /system/bin/curl\"")
            push_console("Push and Chmod curl")
            unmount_system()

            # test
            output = call_adb("shell \"ls /system/bin | grep curl\"")
            if "curl" in output:
                push_console("SUCCESS.\n\n")
            else:
                push_console("FAIL\n\n")
            
        def install_app_http():
            push_console("Installing app_http...")
            # make dir
            output = call_adb("shell \"mkdir /data/app_http && mkdir /data/app_http_web_root\"")
            if output == "":
                push_console("Create dir /data/app_http success")

            # push file
            output = call_adb("push ./files/app_http /data/app_http")
            if "1 file pushed" in output:
                push_console("Push file app_http success")

            output = call_adb("push ./files/key.pem /data/app_http")
            if "1 file pushed" in output:
                push_console("Push file key.pem success")

            output = call_adb("push ./files/cert.pem /data/app_http")
            if "1 file pushed" in output:
                push_console("Push file cert.pem success")

            # chmod file
            output = call_adb("shell \"chmod 777 /data/app_http/app_http && chmod 777 /data/app_http/key.pem && chmod 777 /data/app_http/cert.pem\"")
            if output =="":
                push_console("Chmod files success")
            
            mount_system()
            output = call_adb("exec-out \"cat /system/bin/install-recovery.sh | grep app_http\"")
            if "app_http" not in output:
                push_console("Installing app_http as system service...")
                call_adb('shell "echo \\"sh -c \'export APP_HTTP_WEB_ROOT=/data/app_http_web_root && cd /data/app_http && ./app_http &\'\\" >> /system/bin/install-recovery.sh"')
            unmount_system()

            # test
            output = call_adb("exec-out \"cat /system/bin/install-recovery.sh | grep app_http\"")
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

            output = call_adb("adb connect {}:5555".format(ipValue.get()))
            if "connected" in output:
                lbMsg.config(text="Kết nối thành công")
                load_device()
            else:
                tkinter.messagebox.showerror("Error",  output)

        def onBtnInstAdbServerClick(*args):
            if os.path.isfile("files/curl-arm") == False:
                download_file("curl-arm")
            if os.path.isfile("files/app_http") == False:
                download_file("app_http")
            if os.path.isfile("files/key.pem") == False:
                download_file("key.pem")
            if os.path.isfile("files/cert.pem") == False:
                download_file("cert.pem")

            # tInstall = Thread(target=install_curl)
            # tInstall.start()

            # aInstall = Thread(target=install_app_http)
            # aInstall.start()

            # tInstall.join()
            # aInstall.join()

            pool = ThreadPool(processes=1)
            async_result = pool.apply_async(install_curl)
            async_result = pool.apply_async(install_app_http)
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

# Check adb exist
if check_before() == False:
    exit(1)

# Create windows
w = Tk()
w.title("ADBServer Installer")
w.geometry("600x400")
w.minsize(600, 400)
w.maxsize(600, 400)
App(w)
w.mainloop()