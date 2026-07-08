from collections import Counter

from PyQt5.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui.widgets import HorizontalBarChart, LineChart, MetricCard


class StatisticsPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.total_frames = 0
        self.total_targets = 0
        self.total_defects = 0
        self.confidence_sum = 0.0
        self.confidence_count = 0
        self.class_counts = Counter()

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(12)

        title = QLabel("STATISTICAL ANALYSIS")
        title.setObjectName("PageTitle")
        main.addWidget(title)

        cards = QGridLayout()
        cards.setSpacing(10)
        self.detected_card = MetricCard("Processed Frames", "0")
        self.target_card = MetricCard("Detected Targets", "0")
        self.defect_card = MetricCard("Defect Targets", "0")
        self.conf_card = MetricCard("Average Confidence", "--")
        for i, card in enumerate(
            (
                self.detected_card,
                self.target_card,
                self.defect_card,
                self.conf_card,
            )
        ):
            cards.addWidget(card, 0, i)
        main.addLayout(cards)

        content = QHBoxLayout()
        self.class_chart = HorizontalBarChart("Defect Class Distribution")
        self.fps_chart = LineChart("Inference FPS Trend", y_min=14.0, y_max=16.0, value_decimals=2)
        content.addWidget(self.class_chart, 4)
        content.addWidget(self.fps_chart, 6)
        main.addLayout(content, 1)

    def update_infer_metrics(self, metrics: dict) -> None:
        fps = float(metrics.get("fps", 0))
        self.total_frames = max(self.total_frames, int(metrics.get("frames", 0)))
        self.detected_card.set_value(str(self.total_frames))
        self.fps_chart.append_value(fps)

    def update_detection(self, meta: dict) -> None:
        targets = int(meta.get("target_count", 0))
        defects = int(meta.get("defect_count", targets))
        self.total_targets += targets
        self.total_defects += defects
        self.class_counts.update(meta.get("class_counts", {}))

        detections = meta.get("detections", []) or []
        for det in detections:
            self.confidence_sum += float(det.get("confidence", 0.0))
            self.confidence_count += 1

        avg_conf = self.confidence_sum / self.confidence_count if self.confidence_count else 0.0

        self.target_card.set_value(str(self.total_targets))
        self.defect_card.set_value(str(self.total_defects))
        self.conf_card.set_value("--" if self.confidence_count == 0 else f"{avg_conf * 100:.2f}%")
        self.class_chart.set_items(dict(self.class_counts))
