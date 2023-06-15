from tkinter import *
import os, subprocess, platform
from datetime import datetime
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox
import utils
from multiprocessing.pool import ThreadPool
from threading import Thread, Lock
from time import sleep
from adbutils import adb, errors, AdbInstallError

VERSION = 1.1
CHECKED_VERSION = False

class App(ttk.Frame):
    def __init__(self, parent):
        ttk.Frame.__init__(self)
        for index in [0, 1, 2]:
            self.columnconfigure(index=index, weight=1)
            self.rowconfigure(index=index, weight=1)

        self.POLLING_DELAY = 250  # ms
        self.lock = Lock()  # Lock for shared resources.
        self.finished = False
        self.download_success = True
        self.path = os.path.dirname(__file__)
        print("work dir: "+self.path)

        self.selected_device = None
        self.device = None
        self.model = None
        top_frame = ttk.LabelFrame(self, text="Nhập IP thiết bị", padding=(20, 10))
        top_frame.grid(
            row=0, column=0, padx=(20, 10), pady=10, sticky="nsew"
        )
        drop_frame = ttk.LabelFrame(self, text="Chọn thiết bị", padding=(20, 10))
        drop_frame.grid(
            row=1, column=0, padx=(20, 10), pady=10, sticky="nsew"
        )
        button_frame = ttk.LabelFrame(self, text="Điều khiển", padding=(20, 10))
        button_frame.grid(
            row=2, column=0, padx=(20, 10), pady=10, sticky="nsew"
        )

        console_frame = ttk.LabelFrame(self, text="Nhật ký", padding=(20, 10))
        console_frame.grid(
            row=0, column=1, rowspan=4, padx=(20, 10), pady=10, sticky="nsew"
        )

        def check_update():
            global VERSION, CHECKED_VERSION
            if CHECKED_VERSION:
                return None
            CHECKED_VERSION = True
            json = utils.get_update_json()
            if json is not None:
                if float(json["version"]) > float(VERSION):
                    answer = messagebox.askyesno(title="Có bản cập nhật", message="{}\n\nChọn YES để bắt đầu.".format(json["changelog"]))
                    if answer:
                        if platform.system() == 'Darwin':       # macOS
                            url = json["download_url_macos"]
                        elif platform.system() == 'Windows':    # Windows
                            url = json["download_url_win"]
                        openfile(url)

        def push_console(text, newline = "\n"):
            console.insert(END, "{}{}".format(text, newline))
            console.see(END)

        def start_scrcpy():
            push_console('Đang mở trình điều khiển cho thiết bị %s.\n [*] Nếu trình điều khiển không hiện lên vui lòng thử lại hoặc chọn Debug để kiểm tra lại kết nối.' % self.selected_device)
            if platform.system() == 'Darwin':       # macOS
                subprocess.Popen(['scrcpy', '-s', self.selected_device], stdout=subprocess.PIPE)
            elif platform.system() == 'Windows':    # Windows
                subprocess.Popen(['scrcpy.exe', '-s', self.selected_device], shell=True)

        def openfile(filepath):
            if platform.system() == 'Darwin':       # macOS
                subprocess.Popen(['open', filepath])
            elif platform.system() == 'Windows':    # Windows
                subprocess.Popen(['start', filepath], shell=True)

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
                btnScreenRemote.config(state=NORMAL)
            else:
                btnInstAdbServer.config(state=DISABLED)
                btnCapture.config(state=DISABLED)
                btnReboot.config(state=DISABLED)
                btnBlinkLed.config(state=DISABLED)
                btnInstallApk.config(state=DISABLED)
                btnScreenRemote.config(state=DISABLED)
            return None
        
        def load_device_info(device):
            try:
                self.device = adb.device(serial=self.selected_device)
                self.device.root()
                product = self.device.prop.model
                self.model = product
                lbDeviceConnected.config(text=product)
                # print(self.selected_device)
            except errors.AdbError as e:
                load_device()
            return None

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

        def reboot():
            try:
                push_console("Rebooting device %s" % self.selected_device)
                self.device.shell("reboot")
            except errors.AdbError as e:
                push_console("Reboot fail")

        def install_adb_server():
            pool = ThreadPool(processes=1)
            async_result = pool.apply_async(install_curl)
            async_result = pool.apply_async(install_app_http)
            async_result = pool.apply_async(remove_apps)
            async_result = pool.apply_async(reboot)

        def install_curl():
            push_console("Installing lib.")
            try:
                mount_system()
                push_console("Installing curl...", "")
                self.device.sync.push("./files/curl-arm", "/system/bin/curl")
                self.device.shell("chmod 777 /system/bin/curl")
                push_console("done.")
                unmount_system()
            except errors.AdbError as e:
                print(e)
                push_console("FAIL. Cần làm lại từ đầu!\n\n")
            
        def install_app_http():
            push_console("Installing app_http.")
            # make dir
            try:
                mount_system()
                push_console("Create dir /data/app_http...", "")
                output = self.device.shell("mkdir /data/app_http && mkdir /data/app_http_web_root", timeout=1)
                push_console("done.")

                # push file
                push_console("Upload file...", "")
                self.device.sync.push("./files/app_http", "/system/bin/app_http")
                self.device.sync.push("./files/key.pem", "/system/bin/key.pem")
                self.device.sync.push("./files/cert.pem", "/system/bin/cert.pem")
                push_console("done.")

                push_console("Chmod file...", "")
                self.device.shell("chmod 777 /system/bin/app_http && chmod 777 /system/bin/key.pem && chmod 777 /system/bin/cert.pem")
                push_console("done.")

                # settings [--user 0] put global package_verifier_enable 0  
                push_console("Disable setting package_verifier_enable...", "")
                self.device.shell("settings put global package_verifier_enable 0")
                push_console("done.")

                check_recovery = self.device.shell("ls /system/bin | grep 'install-recovery.sh'")
                if 'install-recovery.sh' in check_recovery:
                    push_console('found install-recovery.sh in /system/bin')
                    output = self.device.shell("cat /system/bin/install-recovery.sh | grep app_http")
                    if "app_http" not in output:
                        push_console("Installing app_http as system service...")
                        self.device.shell("echo \"sh -c \'export APP_HTTP_CERT_DIR=/system/bin && export APP_HTTP_WEB_ROOT=/data/app_http_web_root && cd /system/bin && ./app_http &\'\" >> /system/bin/install-recovery.sh")
                    else:
                        push_console("app_http already installed")  
                else:
                    push_console('install-recovery.sh not found in /system/bin... create it')
                    self.device.shell("echo \"#!/system/bin/sh\" > /system/bin/install-recovery.sh")
                    self.device.shell("echo \"sh -c \'export APP_HTTP_CERT_DIR=/system/bin && export APP_HTTP_WEB_ROOT=/data/app_http_web_root && cd /system/bin && ./app_http &\'\" >> /system/bin/install-recovery.sh")
                    self.device.shell("chmod 777 /system/bin/install-recovery.sh")
                push_console("ALL DONE.\n\n")
                # unmount
                unmount_system()
            except errors.AdbError as e:
                print(e)
                push_console("FAIL {}. Cần làm lại từ đầu!\n\n".format(e))   
        
        def remove_apps():
            try:
                push_console("Gỡ cài đặt XBos...", "")
                output = self.device.shell("pm uninstall -k --user 0 com.tv.box.tgdd.tgddboxexperience")
                push_console("done.")
                push_console("Gỡ cài đặt Facebook...", "")
                output = self.device.shell("pm uninstall -k --user 0 com.facebook.katana", timeout=10)
                push_console("done.")
                push_console("Gỡ cài đặt Skype...", "")
                output = self.device.shell("pm uninstall -k --user 0 com.skype.raider", timeout=10)
                push_console("done.")
                push_console("Gỡ cài đặt OTA Upgrade...", "")
                output = self.device.shell("pm uninstall -k --user 0 com.himedia.hmdupgrade", timeout=10)
                push_console("done.")
                push_console("Gỡ cài đặt HiMediaTV...", "")
                output = self.device.shell("pm uninstall -k --user 0 com.himedia.channeltv", timeout=10)
                push_console("done.")

                push_console("ALL DONE.\n\n")
            except errors.AdbError as e:
                push_console("FAIL: {}\n\n".format(e))   

        def connect(address):
            try:
                output = adb.connect(address, timeout=10.0)
                print("connect output: %s" % output)
                if 'connected to' in output:
                    lbMsg.config(text="Kết nối thành công.")
                else:
                    lbMsg.config(text="Không thể kết nối.")
                    load_device()
            except errors.AdbTimeout as e:
                messagebox.showerror("Error",  "Quá thời gian kết nối")

        def onBtnConnectClick(*args):
            if ipValue.get() is None or ipValue.get() == "":
                messagebox.showerror("Error",  "Vui lòng nhập IP thiết bị")
                return None
            if utils.valid_ip(ipValue.get()) == None:
                messagebox.showerror("Error",  "IP không hợp lệ")
                return None
            connect(ipValue.get())
        
        # def update_finish(val):
        #     self.finished = val

        # def update_download_status(val):
        #     self.download_success = val

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
            
            if miss_files:
                str = ""
                for file in miss_files:
                    str += "- %s \n" % file
                push_console("Thiếu tập tin:\n - %s" % str)
                # push_console("Đang tải tập tin:")
                # with self.lock:
                #     self.finished = False

                # download_thread = utils.DownloadFile(filelist=miss_files, label=lbStatus, 
                #                                      update_download_status = update_download_status, 
                #                                      update_finish=update_finish, 
                #                                      callback=push_console)
                # download_thread.daemon = True
                # self.after(self.POLLING_DELAY, monitor_download)
                # download_thread.start()
            else:
                install_adb_server()


        # def monitor_download():
        #     print(self.finished)
        #     with self.lock:
        #         if not self.finished:
        #             self.after(self.POLLING_DELAY, monitor_download)  # Keep polling.
        #         else:
        #             print(self.download_success)
        #             if self.download_success:
        #                 # download success => install file
        #                 install_adb_server()
        #             else:
        #                 push_console("Error while download file!.")
                    
        def takescreenshoot():
            if os.path.isdir("screenshoots") == False:
                os.makedirs("screenshoots")
            push_console("Đang chụp màn hình...", "")
            now = datetime.now()
            timestr = now.strftime("%d-%m-%Y-%H-%M-%S")
            filename = "screenshoots/{}-{}.png".format(self.model, timestr)
            self.device.shell("screencap -p /sdcard/screenshot.png")
            self.device.sync.pull("/sdcard/screenshot.png", filename)
            push_console("done. %s" % filename)
            openfile(filename)

        def onBtnCaptureClick(*args):
            pool = ThreadPool(processes=1)
            async_result = pool.apply_async(takescreenshoot)
            return None
        
        def onBtnRebootClick(*args):
            reboot()
            push_console("Đang khởi động lại...")
            return None
        
        def onBtnRefreshClick(*args):
            load_device()
        
        def onBtnDebugClick(*args):
            str = "Thiết bị đã kết nối\n"
            for d in adb.list():
                if 'offline' in d.state:
                    state = "cần khởi động lại!"
                else:
                    state = "đã kết nối"
                str += "  " + d.serial + " - " + state + "\n"
            push_console(str)

        def led_blink():
            push_console("Đang nháy đèn 10 lần...", "")
            self.device.shell("i=0; while [ $((i)) -le 10 ]; do i=$(($i+1)); echo $(($i%2)) > /sys/class/leds/green/brightness; sleep 0.5; done")
            push_console("done.")

        def onBtnBlinkLedClick(*args):
            t = Thread(target=led_blink)
            t.start()

        def onBtnScreenRemote(*args):
            start_scrcpy()

        def install_apk(file_path):
            push_console("Đang cài đặt {}...".format(file_path))
            try:
                output = self.device.install(file_path)
                push_console('hoàn tất.')
            except AdbInstallError as e:
                push_console("error: %s" % e)

        def onBtnInstallApkClick():
            file_path = filedialog.askopenfilename(title="Select APK", parent=self, filetypes=[("APK File", "*.apk")])
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
            # if len(new_choices):
            #     drop_devices['values'] = new_choices

        # frame IP
        ipValue = StringVar()
        txtIp = ttk.Entry(top_frame, width=20, textvariable=ipValue, justify=CENTER)
        txtIp.grid(row=0, column=1, sticky='we')
        btnConnect = ttk.Button(top_frame, text="Kết nối", style='Accent.TButton', command=onBtnConnectClick)
        btnConnect.grid(row=0, column=2, padx=10, sticky='w')
        lbMsg = Label(top_frame, text="")
        lbMsg.grid(row=0,column=3, padx=10, sticky='we')

        # Dropdown menu options
        selected = StringVar()
        drop_devices = ttk.OptionMenu( drop_frame , selected , None, command=on_selected)
        drop_devices.config(width=30)
        drop_devices.grid(row=1, column=0, padx=(0, 10), sticky="ew")

        btnRefresh = ttk.Button(drop_frame, text="Tải lại", command=onBtnRefreshClick)
        btnRefresh.grid(row=1, column=1, padx=(0, 10), sticky='ew')
        btnDebug = ttk.Button(drop_frame, text="Debug", command=onBtnDebugClick)
        btnDebug.grid(row=1, column=2, padx=(0, 10), sticky='ew')

        lbDeviceConnected = ttk.Label( drop_frame, text="")
        lbDeviceConnected.config(width=20)
        lbDeviceConnected.grid(row=1, column=3)

        # frame button
        btnInstAdbServer = ttk.Button(button_frame, text="Cài đặt app_http",style='Accent.TButton', command=onBtnInstAdbServerClick)
        btnInstAdbServer.grid(row=0, column=0, padx=(0,10), sticky='w')

        btnInstallApk = ttk.Button(button_frame, text="Cài đặt APK", command=onBtnInstallApkClick)
        btnInstallApk.grid(row=0, column=1, padx=[0, 10], sticky='w')

        btnCapture = ttk.Button(button_frame, text="Chụp màn hình", command=onBtnCaptureClick)
        btnCapture.grid(row=0, column=2, padx=[0, 10], sticky='w')

        btnReboot = ttk.Button(button_frame, text="Khởi động lại", command=onBtnRebootClick)
        btnReboot.grid(row=0, column=3, padx=[0, 10], sticky='w')

        btnBlinkLed = ttk.Button(button_frame, text="Chớp đèn nguồn", command=onBtnBlinkLedClick)
        btnBlinkLed.grid(row=0, column=4, padx=[0, 10], sticky='w')

        btnScreenRemote = ttk.Button(button_frame, text="Điều khiển", command=onBtnScreenRemote)
        btnScreenRemote.grid(row=1, column=0, padx=[0, 10], pady=[10, 0], sticky='w')

        console = Text(console_frame)
        console.pack(anchor=N, fill=BOTH, expand=True, side=LEFT)

        # lbStatus = ttk.Label(footer_frame, text="")
        # lbStatus.grid(row=0,column=3, padx=10, sticky='we')

        
        load_device()

        self.after(1000, check_update)

if __name__ == "__main__":
    root = tk.Tk()
    root.title("ADBServer Installer")

    # Simply set the theme
    root.tk.call("source", "azure.tcl")
    root.tk.call("set_theme", "dark")

    app = App(root)
    app.pack(fill="both", expand=True)

    # Set a minsize for the window, and place it in the middle
    root.update()
    root.minsize(root.winfo_width(), root.winfo_height())
    x_cordinate = int((root.winfo_screenwidth() / 2) - (root.winfo_width() / 2))
    y_cordinate = int((root.winfo_screenheight() / 2) - (root.winfo_height() / 2))
    root.geometry("+{}+{}".format(x_cordinate, y_cordinate-20))

    root.mainloop()