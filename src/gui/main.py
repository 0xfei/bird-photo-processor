"""Main GUI window for bird-photo-processor."""

import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QSize, QTimer
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
    QScrollArea,
    QProgressDialog,
)

from send2trash import send2trash

from src.gui.model import PhotoItem, PhotoModel
from src.scanner.directory import ImageScanner
from src.processor.engine import ProcessingEngine
from src.utils.config import Config


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

        # Column widths
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

            # Clarity
            self.setItem(
                row,
                2,
                QTableWidgetItem(f"{photo.clarity_score:.1f}" if photo.clarity_score else "N/A"),
            )

            # Focus
            self.setItem(
                row, 3, QTableWidgetItem(f"{photo.focus_score:.1f}" if photo.focus_score else "N/A")
            )

            # Sharpness
            self.setItem(
                row,
                4,
                QTableWidgetItem(
                    f"{photo.sharpness_score:.1f}" if photo.sharpness_score else "N/A"
                ),
            )

            # Species
            species = photo.bird_species_cn or photo.bird_species or "-"
            self.setItem(row, 5, QTableWidgetItem(species))

            # Status
            self.setItem(row, 6, QTableWidgetItem(photo.status_text))

            # Lock
            lock_btn = QPushButton("🔒" if photo.locked else "")
            lock_btn.setFixedSize(30, 24)
            lock_btn.clicked.connect(lambda _, p=photo: self._on_lock_clicked(p))
            self.setCellWidget(row, 8, lock_btn)

    def _on_checkbox_changed(self, photo: PhotoItem, state):
        """Handle checkbox state change."""
        photo.selected = state == Qt.CheckState.Checked.value

    def _on_lock_clicked(self, photo: PhotoItem):
        """Handle lock button click."""
        photo.locked = not photo.locked
        if photo.locked:
            photo.selected = False


