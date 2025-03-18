import os
import json
import csv
import logging
import requests
import time
import argparse
from dotenv import load_dotenv
from litellm import completion

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

# Parse command-line arguments
parser = argparse.ArgumentParser(description='Process people data from Apollo API or CSV file')
parser.add_argument('--input', type=str, help='Path to input CSV file')
args = parser.parse_args()

APOLLO_API_KEY = os.getenv("APOLLO_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_PROMPT = os.getenv("DEEPSEEK_PROMPT", "")
CSV_FILENAME = os.getenv("CSV_FILENAME", "result.csv")

if not CSV_FILENAME.strip():  # Check if empty or contains only whitespace
    CSV_FILENAME = "result.csv"

HEADERS = {
    "accept": "application/json",
    "Cache-Control": "no-cache",
    "Content-Type": "application/json",
    "X-Api-Key": APOLLO_API_KEY
}

def update_csv_filename():
    logging.info(f"Setting up CSV file: {CSV_FILENAME}")
    if not os.path.exists(CSV_FILENAME):
        logging.info(f"Using CSV filename: {CSV_FILENAME}")
        return CSV_FILENAME

    name, ext = os.path.splitext(CSV_FILENAME)
    counter = 1

    while True:
        new_filename = f"{name}_{counter}{ext}"
        if not os.path.exists(new_filename):
            logging.info(f"File already exists, using new filename: {new_filename}")
            return new_filename
        counter += 1

CSV_FILENAME = update_csv_filename()

def fetch_person_data(people_id):
    url = f"https://api.apollo.io/api/v1/people/match?id={people_id}"
    try:
        start_time = time.time()
        response = requests.post(url, headers=HEADERS)
        elapsed_time = time.time() - start_time
        
        if response.status_code == 200:
            return response.json()
        else:
            logging.error(f"Failed to fetch person data for {people_id}: Status {response.status_code}")
            logging.error(f"Response: {response.text[:200]}...")
            return None
    except Exception as e:
        logging.error(f"Exception while fetching person data for {people_id}: {str(e)}")
        return None

def filter_person_data(data):
    person = data.get("person", {})
    organization = person.get("organization", {})
    
    filtered_data = {
        "person": {
            "first_name": person.get("first_name"),
            "last_name": person.get("last_name"),
            "title": person.get("title"),
            "headline": person.get("headline"),
            "email": person.get("email")
        },
        "organization": {
            "name": organization.get("name"),
            "city": organization.get("city"),
            "technology_names": organization.get("technology_names"),
            "industries": organization.get("industries"),
            "keywords": organization.get("keywords"),
            "estimated_num_employees": organization.get("estimated_num_employees"),
            "website": organization.get("website_url")
        }
    }
    
    logging.debug(f"Filtered data for {person.get('first_name')} {person.get('last_name')}")
    return filtered_data

def generate_email_content(profile_data):
    person_name = f"{profile_data['person']['first_name']} {profile_data['person']['last_name']}"
    
    content = (
        f"Here is the profile data: {profile_data}. The result should only be in JSON format:\n"
        "[\n"
        "    {\n"
        "        \"subject\": \"Hey John, Special Offer!\",\n"
        "        \"body\": \"Hey John, we have an exclusive discount for Acme Corp!\"\n"
        "    },\n"
        "    {\n"
        "        \"subject\": \"Following up on my last email\",\n"
        "        \"body\": \"Hey John, just checking if you saw my last email about the Acme Corp discount!\"\n"
        "    }\n"
        "]"
    )
    
    try:
        start_time = time.time()
        response = completion(
            model="deepseek/deepseek-chat", 
            messages=[{"role": "user", "content": DEEPSEEK_PROMPT + content}]
        )
        elapsed_time = time.time() - start_time
        return response
    except Exception as e:
        logging.error(f"Error generating email content: {str(e)}")
        return {"choices": [{"message": {"content": "[]"}}]}

def extract_email_content(deepseek_response):
    try:
        content_text = deepseek_response["choices"][0]["message"]["content"]
        
        # Try to find JSON content between ```json and ``` markers
        if "```json" in content_text:
            json_content = content_text.split("```json")[-1].split("```")[0].strip()
        # If not found, try to extract just the JSON part
        else:
            # Find first [ and last ]
            start_idx = content_text.find("[")
            end_idx = content_text.rfind("]") + 1
            if start_idx >= 0 and end_idx > start_idx:
                json_content = content_text[start_idx:end_idx]
            else:
                json_content = content_text
        
        parsed_content = json.loads(json_content)
        return parsed_content
    except Exception as e:
        logging.error(f"Error extracting email data: {e}")
        logging.error(f"Raw content: {deepseek_response.get('choices', [{}])[0].get('message', {}).get('content', '')[:200]}...")
        return []

def save_to_csv(data, filename=CSV_FILENAME):
    person_name = f"{data['person']['first_name']} {data['person']['last_name']}"
    logging.info(f"Saving data for {person_name} to CSV: {filename}")
    
    row = {
        "EMAIL": data["person"]["email"],
        "Website": data["organization"]["website"],
        "First Name": data["person"]["first_name"],
        "Last Name": data["person"]["last_name"],
        "Title": data["person"]["title"],
        "Company": data["organization"]["name"],
        "Mail Subject": data.get("email_subject", ""),
        "Main Email": data.get("email_content", ""),
        "Second Subject": data.get("followup_email_subject", ""),
        "Second Email": data.get("followup_email_content", "")
    }
    
    try:
        file_exists = os.path.isfile(filename)
        with open(filename, "a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=row.keys(), quoting=csv.QUOTE_ALL)
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
    except Exception as e:
        logging.error(f"Error saving to CSV: {str(e)}")

def process_people_data(people_id, current_index, total_count):
    logging.info(f"Processing person {current_index}/{total_count} (ID: {people_id})")
    
    # Fetch person data
    person_data = fetch_person_data(people_id)
    if not person_data:
        logging.warning(f"Skipping person {current_index}/{total_count} - could not fetch data")
        return
    
    # Extract and filter data
    filtered_data = filter_person_data(person_data)
    
    # Generate email content
    deepseek_response = generate_email_content(filtered_data)
    
    # Extract email data
    email_data = extract_email_content(deepseek_response)
    
    # Update data with email content
    if len(email_data) >= 2:
        filtered_data.update({
            "email_subject": email_data[0]["subject"].replace("’", "'"),
            "email_content": email_data[0]["body"].replace("’", "'"),
            "followup_email_subject": email_data[1]["subject"].replace("’", "'"),
            "followup_email_content": email_data[1]["body"].replace("’", "'")
        })
    elif len(email_data) == 1:
        filtered_data.update({
            "email_subject": email_data[0]["subject"].replace("’", "'"),
            "email_content": email_data[0]["body"].replace("’", "'"),
        })
    else:
        logging.error("Failed to generate any email content")
    
    # Save data to CSV
    save_to_csv(filtered_data)
    
    # Log progress
    progress_percentage = (current_index / total_count) * 100
    logging.info(f"Progress: {progress_percentage:.1f}% complete ({current_index}/{total_count})")

def search_people():
    logging.info("Starting people search with Apollo API")
    
    # Build search payload from environment variables
    payload = {k: v for k, v in {
        "person_titles": os.getenv("PERSON_TITLES", "").split(","),
        "person_locations": os.getenv("PERSON_LOCATIONS", "").split(","),
        "person_seniorities": os.getenv("PERSON_SENIORITIES", "").split(","),
        "organization_locations": os.getenv("ORGANIZATION_LOCATIONS", "").split(","),
        "q_organization_domains_list": os.getenv("Q_ORGANIZATION_DOMAINS_LIST", "").split(","),
        "contact_email_status": os.getenv("CONTACT_EMAIL_STATUS", "").split(","),
        "organization_ids": os.getenv("ORGANIZATION_IDS", "").split(","),
        "organization_num_employees_ranges": [os.getenv("ORGANIZATION_NUM_EMPLOYEES_RANGES", "")],
        "q_keywords": os.getenv("Q_KEYWORDS", ""),
        "page": int(os.getenv("PAGE", 1)),
        "per_page": int(os.getenv("PER_PAGE", 10))
    }.items() if v and v != [""]}
    
    # Log search parameters
    logging.info(f"Search parameters: {json.dumps(payload, indent=2)}")
    
    try:
        start_time = time.time()
        response = requests.post("https://api.apollo.io/api/v1/mixed_people/search", headers=HEADERS, json=payload)
        elapsed_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            total_people = len(data.get("people", []))
            logging.info(f"Successfully retrieved {total_people} people from Apollo API in {elapsed_time:.2f}s")
            
            # Extract people IDs
            people_ids = [person["id"] for person in data.get("people", [])]
            
            # Process each person
            for idx, people_id in enumerate(people_ids, 1):
                process_people_data(people_id, idx, total_people)
                
        else:
            logging.error(f"Failed to search people: Status {response.status_code}")
            logging.error(f"Response: {response.text[:500]}...")
    except Exception as e:
        logging.error(f"Exception during people search: {str(e)}")

def process_csv_file(csv_path):
    """Process data from an input CSV file."""
    logging.info(f"Starting CSV file processing mode with file: {csv_path}")
    
    if not os.path.exists(csv_path):
        logging.error(f"Input CSV file does not exist: {csv_path}")
        return
    
    try:
        # Read the input CSV file
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        total_rows = len(rows)
        
        # Create output CSV filename
        output_path = f"{os.path.splitext(os.path.basename(csv_path))[0]}_with_email.csv"        
        if os.path.exists(output_path):
            base, ext = os.path.splitext(output_path)
            counter = 1
            while os.path.exists(f"{base}_{counter}{ext}"):
                counter += 1
            output_path = f"{base}_{counter}{ext}"
        
        logging.info(f"Output will be saved to: {output_path}")
        
        # Open output CSV file
        with open(output_path, 'w', newline='', encoding='utf-8') as f_out:
            # Get all field names from the input CSV plus our new email fields
            fieldnames = list(rows[0].keys()) + [
                "Mail Subject", 
                "Main Email", 
                "Second Subject", 
                "Second Email"
            ]
            
            writer = csv.DictWriter(f_out, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            
            # Process each row
            for idx, row in enumerate(rows, 1):
                logging.info(f"Processing row {idx}/{total_rows}: {row.get('First Name', '')} {row.get('Last Name', '')}")
                
                # Prepare data for Deepseek in the same format as we use for Apollo data
                profile_data = {
                    "person": {
                        "first_name": row.get("First Name", ""),
                        "last_name": row.get("Last Name", ""),
                        "title": row.get("Title", ""),
                        "email": row.get("Email", ""),
                        "headline": ""
                    },
                    "organization": {
                        "name": row.get("Company", ""),
                        "city": row.get("Company City", ""),
                        "technology_names": row.get("Technologies", "").split(", ") if row.get("Technologies") else [],
                        "industries": [row.get("Industry", "")] if row.get("Industry") else [],
                        "keywords": row.get("Keywords", "").split(", ") if row.get("Keywords") else [],
                        "estimated_num_employees": row.get("# Employees", ""),
                        "website": row.get("Website", "")
                    }
                }
                
                # Generate email content
                deepseek_response = generate_email_content(profile_data)
                
                # Extract email data
                email_data = extract_email_content(deepseek_response)
                
                # Update row with email content
                if len(email_data) >= 2:
                    row.update({
                        "Mail Subject": email_data[0]["subject"].replace("’", "'"),
                        "Main Email": email_data[0]["body"].replace("’", "'"),
                        "Second Subject": email_data[1]["subject"].replace("’", "'"),
                        "Second Email": email_data[1]["body"].replace("’", "'")
                    })
                elif len(email_data) == 1:
                    row.update({
                        "Mail Subject": email_data[0]["subject"].replace("’", "'"),
                        "Main Email": email_data[0]["body"].replace("’", "'"),
                        "Second Subject": "",
                        "Second Email": ""
                    })
                else:
                    logging.error(f"Failed to generate any email content for row {idx}")
                    row.update({
                        "Mail Subject": "",
                        "Main Email": "",
                        "Second Subject": "",
                        "Second Email": ""
                    })
                
                # Write the updated row to the output CSV
                writer.writerow(row)
                
                # Log progress
                progress_percentage = (idx / total_rows) * 100
                logging.info(f"Progress: {progress_percentage:.1f}% complete ({idx}/{total_rows})")
                
        logging.info(f"CSV processing completed. Output saved to: {output_path}")
        
    except Exception as e:
        logging.error(f"Error processing CSV file: {str(e)}")

if __name__ == "__main__":
    start_time = time.time()
    logging.info("=== Script execution started ===")
    
    try:
        # Determine which mode to run in
        if args.input:
            # CSV input mode
            process_csv_file(args.input)
        else:
            # Apollo API mode
            search_people()
            
        elapsed_time = time.time() - start_time
        logging.info(f"=== Script completed successfully in {elapsed_time:.2f} seconds ===")
    except Exception as e:
        elapsed_time = time.time() - start_time
        logging.error(f"=== Script failed after {elapsed_time:.2f} seconds: {str(e)} ===")