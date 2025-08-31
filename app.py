from flask import Flask, request, jsonify, render_template, redirect, url_for
import os, json
from langchain.prompts import PromptTemplate
from langchain.memory import ConversationBufferMemory
from langchain.schema.runnable import RunnablePassthrough, RunnableLambda
from langchain_ollama import OllamaLLM

app = Flask(__name__)
CONFIG_DIR = "companions"
DEFAULT_CONFIG = os.path.join(CONFIG_DIR, "default.json")
if not os.path.exists(CONFIG_DIR):
    os.makedirs(CONFIG_DIR)
def load_config():
    if os.path.exists(DEFAULT_CONFIG):
        with open(DEFAULT_CONFIG, "r") as f:
            return json.load(f)
    return None
def save_config(data):
    with open(DEFAULT_CONFIG, "w") as f:
        json.dump(data, f)
@app.route("/")
def index():
    config = load_config()
    if not config:
        return redirect(url_for('setup'))
    return render_template("choose.html", ai_name=config['ai_name'])

@app.route("/setup", methods=["GET", "POST"])
def setup():
    if request.method == "POST":
        ai_name = request.form["ai_name"]
        personality = request.form["personality"]
        flirt_level = request.form["flirt_level"]
        ai_gender = request.form["ai_gender"]
        user_name = request.form["user_name"]
        memory_file = f"{CONFIG_DIR}/{ai_name}_memory.txt"

        config = {
            "ai_name": ai_name,
            "personality": personality,
            "flirt_level": flirt_level,
            "ai_gender": ai_gender,
            "user_name": user_name,
            "memory_file": memory_file
        }
        save_config(config)
        return redirect(url_for('chat'))
    return render_template("setup.html")

@app.route("/chat")
def chat():
    config = load_config()
    if not config:
        return redirect(url_for('setup'))
    return render_template("chat.html", ai_name=config['ai_name'], user_name=config['user_name'])

@app.route("/chat_api", methods=["POST"])
def chat_api():
    config = load_config()
    user_input = request.json.get("message", "")
    ai_name = config["ai_name"]
    personality = config["personality"]
    flirt_level = config["flirt_level"]
    ai_gender = config["ai_gender"]
    user_name = config["user_name"]
    memory_file = config.get("memory_file", f"{CONFIG_DIR}/{ai_name}_memory.txt")

    pronouns_map = {
        "male": {"subject": "he", "object": "him", "possessive": "his"},
        "female": {"subject": "she", "object": "her", "possessive": "her"}
    }
    pronouns = pronouns_map[ai_gender.lower()]
    template = f"""
    You are {{ai_name}}, a {{ai_gender}} AI companion. 
    Your core personality is: {{personality}}.
    Flirt level: {{flirt_level}}.
    You are talking to {{user_name}}.

    Use pronouns correctly: {pronouns['subject']}/{pronouns['object']}/{pronouns['possessive']}.

    IMPORTANT: Always express emotions and actions using actual emojis. 
    For example, instead of writing *wink*, use 😉. 
    Instead of *smile*, use 😊, and so on. 
    Do NOT use text placeholders like *heart*, *laugh*, or *wink* — always use the corresponding emoji.

    Conversation so far:
    {{history}}

    {{user_name}}: {{user_input}}
    {{ai_name}}:
    """

    prompt = PromptTemplate(
        input_variables=["ai_name", "ai_gender", "personality", "flirt_level", "user_name", "history", "user_input"],
        template=template,
    )

    MODEL_NAME = "hf.co/mradermacher/gemma3-4b-it-abliterated-GGUF:Q4_K_M"
    llm = OllamaLLM(model=MODEL_NAME)

    history_text = ""
    if os.path.exists(memory_file):
        with open(memory_file, "r") as f:
            history_text = f.read()

    memory = ConversationBufferMemory(memory_key="history", return_messages=False)
    if history_text:
        memory.save_context({"user_input": "Previous conversation"}, {"output": history_text})

    get_history = RunnableLambda(lambda _: memory.load_memory_variables({})["history"])
    chain = (
        {
            "ai_name": RunnablePassthrough(),
            "ai_gender": RunnablePassthrough(),
            "personality": RunnablePassthrough(),
            "flirt_level": RunnablePassthrough(),
            "user_name": RunnablePassthrough(),
            "user_input": RunnablePassthrough(),
            "history": get_history,
        }
        | prompt
        | llm
    )

    response = chain.invoke({
        "ai_name": ai_name,
        "ai_gender": ai_gender,
        "personality": personality,
        "flirt_level": flirt_level,
        "user_name": user_name,
        "user_input": user_input,
    })

    memory.save_context({"user_input": user_input}, {"output": response})
    all_history = memory.load_memory_variables({})["history"]
    with open(memory_file, "w") as f:
        f.write(all_history)

    return jsonify({"reply": response.strip()})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
