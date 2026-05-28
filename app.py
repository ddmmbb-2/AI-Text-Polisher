import sys
import json
import os
import threading
import time
import requests
import pyperclip
from pynput.keyboard import Controller as KeyboardController, Key, GlobalHotKeys

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPlainTextEdit, QPushButton, QLabel, QLineEdit,
    QComboBox, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QMouseEvent

# ======================== 設定檔路徑 ========================
SETTINGS_FILE = "settings.json"

# ======================== 預設設定 ========================
DEFAULT_SETTINGS = {
    "api_type": "ollama",            # "ollama" 或 "openai"
    "ollama_url": "http://127.0.0.1:11434/api/generate",
    "ollama_model": "llama3",
    "openai_url": "https://api.openai.com/v1/chat/completions",
    "openai_key": "",
    "openai_model": "gpt-3.5-turbo"
}

# ======================== 風格 Prompt ========================
STYLE_PROMPTS = {
    "優美": "請將以下文字改寫得更流暢、優美、超級有文學感，只輸出繁體改寫後的結果：",
    "摘要": "請用最精簡的方式摘要以下內容，只輸出摘要結果："
}
# ============================================================

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return {**DEFAULT_SETTINGS, **json.load(f)}
        except:
            pass
    return DEFAULT_SETTINGS.copy()

def save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except:
        pass

class GuiSignal(QObject):
    show = pyqtSignal()
    hide = pyqtSignal()

gui_signal = GuiSignal()

