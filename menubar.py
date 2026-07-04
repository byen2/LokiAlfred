import rumps
import subprocess
import threading
import webview
import sys
import socket
import time

APP_URL = "http://127.0.0.1:8001"
PORT = 8001
WINDOW_TITLE = "Loki Alfred"

server_process = None


def start_server():
    global server_process
    server_process = subprocess.Popen([sys.executable, "app.py"])


def wait_for_server():
    for _ in range(40):  # wait ~10s
        try:
            with socket.create_connection(("127.0.0.1", PORT), timeout=1):
                return True
        except OSError:
            time.sleep(0.25)
    return False


class RecollMenubarApp(rumps.App):

    def __init__(self):
        super().__init__("📚 Alfred", quit_button=None)

        self.menu = [
            "Open App",
            None,
            "Quit"
        ]

        # start backend server in background
        threading.Thread(target=start_server, daemon=True).start()

        self.window = None

    @rumps.clicked("Open App")
    def open_app(self, _):

        if not wait_for_server():
            rumps.alert("Backend server failed to start.")
            return

        # create window only once
        if self.window is None:
            self.window = webview.create_window(
                WINDOW_TITLE,
                APP_URL,
                width=1000,
                height=750
            )
            webview.start(gui="cocoa")
        else:
            self.window.show()

    @rumps.clicked("Quit")
    def quit_app(self, _):

        if server_process:
            server_process.terminate()

        rumps.quit_application()


if __name__ == "__main__":
    RecollMenubarApp().run()