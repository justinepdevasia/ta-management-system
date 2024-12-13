# TA Management System

A comprehensive web application for managing Teaching Assistant (TA) applications, assignments, and evaluations at universities. Built with Flask and Firebase.

## Features

### For Applicants
- Submit TA applications for multiple courses
- Upload CV and provide academic information
- Track application status
- Accept/reject TA offers
- View application history and timeline

### For Staff
- Review TA applications
- Manage course listings and requirements
- Make course recommendations
- Track application statuses
- Generate reports and analytics

### For Committee Members
- View and manage course assignments
- Review staff recommendations
- Make TA selections
- Track acceptance/rejection rates
- Generate performance reports

### For Instructors
- View assigned TAs
- Evaluate TA performance
- Track TA hours
- Generate TA performance reports

## Technology Stack

- **Backend**: Python/Flask
- **Database**: Firebase Realtime Database
- **Storage**: Firebase Cloud Storage
- **Authentication**: Firebase Authentication
- **Frontend**: HTML, TailwindCSS, JavaScript

## Prerequisites

- Python 3.10 or higher
- Firebase project with Realtime Database and Storage enabled
- Node.js and npm (for TailwindCSS)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/ta-management-system.git
cd ta-management-system
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file based on `.env.example`:
```bash
cp .env.example .env
```

5. Configure your Firebase credentials in the `.env` file:
```
FLASK_SECRET_KEY=your_secret_key
FIREBASE_API_KEY=your_api_key
FIREBASE_AUTH_DOMAIN=your_auth_domain
FIREBASE_PROJECT_ID=your_project_id
FIREBASE_STORAGE_BUCKET=your_storage_bucket
FIREBASE_MESSAGING_SENDER_ID=your_messaging_sender_id
FIREBASE_APP_ID=your_app_id
FIREBASE_DATABASE_URL=your_database_url
```

## Running the Application

### Development Mode

```bash
python run.py
```

The application will be available at `http://localhost:5000`

### Production Mode with Docker

1. Build the Docker image:
```bash
docker build -t ta-management-system .
```

2. Run the container:
```bash
docker run -p 8080:8080 ta-management-system
```

The application will be available at `http://localhost:8080`

## Project Structure

```
├── app/
│   ├── routes/            # Route handlers for different user roles
│   ├── templates/         # HTML templates
│   └── utils/            # Utility functions and decorators
├── config/               # Application configuration
├── static/               # Static files (CSS, JS)
└── tests/               # Test files (not included in current version)
```

## Security Features

- Role-based access control
- Firebase Authentication integration
- Secure file upload handling
- Input validation and sanitization
- Session management
- Environment variable configuration

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Commit your changes: `git commit -am 'Add feature'`
4. Push to the branch: `git push origin feature-name`
5. Submit a pull request

## License

This project is licensed under the Apache License 2.0 - see the LICENSE file for details.

## Acknowledgments

- Flask web framework
- Firebase Backend-as-a-Service
- TailwindCSS for styling
- Contributors and maintainers

## Support

For support, please open an issue in the GitHub repository or contact the development team.