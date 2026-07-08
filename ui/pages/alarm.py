from datetime import datetime

from PyQt5.QtWidgets import QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget


class AlarmPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(12)

        title = QLabel("ALARM CENTER")
        title.setObjectName("PageTitle")
        main.addWidget(title)

        self.list = QListWidget()
        main.addWidget(self.list)
        self.add_alarm("INFO", "系统告警中心已启动")

    def add_alarm(self, level: str, message: str) -> None:
        now = datetime.now().strftime("%H:%M:%S")
        item = QListWidgetItem(f"{now}   {level:<8}   {message}")
        self.list.insertItem(0, item)
        while self.list.count() > 300:
            self.list.takeItem(self.list.count() - 1)
