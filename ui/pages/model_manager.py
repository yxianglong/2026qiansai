from pathlib import Path

from PyQt5.QtWidgets import (
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class ModelManagerPage(QWidget):
    def __init__(self, models, parent=None) -> None:
        super().__init__(parent)
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(12)

        title = QLabel("MODEL MANAGEMENT")
        title.setObjectName("PageTitle")
        main.addWidget(title)

        self.table = QTableWidget(len(models), 7)
        self.table.setHorizontalHeaderLabels(
            ["模型名称", "RKNN 文件", "类别数", "输入尺寸", "TPE", "文件状态", "类别"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)

        for row, model in enumerate(models):
            path = Path(model.get("path", ""))
            values = [
                model.get("name", ""),
                str(path),
                str(len(model.get("classes", []))),
                " × ".join(str(v) for v in model.get("input_size", [])),
                str(model.get("tpes", 8)),
                "存在" if path.exists() else "未找到",
                ", ".join(model.get("classes", [])),
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))
        main.addWidget(self.table)
