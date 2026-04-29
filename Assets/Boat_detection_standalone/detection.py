'''
	Usage:streamlit run detection.py
'''
import streamlit as st
from ultralytics import YOLO
from PIL import Image
import pandas as pd
import tempfile
import os


# -----------------------------
# App settings
# -----------------------------
st.set_page_config(
    page_title="Boat Detector",
    page_icon="🚤",
    layout="wide"
)

st.title("Two-Class Boat Detection")
st.write("Upload an image to detect leader and follower boats.")


# -----------------------------
# Class names
# -----------------------------
CLASS_NAMES = {
    0: "leader",
    1: "follower"
}


# -----------------------------
# Load model
# -----------------------------
@st.cache_resource
def load_model(model_path: str):
    return YOLO(model_path)


MODEL_PATH = "../../best.pt"

if not os.path.exists(MODEL_PATH):
    st.error("Model file not found. Please put your trained model as 'best.pt' in the same folder as app.py.")
    st.stop()

model = load_model(MODEL_PATH)


# -----------------------------
# Sidebar controls
# -----------------------------
st.sidebar.header("Detection Settings")

confidence_threshold = st.sidebar.slider(
    "Confidence threshold",
    min_value=0.0,
    max_value=1.0,
    value=0.25,
    step=0.05
)

image_size = st.sidebar.selectbox(
    "Image size",
    options=[320, 416, 512, 640, 768, 1024],
    index=3
)


# -----------------------------
# Image uploader
# -----------------------------
uploaded_file = st.file_uploader(
    "Upload boat image",
    type=["jpg", "jpeg", "png", "bmp", "webp"]
)

if uploaded_file is not None:
    image = Image.open(uploaded_file).convert("RGB")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Original Image")
        st.image(image, use_container_width=True)

    # Save uploaded image temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
        image.save(temp_file.name)
        temp_image_path = temp_file.name

    # -----------------------------
    # Run detection
    # -----------------------------
    results = model.predict(
        source=temp_image_path,
        conf=confidence_threshold,
        imgsz=image_size,
        verbose=False
    )

    result = results[0]

    # Draw detection result
    annotated_image = result.plot()

    with col2:
        st.subheader("Detection Result")
        st.image(annotated_image, channels="BGR", use_container_width=True)

    # -----------------------------
    # Extract detection data
    # -----------------------------
    detections = []

    if result.boxes is not None and len(result.boxes) > 0:
        for box in result.boxes:
            class_id = int(box.cls[0])
            confidence = float(box.conf[0])
            x1, y1, x2, y2 = box.xyxy[0].tolist()

            detections.append({
                "class_id": class_id,
                "class_name": CLASS_NAMES.get(class_id, f"unknown_{class_id}"),
                "confidence": round(confidence, 4),
                "x1": round(x1, 2),
                "y1": round(y1, 2),
                "x2": round(x2, 2),
                "y2": round(y2, 2)
            })

    st.subheader("Detection Table")

    if detections:
        df = pd.DataFrame(detections)
        st.dataframe(df, use_container_width=True)

        leader_count = sum(1 for d in detections if d["class_id"] == 0)
        follower_count = sum(1 for d in detections if d["class_id"] == 1)

        st.subheader("Summary")
        st.write(f"Leader boats detected: **{leader_count}**")
        st.write(f"Follower boats detected: **{follower_count}**")

    else:
        st.warning("No boat detected. Try lowering the confidence threshold or using a clearer image.")

    # Remove temporary image
    os.remove(temp_image_path)

else:
    st.info("Please upload an image to start detection.")
