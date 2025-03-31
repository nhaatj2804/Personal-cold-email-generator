# Apollo API & DeepSeek Email Generator

A web application that automates lead generation and personalized email creation using the Apollo API and DeepSeek AI.

## Features

- **Authentication System**: Secure login with JWT token-based authentication
- **Apollo API Integration**: Search and retrieve detailed contact information
- **DeepSeek AI Email Generation**: Create personalized outreach emails based on prospect data
- **Real-time Progress Updates**: Stream results as they're processed
- **CSV Import/Export**: Process existing CSV contact lists or export search results
- **User-friendly Interface**: Clean, responsive web interface

## Technology Stack

- **Backend**: FastAPI (Python)
- **Authentication**: JWT tokens with cookie support
- **API Integration**: Apollo API for lead data
- **AI Integration**: DeepSeek AI for email generation
- **Frontend**: HTML, JavaScript with SSE (Server-Sent Events) for real-time updates

## Setup and Installation

### Prerequisites

- Python 3.7+
- Apollo API Key
- DeepSeek API Key
- Secret key for JWT token generation

### Installation

1. **Clone the repository**

   ```sh
   git clone https://github.com/yourusername/apollo-deepseek-email.git
   cd apollo-deepseek-email
   ```

2. **Create a virtual environment**

   ```sh
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

3. **Install dependencies**

   ```sh
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   Create a `.env` file in the root directory with the following:

   ```
   APOLLO_API_KEY=your_apollo_api_key
   DEEPSEEK_API_KEY=your_deepseek_api_key
   INITIAL_DEEPSEEK_PROMPT="Your default prompt for email generation"
   SECRET_KEY=your_jwt_secret_key
   ```

5. **Create templates directory**
   Make sure you have a `templates` directory containing `login.html` and `search.html` templates

6. **Create company overview file**
   Create a file named `Nobisoft_Company_Overview.txt` with your company information

## Usage

### Starting the Server

```sh
uvicorn app:app --reload
```

The application will be available at http://localhost:8000

### Authentication

- Navigate to http://localhost:8000/login

### Search People

After logging in, you'll be redirected to the search page where you can:

1. Enter search criteria for Apollo API
2. Customize the email generation prompt
3. Add your personal information for email signatures
4. View results in real-time as they're processed
5. Export results to CSV

### CSV Processing

You can also upload an existing CSV file containing prospect information to generate personalized emails for each contact.

## API Endpoints

### Authentication

- `POST /token` - OAuth2 token endpoint
- `POST /login` - Form-based login
- `GET /logout` - Log out and clear session

### Main Features

- `GET /peoples/` - Search people with Apollo API and generate emails (streaming)
- `GET /person-detail/{person_id}` - Get detailed information for a specific person
- `POST /export-csv/` - Export current results to CSV
- `POST /process-csv/` - Process an uploaded CSV file

## CSV Format

### Required columns for CSV upload:

- First Name
- Last Name
- Title
- Company
- Email
- Seniority
- Departments
- \# Employees
- Industry
- Keywords
- City
- State
- Country
- Company City
- Company State
- Company Country
- Technologies

## Security Considerations

- JWT tokens expire after 60 minutes
- Passwords should be hashed in production environments
- Secure httponly cookies are used for session management

## Customization

### Email Generation Prompt

You can customize the DeepSeek prompt to generate different styles of emails based on your needs. The system combines:

- Your personal information (name, position, contact)
- Company overview from the text file
- Prospect information from Apollo API
- Your custom prompt instructions

## Troubleshooting

- **Authentication Issues**: Check that your JWT secret key is properly set
- **API Errors**: Verify your Apollo API key is valid and rate limits aren't exceeded
- **Email Generation Failures**: Check that your DeepSeek API key is valid
- **CSV Processing Errors**: Ensure your CSV has all the required columns
