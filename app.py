import sys, json, os, threading, time, requests, pyperclip
from pynput.keyboard import Controller as KeyboardController, Key, GlobalHotKeys
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QPlainTextEdit, QPushButton, QLabel, QLineEdit,
                             QComboBox, QFrame, QTextEdit)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QMouseEvent

SETTINGS_FILE = "settings.json"
DEFAULT_SETTINGS = {
    "api_type": "ollama",
    "ollama_url": "http://127.0.0.1:11434/api/chat", 
    "ollama_model": "llama3",
    "openai_url": "https://api.openai.com/v1/chat/completions",
    "openai_key": "",
    "openai_model": "gpt-3.5-turbo",
    "max_tokens": 5120,
    "beauty_prompt": "請將以下文字改寫得更流暢、優美，只輸出繁體改寫後的結果：",
    "summary_prompt": "請用最精簡的方式摘要以下內容，只輸出繁體摘要結果："
}

class GuiSignal(QObject):
    show_sig = pyqtSignal()
    hide_sig = pyqtSignal()

gui_signal = GuiSignal()

def call_ai(messages, settings):
    is_ollama = (settings["api_type"] == "ollama")
    url = settings["ollama_url"].replace("generate", "chat") if is_ollama else settings["openai_url"]
    
    payload = {
        "model": settings["ollama_model"] if is_ollama else settings["openai_model"],
        "messages": messages
    }
    
    headers = {}
    if is_ollama:
        payload.update({"stream": False, "options": {"num_predict": settings.get("max_tokens", 512)}})
    else:
        payload.update({"temperature": 0.7, "max_tokens": settings.get("max_tokens", 512)})
        headers = {"Authorization": f"Bearer {settings['openai_key']}", "Content-Type": "application/json"}

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "").strip() if is_ollama else data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[AI 錯誤] {e}"

def speech_to_text():
    import speech_recognition as sr
    r = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            r.adjust_for_ambient_noise(source, duration=0.5)
            return r.recognize_google(r.listen(source, timeout=5, phrase_time_limit=10), language="zh-TW")
    except sr.WaitTimeoutError: return "[語音] 等待超時"
    except sr.UnknownValueError: return "[語音] 無法辨識"
    except Exception as e: return f"[語音錯誤] {e}"

def paste_text_at_cursor(text):
    old = pyperclip.paste()
    pyperclip.copy(text)
    kb = KeyboardController()
    time.sleep(0.05)
    with kb.pressed(Key.ctrl): kb.tap('v')
    time.sleep(0.1)
    pyperclip.copy(old)

