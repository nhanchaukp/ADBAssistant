import os, requests, sys
from shutil import which
from threading import Thread



def tool_exist(name):
    return os.path.isfile(name)

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