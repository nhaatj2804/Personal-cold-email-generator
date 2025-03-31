from typing import Union
import os
import json
import csv
import time
import argparse
import io
import asyncio
import httpx
from dotenv import load_dotenv
from litellm import completion
from fastapi import FastAPI, File, UploadFile, Query, Request, HTTPException, Depends, Form
from fastapi.responses import FileResponse, StreamingResponse, RedirectResponse, JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import shutil
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates  
from fastapi.responses import HTMLResponse
import jwt
from datetime import datetime, timedelta
from typing import Optional

app = FastAPI() 

# Mount static files directory
# app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

# Load environment variables
load_dotenv()

APOLLO_API_KEY = os.getenv("APOLLO_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY") 
CSV_FILENAME = "result.csv"  
INITIAL_DEEPSEEK_PROMPT=os.getenv("INITIAL_DEEPSEEK_PROMPT")
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")  # You should set this in .env
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # Set to 60 minutes for better user experience

# This would typically come from a database
FAKE_USERS_DB = {
    "admin@gmail.com": {
        "username": "admin@gmail.com",
        "password": "Abc@12345"  # In production, use hashed passwords
    }
}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

HEADERS = {
    "accept": "application/json",
    "Cache-Control": "no-cache",
    "Content-Type": "application/json",
    "X-Api-Key": APOLLO_API_KEY
}

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=60)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(request: Request):
    token = None
    # Check for token in cookies first
    if "access_token" in request.cookies:
        token = request.cookies["access_token"].replace("Bearer ", "")
    if not token:
        # Then check for Authorization header
        authorization = request.headers.get("Authorization")
        if authorization and authorization.startswith("Bearer "):
            token = authorization.replace("Bearer ", "")
    
    if not token:
        # Check if it's an API request
        if request.headers.get("accept") == "application/json":
            raise HTTPException(
                status_code=401,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return RedirectResponse(url="/login", status_code=302)
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            # Check if it's an API request
            if request.headers.get("accept") == "application/json":
                raise HTTPException(
                    status_code=401,
                    detail="Could not validate credentials",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return RedirectResponse(url="/login", status_code=302)
    except jwt.PyJWTError:
        # Check if it's an API request
        if request.headers.get("accept") == "application/json":
            raise HTTPException(
                status_code=401,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return RedirectResponse(url="/login", status_code=302)
        
    user = FAKE_USERS_DB.get(username)
    if user is None:
        # Check if it's an API request
        if request.headers.get("accept") == "application/json":
            raise HTTPException(
                status_code=401,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return RedirectResponse(url="/login", status_code=302)
        
    return user

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = FAKE_USERS_DB.get(form_data.username)
    if not user or form_data.password != user["password"]:  # In production, verify hashed password
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/login")
async def login_form(credentials: dict):
    user = FAKE_USERS_DB.get(credentials.get("username"))
    if not user or credentials.get("password") != user["password"]:  # In production, verify hashed password
        return JSONResponse(status_code=401, content={"detail": "Invalid credentials"})
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    
    response = JSONResponse(content={"success": True, "redirect": "/search"})
    # Convert minutes to seconds for cookie expiration
    expires_in_seconds = ACCESS_TOKEN_EXPIRE_MINUTES * 60
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=expires_in_seconds,
        expires=expires_in_seconds,
    )
    return response

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie("access_token")
    return response

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse(url="/login")

@app.get("/search", response_class=HTMLResponse)
async def search_page(request: Request):
    token = None
    if "access_token" in request.cookies:
        token = request.cookies["access_token"].replace("Bearer ", "")
    
    if not token:
        return RedirectResponse(url="/login", status_code=302)
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None or not FAKE_USERS_DB.get(username):
            return RedirectResponse(url="/login", status_code=302)
    except jwt.PyJWTError:
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("search.html", {"request": request})

@app.get("/peoples/", response_class=StreamingResponse)
async def search_people(
    request: Request,
    person_titles: str = Query("", description="Comma-separated job titles"),
    person_locations: str = Query("", description="Comma-separated locations"),
    person_seniorities: str = Query("", description="Comma-separated seniority levels"),
    organization_locations: str = Query("", description="Comma-separated organization locations"),
    q_organization_domains_list: str = Query("", description="Comma-separated organization domains"),
    contact_email_status: str = Query("", description="Comma-separated email statuses"),
    organization_ids: str = Query("", description="Comma-separated organization IDs"),
    organization_num_employees_ranges: str = Query("", description="Comma-separated employee ranges"),
    q_keywords: str = Query("", description="Search keywords"),
    page: int = Query(1, description="Page number"),
    per_page: int = Query(10, description="Number of results per page"),
    deepseek_prompt: str = Query("", description="Deepseek prompt"),
    your_name: str = Query("", description="Your name"),
    your_position: str = Query("", description="Your position"),
    your_contact: str = Query("", description="Your contact information")
):
    """Search for people using Apollo API with streaming progress updates."""
    async def generate():
        # Get token from cookie
        token = None
        if "access_token" in request.cookies:
            token = request.cookies["access_token"].replace("Bearer ", "")
        
        # Verify token
        if not token:
            yield ("data: " + json.dumps({"redirect": "/login"}) + "\n\n").encode('utf-8')
            return
        
        try:
            jwt_payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username = jwt_payload.get("sub")
            if not username or not FAKE_USERS_DB.get(username):
                yield "data: " + json.dumps({"redirect": "/login"}) + "\n\n"
                return
        except jwt.PyJWTError:
            yield "data: " + json.dumps({"redirect": "/login"}) + "\n\n"
            return

        # Build search payload
        search_payload = {k: v for k, v in {
            "person_titles": person_titles.split(",") if person_titles else [],
            "person_locations": person_locations.split(",") if person_locations else [],
            "person_seniorities": person_seniorities.split(",") if person_seniorities else [],
            "organization_locations": organization_locations.split(",") if organization_locations else [],
            "q_organization_domains_list": q_organization_domains_list.split(",") if q_organization_domains_list else [],
            "contact_email_status": contact_email_status.split(",") if contact_email_status else [],
            "organization_ids": organization_ids.split(",") if organization_ids else [],
            "organization_num_employees_ranges": [organization_num_employees_ranges] if organization_num_employees_ranges else [],
            "q_keywords": q_keywords,
            "page": page,
            "per_page": per_page
        }.items() if v and v != [""]}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.apollo.io/api/v1/mixed_people/search",
                headers=HEADERS,
                json=search_payload
            )
        
        if response.status_code == 200:
            data = response.json()
            people_ids = [person["id"] for person in data.get("people", [])]
            total_people = len(people_ids)
            results = []

            async def process_person(people_id):
                person_data = await fetch_person_data(people_id)
                if person_data:
                    generated_email_content = await generate_email_content(person_data, deepseek_prompt, your_name, your_position, your_contact)
                    return {
                        "person_data": person_data,
                        "generated_email_content": generated_email_content
                    }
                return None
            
            results = []
            for index, people_id in enumerate(people_ids):
                result = await process_person(people_id)
                if result:
                    results.append(result)
                
                # Calculate and send progress with chunked encoding
                progress = ((index + 1) / total_people) * 100
                response_data = {
                    "success": True,
                    "in_progress": True,
                    "progress": progress,
                    "total_people": total_people,
                    "results": results
                }
                progress_update = "data: " + json.dumps(response_data) + "\n\n"
                yield progress_update.encode('utf-8')
                await asyncio.sleep(0.1)  # Small delay to ensure updates are sent

            # Send final response with chunked encoding to prevent buffering
            final_response = "data: " + json.dumps({
                "success": True,
                "in_progress": False,
                "progress": 100,
                "total_people": total_people,
                "results": results
            }) + "\n\n"
            yield final_response.encode('utf-8')
        elif response.status_code == 401:
            yield ("data: " + json.dumps({"redirect": "/login"}) + "\n\n").encode('utf-8')
        else:
            print(response)
            error_response = "data: " + json.dumps({
                "error": f"API request failed with status {response.status_code}",
                "details": response.text[:500]
            }) + "\n\n"
            yield error_response.encode('utf-8')

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.get("/person-detail/{person_id}")
async def fetch_person_data(person_id):
    url = f"https://api.apollo.io/api/v1/people/match?id={person_id}"
    
    start_time = time.time()
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=HEADERS)
    elapsed_time = time.time() - start_time
    
    if response.status_code == 200:
        data = response.json()
        person = data.get("person", {})
        organization = person.get("organization", {})
        
        result = {
            "first_name": person.get("first_name"),
            "last_name": person.get("last_name"),
            "title": person.get("title"),
            "headline": person.get("headline"),
            "email": person.get("email"),
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
        return result
    elif response.status_code == 401:
        return RedirectResponse(url="/login", status_code=302)
    else:
        return {"error": f"API request failed with status {response.status_code}"}

async def generate_email_content(profile_data, deepseek_prompt,your_name,your_position,your_contact_information):
    person_name = f"{profile_data['first_name']} {profile_data['last_name']}"
    my_staff_info = f" ,knowing my name:{your_name}, my position:{your_position}, my contact information:{your_contact_information}"
    with open("Nobisoft_Company_Overview.txt", "r") as file:
        company_overview = file.read()
    my_company_overview = f" and knowing my company overview:{company_overview}"
    content = (
        f"Here is the profile data: {profile_data}. The result should only be in JSON format like this:\n"
        "[\n"
        "    {\n"
        "        \"Mail Subject\": \"Hey John, Special Offer!\",\n"
        "        \"Main Email\": \"Hey John, we have an exclusive discount for Acme Corp!\"\n"
        "    },\n"
        "    {\n"
        "        \"Second Subject\": \"Following up on my last email\",\n"
        "        \"Second Email\": \"Hey John, just checking if you saw my last email about the Acme Corp discount!\"\n"
        "    }\n"
        "]"
    )
    
    start_time = time.time()
    response = completion(
        model="deepseek/deepseek-chat",
        messages=[{"role": "user", "content": INITIAL_DEEPSEEK_PROMPT+my_staff_info+my_company_overview+deepseek_prompt+content}]
    )
    content_text = response["choices"][0]["message"]["content"].replace("'","'")
    
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
    elapsed_time = time.time() - start_time

    return parsed_content

@app.post("/export-csv/")
async def export_csv(request: Request, current_user: dict = Depends(get_current_user)):
    """Export search results to CSV without calling the API again."""
    # The frontend will send the current results as JSON in the request body
    data = await request.json()
    results = data.get("results", [])
    
    # Create a StringIO object to write CSV data
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header row
    writer.writerow([
        "EMAIL", "Website", "First Name", "Last Name", "Title", "Company",
        "Mail Subject", "Main Email", "Second Subject", "Second Email"
    ])
    
    # Write data rows
    for result in results:
        person_data = result.get("person_data", {})
        email_content = result.get("generated_email_content", [])
        
        first_email = email_content[0] if len(email_content) > 0 else {}
        second_email = email_content[1] if len(email_content) > 1 else {}
        
        organization = person_data.get("organization", {})
        
        writer.writerow([
            person_data.get("email", ""),
            organization.get("website", ""),
            person_data.get("first_name", ""),
            person_data.get("last_name", ""),
            person_data.get("title", ""),
            organization.get("name", ""),
            first_email.get("Mail Subject", ""),
            first_email.get("Main Email", ""),
            second_email.get("Second Subject", ""),
            second_email.get("Second Email", "")
        ])
    
    # Reset the pointer to the beginning of the StringIO object
    output.seek(0)
    
    # Return the CSV file as a streaming response
    current_date = time.strftime("%Y-%m-%d")
    filename = f"result_{current_date}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.post("/process-csv/")
async def process_csv(
    current_user: dict = Depends(get_current_user),
    deepseek_prompt: str = Form("", description="Deepseek prompt"),
    your_name: str = Form("", description="Your name"),
    your_position: str = Form("", description="Your position"),
    your_contact: str = Form("", description="Your contact information"),
    file: UploadFile = File(...)
):
    """Process CSV file with error handling and stream progress updates."""
    if not file.filename.lower().endswith('.csv'):
        return JSONResponse(
            status_code=400,
            content={
                "error": True,
                "message": "Uploaded file must be a CSV file",
                "type": "file_type_error"
            }
        )
    temp_file_path = f"temp_{int(time.time())}.csv"

    try:
        # Save the uploaded file
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        results = []
        with open(temp_file_path, "r", encoding="utf-8-sig") as csvfile:
            reader = csv.DictReader(csvfile)

            required_columns = [
                "First Name", "Last Name", "Title", "Company", "Email", "Seniority",
                "Departments", "# Employees", "Industry", "Keywords", "City", "State",
                "Country", "Company City", "Company State", "Company Country", "Technologies"
            ]

            missing_columns = [col for col in required_columns if col not in reader.fieldnames]
            if missing_columns:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": True,
                        "message": f"Missing required columns: {', '.join(missing_columns)}",
                        "type": "missing_columns",
                        "missing_columns": missing_columns
                    }
                )

            total_rows = sum(1 for _ in open(temp_file_path)) - 1  # Count rows (excluding header)
            processed = 0

            csvfile.seek(0)
            next(reader)  # Skip header row

            for row in reader:
                processed += 1
                
                if not all(row.get(col) for col in required_columns):
                    continue  # Skip invalid rows
                
                profile_data = {
                    "first_name": row.get("First Name", ""),
                    "last_name": row.get("Last Name", ""),
                    "title": row.get("Title", ""),
                    "email": row.get("Email", ""),
                    "organization": {
                        "name": row.get("Company", ""),
                        "city": row.get("Company City", ""),
                        "estimated_num_employees": row.get("# Employees", ""),
                        "website_url": row.get("Technologies", ""),
                        "industries": [row.get("Industry", "")] if row.get("Industry") else [],
                        "keywords": row.get("Keywords", "").split(", ") if row.get("Keywords") else [],
                        "technology_names": row.get("Technologies", "").split(", ") if row.get("Technologies") else []
                    }
                }
                
                # Simulate generating email content
                email_content = await generate_email_content(profile_data, deepseek_prompt, your_name, your_position, your_contact)

                first_email = email_content[0] if len(email_content) > 0 else {}
                second_email = email_content[1] if len(email_content) > 1 else {}

                row_with_email = row.copy()
                row_with_email["Mail Subject"] = first_email.get("Mail Subject", "")
                row_with_email["Main Email"] = first_email.get("Main Email", "")
                row_with_email["Second Subject"] = second_email.get("Second Subject", "")
                row_with_email["Second Email"] = second_email.get("Second Email", "")

                results.append(row_with_email)

        if not results:
            return JSONResponse(
                status_code=400,
                content={
                    "error": True,
                    "message": "No valid rows could be processed from the CSV",
                    "type": "no_valid_rows"
                }
            )

        # Generate output CSV file
        output = io.StringIO()
        fieldnames = list(results[0].keys()) if results else []
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
        output.seek(0)

        os.remove(temp_file_path)  # Clean up temp file
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "total_rows": total_rows,
                "processed": processed,
                "status": "complete",
                "csv_content": output.getvalue(),
                "filename": f"processed_results_{time.strftime('%Y-%m-%d')}.csv"
            }
        )

    except Exception as e:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise HTTPException(
            status_code=500,
            detail={
                "error": True,
                "message": f"Unexpected error processing CSV: {str(e)}",
                "type": "unexpected_error"
            }
        )