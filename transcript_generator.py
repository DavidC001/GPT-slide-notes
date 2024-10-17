import os
import base64
import requests
from pdf2image import convert_from_path
import PyPDF2
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, QFileDialog, QVBoxLayout,
    QLabel, QProgressBar, QLineEdit, QHBoxLayout, QComboBox, QMessageBox, QCheckBox,
    QSpacerItem, QSizePolicy
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPalette, QColor
from dotenv import load_dotenv
import sys

# Load environment variables from .env file or selected file
load_dotenv()

# Configuration
API_KEY = os.getenv("API_KEY", "")
API_ENDPOINT = os.getenv("API_ENDPOINT", "https://api.openai.com/v1/chat/completions")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
CONTEXT = 3  # Number of previous transcripts to include as context

IMAGE_DIR = "slide_images"  # Directory to save extracted images
SETTINGS_FILE = "settings.txt"  # File to save/load settings

# Ensure the image directory exists
os.makedirs(IMAGE_DIR, exist_ok=True)

# Function to encode an image to base64
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# Function to generate transcript for a single slide
def generate_transcript(slide_text, previous_transcripts=[], api_key=API_KEY, api_endpoint=API_ENDPOINT, model_name=MODEL_NAME):
    # Prepare the few-shot example
    few_shot_prompt = """
### Concepts Representation (1)

A concept can be represented in multiple ways. Primarily, a concept is shaped by a **word** or a combination of terms. Examples include "car," "person," or "electric engine." These words serve as the basic building blocks of the concept.

Additionally, a concept is defined by a **gloss**—a textual description that provides clarification and examples to ensure proper interpretation. The gloss helps disambiguate the meaning of the concept and offers context.

Concepts are also linked semantically to other concepts. This is done through two main relationships:
- **Hyponymy**, where a concept is related to a more generic term (e.g., "woman" is a more general concept than "daughter").
- **Hypernymy**, where a concept is related to a more specific term (e.g., "artificial lake" is a more specific concept than "lake"). 

These relationships help form a structured network of concepts that enable deeper understanding and categorization of information.

---
    """

    # Include previous transcripts as context if available
    context_text = ""
    if previous_transcripts:
        context_text = "Here are the transcripts from some of the previous slides to use as additional context:\n" + "\n\n---\n".join(previous_transcripts)

    # Complete prompt with few-shot example, extracted text, and context
    prompt = f"""{few_shot_prompt}

Here is the partially extracted text from the slide:

{slide_text}

{context_text}

Please generate the notes for the slide above. You should follow the following structure, with the slide title, followed by its content rewritten to be readable and explain everything, including the graphical elements if useful to do so, finishing with "---".

IMPORTANT: you should only respond with the provided format, do not add any additional information, directly output the requested content.
"""

    # Prepare the payload
    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": 1000,
        "temperature": 0.3,
        "stop": ["---"]
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    # Send the request to the OpenAI API
    response = requests.post(api_endpoint, headers=headers, json=payload)

    if response.status_code == 200:
        response_data = response.json()
        transcript = response_data['choices'][0]['message']['content'].strip()
        # Remove everything before "###" if needed
        if "###" in transcript:
            transcript = transcript[transcript.find("###"):]
        return transcript
    else:
        return None

# Function to extract text from PDF
def extract_text_from_pdf(pdf_path):
    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        slide_texts = [page.extract_text() if page.extract_text() else "" for page in pdf_reader.pages]
    return slide_texts

