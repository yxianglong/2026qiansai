import csv
from pathlib import Path

from PyQt5.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class HistoryPage(QWidget):
    def __init__(self, store, parent=None) -> None:
        super().__init__(parent)
        self.store = store

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("HISTORY RECORDS")
        title.setObjectName("PageTitle")
        refresh = QPushButton("刷新")
        export = QPushButton("导出 CSV")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(refresh)
        header.addWidget(export)
        main.addLayout(header)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["时间", "模型", "类别统计", "目标数", "缺陷数", "最高置信度", "检测框", "备注"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        main.addWidget(self.table)

        refresh.clicked.connect(self.reload)
        export.clicked.connect(self.export_csv)
        self.reload()

    def reload(self) -> None:
        rows = self.store.load()
        self.table.setRowCount(0)
        for record in reversed(rows):
            self.add_record(record, persist=False)

    def add_record(self, record: dict, persist: bool = True) -> None:
        if persist:
            self.store.append(record)

        row = self.table.rowCount()
        self.table.insertRow(row)
        values = [
            record.get("time", ""),
            record.get("model", ""),
            record.get("classes", ""),
            str(record.get("target_count", 0)),
            str(record.get("defect_count", 0)),
            f"{float(record.get('max_confidence', 0)) * 100:.2f}%",
            record.get("boxes", ""),
            record.get("note", ""),
        ]
        for col, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setToolTip(value)
            self.table.setItem(row, col, item)

    def export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出历史记录",
            "inspection_history.csv",
            "CSV Files (*.csv)",
        )
        if not path:
            return
        with Path(path).open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(
                [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
            )
            for row in range(self.table.rowCount()):
                writer.writerow(
                    [
                        self.table.item(row, col).text() if self.table.item(row, col) else ""
                        for col in range(self.table.columnCount())
                    ]
                )
