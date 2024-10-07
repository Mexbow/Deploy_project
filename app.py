import subprocess
import os
from flask import Flask, request, render_template, redirect, url_for
from PIL import Image
import torch
from transformers import AutoImageProcessor, AutoTokenizer, VisionEncoderDecoderModel
from pyngrok import ngrok

app = Flask(__name__)

# Function to install dependencies
def install_dependencies():
    if os.path.exists('requirements.txt'):
        try:
            subprocess.check_call(['pip', 'install', '-r', 'requirements.txt'])
            print("Dependencies installed.")
        except subprocess.CalledProcessError as e:
            print(f"Error installing dependencies: {e}")
            exit(1)

# Ensure dependencies are installed
install_dependencies()

# Load models once when the app starts
weights_path = os.path.join(os.path.dirname(__file__), 'weights', 'best14.pt')
object_detection_model = torch.hub.load('Mexbow/yolov5_model', 'custom', path=weights_path, autoshape=True)
captioning_processor = AutoImageProcessor.from_pretrained("motheecreator/ViT-GPT2-Image-Captioning")
tokenizer = AutoTokenizer.from_pretrained("motheecreator/ViT-GPT2-Image-Captioning")
caption_model = VisionEncoderDecoderModel.from_pretrained("motheecreator/ViT-GPT2-Image-Captioning")

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'image' not in request.files:
        return redirect(request.url)
    
    file = request.files['image']
    image_path = os.path.join('static', 'uploaded_image.jpg')
    file.save(image_path)
    
    img = Image.open(image_path).convert('RGB')
    results, original_caption = process_image(img)
    
    return render_template('results.html', results=zip(results['labels'], results['captions']), original_caption=original_caption)

def process_image(image):
    results = object_detection_model(image)
    
    img_with_boxes = results.render()[0]
    detected_image_path = os.path.join('static', 'detected_image.jpg')
    img_with_boxes = Image.fromarray(img_with_boxes)
    img_with_boxes.save(detected_image_path)
    
    boxes = results.xyxy[0][:, :4].cpu().numpy()
    labels = [results.names[int(x)] for x in results.xyxy[0][:, 5].cpu().numpy()]

    # Caption the original image
    original_inputs = captioning_processor(images=image, return_tensors="pt")
    with torch.no_grad():
        caption_ids = caption_model.generate(**original_inputs)
    original_caption = tokenizer.decode(caption_ids[0], skip_special_tokens=True)

    # Crop objects and caption them
    cropped_images = crop_objects(image, boxes)
    captions = []
    for cropped_image in cropped_images:
        inputs = captioning_processor(images=cropped_image, return_tensors="pt")
        with torch.no_grad():
            caption_ids = caption_model.generate(**inputs)
        caption = tokenizer.decode(caption_ids[0], skip_special_tokens=True)
        captions.append(caption)
    
    return {'labels': labels, 'captions': captions, 'detected_image_path': detected_image_path}, original_caption


def crop_objects(image, boxes):
    cropped_images = []
    for box in boxes:
        cropped_image = image.crop((box[0], box[1], box[2], box[3]))
        cropped_images.append(cropped_image)
    return cropped_images
if __name__ == '__main__':
    ngrok.set_auth_token("2n6EDPhIXvU79Sh5zLHKyI1clfA_5L59Dy9okywaCGCgDNxHK")
    public_url = ngrok.connect(8000)
    print(f" * ngrok tunnel available at: {public_url}")
    app.run(host='0.0.0.0', port=8000)