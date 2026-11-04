import sys
import os
import threading
import speech_recognition as sr
from pydub import AudioSegment
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QPushButton, QLabel, QFileDialog,
    QTextEdit, QComboBox, QProgressBar, QMessageBox, QGroupBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QIcon

class AudioConverterWorker(QThread):
    """Worker thread for audio conversion to prevent UI freezing"""
    progress_signal = pyqtSignal(int, str) # (percentage, message)
    result_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, audio_file, language):
        super().__init__()
        self.audio_file = audio_file
        self.language = language
        self.recognizer = sr.Recognizer()
        self.converting = False

    def run(self):
        if self.converting:
            self.error_signal.emit("Conversion already in progress.")
            return
        
        self.converting = True
        temp_wav_file = None
        original_file = self.audio_file

        try:
            self.progress_signal.emit(10, "Initializing...")
            
            # Check if file exists
            if not os.path.exists(self.audio_file):
                raise FileNotFoundError(f"File not found: {self.audio_file}")

            # Convert to WAV if needed
            if not self.audio_file.lower().endswith('.wav'):
                self.progress_signal.emit(20, "Converting format to WAV...")
                temp_wav_file = "temp_audio_conversion.wav"
                try:
                    sound = AudioSegment.from_file(self.audio_file)
                    sound.export(temp_wav_file, format="wav")
                    self.audio_file = temp_wav_file
                except Exception as e:
                    raise Exception(f"Failed to convert audio format: {str(e)}")

            self.progress_signal.emit(40, "Analyzing audio...")

            # Process Audio
            with sr.AudioFile(self.audio_file) as source:
                self.recognizer.adjust_for_ambient_noise(source)
                self.progress_signal.emit(60, "Recording audio...")
                audio = self.recognizer.record(source)
            
            self.progress_signal.emit(80, "Recognizing speech...")
            
            # Google Recognition
            text = self.recognizer.recognize_google(audio, language=self.language)
            
            self.progress_signal.emit(100, "Done!")
            self.result_signal.emit(text)

        except sr.UnknownValueError:
            self.error_signal.emit("Sorry, I could not understand the audio.")
        except sr.RequestError as e:
            self.error_signal.emit(f"Google API error: {str(e)}")
        except FileNotFoundError as e:
            self.error_signal.emit(str(e))
        except Exception as e:
            self.error_signal.emit(f"An error occurred: {str(e)}")
        finally:
            self.converting = False
            # Cleanup temp file if we created one
            if temp_wav_file and os.path.exists(temp_wav_file):
                try:
                    os.remove(temp_wav_file)
                except:
                    pass

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.selected_file_path = None
        self.result_text = ""
        
        self.init_ui()
        self.apply_styles()

    def init_ui(self):
        self.setWindowTitle("🎤 Professional Audio to Text Converter")
        self.setGeometry(100, 100, 700, 600)
        self.setMinimumSize(600, 500)

        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Title
        title = QLabel("Audio to Text Converter")
        title.setFont(QFont('Arial', 24, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #2c3e50; margin-bottom: 10px;")
        main_layout.addWidget(title)

        # Settings Group
        settings_group = QGroupBox("Settings")
        settings_layout = QHBoxLayout()
        
        lang_label = QLabel("Language:")
        self.lang_combo = QComboBox()
        self.lang_combo.addItems([
            "en-US", "es-ES", "fr-FR", "de-DE", "it-IT",
            "pt-BR", "ru-RU", "zh-CN", "ja-JP", "ko-KR",
            "ro-RO", "ar-SA", "hi-IN", "bn-BD", "tr-TR", "pl-PL",
        
        ])
        settings_layout.addWidget(lang_label)
        settings_layout.addWidget(self.lang_combo)
        settings_group.setLayout(settings_layout)
        main_layout.addWidget(settings_group)

        # File Info
        self.file_label = QLabel("No file selected")
        self.file_label.setStyleSheet("color: #7f8c8d; font-style: italic;")
        main_layout.addWidget(self.file_label)

        # Buttons
        btn_layout = QHBoxLayout()
        
        self.select_btn = QPushButton("📁 Select Audio File")
        self.select_btn.clicked.connect(self.select_file)
        self.select_btn.setStyleSheet("background-color: #3498db; color: white; padding: 10px; border-radius: 5px;")
        
        self.convert_btn = QPushButton("🔄 Convert")
        self.convert_btn.clicked.connect(self.start_conversion)
        self.convert_btn.setStyleSheet("background-color: #27ae60; color: white; padding: 10px; border-radius: 5px; font-weight: bold;")
        
        self.copy_btn = QPushButton("📋 Copy")
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        self.copy_btn.setEnabled(False)
        
        self.save_btn = QPushButton("💾 Save")
        self.save_btn.clicked.connect(self.save_to_file)
        self.save_btn.setEnabled(False)

        btn_layout.addWidget(self.select_btn)
        btn_layout.addWidget(self.convert_btn)
        btn_layout.addWidget(self.copy_btn)
        btn_layout.addWidget(self.save_btn)
        main_layout.addLayout(btn_layout)

        # Progress Bar
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setVisible(False)
        main_layout.addWidget(self.progress)

        # Status Label
        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #34495e; font-weight: bold;")
        main_layout.addWidget(self.status_label)

        # Result Area
        result_group = QGroupBox("Transcription Result")
        result_layout = QVBoxLayout()
        
        self.result_text_edit = QTextEdit()
        self.result_text_edit.setReadOnly(True)
        self.result_text_edit.setFont(QFont('Consolas', 11))
        self.result_text_edit.setPlaceholderText("Converted text will appear here...")
        
        result_layout.addWidget(self.result_text_edit)
        result_group.setLayout(result_layout)
        main_layout.addWidget(result_group)

    def apply_styles(self):
        # Optional: Global stylesheet for nicer look
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f2f5;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ddd;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QTextEdit {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 5px;
            }
        """)

    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Audio File", "", "Audio Files (*.wav *.mp3 *.flac *.ogg *.m4a)"
        )
        if file_path:
            self.selected_file_path = file_path
            self.file_label.setText(f"Selected: {os.path.basename(file_path)}")
            self.result_text_edit.clear()
            self.copy_btn.setEnabled(False)
            self.save_btn.setEnabled(False)
            self.status_label.setText("File selected. Ready to convert.")

    def start_conversion(self):
        if not self.selected_file_path:
            QMessageBox.warning(self, "No File", "Please select an audio file first.")
            return

        language = self.lang_combo.currentText()

        # Disable buttons
        self.select_btn.setEnabled(False)
        self.convert_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.status_label.setText("Starting conversion...")

        # Start Worker Thread
        self.worker = AudioConverterWorker(self.selected_file_path, language)
        
        # Connect signals
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.result_signal.connect(self.handle_result)
        self.worker.error_signal.connect(self.handle_error)
        self.worker.finished.connect(self.on_thread_finished)

        self.worker.start()

    def update_progress(self, value, message):
        self.progress.setValue(value)
        self.status_label.setText(message)

    def handle_result(self, text):
        self.result_text = text
        self.result_text_edit.setText(text)
        self.status_label.setText("Conversion successful!")
        self.copy_btn.setEnabled(True)
        self.save_btn.setEnabled(True)

    def handle_error(self, error_msg):
        self.status_label.setText(f"Error: {error_msg}")
        self.result_text_edit.setPlaceholderText(error_msg)
        QMessageBox.critical(self, "Conversion Error", error_msg)

    def on_thread_finished(self):
        # Re-enable buttons
        self.select_btn.setEnabled(True)
        self.convert_btn.setEnabled(True)
        self.progress.setVisible(False)
        self.progress.setValue(0)

    def copy_to_clipboard(self):
        from PyQt5.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(self.result_text)
        self.status_label.setText("Copied to clipboard!")
        QMessageBox.information(self, "Success", "Text copied to clipboard.")

    def save_to_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Text File", "", "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.result_text)
                self.status_label.setText(f"Saved to: {file_path}")
                QMessageBox.information(self, "Success", f"File saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Could not save file: {str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())