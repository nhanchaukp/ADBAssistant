from tkinter import *
import os, subprocess, platform, pathlib
from datetime import datetime
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox
import utils
from multiprocessing.pool import ThreadPool
from threading import Thread, Lock
from time import sleep
from adbutils import adb, errors, AdbInstallError
from pyaxmlparser import APK
from packaging import version
import io
from contextlib import redirect_stdout


VERSION = 1.4
CHECKED_VERSION = False
ENABLE_SEND_CMD = False

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
        cmd_frame = ttk.LabelFrame(self, text="Command Line", padding=(20, 10))
        cmd_frame.grid(
            row=3, column=0, padx=(20, 10), pady=10, sticky="nsew"
        )

        console_frame = ttk.LabelFrame(self, text="Nhật ký", padding=(20, 10))
        console_frame.grid(
            row=0, column=1, rowspan=5, padx=(20, 10), pady=10, sticky="nsew"
        )

        footer_frame = ttk.Frame(self)
        footer_frame.grid(
            row=4, column=0, padx=(20, 10), pady=10, sticky="nsew"
        )

        def push_console(text, newline = "\n"):
            console.insert(END, "{}{}".format(text, newline))
            console.see(END)

        def start_scrcpy():
            push_console('Đang mở trình điều khiển cho thiết bị %s.\n [*] Nếu trình điều khiển không hiện lên vui lòng thử lại hoặc chọn Debug để kiểm tra lại kết nối.' % self.selected_device)
            if platform.system() == 'Darwin':       # macOS
                subprocess.Popen(['lib/scrcpy', '-s', self.selected_device], stdout=subprocess.PIPE)
            elif platform.system() == 'Windows':    # Windows
                subprocess.Popen(['lib\scrcpy.exe', '-s', self.selected_device], shell=True)

        def openfile(filepath):
            if platform.system() == 'Darwin':       # macOS
                subprocess.Popen(['open', filepath])
            elif platform.system() == 'Windows':    # Windows
                subprocess.Popen(['start', filepath], shell=True)

        def load_device():
            drop_devices['values'] = []
            devices = []
            for d in adb.list():
                if d.state == "device":
                    devices.append(d.serial)
                else:
                    adb.disconnect(d.serial)
            if len(devices): 
                drop_devices['values'] = devices
                drop_devices.current(0)
                self.selected_device = devices[0]
                load_device_info(self.selected_device)
            else:
                drop_devices.set("")

            if self.selected_device:
                btnInstAdbServer.config(state=NORMAL)
                btnCapture.config(state=NORMAL)
                btnReboot.config(state=NORMAL)
                btnBlinkLed.config(state=NORMAL)
                btnInstallApk.config(state=NORMAL)
                btnScreenRemote.config(state=NORMAL)
                btnInstallMwgTvc.config(state=NORMAL)
                # btnReCheck.config(state=NORMAL)
            else:
                btnInstAdbServer.config(state=DISABLED)
                btnCapture.config(state=DISABLED)
                btnReboot.config(state=DISABLED)
                btnBlinkLed.config(state=DISABLED)
                btnInstallApk.config(state=DISABLED)
                btnScreenRemote.config(state=DISABLED)
                btnInstallMwgTvc.config(state=DISABLED)
                # btnReCheck.config(state=DISABLED)
            return None
        
        def load_device_info(device):
            try:
                if device is not None:
                    self.device = adb.device(serial=device)
                    self.device.root()
                    product = self.device.prop.model
                    self.model = product
                    lbDeviceConnected.config(text=product)
                # print(self.selected_device)
            except errors.AdbError as e:
                load_device()
            return None

        def on_selected(*args):
            self.selected_device=drop_devices.get()
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
            pool.apply_async(remove_apps)
            pool.apply_async(install_curl)
            pool.apply_async(install_app_http)

        def install_curl():
            push_console("Installing lib.")
            try:
                mount_system()
                push_console("Installing curl...", "")
                self.device.sync.push(pathlib.Path("./files/curl-arm"), "/system/bin/curl")
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
                push_console("Create dir /data/app_http_web_root...", "")
                output = self.device.shell("mkdir /data/app_http_web_root", timeout=1)
                push_console("done.")

                # push file
                push_console("Upload file...", "")
                self.device.sync.push(pathlib.Path("./files/app_http"), "/system/bin/app_http")
                self.device.sync.push(pathlib.Path("./files/key.pem"), "/system/bin/key.pem")
                self.device.sync.push(pathlib.Path("./files/cert.pem"), "/system/bin/cert.pem")
                push_console("done.")

                push_console("Chmod file...", "")
                self.device.shell("chmod 777 /system/bin/app_http && chmod 777 /system/bin/key.pem && chmod 777 /system/bin/cert.pem")
                push_console("done.")

                # settings [--user 0] put global package_verifier_enable 0  
                push_console("Disable setting package_verifier_enable...", "")
                self.device.shell("settings put global package_verifier_enable 0")
                push_console("done.")

                # check_recovery = self.device.shell("ls /system/bin | grep 'install-recovery.sh'")
                # if 'install-recovery.sh' in check_recovery: # file exist in system/bin
                #     push_console('found install-recovery.sh in /system/bin')
                #     output = self.device.shell("cat /system/bin/install-recovery.sh")
                #     if "app_http" not in output:
                #         push_console("Installing app_http as system service...")
                #         self.device.shell("echo \"sh -c \'export APP_HTTP_CERT_DIR=/system/bin && export APP_HTTP_WEB_ROOT=/data/app_http_web_root && cd /system/bin && ./app_http &\'\" >> /system/bin/install-recovery.sh")
                #     else:
                #         push_console("app_http already installed")  

                #     if "busybox nc -lp 48069" not in output:
                #         push_console("Start port 48069 on boot...")
                #         # nc port 48069 -> for check box else tv
                #         self.device.shell("echo \"nohup busybox nc -lp 48069 &\" >> /system/bin/install-recovery.sh")
                # else: # file not exist in system/bin
                #     push_console('install-recovery.sh not found in /system/bin... create it')
                #     self.device.shell("echo \"#!/system/bin/sh\" > /system/bin/install-recovery.sh")
                #     self.device.shell("echo \"sh -c \'export APP_HTTP_CERT_DIR=/system/bin && export APP_HTTP_WEB_ROOT=/data/app_http_web_root && cd /system/bin && ./app_http &\'\" >> /system/bin/install-recovery.sh")
                #     # nc port 48069 -> for check box else tv
                #     self.device.shell("echo \"nohup busybox nc -lp 48069 &\" >> /system/bin/install-recovery.sh")
                #     self.device.shell("chmod 777 /system/bin/install-recovery.sh")

                # create or overwite file
                push_console('Create in /system/bin/install-recovery.sh...', '')
                self.device.shell("echo \"#!/system/bin/sh\" > /system/bin/install-recovery.sh")
                self.device.shell("echo \"sh -c \'export APP_HTTP_CERT_DIR=/system/bin && export APP_HTTP_WEB_ROOT=/data/app_http_web_root && cd /system/bin && ./app_http &\'\" >> /system/bin/install-recovery.sh")
                # nc port 48069 -> for check box else tv
                self.device.shell("echo \"nohup busybox nc -lp 48069 &\" >> /system/bin/install-recovery.sh")
                self.device.shell("chmod 777 /system/bin/install-recovery.sh")
                push_console("done.")
                
                # unmount
                unmount_system()
                push_console("=== ALL DONE ===\n\n")

                # reboot
                pool = ThreadPool(processes=1)
                pool.apply_async(reboot)
            except errors.AdbError as e:
                print(e)
                push_console("FAIL {}. Cần làm lại từ đầu!\n\n".format(e))   
        
        def remove_apps():
            try:

                mount_system()
                check_chrome = self.device.shell("ls /system/app | grep Chrome")
                if "Chrome" in check_chrome:
                    push_console("Xoá thư mục Chrome...", "")
                    self.device.shell("rm -rf /system/app/Chrome")
                    push_console("done.")
                check_gmsStiting = self.device.shell("ls /system/priv-app | grep GmsStiting")
                if "GmsStiting" in check_gmsStiting:
                    push_console("Xoá thư mục GmsStiting...", "")
                    self.device.shell("rm -rf /system/priv-app/GmsStiting")
                    push_console("done.")
                    

                push_console("Gỡ cài đặt Chrome...", "")
                output = self.device.shell("pm uninstall -k --user 0 com.google.chrome")
                push_console("done.")
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
                unmount_system()
            except errors.AdbError as e:
                push_console("FAIL: {}\n\n".format(e))   

        def connect(address):
            btnConnect.config(text="Đang kết nối...")
            try:
                output = adb.connect(address, timeout=5)
                print("connect output: %s" % output)
                if 'connected to' in output:
                    drop_devices.focus()
                    lbMsg.config(text="Kết nối thành công.")
                else:
                    lbMsg.config(text="Không thể kết nối.")
                    txtIp.focus()
            except errors.AdbTimeout as e:
                messagebox.showerror("Error",  "Quá thời gian kết nối")
                txtIp.focus()
            load_device()
            btnConnect.config(text="Kết nối")
            

        def onBtnConnectClick(*args):
            ipVal = ipValue.get().strip()
            if ipVal is None or ipVal == "":
                messagebox.showerror("Error",  "Vui lòng nhập IP thiết bị")
                return None
            if utils.valid_ip(ipVal) == None:
                messagebox.showerror("Error",  "IP không hợp lệ")
                return None
            pool = ThreadPool(processes=1)
            pool.apply_async(connect, [ipVal])

        def onBtnDisconnectClick(*args):
            if self.selected_device:
                adb.disconnect(self.selected_device)
                self.selected_device = None
                load_device()
        
        # def update_finish(val):
        #     self.finished = val

        # def update_download_status(val):
        #     self.download_success = val

        def onBtnInstAdbServerClick(*args):
            lbMsg.config(text="") # remove text device connected
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

        def update_dl_process(state):
            process = round((state.total_downloaded / state.total_length) * 100, 1)
            lbDlProcess.config(text=f"Đang tải...{process}%")
            if process==100:
                lbDlProcess.config(text="")

        def check_mwgtvc():
            url = "https://aliasesurl.tgdd.vn/AppBundle/MWG_TVC.apk"

            if os.path.exists("./files/MWG_TVC.apk") == False:
                push_console("Đang tải MWG_TVC.apk...", "")
                utils.downloader(url=url, savepath="./files/MWG_TVC.apk", callback=update_dl_process)
                push_console("done.")
                return True
            
            apk = APK("./files/MWG_TVC.apk")
            json = utils.get_mwgtvc_json()
            # print(json)
            if json is not None:
                if version.parse(str(json["version"])) > version.parse(str(apk.version_name)):
                    # start download file
                    push_console("Có bản cập nhật MWV_TVC mới: {}".format(json["version"]))
                    if json.get("download_url", "") != "":
                        url = json["download_url"]
                    push_console("Đang tải MWG_TVC.apk...", "")
                    utils.downloader(url=url, savepath="./files/MWG_TVC.apk", callback=update_dl_process)
                    push_console("done.")
                    return True
            return False

        def install_apk(file_path):
            push_console("Đang cài đặt {}...".format(file_path))
            try:
                apk = APK(file_path) # recall to get new version
                push_console(f"- Ứng dụng: {apk.application}\n - Phiên bản: {apk.version_name}")
                cap = utils.Capturing()
                cap.on_readline(lambda line: lbDlProcess.config(text=str(line).strip()))
                cap.start()
                self.device.install(file_path)
                cap.stop()
                lbDlProcess.config(text="")
                push_console('hoàn tất.')
            except AdbInstallError as e:
                push_console("error: %s" % e)
            except Exception as e:
                push_console(e)

        def onBtnInstallApkClick(*args):
            file_path = filedialog.askopenfilename(title="Select APK", parent=self, filetypes=[("APK File", "*.apk")])
            if file_path != "":
                pool = ThreadPool(processes=1)
                pool.apply_async(install_apk, [file_path])

        def onBtnInstallMwgTvc(*args):
            pool = ThreadPool(processes=1)
            pool.apply_async(check_mwgtvc)
            pool.apply_async(install_apk, ['files/MWG_TVC.apk'])

        def onBtnReCheck(*args):
            if self.selected_device is not None:
                ip = self.selected_device
            else:
                ip = ipValue.get() +":8443"

            version = utils.recheck_version(ip)
            if version != None:
                push_console("Service đã được cài đặt. Phiên bản: {}".format(version))
            else:
                push_console("Service chưa được cài đặt, vui lòng thực hiện lại!")

        def onBtnSendCmdClick(*args):
            if not ENABLE_SEND_CMD:
                push_console("Tính năng chỉ dành cho admin!")
                return False
            
            if self.selected_device is not None:
                ip = self.selected_device
            else:
                ip = ipValue.get() +":8443"
            utils.send_cmd(ip, cmdStr.get(), push_console)
        # frame IP
        ipValue = StringVar()
        txtIp = ttk.Entry(top_frame, width=20, textvariable=ipValue, justify=CENTER)
        txtIp.grid(row=0, column=1, sticky='we')
        btnConnect = ttk.Button(top_frame, text="Kết nối", style='Accent.TButton', command=onBtnConnectClick)
        btnConnect.grid(row=0, column=2, padx=10, sticky='w')
        lbMsg = Label(top_frame, text="")
        lbMsg.grid(row=0,column=3, padx=10, sticky='we')

        # Dropdown menu options
        drop_devices = ttk.Combobox(drop_frame, state="readonly")
        drop_devices.bind("<<ComboboxSelected>>", on_selected)
        drop_devices.config(width=30)
        drop_devices.grid(row=0, column=0, padx=(0, 10), sticky="ew")

        btnRefresh = ttk.Button(drop_frame, text="Tải lại", command=onBtnRefreshClick)
        btnRefresh.grid(row=0, column=1, padx=(0, 10), sticky='ew')
        btnDisconnect = ttk.Button(drop_frame, text="Ngắt kết nối", command=onBtnDisconnectClick)
        btnDisconnect.grid(row=0, column=2, padx=(0, 10), sticky='ew')
        btnDebug = ttk.Button(drop_frame, text="Debug", command=onBtnDebugClick)
        btnDebug.grid(row=0, column=3, padx=(0, 10), sticky='ew')

        lbDeviceConnected = ttk.Label( drop_frame, text="")
        lbDeviceConnected.config(width=20)
        lbDeviceConnected.grid(row=0, column=4)

        # frame button
        btnInstAdbServer = ttk.Button(button_frame, text="Cài đặt app_http",style='Accent.TButton', command=onBtnInstAdbServerClick)
        btnInstAdbServer.grid(row=0, column=0, padx=(0,10), sticky='w')

        btnInstallApk = ttk.Button(button_frame, text="Cài đặt APK", command=onBtnInstallApkClick)
        btnInstallApk.grid(row=0, column=1, padx=[0, 10], sticky='w')

        btnInstallMwgTvc = ttk.Button(button_frame, text="Cài đặt MWG_TVC", command=onBtnInstallMwgTvc)
        btnInstallMwgTvc.grid(row=0, column=2, padx=[0, 10], sticky='w')

        btnCapture = ttk.Button(button_frame, text="Chụp màn hình", command=onBtnCaptureClick)
        btnCapture.grid(row=0, column=3, padx=[0, 10], sticky='w')

        btnReboot = ttk.Button(button_frame, text="Khởi động lại", command=onBtnRebootClick)
        btnReboot.grid(row=0, column=4, padx=[0, 10], sticky='w')

        btnBlinkLed = ttk.Button(button_frame, text="Chớp đèn nguồn", command=onBtnBlinkLedClick)
        btnBlinkLed.grid(row=1, column=0, padx=[0, 10], pady=(10, 0), sticky='w')

        btnScreenRemote = ttk.Button(button_frame, text="Điều khiển", command=onBtnScreenRemote)
        btnScreenRemote.grid(row=1, column=1, padx=[0, 10], pady=[10, 0], sticky='w')

        btnReCheck = ttk.Button(button_frame, text="Kiểm tra lại cài đặt", command=onBtnReCheck)
        btnReCheck.grid(row=1, column=2, padx=[0, 10], pady=[10, 0], sticky='w')

        cmdStr = StringVar()
        txtCmd = ttk.Entry(cmd_frame, width=20, textvariable=cmdStr)
        txtCmd.config(width=40)
        txtCmd.grid(row=0, column=0, sticky='we')
        btnSendCmd = ttk.Button(cmd_frame, text="Gửi", style='Accent.TButton', command=onBtnSendCmdClick)
        btnSendCmd.grid(row=0, column=1, padx=10, sticky='w')

        console = Text(console_frame)
        console.pack(anchor=N, fill=BOTH, expand=True, side=LEFT)

        str_footer = "Phiên bản: {}".format(VERSION)
        lbStatus = ttk.Label(footer_frame, text=str_footer)
        lbStatus.grid(row=0,column=0, padx=(0, 10), sticky='we')

        lbDlProcess = ttk.Label(footer_frame, text="")
        lbDlProcess.grid(row=0,column=1, padx=(0, 10), sticky='we')

        
        load_device()
        # with APK.from_file("./files/MWG_TVC.apk") as apk:
        #     apk.get_manifest()

        self.after(1000, check_update)

