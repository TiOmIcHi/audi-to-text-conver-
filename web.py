import json
import os

os.environ.setdefault("QT_API", "pyqt6")

import webview
import speech_recognition as sr
from pydub import AudioSegment
import threading
import time
from typing import cast

window = None

class AudioToTextConverter:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.converting = False
        self.status_callback = lambda _message: None

    def convert_file(self, audio_file: str, language: str = "ro-RO"):
        """Convert audio file to text. This runs in a background thread."""
        if self.converting:
            return "Error: Already converting..."
        
        self.converting = True
        temp_wav = None

        try:
            # Feedback: Start
            self.status_callback("Analyzing audio...")
            time.sleep(0.5) # Simulate slight delay for UX feel if needed, or just let it run

            # Convert to WAV if needed
            if not audio_file.lower().endswith('.wav'):
                self.status_callback("Converting format to WAV...")
                temp_wav = "temp_audio.wav"
                try:
                    sound = AudioSegment.from_file(audio_file)
                    sound.export(temp_wav, format="wav")
                    audio_file = temp_wav
                except Exception as e:
                    return f"Error converting format: {str(e)}"

            self.status_callback("Recognizing speech...")

            with sr.AudioFile(audio_file) as source:
                self.recognizer.adjust_for_ambient_noise(source)
                audio = self.recognizer.record(source)
            
            recognize_google = getattr(self.recognizer, "recognize_google")
            text = recognize_google(audio, language=language)
            return text
            
        except sr.UnknownValueError:
            return "Could not understand the audio. Please try again with clearer speech."
        except sr.RequestError as e:
            return f"Google API Error: {str(e)}"
        except FileNotFoundError:
            return "File not found."
        except Exception as e:
            return f"Unexpected Error: {str(e)}"
        finally:
            self.converting = False
            self.status_callback("Ready")
            # Cleanup temp file ONLY if we created it
            if temp_wav and os.path.exists(temp_wav):
                try:
                    os.remove(temp_wav)
                except:
                    pass

class PythonAPI:
    def __init__(self, converter):
        self.converter = converter
        self.status = "Ready"
        self.converter.status_callback = self.update_status

    def select_audio_file(self):
        if window is None:
            return None
        create_file_dialog = getattr(window, "create_file_dialog")
        paths = create_file_dialog(
            cast(int, webview.OPEN_DIALOG),
            file_types=("Audio files (*.wav;*.mp3;*.m4a;*.ogg;*.flac)", "All files (*.*)"),
        )
        return paths[0] if paths else None

    def convert_file(self, file_path, language):
        # Run conversion in a separate thread to not block the UI thread (JS)
        result_holder = {'text': ''}
        
        def run_conversion():
            result = self.converter.convert_file(file_path, language)
            result_holder['text'] = result

        thread = threading.Thread(target=run_conversion)
        thread.start()
        
        # Wait for thread to finish (since JS is async, we could use promises, 
        # but for simplicity in pywebview sync call, we block until done.
        # Note: pywebview handles this well, but for very long audio, 
        # a proper async JS API is better. Here we assume reasonable length.)
        thread.join()
        
        return result_holder['text']

    def update_status(self, message):
        self.status = message
        # Note: Direct UI update from Python thread in pywebview can be tricky.
        # For this simple example, we rely on the JS side to poll or we just set it here.
        # A better way is to call a JS function from Python.
        # For now, we will update the status in the JS via a small hack or just return it.
        # Let's stick to returning status in the result or using a simpler approach.
        # Actually, pywebview allows calling JS functions.
        if window is not None:
            window.evaluate_js(
                f"document.getElementById('status').textContent = {json.dumps(message)};"
            )

    def save_file_dialog(self, text):
        if window is None:
            return None
        create_file_dialog = getattr(window, "create_file_dialog")
        file_path = create_file_dialog(
            cast(int, webview.SAVE_DIALOG),
            save_filename="transcription.txt",
            file_types=("Text files (*.txt)",),
        )
        if not isinstance(file_path, str):
            file_path = file_path[0] if file_path else None
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(text)
            return file_path
        return None

# Initialize
converter = AudioToTextConverter()
api = PythonAPI(converter)

