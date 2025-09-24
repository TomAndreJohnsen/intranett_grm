# GRM Intranet Application - Project Overview

## Project Overview

The GRM Intranet Application is a comprehensive internal web platform built for GRM's employees to manage daily operations, collaborate, and stay informed. The application serves as a centralized hub for document management, task tracking, calendar events, newsletters, and supplier information.

### Key Features

- **Dashboard**: Central hub displaying recent newsletters, upcoming tasks, calendar events, and quick navigation links
- **Document Management**: Organized file storage with user-created tags, comments, and folder-based categorization (Salg, Verksted, HMS, IT, Varemottak)
- **Task Management**: Create, assign, and track tasks with priority levels, status updates, and completion history
- **Calendar System**: Event scheduling with location, responsible users, and integration capabilities
- **Newsletter System**: Company-wide communications from leadership with draft/published status
- **Supplier Management**: Vendor contact information and relationship management (admin-only)
- **Authentication**: Secure Microsoft Entra ID (Azure AD) integration for single sign-on
- **Role-based Access**: Admin and standard user permissions with appropriate feature restrictions

## Tech Stack

### Backend
- **Python 3.x**: Core programming language
- **Flask 2.3.3**: Lightweight web framework
- **Jinja2 3.1.6**: Template engine for dynamic HTML rendering
- **SQLite**: Embedded database for data persistence

### Supporting Libraries
- **Flask-Session 0.8.0**: Server-side session management
- **MSAL 1.33.0**: Microsoft Authentication Library for Entra ID integration
- **Werkzeug 2.3.7**: WSGI utilities and development server
- **python-dotenv 1.1.1**: Environment variable management
- **requests 2.32.5**: HTTP library for external API calls

### Frontend
- **HTML5/CSS3**: Modern web standards
- **Vanilla JavaScript**: Client-side interactivity without heavy frameworks
- **Font Awesome**: Icon library for consistent UI elements
- **Responsive Design**: Mobile-friendly layouts with CSS Grid and Flexbox

## Database Schema

### Database Type
- **SQLite**: File-based database (`database.db`) for simplicity and portability

### Main Tables

#### Core Tables
- **users**: User profiles, authentication data, admin flags
- **documents**: File storage with metadata, folder organization, comments
- **user_tags**: Custom tags created by users with color coding
- **document_tags**: Many-to-many relationship between documents and tags
- **tasks**: Task management with assignment, priority, status, and history tracking
- **calendar_events**: Event scheduling with location and responsible user data
- **newsletters**: Company communications with draft/published status
- **suppliers**: Vendor management (admin-only access)

#### Relationships
- **Users → Documents**: 1:N (creator relationship)
- **Users → Tasks**: 1:N (assignee relationship)
- **Users → Tags**: 1:N (creator relationship)
- **Documents → Tags**: N:M (via document_tags junction table)
- **Users → Events**: 1:N (responsible user relationship)

### Migration Considerations
- Database schema has evolved from predefined tags to user-created tags
- Migration scripts handle data preservation during schema updates
- Foreign key constraints with CASCADE deletion for data integrity

## Authentication & Authorization

### Microsoft Entra ID Integration
- **OAuth 2.0 Flow**: Standard authorization code flow
- **MSAL Library**: Microsoft's official authentication library
- **Single Sign-On**: Seamless integration with existing Microsoft 365 accounts
- **Token Management**: Automatic token refresh and validation

### Session Handling
- **Flask-Session**: Server-side session storage in filesystem
- **Secure Cookies**: HttpOnly, SameSite, and optional Secure flags
- **Session Persistence**: Configurable session lifetime and storage

### Role & Permissions
- **Admin Users**: Defined via `ADMIN_UPNS` environment variable
- **Standard Users**: Default role with limited administrative access
- **Feature Access**: Role-based UI and API endpoint restrictions
- **Data Security**: Users can only edit their own content (except admins)

## Hosting & Deployment

### Current Development Setup
- **Local Development**: Flask development server (`python3 main.py`)
- **Alternative Startup**: `python3 start.py` wrapper script
- **Port Configuration**: Default localhost:5000

