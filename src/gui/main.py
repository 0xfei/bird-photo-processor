"""Main GUI window for bird-photo-processor."""

import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QSize, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QAction, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QCheckBox,
    QPushButton,
    QLabel,
    QFileDialog,
    QMessageBox,
    QHeaderView,
    QAbstractItemView,
    QGroupBox,
    QLineEdit,
    QSpinBox,
    QSplitter,
    QFrame,
    QTabWidget,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QTextEdit,
    QProgressBar,
)

from send2trash import send2trash

from src.gui.model import PhotoItem, PhotoModel
from src.scanner.directory import ImageScanner
from src.processor.engine import ProcessingEngine
from src.processor.quality_advanced import AdvancedQualityAssessor
from src.utils.config import Config, get_config
from src.api.inaturalist import INaturalistClient
from src.api.ebird import EbirdClient


class RecognitionThread(QThread):
    """Thread for running recognition in background."""

    result_ready = pyqtSignal(dict)
    progress = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, image_path: str, config: Config):
        super().__init__()
        self.image_path = image_path
        self.config = config

    def run(self):
        """Run recognition."""
        try:
            result = {
                "image_path": self.image_path,
                "quality": {},
                "species": None,
                "species_cn": None,
                "confidence": None,
            }

            # Quality assessment
            self.progress.emit("正在评估质量...")
            assessor = AdvancedQualityAssessor(threshold=self.config.quality.threshold)

            from src.utils.models import ImageInfo

            image_info = ImageInfo(path=Path(self.image_path), filename=Path(self.image_path).name)

            image_info = assessor.assess(image_info)

            result["quality"] = {
                "score": image_info.quality_score,
                "clarity": image_info.clarity_score,
                "focus": image_info.focus_score,
                "sharpness": image_info.sharpness_score,
                "level": image_info.quality_level,
            }

            # Species recognition
            if self.config.recognizer.inat_api_key:
                self.progress.emit("正在识别物种...")
                client = INaturalistClient(self.config.recognizer.inat_api_key)
                species_result = client.identify_species(self.image_path)

                if species_result:
                    result["species"] = species_result.get("scientific_name")
                    result["species_cn"] = species_result.get("common_name")
                    result["confidence"] = species_result.get("confidence")
                    result["source"] = "iNaturalist"

            self.result_ready.emit(result)

        except Exception as e:
            self.error.emit(str(e))


class ConfigDialog(QDialog):
    """Dialog for configuring API keys and settings."""

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("⚙️ 配置设置")
        self.setMinimumSize(500, 400)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # API Keys section
        api_group = QGroupBox("🔑 API 配置")
        api_layout = QFormLayout()

        # iNaturalist
        self.inat_key_edit = QLineEdit()
        self.inat_key_edit.setPlaceholderText("输入 iNaturalist API Key")
        self.inat_key_edit.setText(self.config.recognizer.inat_api_key)
        self.inat_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        api_layout.addRow("iNaturalist:", self.inat_key_edit)

        inat_help = QLabel(
            "<small>iNaturalist API Key 申请: <a href='https://www.inaturalist.org/users/api_token'>https://www.inaturalist.org/users/api_token</a></small>"
        )
        inat_help.setOpenExternalLinks(True)
        api_layout.addRow("", inat_help)

        # eBird
        self.ebird_key_edit = QLineEdit()
        self.ebird_key_edit.setPlaceholderText("输入 eBird API Key")
        self.ebird_key_edit.setText(self.config.recognizer.ebird_api_key)
        self.ebird_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        api_layout.addRow("eBird:", self.ebird_key_edit)

        ebird_help = QLabel(
            "<small>eBird API Key 申请: <a href='https://ebird.org/st/request'>https://ebird.org/st/request</a></small>"
        )
        ebird_help.setOpenExternalLinks(True)
        api_layout.addRow("", ebird_help)

        api_group.setLayout(api_layout)
        layout.addWidget(api_group)

        # Quality settings
        quality_group = QGroupBox("📊 质量评估设置")
        quality_layout = QFormLayout()

        self.quality_threshold = QSpinBox()
        self.quality_threshold.setRange(0, 100)
        self.quality_threshold.setValue(int(self.config.quality.threshold))
        self.quality_threshold.setSuffix(" 分")
        quality_layout.addRow("质量阈值:", self.quality_threshold)

        self.dedup_threshold = QSpinBox()
        self.dedup_threshold.setRange(0, 100)
        self.dedup_threshold.setValue(int(self.config.dedup.similarity_threshold * 100))
        self.dedup_threshold.setSuffix("%")
        quality_layout.addRow("重复相似度阈值:", self.dedup_threshold)

        quality_group.setLayout(quality_layout)
        layout.addWidget(quality_group)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_save(self):
        """Save configuration."""
        self.config.recognizer.inat_api_key = self.inat_key_edit.text()
        self.config.recognizer.ebird_api_key = self.ebird_key_edit.text()
        self.config.quality.threshold = float(self.quality_threshold.value())
        self.config.dedup.similarity_threshold = self.dedup_threshold.value() / 100.0

        self.config.save()
        self.accept()


