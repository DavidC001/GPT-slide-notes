# GPT-slide-notes

A simple Python tool to extract slides from a lecture PDF, convert them into images, and generate structured transcripts for each slide using OpenAI's `gpt-4o-mini` model.

## Getting Started

### ⏬ Installation

1. **Clone the Repository**

   ```bash
   git clone https://github.com/DavidC001/GPT-slide-notes.git
   cd lecture-pdf-transcript-generator
   ```

2. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```
   
3. **Install Poppler**

    Poppler is the underlying project that does the magic in pdf2image. You can check if you already have it installed by calling `pdftoppm -h` in your terminal/cmd.

    #### Ubuntu

    `sudo apt-get install poppler-utils`

    #### Archlinux

    `sudo pacman -S poppler`

    #### MacOS

    `brew install poppler`

    #### Windows

    1. Download the latest poppler package from [@oschwartz10612 version](https://github.com/oschwartz10612/poppler-windows/releases/) which is the most up-to-date.
    2. Move the extracted directory to the desired place on your system
    3. Add the `bin/` directory to your [PATH](https://www.architectryan.com/2018/03/17/add-to-the-path-on-windows-10/)
    4. Test that all went well by opening `cmd` and making sure that you can call `pdftoppm -h`

### ⚙️ Configuration

1. **Obtain OpenAI API Key**

   - Sign up or log in to your [OpenAI account](https://platform.openai.com/account).
   - Create a new API key and keep it secure.

2. **Set Up Variables**

   - Create a `.env` file
   - Save your API key in the `.env` file:

   ```
   API_KEY="YOUR_OPENAI_API_KEY"
   ```

## ⚡ Usage

Run the script using Python:

```bash
python transcript_generator.py
```

The script will:

1. Automatically load your OpenAI API key, allowing you to use a different one, if needed.
2. Prompt you to specify the PDF to be converted.
3. Convert each page of the specified PDF into an image.
4. Send each image to the `gpt-4o-mini` model to generate a structured transcript, along with the context of the previous `CONTEXT` slide transcripts.
5. Save all transcripts to the `TRANSCRIPT_FILE` file.

> [!TIP]
> If you don't want to convert the whole PDF, but only some pages, you can extract the pages before converting the PDF:
> ```bash
> python extract_pages.py
> ```

## License

This project is licensed under the [MIT License](LICENSE).

---

Feel free to contribute or raise issues for any improvements!