# Worker thread to process the PDF
class PDFProcessorThread(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, pdf_path, api_key, api_endpoint, model_name, save_to_clipboard, save_path):
        super().__init__()
        self.pdf_path = pdf_path
        self.api_key = api_key
        self.api_endpoint = api_endpoint
        self.model_name = model_name
        self.save_to_clipboard = save_to_clipboard
        self.save_path = save_path

    def run(self):
        try:
            pages = convert_from_path(self.pdf_path)
            slide_texts = extract_text_from_pdf(self.pdf_path)
            transcripts = []

            for i, (page, slide_text) in enumerate(zip(pages, slide_texts)):
                image_path = os.path.join(IMAGE_DIR, f'slide_{i + 1}.jpg')
                page.save(image_path, 'JPEG')

                self.status.emit(f"Generating transcript for Slide {i + 1}...")
                context_slides = transcripts[-CONTEXT:]
                transcript = generate_transcript(slide_text, context_slides, self.api_key, self.api_endpoint, self.model_name)

                if transcript:
                    transcripts.append(transcript)
                    self.status.emit(f"Transcript for Slide {i + 1} generated successfully.")
                else:
                    self.status.emit(f"Failed to generate transcript for Slide {i + 1}.")

                self.progress.emit(int((i + 1) / len(pages) * 100))

            final_transcript = "\n\n---\n".join(transcripts)

            if self.save_to_clipboard:
                clipboard = QApplication.instance().clipboard()
                clipboard.setText(final_transcript)
                self.finished.emit("All transcripts have been generated and copied to clipboard.")
            else:
                with open(self.save_path, 'w', encoding='utf-8') as f:
                    f.write(final_transcript)
                self.finished.emit("All transcripts have been generated and saved.")
        except Exception as e:
            self.error.emit(str(e))

