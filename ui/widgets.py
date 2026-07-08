from collections import deque
from typing import Iterable, List

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


ACCENT = QColor("#65D9FF")
TEXT = QColor("#D8F2FF")
MUTED = QColor("#7FAAC5")
GRID = QColor("#1B3954")
ALERT = QColor("#FF5D70")
WARNING = QColor("#FFB84D")
NORMAL = QColor("#42D6A4")


class SectionFrame(QFrame):
    def __init__(self, title: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("SectionFrame")
        self.outer = QVBoxLayout(self)
        self.outer.setContentsMargins(14, 12, 14, 14)
        self.outer.setSpacing(10)
        if title:
            label = QLabel(title.upper())
            label.setObjectName("SectionTitle")
            self.outer.addWidget(label)

    def add_widget(self, widget: QWidget, stretch: int = 0) -> None:
        self.outer.addWidget(widget, stretch)


class MetricCard(QFrame):
    def __init__(self, title: str, value: str = "--", subtitle: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("MetricCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(2)

        self.title_label = QLabel(title.upper())
        self.title_label.setObjectName("MetricTitle")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("MetricValue")
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("MetricSubtitle")
        self.subtitle_label.setWordWrap(True)

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.subtitle_label)
        layout.addStretch(1)

    def set_value(self, value: str, subtitle: str = None) -> None:
        self.value_label.setText(value)
        if subtitle is not None:
            self.subtitle_label.setText(subtitle)


class CoreUsageWidget(QFrame):
    def __init__(self, index: int, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("CoreUsage")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        top = QHBoxLayout()
        self.name = QLabel(f"CORE {index}")
        self.name.setObjectName("CoreName")
        self.value = QLabel("0%")
        self.value.setAlignment(Qt.AlignRight)
        self.value.setObjectName("CoreValue")
        top.addWidget(self.name)
        top.addStretch()
        top.addWidget(self.value)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(7)

        self.freq = QLabel("0 MHz")
        self.freq.setObjectName("SmallMuted")
        layout.addLayout(top)
        layout.addWidget(self.bar)
        layout.addWidget(self.freq)

    def set_data(self, usage: float, freq_mhz: float) -> None:
        self.bar.setValue(int(max(0, min(100, usage))))
        self.value.setText(f"{usage:.0f}%")
        self.freq.setText(f"{freq_mhz:.0f} MHz")


class RingGauge(QWidget):
    def __init__(self, title: str, unit: str = "%", parent=None) -> None:
        super().__init__(parent)
        self.title = title
        self.unit = unit
        self.value = 0.0
        self.setMinimumSize(128, 128)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_value(self, value: float) -> None:
        self.value = max(0.0, min(100.0, float(value)))
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(14, 14, self.width() - 28, self.height() - 28)
        pen = QPen(QColor("#17344D"), 9)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, 210 * 16, -240 * 16)

        pen.setColor(ACCENT)
        painter.setPen(pen)
        painter.drawArc(rect, 210 * 16, int(-240 * 16 * self.value / 100.0))

        painter.setPen(TEXT)
        font = QFont()
        font.setPointSize(17)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignCenter, f"{self.value:.0f}{self.unit}")

        painter.setPen(MUTED)
        font.setPointSize(9)
        font.setBold(False)
        painter.setFont(font)
        painter.drawText(
            QRectF(0, self.height() - 28, self.width(), 22),
            Qt.AlignCenter,
            self.title.upper(),
        )


class LineChart(QWidget):
    def __init__(
        self,
        title: str,
        max_points: int = 60,
        y_max: float = 100.0,
        y_min: float = 0.0,
        value_decimals: int = 1,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.title = title
        self.y_min = float(y_min)
        self.y_max = float(y_max)
        if self.y_max <= self.y_min:
            self.y_max = self.y_min + 1.0
        self.value_decimals = int(max(0, value_decimals))
        self.values = deque(maxlen=max_points)
        self.setMinimumHeight(160)

    def append_value(self, value: float) -> None:
        self.values.append(float(value))
        self.update()

    def _format_value(self, value: float) -> str:
        return f"{value:.{self.value_decimals}f}"

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#08182D"))

        left, top, right, bottom = 48, 30, 14, 26
        chart = QRectF(left, top, self.width() - left - right, self.height() - top - bottom)
        y_range = max(self.y_max - self.y_min, 1e-6)

        painter.setPen(MUTED)
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)
        painter.drawText(12, 18, self.title.upper())

        painter.setPen(QPen(GRID, 1))
        for i in range(5):
            ratio = i / 4
            y = chart.top() + ratio * chart.height()
            painter.drawLine(QPointF(chart.left(), y), QPointF(chart.right(), y))
            label_value = self.y_max - ratio * y_range
            painter.setPen(MUTED)
            painter.drawText(
                QRectF(4, y - 8, left - 8, 16),
                Qt.AlignRight | Qt.AlignVCenter,
                self._format_value(label_value),
            )
            painter.setPen(QPen(GRID, 1))

        vals = list(self.values)
        if len(vals) < 2:
            return

        points = []
        count = max(len(vals) - 1, 1)
        for idx, value in enumerate(vals):
            x = chart.left() + idx * chart.width() / count
            clipped = max(self.y_min, min(self.y_max, value))
            y = chart.bottom() - (clipped - self.y_min) / y_range * chart.height()
            points.append(QPointF(x, y))

        painter.setPen(QPen(ACCENT, 2))
        painter.drawPolyline(QPolygonF(points))

        painter.setPen(TEXT)
        painter.drawText(
            QRectF(chart.right() - 85, 4, 80, 20),
            Qt.AlignRight,
            self._format_value(vals[-1]),
        )

class HorizontalBarChart(QWidget):
    def __init__(self, title: str = "类别分布", parent=None) -> None:
        super().__init__(parent)
        self.title = title
        self.items = {}
        self.setMinimumHeight(260)

    def set_items(self, items: dict) -> None:
        self.items = dict(items)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#08182D"))
        painter.setPen(MUTED)
        painter.drawText(12, 22, self.title.upper())

        if not self.items:
            painter.drawText(self.rect(), Qt.AlignCenter, "暂无结构化检测数据")
            return

        top = 44
        row_h = max(28, (self.height() - top - 18) // max(len(self.items), 1))
        max_value = max(self.items.values()) if self.items else 1
        for idx, (name, value) in enumerate(self.items.items()):
            y = top + idx * row_h
            painter.setPen(TEXT)
            painter.drawText(12, y + 17, str(name))
            bar_x = min(180, max(100, self.width() // 3))
            bar_w = max(20, self.width() - bar_x - 70)
            painter.fillRect(QRectF(bar_x, y + 5, bar_w, 12), QColor("#17344D"))
            fill = bar_w * float(value) / max(max_value, 1)
            painter.fillRect(QRectF(bar_x, y + 5, fill, 12), ACCENT)
            painter.drawText(self.width() - 56, y + 17, str(value))
