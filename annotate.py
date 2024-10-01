import os
import base64
import requests
from pdf2image import convert_from_path

# Configuration
API_KEY = "OPENAI-KEY"  # Replace with your OpenAI API key
PDF_PATH = "PDF_PATH"          # Path to your PDF file
IMAGE_DIR = "slide_images"        # Directory to save extracted images
TRANSCRIPT_FILE = "transcripts.txt"  # Output transcript file
MODEL_NAME = "gpt-4o-mini"        # Replace with the correct model name if different

# Ensure the image directory exists
os.makedirs(IMAGE_DIR, exist_ok=True)

# Function to encode an image to base64
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# Function to generate transcript for a single image
def generate_transcript(image_path):
    base64_image = encode_image(image_path)
    
    # Prepare the few-shot examples
    few_shot_prompt = """
### Streams: Timeseries vs Graph Streaming

**Timeseries**:
- A timeseries consists of a set of measurements taken over time.
- Sampling in a timeseries is generally periodic.
- It lacks explicit context, meaning the data points do not inherently convey a broader context or relationships.
- Examples include stock prices and sensor data.

**Graph Streams**:
- Graph streams represent the state of a set of entities and their relationships.
- They are generally event-based, with updates occurring in response to events.
- Context is explicitly defined, providing a structured understanding of how entities relate over time.
- An example of graph streaming is DBPedia.

**Note**: Streaming entities are often built upon timeseries data, offering a higher level of abstraction. This abstraction helps solve representation issues, such as those addressed by Shannon's Theorem.

---
    """

    # Complete prompt with few-shot and current slide
    prompt = few_shot_prompt + "\n"

    # Prepare the payload
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Please generate the notes for the slide in the image. You should follow the following structure, whit the slide title, followed by its content rewritten to be readable and explain everything while also minimizing the number of bulletpoints finishing with \"---\".\nHere is an example:\n\n{prompt}\n\n IMPORTANT: you should only respond with the provided format, do not add any additional information, diretly output the requested content."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 500,
        "temperature": 0.7,
        "stop": ["---"]
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    # Send the request to OpenAI API
    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)

    if response.status_code == 200:
        response_data = response.json()
        transcript = response_data['choices'][0]['message']['content'].strip()
        # remove everything before "###"
        transcript = transcript[transcript.find("###"):]
        breakpoint()
        return transcript
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None

def main():
    # Convert PDF to images
    print("Converting PDF to images...")
    pages = convert_from_path(PDF_PATH)
    print(f"Total pages extracted: {len(pages)}")

    transcripts = []

    for i, page in enumerate(pages):
        image_path = os.path.join(IMAGE_DIR, f'slide_{i+1}.jpg')
        page.save(image_path, 'JPEG')
        print(f"Saved {image_path}")

        print(f"Generating transcript for Slide {i+1}...")
        transcript = generate_transcript(image_path)

        if transcript:
            transcripts.append((i+1, transcript))
            print(f"Transcript for Slide {i+1} generated successfully.")
        else:
            print(f"Failed to generate transcript for Slide {i+1}.")

    # Save all transcripts to a text file
    print(f"Saving transcripts to {TRANSCRIPT_FILE}...")
    with open(TRANSCRIPT_FILE, 'w', encoding='utf-8') as f:
        for slide_num, transcript in transcripts:
            f.write(f"---\nSlide {slide_num} Transcript:\n\n{transcript}\n\n")

    print("All transcripts have been generated and saved.")

if __name__ == "__main__":
    main()
