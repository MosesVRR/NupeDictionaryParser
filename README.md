# Nupe-to-English Dictionary Text Processor

An experimental Python project exploring AI-assisted transcription and digitization of a scanned Nupe–English dictionary into structured, machine-readable data.

## Overview

Historical and linguistic dictionaries are valuable resources for language preservation, research, and language technology development. However, when dictionaries are available only as scanned documents, their contents can be difficult to search, process, and reuse programmatically.

This project aims to develop a workflow for extracting dictionary entries from scanned pages and converting them into structured data. Particular attention is given to preserving **Nupe orthography, tone marks, diacritics, and the relationships between headwords and their definitions**.

The long-term goal is to produce a structured Nupe–English dictionary that can support search applications, linguistic research, and future language technology projects.

## Objectives

- Extract Nupe headwords and their English definitions from scanned dictionary pages.
- Preserve Nupe spelling, including tone marks, diacritics, apostrophes, and repeated vowels.
- Identify parts of speech, category codes, alternative spellings, and additional information.
- Represent entries and their multiple senses in a consistent, machine-readable format.
- Evaluate AI vision models for transcription accuracy on linguistic material.
- Develop a repeatable pipeline for processing dictionary pages while retaining links to the original source.

## Approach

The project is being developed incrementally, beginning with individual page images and small transcription experiments.

### 1. Image-based transcription

Scanned dictionary pages are rendered as images so that their contents can be processed by vision-capable AI models.

Experiments have included local models through Ollama and vision models accessed through the OpenAI API.

### 2. Headword transcription

Headwords are transcribed separately to evaluate how accurately models reproduce the original Nupe spelling. This is particularly important because a model may recognize a word while incorrectly substituting one diacritic for another.

Initial experiments indicate that cropping the headword column can improve transcription results for the tested page.

### 3. Structured data extraction

Dictionary entries are represented as structured records containing fields such as:

- Headword
- Alternative spellings
- Part of speech
- English definitions and senses
- Category codes
- Additional information and cross-references
- Source page and transcription review status

Python and Pydantic are used to validate the structure of extracted data.

### 4. Verification and quality control

AI-generated transcriptions are not automatically considered verified. Results must be compared with the original scanned page, particularly where tone marks, diacritics, or individual characters are unclear.

The workflow is being designed to preserve source information and flag entries requiring review.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Main development language |
| OpenAI API | Experiments with vision-based transcription and extraction |
| Ollama | Local and cloud-connected model experiments |
| Pydantic | Data models and validation |
| JSON | Structured dictionary output |
| PDF and image processing | Rendering and preparing scanned pages |

## Current Status

**Stage: Experimental prototype**

Current work focuses on evaluating transcription accuracy and establishing a reliable extraction workflow.

- [x] Render scanned dictionary pages as images.
- [x] Experiment with vision models for dictionary extraction.
- [x] Develop Pydantic models for structured dictionary entries.
- [x] Generate JSON output from an individual dictionary page.
- [x] Test isolated-word and headword-column transcription.
- [x] Obtain a successful headword-column transcription in an initial test.
- [ ] Evaluate accuracy across additional pages.
- [ ] Automate page rendering and headword-column cropping.
- [ ] Develop a repeatable process for extracting definitions and metadata.
- [ ] Implement a review workflow for uncertain transcriptions.
- [ ] Process the complete dictionary and evaluate the resulting dataset.

The successful headword-column transcription is an initial result, not yet a comprehensive accuracy evaluation of the entire dictionary.

## Project Structure

The repository is organized around the Python application, its data models, and its input and output files.

```text
nupe_to_eng_textprocessor/
├── main.py
├── models.py
├── requirements.txt
├── .env
├── data/
├── output/
└── experiments/
```

- `main.py` — application entry point for extraction experiments.
- `models.py` — Pydantic models for dictionary pages, entries, and senses.
- `requirements.txt` — Python dependencies.
- `.env` — local configuration, including API credentials.
- `data/` — input documents and related source data.
- `output/` — rendered pages, raw model responses, and structured output.
- `experiments/` — scripts used to test transcription methods and model configurations.

*The directory layout may evolve as the extraction pipeline develops.*

## Getting Started

### Prerequisites

- Python 3.10 or later
- A copy of the source dictionary PDF
- An OpenAI API key for OpenAI-based experiments
- Ollama, if running the local or Ollama-based experiments

### Installation

Clone the repository:

```bash
git clone <repository-url>
cd nupe_to_eng_textprocessor
```

Create and activate a virtual environment:

```bash
python -m venv venv
```

On Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

Install the dependencies:

```bash
python -m pip install -r requirements.txt
```

If the OpenAI API package is not included in the requirements yet, install it with:

```bash
python -m pip install openai python-dotenv
```

### Configuration

For OpenAI-based experiments, create a local `.env` file containing:

```text
OPENAI_API_KEY=your_api_key_here
```

Replace the placeholder with your API key. API usage may incur charges.

**Security:** Never commit API keys, credentials, or other secrets to version control. Add `.env` and other sensitive local files to `.gitignore`.

### Running an Experiment

Activate the virtual environment and run the relevant experiment script from the project root.

For example:

```bash
python main.py
```

The current extraction script expects its rendered input image at `output/dictionary_page_1.png`. Adjust the paths and model configuration as needed for your environment.

## Challenges and Limitations

The principal technical challenge is accurate transcription of Nupe orthography from scanned historical documents.

General-purpose vision models can produce plausible text while changing individual characters, adding or omitting letters, or substituting diacritics. Valid JSON and successful schema validation do not guarantee transcription accuracy.

For this reason, the project treats AI output as a candidate transcription rather than an authoritative linguistic reference. The original scanned document remains the source of truth.

The current prototype has been tested on a limited number of images. Accuracy, processing cost, and scalability across the complete dictionary have not yet been established.

## Future Work

Planned development includes:

- Automating page rendering and headword-column extraction.
- Benchmarking models against manually verified transcriptions.
- Measuring exact headword accuracy and character error rates.
- Separating headword transcription from definition extraction.
- Improving source-page tracking and review status.
- Exporting validated entries to CSV and other formats.
- Building a reusable dataset suitable for dictionary search and further linguistic applications.

## Motivation

This project explores how modern AI-assisted document processing can help make linguistic resources more accessible and useful in digital form.

By combining image processing, vision models, structured data validation, and careful verification, the aim is to develop a practical workflow for transforming scanned dictionary material into reusable digital data.

## License and Source Attribution

The source dictionary and its contents may be subject to copyright or other usage restrictions. Verify the applicable permissions before redistributing the original scans or a substantial transcription.

The project's source-code license and attribution requirements should be documented separately once they have been established.
