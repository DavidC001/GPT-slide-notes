import sys
import os
import shutil
from tempfile import mkdtemp
import re

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QListWidget, QListWidgetItem,
    QPushButton, QFileDialog, QHBoxLayout, QVBoxLayout, QMessageBox,
    QProgressBar, QLabel, QStyle, QSizePolicy, QSpacerItem, QLineEdit
)
from PyQt5.QtGui import QIcon, QFont, QPixmap, QColor, QPalette
from PyQt5.QtCore import QSize, Qt, QThread, pyqtSignal

import PyPDF2
from pdf2image import convert_from_path

class PDFLoaderThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(list, PyPDF2.PdfReader, object)
    error = pyqtSignal(str)

    def __init__(self, pdf_path, temp_dir):
        super().__init__()
        self.pdf_path = pdf_path
        self.temp_dir = temp_dir

    def run(self):
        try:
            file = open(self.pdf_path, 'rb')
            pdf_reader = PyPDF2.PdfReader(file)
            num_pages = len(pdf_reader.pages)

            # Convert PDF pages to images one by one
            page_images = []
            for i in range(num_pages):
                images = convert_from_path(
                    self.pdf_path, first_page=i+1, last_page=i+1, dpi=100
                )
                image = images[0]
                image_path = os.path.join(self.temp_dir, f"temp_page_{i}.png")
                image.save(image_path, 'PNG')
                page_images.append((i, image_path))

                # Emit progress
                self.progress.emit(int((i + 1) / num_pages * 100))

            self.finished.emit(page_images, pdf_reader, file)

        except Exception as e:
            self.error.emit(str(e))

class PDFSaverThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, save_path, pdf_reader, selected_pages):
        super().__init__()
        self.save_path = save_path
        self.pdf_reader = pdf_reader
        self.selected_pages = selected_pages

    def run(self):
        try:
            writer = PyPDF2.PdfWriter()
            num_pages = len(self.selected_pages)
            for i, page_index in enumerate(self.selected_pages):
                writer.add_page(self.pdf_reader.pages[page_index])
                self.progress.emit(int((i + 1) / num_pages * 100))

            with open(self.save_path, 'wb') as f:
                writer.write(f)

            self.finished.emit()

        except Exception as e:
            self.error.emit(str(e))

