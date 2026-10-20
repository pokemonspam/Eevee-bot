import json
import os
import urllib.request
import numpy as np
import streamlit as st
import tensorflow as tf
from PIL import Image

st.title("Poketwo Classifier API")

# Hugging Face raw file URL for your model in your dataset
MODEL_URL = "https://huggingface.co/datasets/Eeveebot/Poketwo-Spawn-Images/resolve/main/pokemon_model.keras"
MODEL_PATH = "pokemon_model.keras"

@st.cache_resource
def load_model_and_classes():
    # Download the model file if it doesn't exist locally in the container yet
    if not os.path.exists(MODEL_PATH):
        with st.spinner("Downloading model from Hugging Face dataset... (this may take a moment)"):
            urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
            
    model = tf.keras.models.load_model(MODEL_PATH)
    
    with open("classes.json", "r") as f:
        class_indices = json.load(f)
    idx_to_class = {v: k for k, v in class_indices.items()}
    return model, idx_to_class

model, idx_to_class = load_model_and_classes()

# File uploader interface
uploaded_file = st.file_uploader("Upload a Pokémon spawn image", type=["png", "jpg", "jpeg"])

if uploaded_file is not None:
    image = Image.open(uploaded_file).convert("RGB").resize((128, 128))
    st.image(uploaded_file, caption="Uploaded Image", use_container_width=True)
    
    # Preprocess
    img_array = np.array(image) / 255.0
    img_array = np.expand_dims(img_array, axis=0)

    # Predict
    preds = model.predict(img_array)[0]
    top_idx = np.argmax(preds)
    pokemon_name = idx_to_class[top_idx]
    confidence = float(preds[top_idx] * 100)

    st.success(f"**Prediction:** {pokemon_name} ({confidence:.2f}%)")
    
    # Output raw JSON for bot consumption
    st.json({"pokemon": pokemon_name, "confidence": round(confidence, 2)})