class PhotoTableWidget(QTableWidget):
    """Custom table widget for photo list."""

    def __init__(self):
        super().__init__()
        self.setColumnCount(9)
        self.setHorizontalHeaderLabels(
            ["", "文件名", "质量", "清晰度", "对焦度", "锐利度", "鸟种", "状态", "锁定"]
        )
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.verticalHeader().setVisible(False)

        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.setColumnWidth(0, 30)
        self.setColumnWidth(7, 80)
        self.setColumnWidth(8, 50)

    def populate(self, model: PhotoModel):
        """Populate table with photos."""
        self.setRowCount(0)

        for photo in model.photos:
            row = self.rowCount()
            self.insertRow(row)

            # Checkbox
            checkbox = QCheckBox()
            checkbox.setChecked(photo.selected)
            checkbox.stateChanged.connect(
                lambda state, p=photo: self._on_checkbox_changed(p, state)
            )
            self.setCellWidget(row, 0, checkbox)

            # Filename
            self.setItem(row, 1, QTableWidgetItem(photo.filename))

            # Quality
            score = photo.effective_score
            quality_text = f"{score:.1f}" if score else "N/A"
            item = QTableWidgetItem(quality_text)
            if photo.quality_level == "low":
                item.setBackground(Qt.GlobalColor.red)
            elif photo.quality_level == "high":
                item.setBackground(Qt.GlobalColor.green)
            self.setItem(row, 2, item)

            # Other columns
            for col, val in [
                (3, photo.clarity_score),
                (4, photo.focus_score),
                (5, photo.sharpness_score),
            ]:
                self.setItem(row, col, QTableWidgetItem(f"{val:.1f}" if val else "N/A"))

            # Species
            species = photo.bird_species_cn or photo.bird_species or "-"
            self.setItem(row, 6, QTableWidgetItem(species))

            # Status
            self.setItem(row, 7, QTableWidgetItem(photo.status_text))

            # Lock
            lock_btn = QPushButton("🔒" if photo.locked else "")
            lock_btn.setFixedSize(30, 24)
            lock_btn.clicked.connect(lambda _, p=photo: self._on_lock_clicked(p))
            self.setCellWidget(row, 8, lock_btn)

    def _on_checkbox_changed(self, photo: PhotoItem, state):
        photo.selected = state == Qt.CheckState.Checked.value

    def _on_lock_clicked(self, photo: PhotoItem):
        photo.locked = not photo.locked


