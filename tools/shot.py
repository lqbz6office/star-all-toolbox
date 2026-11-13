import os
import sys

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app"))
import main as m

app = QApplication(sys.argv)
w = m.MainWindow()
w.show()
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shot.png")


def grab():
    w.grab().save(out, "PNG")
    print("saved", out, os.path.getsize(out))
    app.quit()


QTimer.singleShot(1500, grab)
app.exec_()