def check_update(force = False):
    global VERSION, CHECKED_VERSION
    if CHECKED_VERSION and force is False:
        return None
    CHECKED_VERSION = True
    json = utils.get_update_json()
    if json is not None:
        if version.parse(str(json["version"])) > version.parse(str(VERSION)):
            answer = messagebox.askyesno(title="Có bản cập nhật", message="{}\n\nChọn YES để bắt đầu.".format(json["changelog"]))
            if answer:
                if platform.system() == 'Darwin':       # macOS
                    url = json["download_url_macos"]
                elif platform.system() == 'Windows':    # Windows
                    url = json["download_url_win"]
                utils.openfile(url)
    elif force == True:
        messagebox.showinfo(title="Kiểm tra cập nhật", message="Bạn đang dùng phiên bản mới nhất")

if __name__ == "__main__":
    root = tk.Tk()
    root.title("ADB Assistant")
    if platform.system() == 'Windows':    # Windows
        root.iconbitmap('icon.ico')

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


    menubar = Menu(root)
    filemenu = Menu(menubar, tearoff=0, type="menubar")
    filemenu.add_command(label="Thoát", command=root.quit, accelerator="Ctrl+Q")
    menubar.add_cascade(label="Hệ thống", menu=filemenu)

    utilmenu = Menu(menubar, tearoff=0)
    utilmenu.add_command(label="Tải MWG_TVC.apk", command=lambda: utils.openfile("https://aliasesurl.tgdd.vn/AppBundle/MWG_TVC.apk"))
    menubar.add_cascade(label="Tiện ích", menu=utilmenu)

    supportmenu = Menu(menubar, tearoff=0)
    supportmenu.add_command(label="Giới thiệu", command=lambda: messagebox.showinfo(title="Giới thiệu", message=f"ADBAssistant\n\nPhiên bản: {VERSION}\nLiên hệ báo lỗi: 48069"))
    supportmenu.add_command(label="Kiểm tra cập nhật", command=lambda:check_update(True))
    menubar.add_cascade(label="Hỗ trợ", menu=supportmenu)
    root.bind("<Control-q>", root.quit)
    def set_enable_cmd(*args):
        global ENABLE_SEND_CMD
        ENABLE_SEND_CMD=not ENABLE_SEND_CMD
    root.bind("<Control-Return>", func=set_enable_cmd)
    root.config(menu=menubar)
    root.mainloop()