# GUI Setup
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
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
            QProgressBar {
                border: 1px solid #5c5c5c;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #007acc;
                width: 20px;
            }
            QComboBox {
                background-color: #3c3f41;
                color: #ffffff;
                border: 1px solid #5c5c5c;
                border-radius: 5px;
            }
            QCheckBox {
                color: #ffffff;
            }
        """)

        # Set window title and geometry
        self.setWindowTitle("PDF to Transcript Generator")
        self.setGeometry(100, 100, 800, 600)

        # Main widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # Load settings from file
        api_key = API_KEY
        api_endpoint = API_ENDPOINT
        model_name = MODEL_NAME

        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as f:
                settings = f.read().splitlines()
                if len(settings) >= 3:
                    api_key = settings[0]
                    api_endpoint = settings[1]
                    model_name = settings[2]

        # PDF File Selection
        top_layout = QHBoxLayout()
        pdf_label = QLabel("Select PDF File:")
        top_layout.addWidget(pdf_label)

        self.pdf_path_edit = QLineEdit()
        top_layout.addWidget(self.pdf_path_edit)

        self.browse_button = QPushButton("Browse")
        top_layout.addWidget(self.browse_button)

        self.browse_button.clicked.connect(self.select_pdf)

        main_layout.addLayout(top_layout)

        # API Key Input
        api_key_label = QLabel("API Key:")
        main_layout.addWidget(api_key_label)

        self.api_key_edit = QLineEdit(api_key)
        main_layout.addWidget(self.api_key_edit)

        # Model Selection
        model_label = QLabel("Model:")
        main_layout.addWidget(model_label)

        self.model_combo = QComboBox()
        self.model_combo.addItems(["gpt-4o", "gpt-4", "gpt-4o-mini", "custom"])
        self.model_combo.setCurrentText(model_name)
        main_layout.addWidget(self.model_combo)

        # Custom API Settings
        self.custom_settings_widget = QWidget()
        custom_settings_layout = QVBoxLayout()
        self.custom_settings_widget.setLayout(custom_settings_layout)

        api_endpoint_label = QLabel("API Endpoint:")
        custom_settings_layout.addWidget(api_endpoint_label)

        self.api_endpoint_edit = QLineEdit(api_endpoint)
        custom_settings_layout.addWidget(self.api_endpoint_edit)

        custom_model_label = QLabel("Model Name:")
        custom_settings_layout.addWidget(custom_model_label)

        self.custom_model_edit = QLineEdit()
        custom_settings_layout.addWidget(self.custom_model_edit)

        main_layout.addWidget(self.custom_settings_widget)
        self.custom_settings_widget.setVisible(self.model_combo.currentText() == "custom")

        self.model_combo.currentTextChanged.connect(self.model_changed)

        # Save Options
        self.save_to_clipboard_checkbox = QCheckBox("Save to Clipboard")
        main_layout.addWidget(self.save_to_clipboard_checkbox)

        save_path_layout = QHBoxLayout()
        self.save_path_edit = QLineEdit()
        self.save_path_edit.setPlaceholderText("Save Path for Transcript (if not using clipboard)")
        save_path_layout.addWidget(self.save_path_edit)

        self.save_browse_button = QPushButton("Browse Save Path")
        save_path_layout.addWidget(self.save_browse_button)
        main_layout.addLayout(save_path_layout)

        self.save_browse_button.clicked.connect(self.select_save_path)

        self.save_to_clipboard_checkbox.stateChanged.connect(self.toggle_save_options)
        self.toggle_save_options()

        # Start Button
        self.start_button = QPushButton("Start")
        main_layout.addWidget(self.start_button)

        # Progress Bar and Status Label
        self.progress_bar = QProgressBar()
        main_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Status: Waiting for user input.")
        main_layout.addWidget(self.status_label)

        self.start_button.clicked.connect(self.start_processing)

    def select_pdf(self):
        pdf_path, _ = QFileDialog.getOpenFileName(self, "Select PDF File", "", "PDF files (*.pdf)")
        if pdf_path:
            self.pdf_path_edit.setText(pdf_path)

    def select_save_path(self):
        save_path, _ = QFileDialog.getSaveFileName(self, "Save Transcript As", "", "Text Files (*.txt)")
        if save_path:
            self.save_path_edit.setText(save_path)

    def model_changed(self):
        if self.model_combo.currentText() == "custom":
            self.custom_settings_widget.setVisible(True)
        else:
            self.custom_settings_widget.setVisible(False)

    def toggle_save_options(self):
        if self.save_to_clipboard_checkbox.isChecked():
            self.save_path_edit.setVisible(False)
            self.save_browse_button.setVisible(False)
        else:
            self.save_path_edit.setVisible(True)
            self.save_browse_button.setVisible(True)

    def start_processing(self):
        pdf_path = self.pdf_path_edit.text()
        if not pdf_path:
            QMessageBox.warning(self, "Input Error", "Please select a PDF file.")
            return

        selected_model = self.model_combo.currentText()
        if selected_model == "custom":
            model_name_to_use = self.custom_model_edit.text()
            endpoint_to_use = self.api_endpoint_edit.text()
        else:
            model_name_to_use = selected_model
            endpoint_to_use = API_ENDPOINT

        save_to_clipboard = self.save_to_clipboard_checkbox.isChecked()
        save_path = self.save_path_edit.text() if not save_to_clipboard else None

        if not save_to_clipboard and not save_path:
            QMessageBox.warning(self, "Input Error", "Please specify a save path or select save to clipboard.")
            return

        # Save current settings to file
        with open(SETTINGS_FILE, 'w') as f:
            f.write(f"{self.api_key_edit.text()}\n")
            f.write(f"{endpoint_to_use}\n")
            f.write(f"{model_name_to_use}\n")

        # Disable inputs during processing
        self.set_all_inputs_enabled(False)

        self.processor_thread = PDFProcessorThread(
            pdf_path, self.api_key_edit.text(), endpoint_to_use,
            model_name_to_use, save_to_clipboard, save_path)
        self.processor_thread.progress.connect(self.progress_bar.setValue)
        self.processor_thread.status.connect(self.status_label.setText)
        self.processor_thread.finished.connect(self.processing_finished)
        self.processor_thread.error.connect(self.processing_error)
        self.processor_thread.start()

    def processing_finished(self, message):
        self.status_label.setText(message)
        QMessageBox.information(self, "Processing Finished", message)
        # Re-enable inputs
        self.set_all_inputs_enabled(True)

    def processing_error(self, error_message):
        QMessageBox.critical(self, "Error", error_message)
        # Re-enable inputs
        self.set_all_inputs_enabled(True)

    def set_all_inputs_enabled(self, enabled):
        self.pdf_path_edit.setEnabled(enabled)
        self.browse_button.setEnabled(enabled)
        self.api_key_edit.setEnabled(enabled)
        self.model_combo.setEnabled(enabled)
        self.custom_settings_widget.setEnabled(enabled)
        self.save_to_clipboard_checkbox.setEnabled(enabled)
        self.save_path_edit.setEnabled(enabled)
        self.save_browse_button.setEnabled(enabled)
        self.start_button.setEnabled(enabled)

def main():
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

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
