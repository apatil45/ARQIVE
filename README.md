# ARQIVE

**A**udit-document **R**etrieval and **Q**uery **I**ntelligence **V**ia **E**mbeddings

A smart document assistant that helps you find answers in your documents using AI. Everything runs on your computer - no cloud needed!

## What is ARQIVE?

ARQIVE is like having a smart assistant that can read all your documents and answer questions about them. Upload PDFs, Word docs, or text files, and then ask questions - ARQIVE will find the relevant information and give you answers.

## Features

- 🤖 **AI-Powered**: Uses local AI to understand and answer questions about your documents
- 🔒 **Private**: Everything runs on your computer - your documents never leave your machine
- 📄 **Multiple Formats**: Works with PDF, Word (DOCX), and text files
- 🔍 **Smart Search**: Finds relevant information even if you don't use exact words
- 👥 **User Management**: Control who can access which documents
- 💬 **Chat Interface**: Simple chat interface to ask questions

## What You Need

1. **Python 3.9 or newer** - [Download here](https://www.python.org/downloads/)
2. **Node.js 18 or newer** - [Download here](https://nodejs.org/)
3. **Ollama** - [Download here](https://ollama.ai)
   - After installing Ollama, open a terminal and run:
     ```bash
     ollama pull tinyllama
     ```

## Getting Started

### Step 1: Setup Backend

```bash
# Go to the backend folder
cd backend

# Create a virtual environment
python -m venv venv

# Activate it
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# Install required packages
pip install -r requirements.txt
```

### Step 2: Start Backend

```bash
# Make sure you're in the backend folder with venv activated
python main.py
```

You should see: `Uvicorn running on http://0.0.0.0:8000`

### Step 3: Setup Frontend

Open a **new terminal window**:

```bash
# Go to the frontend folder
cd frontend

# Install packages
npm install

# Start the frontend
npm run dev
```

You should see: `Ready on http://localhost:3000`

### Step 4: Use the App

1. Open your browser and go to: `http://localhost:3000`
2. Login with:
   - Username: `admin`
   - Password: `admin`
   - ⚠️ **Remember to change this password later!**

## How to Use

### Upload Documents

1. Click on "Upload" in the menu
2. Choose a PDF, Word document, or text file
3. Click "Upload Document"
4. Wait a moment while it processes (this might take a bit for large files)

### Ask Questions

1. Go to the "Chat" page
2. Type your question in the box
3. Press Enter or click Send
4. ARQIVE will search through your documents and give you an answer with sources

### Example Questions

- "What is the title of the document?"
- "What is the overview?"
- "What are the key findings?"
- "Who is the author?"

## Troubleshooting

### "Can't connect to Ollama"

- Make sure Ollama is running. Open a terminal and type: `ollama serve`
- Wait a few seconds, then try again

### "Model not found"

- Install the model: `ollama pull tinyllama`
- Make sure you're using the right model name

### Backend won't start

- Make sure you activated the virtual environment (you should see `(venv)` in your terminal)
- Try reinstalling: `pip install -r requirements.txt`

### Frontend won't start

- Make sure the backend is running first
- Try: `npm install` again
- Check that nothing else is using port 3000

## Project Structure

```
ARQIVE/
├── backend/          # The Python server that does the AI work
├── frontend/         # The web interface you see in your browser
└── README.md         # This file
```

## Need Help?

- Check the browser console (F12) for errors
- Check the backend terminal for error messages
- Make sure Ollama is running: `ollama list`

## Security Note

This is designed for local use. For production, make sure to:
- Change the default admin password
- Use a strong secret key
- Keep your documents secure

---

**Happy querying! 🎉**