class PDFPageSelector(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF Page Selector")
        self.setMinimumSize(1200, 800)

        self.pdf_path = None
        self.pdf_file = None
        self.pdf_reader = None
        self.page_images = []
        self.current_pages = []
        self.temp_dir = mkdtemp()
        self.selected_pages = []  # Keep track of selected pages

        # Initialize thumbnail size
        self.thumbnail_size = QSize(200, 260)
        self.min_thumbnail_size = QSize(100, 130)
        self.max_thumbnail_size = QSize(400, 520)
        self.zoom_step = 20  # Pixels to increase/decrease

        self.initUI()

    def initUI(self):
        # Apply StyleSheet for a modern look
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
            }
            QPushButton {
                background-color: #3c3f41;
                color: #ffffff;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #505354;
            }
            QPushButton:pressed {
                background-color: #686a6c;
            }
            QListWidget {
                background-color: #3c3f41;
                border: 1px solid #5c5c5c;
            }
            QListWidget::item {
                border: 1px solid #5c5c5c;
                margin: 5px;
                padding: 5px;
                border-radius: 5px;
            }
            QListWidget::item:selected {
                background-color: #007acc;
                color: #ffffff;
            }
            QProgressBar {
                border: 1px solid #5c5c5c;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #007acc;
                width: 20px;
            }
            QLabel {
                color: #ffffff;
                font-size: 14px;
            }
            QLineEdit {
                padding: 5px;
                border: 1px solid #5c5c5c;
                border-radius: 5px;
                background-color: #3c3f41;
                color: #ffffff;
            }
            QLineEdit::placeholder {
                color: #888888;
            }
        """)

        # Main widget
        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        # Layouts
        main_layout = QVBoxLayout()
        top_layout = QHBoxLayout()
        middle_layout = QHBoxLayout()
        button_layout = QHBoxLayout()
        status_layout = QHBoxLayout()

        # Spacer to push buttons to the left
        spacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        # Buttons with icons
        open_icon = self.style().standardIcon(QStyle.SP_DialogOpenButton)
        save_icon = self.style().standardIcon(QStyle.SP_DialogSaveButton)
        delete_icon = self.style().standardIcon(QStyle.SP_TrashIcon)
        zoom_in_icon = self.style().standardIcon(QStyle.SP_ArrowUp)
        zoom_out_icon = self.style().standardIcon(QStyle.SP_ArrowDown)
        preview_icon = self.style().standardIcon(QStyle.SP_FileDialogDetailedView)
        reset_preview_icon = self.style().standardIcon(QStyle.SP_BrowserReload)

        # Initialize buttons as instance variables for easier management
        self.open_button = QPushButton("Open PDF")
        self.open_button.setIcon(open_icon)
        self.open_button.setIconSize(QSize(24, 24))
        self.open_button.clicked.connect(self.open_pdf)
        self.open_button.setToolTip("Open a PDF file")

        self.save_button = QPushButton("Save Selected Pages")
        self.save_button.setIcon(save_icon)
        self.save_button.setIconSize(QSize(24, 24))
        self.save_button.clicked.connect(self.save_pdf)
        self.save_button.setToolTip("Save the selected pages as a new PDF")

        self.delete_button = QPushButton("Delete Selected Pages")
        self.delete_button.setIcon(delete_icon)
        self.delete_button.setIconSize(QSize(24, 24))
        self.delete_button.clicked.connect(self.delete_selected_pages)
        self.delete_button.setToolTip("Delete the selected pages from the selection")

        self.zoom_in_button = QPushButton("Zoom In")
        self.zoom_in_button.setIcon(zoom_in_icon)
        self.zoom_in_button.setIconSize(QSize(24, 24))
        self.zoom_in_button.clicked.connect(self.zoom_in)
        self.zoom_in_button.setToolTip("Increase thumbnail size")

        self.zoom_out_button = QPushButton("Zoom Out")
        self.zoom_out_button.setIcon(zoom_out_icon)
        self.zoom_out_button.setIconSize(QSize(24, 24))
        self.zoom_out_button.clicked.connect(self.zoom_out)
        self.zoom_out_button.setToolTip("Decrease thumbnail size")

        # Add buttons to top layout
        top_layout.addWidget(self.open_button)
        top_layout.addWidget(self.save_button)
        top_layout.addWidget(self.delete_button)
        top_layout.addWidget(self.zoom_in_button)
        top_layout.addWidget(self.zoom_out_button)
        top_layout.addSpacerItem(spacer)

        # Page Range Input
        self.page_range_input = QLineEdit()
        self.page_range_input.setPlaceholderText("Enter page ranges (e.g., 1-3,5,7)")
        self.page_range_input.setFixedWidth(300)
        self.page_range_input.returnPressed.connect(self.select_pages_from_input)  # Trigger page selection on Enter

        # Select Pages Button
        self.select_button = QPushButton("Select Pages")
        self.select_button.setIcon(preview_icon)
        self.select_button.setIconSize(QSize(24, 24))
        self.select_button.clicked.connect(self.select_pages_from_input)
        self.select_button.setToolTip("Select the specified page ranges")

        # Show Only Selected Pages Button
        self.show_selected_button = QPushButton("Show Only Selected Pages")
        self.show_selected_button.setIcon(reset_preview_icon)
        self.show_selected_button.setIconSize(QSize(24, 24))
        self.show_selected_button.clicked.connect(self.show_only_selected_pages)
        self.show_selected_button.setToolTip("Show only the selected page previews")

        # Show All Pages Button
        self.reset_preview_button = QPushButton("Show All Pages")
        self.reset_preview_button.setIcon(reset_preview_icon)
        self.reset_preview_button.setIconSize(QSize(24, 24))
        self.reset_preview_button.clicked.connect(self.show_all_pages)
        self.reset_preview_button.setToolTip("Show all page previews")

        # Add page range input and selection buttons to middle layout
        middle_layout.addWidget(QLabel("Page Range:"))
        middle_layout.addWidget(self.page_range_input)
        middle_layout.addWidget(self.select_button)
        middle_layout.addWidget(self.show_selected_button)
        middle_layout.addWidget(self.reset_preview_button)
        middle_layout.addSpacerItem(spacer)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(20)

        # Status Label
        self.status_label = QLabel()
        self.status_label.setVisible(False)

        # Add progress bar and status label to status layout
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.progress_bar)

        # List widget to display pages
        self.page_list_widget = QListWidget()
        # Set selection mode to ExtendedSelection to enable shift-click selection
        self.page_list_widget.setSelectionMode(QListWidget.ExtendedSelection)
        self.page_list_widget.itemDoubleClicked.connect(self.select_only_this_page)
        self.page_list_widget.setSpacing(10)
        self.page_list_widget.setResizeMode(QListWidget.Adjust)
        self.page_list_widget.setViewMode(QListWidget.IconMode)
        self.page_list_widget.setIconSize(self.thumbnail_size)  # Initial thumbnail size
        self.page_list_widget.setMovement(QListWidget.Static)
        self.page_list_widget.setUniformItemSizes(True)
        self.page_list_widget.setWordWrap(True)
        self.page_list_widget.setStyleSheet("""
            QListWidget::item:hover {
                background-color: #505354;
            }
        """)

        # Assemble main layout
        main_layout.addLayout(top_layout)
        main_layout.addLayout(middle_layout)
        main_layout.addWidget(self.page_list_widget)
        main_layout.addLayout(status_layout)

        # Set main layout
        main_widget.setLayout(main_layout)

    def open_pdf(self):
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly
        pdf_path, _ = QFileDialog.getOpenFileName(
            self, "Open PDF File", "", "PDF Files (*.pdf)", options=options
        )
        if pdf_path:
            self.pdf_path = pdf_path
            self.load_pdf()

    def load_pdf(self):
        # close old file if open
        if self.pdf_file:
            self.pdf_file.close()

        # Clear previous data
        self.page_list_widget.clear()
        self.page_images = []
        self.current_pages = []
        self.selected_pages = []

        # Clean up previous temp images
        shutil.rmtree(self.temp_dir)
        self.temp_dir = mkdtemp()

        # Show progress bar and status
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Loading PDF...")
        self.status_label.setVisible(True)

        # Disable buttons during loading
        self.set_all_buttons_enabled(False)

        # Start loader thread
        self.loader_thread = PDFLoaderThread(self.pdf_path, self.temp_dir)
        self.loader_thread.progress.connect(self.progress_bar.setValue)
        self.loader_thread.finished.connect(self.load_pdf_finished)
        self.loader_thread.error.connect(self.load_pdf_error)
        self.loader_thread.start()

    def load_pdf_finished(self, page_images, pdf_reader, pdf_file):
        self.pdf_file = pdf_file
        self.pdf_reader = pdf_reader
        self.page_images = page_images
        for i, image_path in page_images:
            # Create QListWidgetItem with the image
            item = QListWidgetItem(f"Page {i+1}")
            icon = QIcon(image_path)
            item.setIcon(icon)
            item.setTextAlignment(Qt.AlignCenter)
            self.page_list_widget.addItem(item)
            self.current_pages.append(i)

        # Restore previous selections
        for page_index in self.selected_pages:
            item = self.page_list_widget.item(page_index)
            if item:
                item.setSelected(True)

        # Hide progress bar and status
        self.progress_bar.setVisible(False)
        self.status_label.setVisible(False)

        # Re-enable buttons
        self.set_all_buttons_enabled(True)

    def load_pdf_error(self, error_message):
        # Hide progress bar and status
        self.progress_bar.setVisible(False)
        self.status_label.setVisible(False)
        QMessageBox.critical(self, "Error", f"Failed to load PDF: {error_message}")

        # Re-enable buttons
        self.set_all_buttons_enabled(True)

    def delete_selected_pages(self):
        selected_items = self.page_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select pages to delete.")
            return

        selected_rows = sorted(
            [self.page_list_widget.row(item) for item in selected_items],
            reverse=True
        )
        for row in selected_rows:
            self.page_list_widget.takeItem(row)
            del self.current_pages[row]
            self.selected_pages = [p for p in self.selected_pages if p != row]

        QMessageBox.information(
            self, "Deleted", "Selected pages have been deleted from selection."
        )

    def save_pdf(self):
        if not self.current_pages:
            QMessageBox.warning(self, "No Pages", "No pages to save.")
            return

        options = QFileDialog.Options()
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF", "", "PDF Files (*.pdf)", options=options
        )
        if save_path:
            # Show progress bar and status
            self.progress_bar.setValue(0)
            self.progress_bar.setVisible(True)
            self.status_label.setText("Saving PDF...")
            self.status_label.setVisible(True)

            # Disable buttons during saving
            self.set_all_buttons_enabled(False)

            # Start saver thread
            self.saver_thread = PDFSaverThread(save_path, self.pdf_reader, self.selected_pages)
            self.saver_thread.progress.connect(self.progress_bar.setValue)
            self.saver_thread.finished.connect(self.save_pdf_finished)
            self.saver_thread.error.connect(self.save_pdf_error)
            self.saver_thread.start()

    def save_pdf_finished(self):
        # Hide progress bar and status
        self.progress_bar.setVisible(False)
        self.status_label.setVisible(False)
        QMessageBox.information(self, "Success", "PDF saved successfully.")

        # Re-enable buttons
        self.set_all_buttons_enabled(True)

    def save_pdf_error(self, error_message):
        # Hide progress bar and status
        self.progress_bar.setVisible(False)
        self.status_label.setVisible(False)
        QMessageBox.critical(self, "Error", f"Failed to save PDF: {error_message}")

        # Re-enable buttons
        self.set_all_buttons_enabled(True)

    def select_only_this_page(self, item):
        self.page_list_widget.clearSelection()
        item.setSelected(True)
        self.update_selected_pages()

    def zoom_in(self):
        if self.thumbnail_size.width() + self.zoom_step <= self.max_thumbnail_size.width() and \
           self.thumbnail_size.height() + self.zoom_step <= self.max_thumbnail_size.height():
            self.thumbnail_size = QSize(
                self.thumbnail_size.width() + self.zoom_step,
                self.thumbnail_size.height() + self.zoom_step
            )
            self.page_list_widget.setIconSize(self.thumbnail_size)
            self.update_zoom_buttons()

    def zoom_out(self):
        if self.thumbnail_size.width() - self.zoom_step >= self.min_thumbnail_size.width() and \
           self.thumbnail_size.height() - self.zoom_step >= self.min_thumbnail_size.height():
            self.thumbnail_size = QSize(
                self.thumbnail_size.width() - self.zoom_step,
                self.thumbnail_size.height() - self.zoom_step
            )
            self.page_list_widget.setIconSize(self.thumbnail_size)
            self.update_zoom_buttons()

    def update_zoom_buttons(self):
        # Enable or disable zoom buttons based on current thumbnail size
        if self.thumbnail_size.width() >= self.max_thumbnail_size.width() or \
           self.thumbnail_size.height() >= self.max_thumbnail_size.height():
            self.zoom_in_button.setEnabled(False)
        else:
            self.zoom_in_button.setEnabled(True)

        if self.thumbnail_size.width() <= self.min_thumbnail_size.width() or \
           self.thumbnail_size.height() <= self.min_thumbnail_size.height():
            self.zoom_out_button.setEnabled(False)
        else:
            self.zoom_out_button.setEnabled(True)

    def set_all_buttons_enabled(self, enabled):
        # Enable or disable all main buttons except Zoom
        self.open_button.setEnabled(enabled)
        self.save_button.setEnabled(enabled)
        self.delete_button.setEnabled(enabled)
        self.select_button.setEnabled(enabled)
        self.show_selected_button.setEnabled(enabled)
        self.reset_preview_button.setEnabled(enabled)
        self.zoom_in_button.setEnabled(enabled and self.thumbnail_size.width() < self.max_thumbnail_size.width())
        self.zoom_out_button.setEnabled(enabled and self.thumbnail_size.width() > self.min_thumbnail_size.width())

    def select_pages_from_input(self):
        page_range_text = self.page_range_input.text().strip()
        if not page_range_text:
            QMessageBox.warning(self, "Input Required", "Please enter page ranges to select.")
            return

        # Parse page ranges
        try:
            selected_pages = self.parse_page_ranges(page_range_text)
        except ValueError as ve:
            QMessageBox.critical(self, "Invalid Input", str(ve))
            return

        if not selected_pages:
            QMessageBox.warning(self, "No Pages", "No valid pages found in the input range.")
            return

        # Check if selected pages are within the document
        total_pages = len(self.pdf_reader.pages)
        for page in selected_pages:
            if page < 0 or page >= total_pages:
                QMessageBox.critical(self, "Invalid Page Number", f"Page {page + 1} is out of range.")
                return

        # Select the pages in the QListWidget
        for page_index in selected_pages:
            if page_index not in self.selected_pages:
                self.selected_pages.append(page_index)
                item = self.page_list_widget.item(page_index)
                if item:
                    item.setSelected(True)

        self.selected_pages = sorted(self.selected_pages)
        QMessageBox.information(self, "Pages Selected", f"Pages {page_range_text} have been selected.")

    def show_only_selected_pages(self):
        # Update selected pages from the current selection
        self.update_selected_pages()

        if not self.selected_pages:
            QMessageBox.warning(self, "No Selection", "Please select pages to show.")
            return

        self.page_list_widget.clear()
        for page_index in self.selected_pages:
            image_path = self.page_images[page_index][1]
            item = QListWidgetItem(f"Page {page_index + 1}")
            icon = QIcon(image_path)
            item.setIcon(icon)
            item.setTextAlignment(Qt.AlignCenter)
            self.page_list_widget.addItem(item)

        QMessageBox.information(self, "Show Selected Pages", f"Showing {len(self.selected_pages)} selected pages.")

    def show_all_pages(self):
        if not self.page_images:
            return

        self.page_list_widget.clear()
        for i, image_path in self.page_images:
            item = QListWidgetItem(f"Page {i + 1}")
            icon = QIcon(image_path)
            item.setIcon(icon)
            item.setTextAlignment(Qt.AlignCenter)
            self.page_list_widget.addItem(item)

        # Restore previous selections
        for page_index in self.selected_pages:
            item = self.page_list_widget.item(page_index)
            if item:
                item.setSelected(True)

        QMessageBox.information(self, "Preview Reset", "All pages are now being displayed.")

    def update_selected_pages(self):
        # Update the selected_pages list based on the current selection in the QListWidget
        self.selected_pages = sorted([self.page_list_widget.row(item) for item in self.page_list_widget.selectedItems()])

    def parse_page_ranges(self, input_str):
        """
        Parses a string containing page ranges and returns a list of page indices.
        Example input: "1-3,5,7"
        Returns: [0,1,2,4,6]
        """
        page_indices = []
        # Split the input by commas
        parts = input_str.split(',')
        for part in parts:
            part = part.strip()
            if '-' in part:
                # It's a range
                range_match = re.match(r'^(\d+)-(\d+)$', part)
                if not range_match:
                    raise ValueError(f"Invalid range format: '{part}'. Use 'start-end' format.")
                start_str, end_str = range_match.groups()
                start = int(start_str) - 1
                end = int(end_str) - 1
                if start > end:
                    raise ValueError(f"Invalid range: {part}. Start page is greater than end page.")
                page_indices.extend(range(start, end + 1))
            else:
                # It's a single page
                if not part.isdigit():
                    raise ValueError(f"Invalid page number: '{part}'. Must be an integer.")
                page = int(part) - 1
                page_indices.append(page)
        # Remove duplicates and sort
        page_indices = sorted(list(set(page_indices)))
        return page_indices

    def closeEvent(self, event):
        try:
            # Clean up temporary directory
            shutil.rmtree(self.temp_dir)
        except Exception as e:
            print(f"Error while cleaning up temporary files: {e}")
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Optional: Set a Fusion style for better aesthetics
    app.setStyle("Fusion")

    # Optional: Customize the palette for the Fusion style
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(43, 43, 43))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor(60, 63, 65))
    palette.setColor(QPalette.AlternateBase, QColor(43, 43, 43))
    palette.setColor(QPalette.ToolTipBase, Qt.white)
    palette.setColor(QPalette.ToolTipText, Qt.white)
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor(60, 63, 65))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)

    window = PDFPageSelector()
    window.show()
    sys.exit(app.exec_())