class PreviewPanel(QFrame):
    """Preview panel showing image and quality info."""

    def __init__(self):
        super().__init__()
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setMinimumSize(400, 300)

        layout = QVBoxLayout(self)

        # Image preview
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(400, 250)
        self.image_label.setStyleSheet("border: 1px solid #ccc;")
        layout.addWidget(self.image_label)

        # Info panel
        self.info_label = QLabel()
        self.info_label.setStyleSheet("font-size: 12px; padding: 5px;")
        layout.addWidget(self.info_label)

        self._current_photo: Optional[PhotoItem] = None

    def show_photo(self, photo: Optional[PhotoItem]):
        """Show photo preview."""
        self._current_photo = photo

        if photo is None:
            self.image_label.setText("点击列表中的图片查看预览")
            self.info_label.setText("")
            return

        # Load and display image
        try:
            pixmap = QPixmap(str(photo.path))

            # Scale to fit
            scaled = pixmap.scaled(
                380,
                230,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.image_label.setPixmap(scaled)
        except Exception as e:
            self.image_label.setText(f"无法加载图片: {e}")

        # Show info
        info = photo.get_info_dict()

        info_text = f"""
<table style="font-size: 12px; width: 100%;">
<tr><td><b>文件:</b></td><td>{photo.filename}</td></tr>
<tr><td><b>质量:</b></td><td>{info["quality"]}</td></tr>
<tr><td><b>清晰度:</b></td><td>{info["clarity"]}</td></tr>
<tr><td><b>对焦度:</b></td><td>{info["focus"]}</td></tr>
<tr><td><b>锐利度:</b></td><td>{info["sharpness"]}</td></tr>
<tr><td><b>鸟种:</b></td><td>{info["species"]}</td></tr>
<tr><td><b>置信度:</b></td><td>{info["confidence"]}</td></tr>
<tr><td><b>状态:</b></td><td>{info["status"]}</td></tr>
<tr><td><b>路径:</b></td><td style="font-size: 10px;">{photo.path}</td></tr>
</table>
"""
        self.info_label.setText(info_text)


class MainWindow(QMainWindow):
    """Main window for photo processor GUI."""

    def __init__(self, initial_path: Optional[str] = None):
        super().__init__()

        self.model = PhotoModel()
        self.current_directory: Optional[Path] = None

        self._init_ui()
        self._init_menu()

        if initial_path:
            QTimer.singleShot(100, lambda: self.load_directory(initial_path))

    def _init_ui(self):
        """Initialize UI components."""
        self.setWindowTitle("🐦 照片筛选工具")
        self.setMinimumSize(1200, 700)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)

        # Toolbar
        toolbar = self._create_toolbar()
        main_layout.addLayout(toolbar)

        # Filter panel
        filter_panel = self._create_filter_panel()
        main_layout.addWidget(filter_panel)

        # Main splitter
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Table
        self.table = PhotoTableWidget()
        self.table.itemClicked.connect(self._on_table_item_clicked)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        splitter.addWidget(self.table)

        # Preview panel
        self.preview = PreviewPanel()
        splitter.addWidget(self.preview)

        splitter.setSizes([400, 300])
        main_layout.addWidget(splitter)

        # Status bar
        self.statusBar().showMessage("就绪")

    def _create_toolbar(self) -> QHBoxLayout:
        """Create toolbar."""
        layout = QHBoxLayout()

        # Scan button
        self.scan_btn = QPushButton("📂 扫描目录")
        self.scan_btn.clicked.connect(self._on_scan_clicked)
        layout.addWidget(self.scan_btn)

        # Refresh button
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.clicked.connect(self._on_refresh_clicked)
        layout.addWidget(self.refresh_btn)

        layout.addStretch()

        # Selection buttons
        self.select_all_btn = QPushButton("☑️ 全选")
        self.select_all_btn.clicked.connect(self._on_select_all)
        layout.addWidget(self.select_all_btn)

        self.deselect_btn = QPushButton("☐ 取消")
        self.deselect_btn.clicked.connect(self._on_deselect_all)
        layout.addWidget(self.deselect_btn)

        # Delete button
        self.delete_btn = QPushButton("🗑️ 删除选中")
        self.delete_btn.setStyleSheet("background-color: #ffcccc;")
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        layout.addWidget(self.delete_btn)

        # Stats label
        self.stats_label = QLabel("总计: 0 张 | 已选: 0 张 | 锁定: 0 张")
        layout.addWidget(self.stats_label)

        return layout

    def _create_filter_panel(self) -> QWidget:
        """Create filter panel."""
        group = QGroupBox("筛选条件")
        layout = QHBoxLayout(group)

        # Quality threshold
        layout.addWidget(QLabel("质量 <"))
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(0, 100)
        self.quality_spin.setValue(40)
        self.quality_spin.setSuffix(" 分")
        self.quality_spin.valueChanged.connect(self._on_filter_changed)
        layout.addWidget(self.quality_spin)

        # Species filter
        layout.addWidget(QLabel("  鸟种:"))
        self.species_edit = QLineEdit()
        self.species_edit.setPlaceholderText("输入鸟种筛选...")
        self.species_edit.textChanged.connect(self._on_filter_changed)
        layout.addWidget(self.species_edit)

        # Quick filters
        self.filter_duplicates_btn = QPushButton("筛选重复")
        self.filter_duplicates_btn.clicked.connect(self._on_filter_duplicates)
        layout.addWidget(self.filter_duplicates_btn)

        self.filter_low_btn = QPushButton("筛选低质量")
        self.filter_low_btn.clicked.connect(self._on_filter_low_quality)
        layout.addWidget(self.filter_low_btn)

        layout.addStretch()

        return group

    def _init_menu(self):
        """Initialize menu bar."""
        menubar = self.menuBar()

        # File menu
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
        """Load directory and process photos."""
        dir_path = Path(path)
        if not dir_path.exists() or not dir_path.is_dir():
            QMessageBox.warning(self, "错误", "请选择有效的目录")
            return

        self.current_directory = dir_path
        self.setWindowTitle(f"🐦 照片筛选工具 - {dir_path}")

        # Show progress
        progress = QProgressDialog("正在扫描和处理照片...", "取消", 0, 100, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()

        try:
            # Scan photos
            progress.setValue(10)
            QApplication.processEvents()

            scanner = ImageScanner()
            photos = scanner.scan(dir_path)

            progress.setValue(30)
            QApplication.processEvents()

            if not photos:
                QMessageBox.information(self, "提示", "目录中没有找到图片")
                progress.close()
                return

            # Process photos
            config = Config()
            engine = ProcessingEngine(config)

            progress.setValue(50)
            QApplication.processEvents()

            result = engine.process(dir_path)

            progress.setValue(80)
            QApplication.processEvents()

            # Convert to PhotoItem
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

            progress.setValue(100)
            progress.close()

            self._update_status()
            self.statusBar().showMessage(f"已加载 {len(photo_items)} 张照片")

        except Exception as e:
            progress.close()
            QMessageBox.critical(self, "错误", f"处理失败: {e}")

    def _update_status(self):
        """Update status bar."""
        total = len(self.model.photos)
        selected = self.model.get_selected_count()
        locked = self.model.get_locked_count()
        self.stats_label.setText(f"总计: {total} 张 | 已选: {selected} 张 | 锁定: {locked}")

    # Event handlers
    def _on_scan_clicked(self):
        """Handle scan button click."""
        dir_path = QFileDialog.getExistingDirectory(self, "选择照片目录")
        if dir_path:
            self.load_directory(dir_path)

    def _on_refresh_clicked(self):
        """Handle refresh button click."""
        if self.current_directory:
            self.load_directory(str(self.current_directory))

    def _on_select_all(self):
        """Handle select all button."""
        self.model.select_all()
        self.table.populate(self.model)
        self._update_status()

    def _on_deselect_all(self):
        """Handle deselect all button."""
        self.model.deselect_all()
        self.table.populate(self.model)
        self._update_status()

    def _on_delete_clicked(self):
        """Handle delete button click."""
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
                    QMessageBox.warning(self, "警告", f"删除失败: {photo.filename}\n{e}")

            self.table.populate(self.model)
            self._update_status()
            self.statusBar().showMessage(f"已删除 {deleted} 张照片")

    def _on_table_item_clicked(self, item):
        """Handle table item click."""
        row = item.row()
        photo = self.model.get_photo(row)
        if photo:
            self.preview.show_photo(photo)

    def _on_selection_changed(self):
        """Handle selection changed."""
        selected_rows = self.table.selectionModel().selectedRows()
        if selected_rows:
            row = selected_rows[0].row()
            photo = self.model.get_photo(row)
            if photo:
                self.preview.show_photo(photo)

    def _on_filter_changed(self):
        """Handle filter change."""
        threshold = self.quality_spin.value()
        species = self.species_edit.text()

        # This is a simple filter - in a full implementation,
        # you would filter the table based on these criteria
        pass

    def _on_filter_duplicates(self):
        """Filter to show only duplicates."""
        for i, photo in enumerate(self.model.photos):
            if photo.is_duplicate and not photo.locked:
                self.table.selectRow(i)

    def _on_filter_low_quality(self):
        """Filter to show only low quality."""
        for i, photo in enumerate(self.model.photos):
            if photo.quality_level == "low" and not photo.locked:
                self.table.selectRow(i)


def run_gui(initial_path: Optional[str] = None):
    """Run the GUI application."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = MainWindow(initial_path)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    run_gui()
