# Spiritor - Flask Chatbot Backend

This is the backend for **Spiritor**, a chatbot service built with Flask. It provides an API to handle chatbot queries and respond accordingly.

## Getting Started

### Prerequisites
Make sure you have **Python 3.x** installed. You can download it from [Python official website](https://www.python.org/downloads/).

### Installation
Clone the repository and install dependencies:

```bash
git clone https://github.com/your-repo/spiritor-backend.git
cd spiritor-backend
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
pip install -r requirements.txt
```

### Running the Server

```bash
python app.py
```

The server will start on `http://localhost:5000/`.

## API Endpoints

### Chatbot Query
```
GET /chatbot/query/?query=<your_question>
```
#### Example Request
```
GET http://localhost:5000/chatbot/query/?query=who is player nuwan?
```
#### Response
```json
{
  "response": "Player Nuwan is a top scorer in the league."
}
```

## Project Structure
- `app.py` - Main application entry point.
- `routes/` - Contains API route handlers.
- `models/` - Database models if applicable.
- `services/` - Chatbot logic and processing.
- `config.py` - Configuration settings.
- `requirements.txt` - Python dependencies.

## Deployment

To deploy on a cloud platform like **Heroku** or **Render**, follow their respective documentation.

## License
This project is licensed under the MIT License.
