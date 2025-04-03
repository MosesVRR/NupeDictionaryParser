# Nupe to English Text Processor

This project is designed to parse dictionary data from Nupe to English into machine-readable formats such as CSV or JSON. The processed data can then be used in other applications, including those with a backend.

## Features

- Parse dictionary data from raw text or other formats.
- Export data to CSV or JSON for easy integration with other systems.
- Modular and extensible design for future enhancements.

## Requirements

- Python 3.8 or higher
- Virtual environment (recommended)

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd Nupe_to_Eng_TextProcessor
   ```

2. Set up a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. Place the raw dictionary data in the `data/` directory (or specify the input file path in the script).
2. Run the processing script:
   ```bash
   python process_data.py --input data/raw_dictionary.txt --output output/dictionary.json
   ```
   Replace `--output` with `output/dictionary.csv` to export as CSV.

3. The processed data will be saved in the `output/` directory.

## File Structure

```
Nupe_to_Eng_TextProcessor/
├── data/               # Directory for raw input data
├── output/             # Directory for processed output files
├── process_data.py     # Main script for processing data
├── requirements.txt    # Python dependencies
├── .gitignore          # Git ignore rules
└── README.md           # Project documentation
```

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request with your changes.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