class FloatWindow(QWidget):
    process_done = pyqtSignal(str)
    voice_done = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.settings = {**DEFAULT_SETTINGS, **self._load_settings()}
        self.inputs = {}  
        self.chat_history = [] 
        self.current_style = "優美"
        self.old_pos = None

        self.process_done.connect(self._on_ai_result)
        self.voice_done.connect(self._on_voice_result)
        gui_signal.show_sig.connect(self.show_and_focus)
        gui_signal.hide_sig.connect(self.hide)

        self.init_ui()

    def _load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f: return json.load(f)
            except: pass
        return {}

    def save_settings(self):
        for k, w in self.inputs.items():
            val = w.toPlainText().strip() if isinstance(w, QTextEdit) else w.text().strip()
            self.settings[k] = int(val) if k == "max_tokens" and val.isdigit() else val
        self.settings["api_type"] = "openai" if self.api_type_combo.currentText() == "OpenAI" else "ollama"
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except: pass

    def init_ui(self):
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("""
            QWidget { background: rgba(30,30,30,210); border-radius: 10px; color: white; font-size: 13px; }
            QPlainTextEdit, QTextEdit#chatDisplay { background: rgba(50,50,50,230); border: 1px solid #555; border-radius: 8px; padding: 8px; font-size: 14px; }
            QPushButton { background: #2a82da; border-radius: 6px; padding: 6px 10px; font-weight: bold; }
            QPushButton:hover { background: #3c92ea; }
            QPushButton:checked { background: #27ae60; border: 2px solid white; }
            QLineEdit, QComboBox, QTextEdit { background: rgba(50,50,50,230); border: 1px solid #555; border-radius: 4px; padding: 4px; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        # 頂部標題
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("✨ AI 寫手 | Ctrl+Enter 送出 | Esc 隱藏"), 1, Qt.AlignCenter)
        btn_set = QPushButton("⚙️")
        btn_set.setFixedSize(30, 30)
        btn_set.setStyleSheet("background: #555;")
        btn_set.clicked.connect(self.toggle_settings)
        top_layout.addWidget(btn_set)
        layout.addLayout(top_layout)

        # 對話歷史顯示區 (專屬於對話模式)
        self.chat_display = QTextEdit()
        self.chat_display.setObjectName("chatDisplay")
        self.chat_display.setReadOnly(True)
        self.chat_display.setVisible(False)
        self.chat_display.setMinimumHeight(150)
        layout.addWidget(self.chat_display)

        # 文本輸入框
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("輸入文字...")
        self.text_edit.installEventFilter(self)
        layout.addWidget(self.text_edit)

        # 底部按鈕區
        btn_layout = QHBoxLayout()
        self.mode_btns = {}
        for mode, icon in [("優美", "✨"), ("摘要", "📝"), ("對話", "💬")]:
            btn = QPushButton(f"{icon} {mode}")
            btn.setCheckable(True)
            btn.clicked.connect(lambda chk, m=mode: self.select_style(m))
            btn_layout.addWidget(btn)
            self.mode_btns[mode] = btn
        
        btn_voice = QPushButton("🎤 語音")
        btn_voice.clicked.connect(self.on_voice)
        btn_close = QPushButton("✕")
        btn_close.setStyleSheet("background: #c0392b;")
        btn_close.clicked.connect(QApplication.quit)
        btn_layout.addWidget(btn_voice)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

        # 設定面板 (動態生成)
        self.settings_frame = QFrame()
        self.settings_frame.setVisible(False)
        set_layout = QVBoxLayout(self.settings_frame)
        
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("模式:"))
        self.api_type_combo = QComboBox()
        self.api_type_combo.addItems(["Ollama", "OpenAI"])
        self.api_type_combo.currentTextChanged.connect(self.on_api_type_changed)
        type_layout.addWidget(self.api_type_combo)
        set_layout.addLayout(type_layout)

        def _add_input(key, label, holder="", is_pw=False, is_text=False):
            set_layout.addWidget(QLabel(label))
            w = QTextEdit() if is_text else QLineEdit()
            w.setMaximumHeight(60 if is_text else 30)
            if not is_text:
                w.setPlaceholderText(holder)
                if is_pw: w.setEchoMode(QLineEdit.Password)
            set_layout.addWidget(w)
            self.inputs[key] = w
            val = str(self.settings.get(key, ""))
            if is_text: w.setPlainText(val)
            else: w.setText(val)

        _add_input("ollama_url", "[Ollama] 端點:", "http://127.0.0.1:11434/api/chat")
        _add_input("ollama_model", "[Ollama] 模型:", "llama3")
        _add_input("openai_url", "[OpenAI] 端點:", "https://api.openai.com/v1/chat/completions")
        _add_input("openai_key", "[OpenAI] 金鑰:", "sk-...", is_pw=True)
        _add_input("openai_model", "[OpenAI] 模型:", "gpt-3.5-turbo")
        _add_input("max_tokens", "輸出長度 (Tokens):", "512")
        _add_input("beauty_prompt", "優美提示詞:", is_text=True)
        _add_input("summary_prompt", "摘要提示詞:", is_text=True)
        
        layout.addWidget(self.settings_frame)
        
        self.status_label = QLabel("準備就緒")
        layout.addWidget(self.status_label, 0, Qt.AlignCenter)

        self.on_api_type_changed("OpenAI" if self.settings["api_type"] == "openai" else "Ollama")
        self.select_style("優美")
        self.resize(450, 300)

    # 修復 2：設定開關時，強制視窗重新適應大小 (adjustSize)
    def toggle_settings(self):
        self.settings_frame.setVisible(not self.settings_frame.isVisible())
        self.adjustSize() 

    def on_api_type_changed(self, text):
        is_ollama = (text == "Ollama")
        for k in ["ollama_url", "ollama_model"]: self.inputs[k].setVisible(is_ollama)
        for k in ["openai_url", "openai_key", "openai_model"]: self.inputs[k].setVisible(not is_ollama)
        self.save_settings()
        self.adjustSize() # 如果切換 API 類型導致高度改變，也自適應

    def select_style(self, style):
        self.current_style = style
        for k, btn in self.mode_btns.items():
            btn.setChecked(k == style)
        
        # 控制對話視窗的顯示與隱藏
        is_chat = (style == "對話")
        self.chat_display.setVisible(is_chat)
        self.text_edit.setMaximumHeight(60 if is_chat else 16777215) # 在對話模式中縮小輸入框
        
        if not is_chat: 
            self.chat_history.clear()
            self.chat_display.clear()

        self.status_label.setText(f"模式：{style}")
        self.adjustSize() # 模式切換時自適應大小

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

    def _trim_history(self, limit=2000):
        while self.chat_history and sum(len(m["content"]) for m in self.chat_history) > limit:
            self.chat_history.pop(0)

    def process_and_paste(self):
        self.save_settings()
        text = self.text_edit.toPlainText().strip()
        if not text: return self.status_label.setText("請先輸入文字")
        
        self.status_label.setText(f"🤖 {self.current_style} 處理中...")
        QApplication.processEvents()

        if self.current_style == "對話":
            self.chat_history.append({"role": "user", "content": text})
            self._trim_history()
            self.chat_display.append(f"<span style='color:#4ea8de;'>👤 你：</span> {text}<br>")
            self.text_edit.clear() # 對話送出後清空輸入框，方便下次輸入
            msgs = self.chat_history
        else:
            prompt_key = "beauty_prompt" if self.current_style == "優美" else "summary_prompt"
            msgs = [{"role": "system", "content": self.settings[prompt_key]},
                    {"role": "user", "content": text}]

        threading.Thread(target=lambda: self.process_done.emit(call_ai(msgs, self.settings)), daemon=True).start()

    # 修復 1：如果是對話模式，直接將結果印在視窗內，不執行自動貼上
    def _on_ai_result(self, result):
        if self.current_style == "對話":
            if not result.startswith("[AI 錯誤]"):
                self.chat_history.append({"role": "assistant", "content": result})
            self.chat_display.append(f"<span style='color:#a7c957;'>🤖 AI：</span> {result}<br><br>")
            
            # 自動捲動到底部
            sb = self.chat_display.verticalScrollBar()
            sb.setValue(sb.maximum())
            self.status_label.setText("✅ 完成 (對話)")
            return # 中斷，不往下執行隱藏和貼上邏輯

        # 優美 / 摘要 模式：原本的隱藏與貼上邏輯
        self.hide()
        QApplication.processEvents()
        time.sleep(0.1)
        paste_text_at_cursor(result)
        time.sleep(0.1)
        self.show_and_focus()
        self.status_label.setText(f"✅ 完成 ({self.current_style})")

    def on_voice(self):
        self.status_label.setText("🎤 聆聽中...")
        threading.Thread(target=lambda: self.voice_done.emit(speech_to_text()), daemon=True).start()

    def _on_voice_result(self, text):
        self.text_edit.appendPlainText(text)
        self.status_label.setText("語音輸入完成")

    # 拖曳移動視窗
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton: self.old_pos = event.globalPos()
    def mouseMoveEvent(self, event: QMouseEvent):
        if self.old_pos:
            delta = event.globalPos() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPos()
    def mouseReleaseEvent(self, event: QMouseEvent): self.old_pos = None

    def show_and_focus(self):
        self.show()
        self.activateWindow()
        self.text_edit.clear()
        self.text_edit.setFocus()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FloatWindow()
    
    def start_hotkeys():
        with GlobalHotKeys({'<ctrl>+<shift>+z': gui_signal.show_sig.emit}) as listener:
            listener.join()
            
    threading.Thread(target=start_hotkeys, daemon=True).start()
    
    print("AI 助手已啟動，按 Ctrl+Shift+Z 顯示")
    sys.exit(app.exec_())