js_code = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Audio to Text Converter</title>
    <style>
        :root {
            --primary: #4CAF50;
            --primary-hover: #45a049;
            --bg: #f5f7fa;
            --card-bg: #ffffff;
            --text: #333;
            --border: #e1e4e8;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            padding: 20px;
        }
        .container {
            background-color: var(--card-bg);
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            width: 100%;
            max-width: 600px;
        }
        h1 {
            text-align: center;
            color: var(--primary);
            margin-bottom: 30px;
        }
        .controls {
            display: flex;
            flex-direction: column;
            gap: 15px;
        }
        .row {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        label {
            font-weight: 600;
            min-width: 80px;
        }
        select, input[type="file"] {
            padding: 10px;
            border: 1px solid var(--border);
            border-radius: 6px;
            flex-grow: 1;
        }
        button {
            padding: 12px 20px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 600;
            transition: background-color 0.2s;
        }
        .btn-primary {
            background-color: var(--primary);
            color: white;
            flex-grow: 1;
        }
        .btn-primary:hover {
            background-color: var(--primary-hover);
        }
        .btn-primary:disabled {
            background-color: #ccc;
            cursor: not-allowed;
        }
        .btn-secondary {
            background-color: #6c757d;
            color: white;
        }
        .btn-secondary:hover {
            background-color: #5a6268;
        }
        .btn-secondary:disabled {
            background-color: #eee;
            color: #ccc;
            cursor: not-allowed;
        }
        #status {
            margin-top: 15px;
            text-align: center;
            color: #666;
            font-size: 14px;
            min-height: 20px;
        }
        #result {
            margin-top: 20px;
            padding: 15px;
            background-color: #f8f9fa;
            border: 1px solid var(--border);
            border-radius: 6px;
            min-height: 100px;
            white-space: pre-wrap;
            font-family: monospace;
            line-height: 1.5;
        }
        .actions {
            margin-top: 15px;
            display: flex;
            gap: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎤 Audio to Text</h1>
        
        <div class="controls">
            <div class="row">
                <label for="language">Language:</label>
                <select id="language">
                    <option value="ro-RO" selected>Romanian</option>
                    <option value="en-US">English (US)</option>
                    <option value="es-ES">Spanish</option>
                    <option value="fr-FR">French</option>
                    <option value="de-DE">German</option>
                    <option value="it-IT">Italian</option>
                    <option value="pt-BR">Portuguese</option>
                    <option value="ru-RU">Russian</option>
                    <option value="zh-CN">Chinese</option>
                    <option value="ja-JP">Japanese</option>
                    <option value="ko-KR">Korean</option>
                </select>
            </div>

            <div class="row">
                <button class="btn-secondary" onclick="selectFile()">📁 Select File</button>
                <span id="file-name" style="flex-grow:1; text-align:center; color:#888;">No file selected</span>
            </div>

            <button class="btn-primary" id="convertBtn" onclick="convertAudio()" disabled>🔄 Convert to Text</button>
        </div>

        <div id="status">Ready</div>
        
        <div id="result"></div>

        <div class="actions">
            <button class="btn-secondary" id="copyBtn" onclick="copyToClipboard()" disabled>📋 Copy Text</button>
            <button class="btn-secondary" id="saveBtn" onclick="saveToFile()" disabled>💾 Save File</button>
        </div>
    </div>

    <script>
        let selectedFile = null;
        let resultText = '';

        async function selectFile() {
            const filePath = await window.pywebview.api.select_audio_file();
            if (filePath) {
                selectedFile = filePath;
                document.getElementById('file-name').textContent = filePath.split(/[\\/]/).pop();
                document.getElementById('convertBtn').disabled = false;
                document.getElementById('result').textContent = '';
                document.getElementById('copyBtn').disabled = true;
                document.getElementById('saveBtn').disabled = true;
            }
        }

        async function convertAudio() {
            if (!selectedFile) return;

            const convertBtn = document.getElementById('convertBtn');
            const statusEl = document.getElementById('status');
            
            convertBtn.disabled = true;
            convertBtn.textContent = "⏳ Converting...";
            statusEl.textContent = "Processing audio...";

            try {
                const language = document.getElementById('language').value;
                
                // Call Python API
                const text = await window.pywebview.api.convert_file(selectedFile, language);
                
                document.getElementById('result').textContent = text;
                statusEl.textContent = "Conversion complete!";
                resultText = text;
                
                if (text && !text.startsWith("Error") && !text.startsWith("Could not")) {
                    document.getElementById('copyBtn').disabled = false;
                    document.getElementById('saveBtn').disabled = false;
                } else {
                    document.getElementById('copyBtn').disabled = true;
                    document.getElementById('saveBtn').disabled = true;
                }

            } catch (error) {
                statusEl.textContent = "Error: " + error.message;
                console.error(error);
            } finally {
                convertBtn.disabled = false;
                convertBtn.textContent = "🔄 Convert to Text";
            }
        }

        function copyToClipboard() {
            if (!resultText) return;
            navigator.clipboard.writeText(resultText).then(() => {
                alert('Text copied to clipboard!');
            });
        }

        async function saveToFile() {
            if (!resultText) return;
            const path = await window.pywebview.api.save_file_dialog(resultText);
            if (path) {
                alert('Saved to: ' + path);
            }
        }
    </script>
</body>
</html>
"""

# Create window
window = webview.create_window(
    "Audio to Text Converter",
    html=js_code,
    js_api=api,
    width=700,
    height=650
)

webview.start()