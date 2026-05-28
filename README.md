# ✨ AI Text Polisher

> 一扇漂浮於所有視窗之上的 AI 修飾之窗  
> 打字或說話，按下快捷鍵，文字立刻變得優美或精簡，然後貼回你正在輸入的地方。

---

## 🎯 核心特色

- 🪟 **浮動置頂視窗** – 無邊框、可拖曳，不干擾原本工作  
- 🎤 **語音輸入** – 說出你想寫的，自動轉成文字  
- ✨ **一鍵美化** – 選擇「優美」或「摘要」模式，交由 AI 重新潤飾  
- ⌨️ **Ctrl+Enter 送出** – 自動將 AI 結果貼回原本的游標位置，視窗不消失  
- ⚙️ **雙 API 支援** – 可切換 **Ollama**（本機）或 **OpenAI**（雲端）  
- 💾 **設定自動儲存** – API 金鑰、模型、端點皆記憶在 `settings.json`  
- 🚀 **可打包成 EXE** – 使用 PyInstaller 一鍵轉為獨立執行檔，無需 Python 環境  

---

## 🎬 快速預覽

1. 在任何應用程式中按下 **Ctrl+Shift+Z**  
2. 浮動視窗出現，輸入文字或按下 🎤 語音  
3. 點選「優美」或「摘要」模式  
4. 按下 **Ctrl+Enter**  
5. AI 修飾後的自動貼回你的文件/聊天室/郵件中 ✨  

---

## 🧰 技術棧

- [Python 3.10+](https://www.python.org/)
- [PyQt5](https://pypi.org/project/PyQt5/) – GUI 框架
- [pynput](https://pypi.org/project/pynput/) – 全域熱鍵與鍵盤模擬
- [requests](https://pypi.org/project/requests/) – API 呼叫
- [SpeechRecognition](https://pypi.org/project/SpeechRecognition/) – 語音辨識
- [pyperclip](https://pypi.org/project/pyperclip/) – 剪貼簿操作
- 支援 **Ollama** 本地模型或 **OpenAI API**（含相容端點）

---

## 📦 安裝與執行

### 1. 複製專案
```bash
git clone https://github.com/你的帳號/ai-text-polisher.git
cd ai-text-polisher