### Virtual Environment
```bash
# Setup virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Environment Configuration
- **Environment File**: `.env` for sensitive configuration
- **Example Template**: `.env.example` for setup guidance
- **Required Variables**:
  - `MS_CLIENT_ID`: Microsoft application ID
  - `MS_CLIENT_SECRET`: Microsoft application secret
  - `MS_TENANT_ID`: Microsoft tenant ID
  - `FLASK_SECRET_KEY`: Application secret key
  - `ADMIN_UPNS`: Comma-separated admin email addresses

### Production Deployment Plans
- **WSGI Server**: Gunicorn or uWSGI for production
- **Reverse Proxy**: Nginx for static file serving and SSL termination
- **Alternative**: Windows Service deployment for internal hosting
- **Database**: Consider PostgreSQL for production scaling
- **Security**: HTTPS enforcement, security headers, rate limiting

## File Structure

### Root Level
```
intranett_grm/
├── main.py                 # Main application file with all routes and logic
├── start.py               # Alternative startup script
├── requirements.txt       # Python dependencies
├── database.db           # SQLite database file
├── .env                  # Environment variables (not in git)
├── .env.example          # Environment template
├── config.py             # Configuration classes
└── logo.png              # Company branding
```

### Application Structure
```
├── app/                   # Modular application structure (legacy)
│   ├── models/           # Database models
│   ├── routes/           # Route blueprints
│   ├── templates/        # Jinja2 templates
│   ├── static/           # CSS, JS, images
│   └── utils/            # Helper functions
├── templates/            # Main template directory
│   ├── base.html         # Base template with common layout
│   ├── dashboard.html    # Main dashboard
│   ├── documents.html    # Document management interface
│   ├── tasks.html        # Task management
│   ├── calendar.html     # Calendar interface
│   ├── newsletter.html   # Newsletter management
│   └── suppliers.html    # Supplier management
├── static/               # Static assets
│   ├── css/              # Stylesheets
│   ├── js/               # JavaScript files
│   └── logo.png          # Company logo
├── uploads/              # User uploaded files
│   ├── salg/             # Sales documents
│   ├── verksted/         # Workshop documents
│   ├── hms/              # Health & Safety documents
│   ├── it/               # IT documents
│   └── varemottak/       # Receiving documents
└── flask_session/        # Server-side session storage
```

## Development Workflow

### Git Strategy
- **Main Branch**: `main` for stable releases
- **Feature Branches**: Individual features developed in separate branches
- **Commit Messages**: Descriptive commits with context
- **Rollback Capability**: Git history maintained for easy rollbacks

### Dependency Management
```bash
# Install dependencies
pip install -r requirements.txt

# Update dependencies
pip freeze > requirements.txt
```

### Database Management
```bash
# Initialize database (automatic on first run)
python3 main.py

# Reset database (delete database.db and restart)
rm database.db && python3 main.py
```

### Testing Approach
- **Manual Testing**: Comprehensive user acceptance testing
- **Beta Environment**: Internal testing before production
- **Unit Tests**: Planned for future implementation
- **Integration Tests**: API endpoint validation planned

## Next Steps & Roadmap

### Features in Progress
- **User Profiles**: Personal settings and profile management
- **Task Archive**: Completed task history and analytics
- **Dashboard Improvements**: Enhanced quick actions and widgets
- **Mobile Optimization**: Improved mobile user experience

### Planned Improvements

#### Integration Features
- **Outlook Sync**: Two-way calendar synchronization
- **Social Media Integration**: News feed from company social accounts
- **Email Notifications**: Task assignments and deadline reminders

#### Technical Enhancements
- **Code Organization**: Refactor monolithic `main.py` into modular blueprints
- **Production Hosting**: Deploy to production environment with proper scaling
- **Database Optimization**: Query optimization and potential PostgreSQL migration
- **Security Hardening**: Enhanced security headers, CSRF protection, rate limiting

#### User Experience
- **Advanced Search**: Full-text search across all content types
- **Bulk Operations**: Multi-select for documents and tasks
- **Export Functionality**: Data export for reporting and backup
- **Real-time Updates**: WebSocket integration for live notifications

### Technical Debt
- **Monolithic Structure**: Break down `main.py` into focused modules
- **Error Handling**: Comprehensive error handling and logging
- **Documentation**: API documentation and deployment guides
- **Performance**: Database indexing and query optimization

## Configuration Reference

### Environment Variables
```bash
# Microsoft Entra ID Configuration
MS_CLIENT_ID=your-application-id
MS_CLIENT_SECRET=your-client-secret
MS_TENANT_ID=your-tenant-id

# Application Configuration
FLASK_SECRET_KEY=your-secret-key
APP_BASE_URL=http://localhost:5000
ADMIN_UPNS=admin1@company.com,admin2@company.com

# Session Configuration
SESSION_TYPE=filesystem
SESSION_COOKIE_SECURE=false
SESSION_COOKIE_SAMESITE=Lax
```

### Running the Application
```bash
# Method 1: Direct execution
python3 main.py

# Method 2: Using start script
python3 start.py

# Method 3: Flask development server
flask --app main run --debug
```

---

*Generated on: September 24, 2025*
*Version: 1.0*
*Contact: Development Team*