class SingleImagePanel(QFrame):
    """Panel for single image recognition."""

    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.recognition_thread: Optional[RecognitionThread] = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        self.setFrameStyle(QFrame.Shape.StyledPanel)

        # Toolbar
        toolbar = QHBoxLayout()

        load_btn = QPushButton("📂 选择图片")
        load_btn.clicked.connect(self._on_load_image)
        toolbar.addWidget(load_btn)

        recognize_btn = QPushButton("🔍 识别")
        recognize_btn.clicked.connect(self._on_recognize)
        toolbar.addWidget(recognize_btn)

        toolbar.addStretch()

        lock_btn = QPushButton("🔒 锁定")
        lock_btn.clicked.connect(self._on_lock)
        toolbar.addWidget(lock_btn)

        delete_btn = QPushButton("🗑️ 删除")
        delete_btn.setStyleSheet("background-color: #ffcccc;")
        delete_btn.clicked.connect(self._on_delete)
        toolbar.addWidget(delete_btn)

        layout.addLayout(toolbar)

        # Image preview
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Image
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(400, 300)
        self.image_label.setStyleSheet("border: 1px solid #ccc; background: #f5f5f5;")
        splitter.addWidget(self.image_label)

        # Info panel
        info_container = QWidget()
        info_layout = QVBoxLayout(info_container)

        info_layout.addWidget(QLabel("<h3>📊 识别结果</h3>"))

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMaximumWidth(300)
        info_layout.addWidget(self.result_text)

        splitter.addWidget(info_container)

        layout.addWidget(splitter)

        # Progress
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.current_image_path: Optional[str] = None
        self.current_photo: Optional[PhotoItem] = None

    def _on_load_image(self):
        """Load image for recognition."""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "", "Images (*.jpg *.jpeg *.png *.heic *.webp)"
        )

        if path:
            self.current_image_path = path
            self._display_image(path)

    def _display_image(self, path: str):
        """Display image."""
        try:
            pixmap = QPixmap(path)
            scaled = pixmap.scaled(
                380,
                280,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.image_label.setPixmap(scaled)
        except Exception as e:
            self.image_label.setText(f"无法加载图片: {e}")

        self.result_text.setText("点击「识别」开始分析图片")

    def _on_recognize(self):
        """Run recognition on current image."""
        if not self.current_image_path:
            QMessageBox.warning(self, "提示", "请先选择图片")
            return

        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.result_text.setText("正在处理...")

        self.recognition_thread = RecognitionThread(self.current_image_path, self.config)
        self.recognition_thread.result_ready.connect(self._on_result_ready)
        self.recognition_thread.progress.connect(self._on_progress)
        self.recognition_thread.error.connect(self._on_error)
        self.recognition_thread.start()

    def _on_result_ready(self, result: dict):
        """Handle recognition result."""
        self.progress.setVisible(False)

        # Update display
        quality = result.get("quality", {})

        html = f"""
<h4>质量评估</h4>
<table>
<tr><td>综合质量:</td><td><b>{quality.get("score", "N/A"):.1f}</b></td></tr>
<tr><td>清晰度:</td><td>{quality.get("clarity", "N/A"):.1f}</td></tr>
<tr><td>对焦度:</td><td>{quality.get("focus", "N/A"):.1f}</td></tr>
<tr><td>边缘锐利度:</td><td>{quality.get("sharpness", "N/A"):.1f}</td></tr>
<tr><td>质量等级:</td><td>{quality.get("level", "N/A")}</td></tr>
</table>
"""

        if result.get("species"):
            html += f"""
<h4>物种识别</h4>
<table>
<tr><td>物种:</td><td><b>{result.get("species_cn") or result.get("species")}</b></td></tr>
<tr><td>学名:</td><td><i>{result.get("species")}</i></td></tr>
<tr><td>置信度:</td><td>{result.get("confidence", 0):.1%}</td></tr>
<tr><td>来源:</td><td>{result.get("source", "N/A")}</td></tr>
</table>
"""
        else:
            html += "<p>未识别到鸟类</p>"

        self.result_text.setHtml(html)

    def _on_progress(self, message: str):
        """Handle progress message."""
        self.result_text.setText(message)

    def _on_error(self, error: str):
        """Handle error."""
        self.progress.setVisible(False)
        self.result_text.setText(f"错误: {error}")

    def _on_lock(self):
        """Toggle lock."""
        QMessageBox.information(self, "锁定", "锁定功能：在列表模式下可用")

    def _on_delete(self):
        """Delete current image."""
        if not self.current_image_path:
            return

        reply = QMessageBox.question(
            self,
            "确认删除",
            "确定要将这张照片移到回收站吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                send2trash(self.current_image_path)
                self.image_label.clear()
                self.result_text.setText("已删除")
                self.current_image_path = None
            except Exception as e:
                QMessageBox.warning(self, "错误", f"删除失败: {e}")


class MainWindow(QMainWindow):
    """Main window for photo processor GUI."""

    def __init__(self, initial_path: Optional[str] = None):
        super().__init__()

        self.config = get_config()
        self.model = PhotoModel()
        self.current_directory: Optional[Path] = None

        self._init_ui()
        self._init_menu()

        if initial_path:
            QTimer.singleShot(100, lambda: self.load_directory(initial_path))

    def _init_ui(self):
        """Initialize UI."""
        self.setWindowTitle("🐦 照片筛选工具")
        self.setMinimumSize(1000, 600)

        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)

        # Toolbar
        toolbar = self._create_toolbar()
        layout.addLayout(toolbar)

        # Tab widget
        self.tabs = QTabWidget()

        # List mode
        list_widget = QWidget()
        list_layout = QVBoxLayout(list_widget)

        # Filter panel
        filter_panel = self._create_filter_panel()
        list_layout.addWidget(filter_panel)

        # Table
        self.table = PhotoTableWidget()
        self.table.itemClicked.connect(self._on_table_item_clicked)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        list_layout.addWidget(self.table)

        self.tabs.addTab(list_widget, "📋 列表模式")

        # Single image mode
        self.single_panel = SingleImagePanel(self.config)
        self.tabs.addTab(self.single_panel, "🖼️ 单张识别")

        layout.addWidget(self.tabs)

        # Status bar
        self.statusBar().showMessage("就绪")

    def _create_toolbar(self) -> QHBoxLayout:
        """Create toolbar."""
        layout = QHBoxLayout()

        scan_btn = QPushButton("📂 扫描目录")
        scan_btn.clicked.connect(self._on_scan_clicked)
        layout.addWidget(scan_btn)

        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self._on_refresh_clicked)
        layout.addWidget(refresh_btn)

        layout.addStretch()

        # Selection buttons
        select_all_btn = QPushButton("☑️ 全选")
        select_all_btn.clicked.connect(self._on_select_all)
        layout.addWidget(select_all_btn)

        deselect_btn = QPushButton("☐ 取消")
        deselect_btn.clicked.connect(self._on_deselect_all)
        layout.addWidget(deselect_btn)

        delete_btn = QPushButton("🗑️ 删除选中")
        delete_btn.setStyleSheet("background-color: #ffcccc;")
        delete_btn.clicked.connect(self._on_delete_clicked)
        layout.addWidget(delete_btn)

        self.stats_label = QLabel("总计: 0 | 已选: 0 | 锁定: 0")
        layout.addWidget(self.stats_label)

        # Config button
        config_btn = QPushButton("⚙️ 配置")
        config_btn.clicked.connect(self._on_config_clicked)
        layout.addWidget(config_btn)

        return layout

    def _create_filter_panel(self) -> QWidget:
        """Create filter panel."""
        group = QGroupBox("筛选条件")
        layout = QHBoxLayout()

        layout.addWidget(QLabel("质量 <"))
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(0, 100)
        self.quality_spin.setValue(40)
        self.quality_spin.setSuffix(" 分")
        layout.addWidget(self.quality_spin)

        layout.addWidget(QLabel("  鸟种:"))
        self.species_edit = QLineEdit()
        self.species_edit.setPlaceholderText("输入鸟种筛选...")
        layout.addWidget(self.species_edit)

        layout.addStretch()

        return group

    def _init_menu(self):
        """Initialize menu."""
        menubar = self.menuBar()

        file_menu = menubar.addMenu("文件")

        open_action = QAction("打开目录", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._on_scan_clicked)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def load_directory(self, path: str):
        """Load directory."""
        dir_path = Path(path)
        if not dir_path.exists() or not dir_path.is_dir():
            QMessageBox.warning(self, "错误", "请选择有效的目录")
            return

        self.current_directory = dir_path
        self.setWindowTitle(f"🐦 照片筛选工具 - {dir_path}")

        try:
            scanner = ImageScanner()
            photos = scanner.scan(dir_path)

            if not photos:
                QMessageBox.information(self, "提示", "目录中没有找到图片")
                return

            # Process
            from src.processor.engine import ProcessingEngine

            engine = ProcessingEngine(self.config)
            result = engine.process(dir_path)

            # Convert
            photo_items = []
            for img in photos:
                item = PhotoItem(
                    path=img.path,
                    filename=img.filename,
                    size=img.size,
                    created_time=img.created_time,
                    quality_score=img.quality_score,
                    clarity_score=img.clarity_score,
                    focus_score=img.focus_score,
                    sharpness_score=img.sharpness_score,
                    bird_species=img.bird_species,
                    bird_species_cn=img.bird_species_cn,
                    bird_confidence=img.bird_confidence,
                    is_duplicate=img.is_duplicate,
                    duplicate_group=img.duplicate_group,
                    quality_level=img.quality_level or "unknown",
                )
                photo_items.append(item)

            self.model.set_photos(photo_items)
            self.table.populate(self.model)

            self._update_status()
            self.statusBar().showMessage(f"已加载 {len(photo_items)} 张照片")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"处理失败: {e}")

    def _update_status(self):
        """Update status."""
        total = len(self.model.photos)
        selected = self.model.get_selected_count()
        locked = self.model.get_locked_count()
        self.stats_label.setText(f"总计: {total} | 已选: {selected} | 锁定: {locked}")

    # Event handlers
    def _on_scan_clicked(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择照片目录")
        if dir_path:
            self.load_directory(dir_path)

    def _on_refresh_clicked(self):
        if self.current_directory:
            self.load_directory(str(self.current_directory))

    def _on_select_all(self):
        self.model.select_all()
        self.table.populate(self.model)
        self._update_status()

    def _on_deselect_all(self):
        self.model.deselect_all()
        self.table.populate(self.model)
        self._update_status()

    def _on_delete_clicked(self):
        selected = self.model.get_selected_photos()
        if not selected:
            QMessageBox.information(self, "提示", "请先选择要删除的照片")
            return

        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要将 {len(selected)} 张照片移到回收站吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            deleted = 0
            for photo in selected:
                try:
                    send2trash(str(photo.path))
                    self.model.remove_photo(photo.index)
                    deleted += 1
                except Exception as e:
                    QMessageBox.warning(self, "警告", f"删除失败: {photo.filename}")

            self.table.populate(self.model)
            self._update_status()
            self.statusBar().showMessage(f"已删除 {deleted} 张照片")

    def _on_table_item_clicked(self, item):
        row = item.row()
        photo = self.model.get_photo(row)
        if photo:
            self.single_panel.current_image_path = str(photo.path)
            self.single_panel._display_image(str(photo.path))
            self.tabs.setCurrentIndex(1)  # Switch to single mode

    def _on_selection_changed(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if selected_rows:
            row = selected_rows[0].row()
            photo = self.model.get_photo(row)
            if photo:
                self.single_panel.current_image_path = str(photo.path)
                self.single_panel._display_image(str(photo.path))

    def _on_config_clicked(self):
        dialog = ConfigDialog(self.config, self)
        if dialog.exec():
            self.config = get_config()
            self.single_panel.config = self.config


def run_gui(initial_path: Optional[str] = None):
    """Run the GUI application."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = MainWindow(initial_path)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    run_gui()
