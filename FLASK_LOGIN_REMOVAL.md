# Flask-Login Removal Notice

**flask_login removed** — use `user` variable from app.py in all templates.

## Changes Made

- Removed flask_login dependency from the application
- All templates now use the `user` object provided by Microsoft Entra ID authentication
- The `user` object is injected into all template contexts via `render_template()`

## Template Usage

Instead of `current_user`, use the `user` variable:

```jinja2
<!-- Old (flask_login) -->
{% if current_user.is_authenticated %}
{% if current_user.role == 'admin' %}

<!-- New (Microsoft Entra ID) -->
{% if user %}
{% if user and user.is_admin %}
```

## User Object Structure

The `user` object contains Microsoft Graph user data:

```json
{
  "displayName": "Tom Andre Johnsen",
  "mail": "Tom.Andre@gronvoldmaskin.no",
  "is_admin": true
}
```

## Authentication

Authentication is now handled entirely through Microsoft Entra ID (Office 365) with session-based storage.