def call_llama(text, style_key, settings):
    instruction = STYLE_PROMPTS.get(style_key, "請美化以下文字：")
    prompt = f"{instruction}\n{text}"

    try:
        if settings["api_type"] == "ollama":
            payload = {
                "model": settings["ollama_model"],
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "num_predict": 5120
                }
            }
            resp = requests.post(settings["ollama_url"], json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", "").strip()
        else:  # openai
            headers = {
                "Authorization": f"Bearer {settings['openai_key']}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": settings["openai_model"],
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 5120
            }
            resp = requests.post(settings["openai_url"], headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("AI 呼叫錯誤:", e)
        return f"[AI 錯誤] {e}"

def speech_to_text():
    import speech_recognition as sr
    r = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            r.adjust_for_ambient_noise(source, duration=0.5)
            audio = r.listen(source, timeout=5, phrase_time_limit=10)
        return r.recognize_google(audio, language="zh-TW")
    except sr.WaitTimeoutError:
        return "[語音] 等待超時，請重試"
    except sr.UnknownValueError:
        return "[語音] 無法辨識，請再說一次"
    except Exception as e:
        return f"[語音錯誤] {e}"

def paste_text_at_cursor(text):
    old = pyperclip.paste()
    pyperclip.copy(text)
    kb = KeyboardController()
    time.sleep(0.05)
    with kb.pressed(Key.ctrl):
        kb.tap('v')
    time.sleep(0.1)
    pyperclip.copy(old)

class FloatWindow(QWidget):
    process_done = pyqtSignal(str)
    voice_done = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self.old_pos = None
        self.current_style = "優美"

        self.process_done.connect(self._on_ai_result)
        self.voice_done.connect(self._on_voice_result)

        self.init_ui()
        gui_signal.show.connect(self.show_and_focus)
        gui_signal.hide.connect(self.hide)

    def init_ui(self):
        self.setWindowFlags(
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(30, 30, 30, 210);
                border-radius: 12px;
                color: white;
                font-size: 13px;
            }
            QPlainTextEdit {
                background-color: rgba(50, 50, 50, 230);
                border: 1px solid #555;
                border-radius: 8px;
                padding: 8px;
                color: #eee;
                font-size: 15px;
            }
            QPushButton {
                background-color: #2a82da;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #3c92ea; }
            QPushButton:pressed { background-color: #1a72ca; }
            QPushButton[selected="true"] {
                background-color: #27ae60;
                border: 2px solid white;
            }
            QPushButton#closeBtn {
                background-color: #c0392b;
                font-size: 14px;
                padding: 4px 10px;
            }
            QPushButton#closeBtn:hover { background-color: #e74c3c; }
            QPushButton#settingsBtn {
                background-color: #555;
                font-size: 14px;
                padding: 4px 8px;
            }
            QPushButton#settingsBtn:hover { background-color: #777; }
            QLineEdit, QComboBox {
                background-color: rgba(50, 50, 50, 230);
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px;
                color: #eee;
            }
            QFrame#settingsFrame {
                background-color: rgba(20, 20, 20, 180);
                border-radius: 8px;
                padding: 8px;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(8)

        # 標題列 (含設定按鈕)
        title_layout = QHBoxLayout()
        title = QLabel("✨ AI 寫手  |  Ctrl+Enter 送出  |  Esc 隱藏")
        title.setAlignment(Qt.AlignCenter)
        title_layout.addWidget(title)

        self.settings_btn = QPushButton("⚙️")
        self.settings_btn.setObjectName("settingsBtn")
        self.settings_btn.setFixedSize(30, 30)
        self.settings_btn.clicked.connect(self.toggle_settings)
        title_layout.addWidget(self.settings_btn)
        main_layout.addLayout(title_layout)

        # 輸入框
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("輸入文字，或按語音按鈕說話...")
        self.text_edit.setMinimumHeight(90)
        main_layout.addWidget(self.text_edit)

        # 按鈕列
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        self.btn_beauty = QPushButton("✨ 優美")
        self.btn_beauty.setCheckable(True)
        self.btn_beauty.setChecked(True)
        self.btn_beauty.setProperty("selected", True)
        self.btn_beauty.clicked.connect(lambda: self.select_style("優美"))
        btn_layout.addWidget(self.btn_beauty)

        self.btn_summary = QPushButton("📝 摘要")
        self.btn_summary.setCheckable(True)
        self.btn_summary.clicked.connect(lambda: self.select_style("摘要"))
        btn_layout.addWidget(self.btn_summary)

        self.voice_btn = QPushButton("🎤 語音")
        self.voice_btn.clicked.connect(self.on_voice)
        btn_layout.addWidget(self.voice_btn)

        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("closeBtn")
        self.close_btn.clicked.connect(QApplication.quit)
        btn_layout.addWidget(self.close_btn)

        main_layout.addLayout(btn_layout)

        # 設定面板 (預設隱藏)
        self.settings_frame = QFrame()
        self.settings_frame.setObjectName("settingsFrame")
        self.settings_frame.setVisible(False)
        settings_layout = QVBoxLayout(self.settings_frame)
        settings_layout.setContentsMargins(8, 8, 8, 8)
        settings_layout.setSpacing(6)

        # API 類型選擇
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("模式:"))
        self.api_type_combo = QComboBox()
        self.api_type_combo.addItems(["Ollama", "OpenAI"])
        self.api_type_combo.currentTextChanged.connect(self.on_api_type_changed)
        type_layout.addWidget(self.api_type_combo)
        settings_layout.addLayout(type_layout)

        # Ollama 設定
        self.ollama_group = QFrame()
        ollama_layout = QVBoxLayout(self.ollama_group)
        ollama_layout.setContentsMargins(0, 0, 0, 0)
        ollama_layout.addWidget(QLabel("Ollama 端點:"))
        self.ollama_url_edit = QLineEdit()
        self.ollama_url_edit.setPlaceholderText("http://127.0.0.1:11434/api/generate")
        ollama_layout.addWidget(self.ollama_url_edit)
        ollama_layout.addWidget(QLabel("模型:"))
        self.ollama_model_edit = QLineEdit()
        self.ollama_model_edit.setPlaceholderText("llama3")
        ollama_layout.addWidget(self.ollama_model_edit)
        settings_layout.addWidget(self.ollama_group)

        # OpenAI 設定
        self.openai_group = QFrame()
        openai_layout = QVBoxLayout(self.openai_group)
        openai_layout.setContentsMargins(0, 0, 0, 0)
        openai_layout.addWidget(QLabel("OpenAI 端點:"))
        self.openai_url_edit = QLineEdit()
        self.openai_url_edit.setPlaceholderText("https://api.openai.com/v1/chat/completions")
        openai_layout.addWidget(self.openai_url_edit)
        openai_layout.addWidget(QLabel("API 金鑰:"))
        self.openai_key_edit = QLineEdit()
        self.openai_key_edit.setEchoMode(QLineEdit.Password)
        self.openai_key_edit.setPlaceholderText("sk-...")
        openai_layout.addWidget(self.openai_key_edit)
        openai_layout.addWidget(QLabel("模型:"))
        self.openai_model_edit = QLineEdit()
        self.openai_model_edit.setPlaceholderText("gpt-3.5-turbo")
        openai_layout.addWidget(self.openai_model_edit)
        settings_layout.addWidget(self.openai_group)

        main_layout.addWidget(self.settings_frame)

        # 狀態列
        self.status_label = QLabel(f"模式：{self.current_style}")
        self.status_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.status_label)

        # 載入設定值到 UI
        self.load_settings_to_ui()

        # 事件攔截
        self.text_edit.installEventFilter(self)
        self.resize(460, 300)

    def load_settings_to_ui(self):
        # API 類型
        if self.settings["api_type"] == "openai":
            self.api_type_combo.setCurrentText("OpenAI")
        else:
            self.api_type_combo.setCurrentText("Ollama")

        # Ollama
        self.ollama_url_edit.setText(self.settings.get("ollama_url", ""))
        self.ollama_model_edit.setText(self.settings.get("ollama_model", ""))

        # OpenAI
        self.openai_url_edit.setText(self.settings.get("openai_url", ""))
        self.openai_key_edit.setText(self.settings.get("openai_key", ""))
        self.openai_model_edit.setText(self.settings.get("openai_model", ""))

        self.on_api_type_changed(self.api_type_combo.currentText())

    def on_api_type_changed(self, text):
        if text == "OpenAI":
            self.ollama_group.setVisible(False)
            self.openai_group.setVisible(True)
            self.settings["api_type"] = "openai"
        else:
            self.ollama_group.setVisible(True)
            self.openai_group.setVisible(False)
            self.settings["api_type"] = "ollama"
        self.save_current_settings()

    def save_current_settings(self):
        # 收集 UI 數值
        self.settings["ollama_url"] = self.ollama_url_edit.text().strip()
        self.settings["ollama_model"] = self.ollama_model_edit.text().strip()
        self.settings["openai_url"] = self.openai_url_edit.text().strip()
        self.settings["openai_key"] = self.openai_key_edit.text().strip()
        self.settings["openai_model"] = self.openai_model_edit.text().strip()
        save_settings(self.settings)

    def toggle_settings(self):
        visible = not self.settings_frame.isVisible()
        self.settings_frame.setVisible(visible)
        # 自動調整視窗大小 (簡單做法)
        self.adjustSize()

    def select_style(self, style):
        self.current_style = style
        self.btn_beauty.setChecked(style == "優美")
        self.btn_beauty.setProperty("selected", style == "優美")
        self.btn_summary.setChecked(style == "摘要")
        self.btn_summary.setProperty("selected", style == "摘要")
        self.btn_beauty.style().unpolish(self.btn_beauty)
        self.btn_beauty.style().polish(self.btn_beauty)
        self.btn_summary.style().unpolish(self.btn_summary)
        self.btn_summary.style().polish(self.btn_summary)
        self.status_label.setText(f"模式：{self.current_style}")

    def eventFilter(self, obj, event):
        from PyQt5.QtCore import QEvent
        if obj == self.text_edit and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Return and event.modifiers() == Qt.ControlModifier:
                self.process_and_paste()
                return True
            if event.key() == Qt.Key_Escape:
                self.hide()
                return True
        return super().eventFilter(obj, event)

    def process_and_paste(self):
        self.save_current_settings()   # 確保最新
        text = self.text_edit.toPlainText().strip()
        if not text:
            self.status_label.setText("請先輸入文字")
            return
        self.status_label.setText(f"🤖 {self.current_style} 處理中...")
        QApplication.processEvents()

        def task():
            result = call_llama(text, self.current_style, self.settings)
            self.process_done.emit(result)
        threading.Thread(target=task, daemon=True).start()

    def _on_ai_result(self, result):
        self.hide()
        QApplication.processEvents()
        time.sleep(0.2)
        paste_text_at_cursor(result)
        time.sleep(0.1)
        self.show()
        self.activateWindow()
        self.text_edit.setFocus()
        self.text_edit.clear()
        self.status_label.setText(f"✅ 完成 (模式：{self.current_style})")

    def on_voice(self):
        self.status_label.setText("🎤 聆聽中...")
        QApplication.processEvents()
        def task():
            result = speech_to_text()
            self.voice_done.emit(result)
        threading.Thread(target=task, daemon=True).start()

    def _on_voice_result(self, text):
        self.text_edit.appendPlainText(text)
        self.status_label.setText(f"語音輸入完成 (模式：{self.current_style})")

    # 拖曳移動
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.old_pos is not None:
            delta = event.globalPos() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPos()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.old_pos = None
        super().mouseReleaseEvent(event)

    def show_and_focus(self):
        self.show()
        self.activateWindow()
        self.text_edit.setFocus()
        self.text_edit.clear()
        self.status_label.setText(f"模式：{self.current_style}")

def start_hotkey_listener():
    def on_activate():
        gui_signal.show.emit()
    with GlobalHotKeys({'<ctrl>+<shift>+z': on_activate}) as listener:
        listener.join()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FloatWindow()
    hotkey_thread = threading.Thread(target=start_hotkey_listener, daemon=True)
    hotkey_thread.start()
    print("AI 文字助手已啟動，按下 Ctrl+Shift+Z 顯示視窗")
    sys.exit(app.exec_())