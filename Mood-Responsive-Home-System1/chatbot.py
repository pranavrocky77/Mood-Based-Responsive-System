from flask import Flask, request, jsonify
from flask_cors import CORS
import nltk
from nltk.chat.util import Chat, reflections

# Download NLTK resources (run only once)
nltk.download('punkt')

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend communication

# Define chatbot responses (Modify as needed)
pairs = [
    ["hi|hello|hey", ["Hello!", "Hi there!", "Hey!"]],
    ["how are you?", ["I'm just a bot, but I'm doing fine!", "I'm doing great!"]],
    ["what is your name?", ["I'm your friendly chatbot!", "Call me ChatBot!"]],
    ["bye|goodbye", ["Goodbye!", "See you later!", "Bye! Have a great day!"]],
    ["who created you?", ["I was created by a developer like you!", "A human built me using Python."]],
    ["(.*)", ["I'm not sure how to respond to that. Can you ask something else?"]]
]

# Create chatbot instance
chatbot = Chat(pairs, reflections)

@app.route("/ask", methods=["POST"])
def ask():
    user_message = request.json.get("message")

    if not user_message:
        return jsonify({"response": "I'm listening... What would you like to ask?"})

    try:
        # Get response from the chatbot
        bot_response = chatbot.respond(user_message.lower())
        return jsonify({"response": bot_response})
    except Exception as e:
        print(f"Error in Flask: {e}")  # Debugging
        return jsonify({"response": "Sorry, an error occurred while processing your request."})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)  # Ensure it's running on all interfaces
