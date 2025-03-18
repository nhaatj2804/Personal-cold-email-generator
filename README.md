# People Data Processing with Apollo API & DeepSeek

This project automates the process of retrieving and processing people data from the Apollo API, generating personalized email content using DeepSeek, and saving the results in a CSV file.

## Features

- Fetches person and organization data from Apollo API.
- Filters and structures relevant data.
- Uses DeepSeek AI to generate personalized email content.
- Saves processed data into a CSV file.
- Logs all actions for easy debugging and monitoring.

## Prerequisites

- Python 3.7+
- An Apollo API Key
- A DeepSeek API Key

## Installation

1. **Clone the repository**

   ```sh
   git clone https://github.com/your-username/your-repo.git
   cd your-repo
   ```

2. **Create a virtual environment (optional but recommended)**

   ```sh
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

3. **Install dependencies**

   ```sh
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   - Create a `.env` file in the root directory and add the following:
     ```env
     APOLLO_API_KEY=your_apollo_api_key
     DEEPSEEK_API_KEY=your_deepseek_api_key
     DEEPSEEK_PROMPT="Your AI prompt"
     CSV_FILENAME=result.csv
     PAGE=1
     PER_PAGE=10
     PERSON_TITLES=CEO,CTO
     PERSON_LOCATIONS=USA
     PERSON_SENIORITIES=Executive
     ORGANIZATION_LOCATIONS=USA
     Q_ORGANIZATION_DOMAINS_LIST=
     CONTACT_EMAIL_STATUS=
     ORGANIZATION_IDS=
     ORGANIZATION_NUM_EMPLOYEES_RANGES=
     Q_KEYWORDS=
     ```

## Usage

Run the script using:

```sh
python app.py
```

## How It Works

1. **Search for people**: The script fetches people data from the Apollo API using filters from `.env`.
2. **Process each person**: Extracts relevant details and organization data.
3. **Generate email content**: Uses DeepSeek to generate email subjects and bodies.
4. **Save to CSV**: Stores the processed data in a CSV file.
5. **Log progress**: Tracks execution time and potential errors.

## Logging

- Logs are saved to `app.log`.
- Logs include request statuses, errors, and execution times.

## Troubleshooting

- **Invalid API keys**: Check that your `.env` file contains the correct API keys.
- **Rate limits**: Apollo API has rate limits. If requests fail, try again later.
- **Dependency issues**: Run `pip install -r requirements.txt` to ensure all dependencies are installed.
