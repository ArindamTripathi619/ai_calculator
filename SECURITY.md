# Security Policy

## Overview

The AI Calculator is a Flask-based web application that uses Google Gemini API for mathematical problem solving with matplotlib and networkx for diagram generation. We take security seriously and have implemented multiple layers of protection.

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| Latest  |        ☑️          |

## Security Features

### 1. API Security
- **Rate Limiting**: 10 requests per minute, 50 per hour, 200 per day using Flask-Limiter with Redis backend
- **CORS Protection**: Configured to allow only specific domains (aicalculator.devcrewx.tech, devcrewx.tech)
- **Environment Variables**: Sensitive data (API keys, Redis URLs) stored in environment variables

### 2. Code Execution Security
- **Safe Execution Environment**: Matplotlib/NetworkX code runs in restricted globals with only whitelisted functions
- **Input Sanitization**: AI-generated code is cleaned and validated before execution
- **Error Handling**: Comprehensive error handling prevents information disclosure

### 3. Infrastructure Security
- **Production WSGI**: Uses Gunicorn for production deployment
- **Debug Mode**: Disabled in production (`debug=False`)
- **Static File Security**: Proper static file serving with Flask's `send_from_directory`
- **Redis Security**: Secure Redis connection for rate limiting storage

### 4. Data Protection
- **No Persistent Storage**: User drawings are processed in memory and not stored
- **Image Processing**: Base64 images are validated and processed securely
- **Temporary Files**: No temporary files are stored on disk

## Reporting Security Vulnerabilities

We appreciate responsible disclosure of security vulnerabilities.

### How to Report
1. **Do not** create public GitHub issues for security vulnerabilities
2. Send an email to: security@devcrewx.tech
3. Include detailed description of the vulnerability
4. Provide steps to reproduce (if applicable)
5. Include your contact information for follow-up

### What to Include
- Description of the vulnerability
- Steps to reproduce
- Potential impact assessment
- Suggested fix (if available)

### Response Timeline
- **Initial Response**: Within 24 hours
- **Investigation**: Within 72 hours
- **Fix Development**: Within 1 week (depending on severity)
- **Public Disclosure**: After fix is deployed

## Security Best Practices for Users

### For End Users
- Use the application over HTTPS only
- Do not input sensitive personal information in mathematical expressions
- Report any suspicious behavior immediately

### For Developers/Deployers
- Always use environment variables for sensitive configuration
- Deploy with HTTPS/TLS encryption
- Keep dependencies updated regularly
- Monitor rate limiting logs for abuse
- Use strong Redis authentication if exposing Redis publicly
- Regular security audits of the codebase

## Known Security Considerations

### AI Model Security
- **Input Validation**: User drawings are processed by Google Gemini API
- **Output Sanitization**: AI responses are cleaned of potentially harmful content
- **Rate Limiting**: Prevents abuse of the AI service

### Code Generation Security
- **Restricted Environment**: Only matplotlib, numpy, and networkx functions are available
- **No File System Access**: Generated code cannot access the file system
- **Memory Limits**: Execution is contained within the web process

### Network Security
- **CORS**: Properly configured for production domains
- **Rate Limiting**: Prevents DDoS and abuse
- **Input Size Limits**: Canvas data is size-limited

## Security Configuration

### Environment Variables Required
```bash
GEMINI_API_KEY=your_api_key_here
CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
REDIS_URL=redis://localhost:6379
```

### Production Deployment Security
- Use HTTPS/TLS for all connections
- Configure firewall rules appropriately
- Use strong Redis authentication
- Regular dependency updates
- Monitor application logs

## Dependencies Security

We regularly monitor and update dependencies for security vulnerabilities:
- Flask and related packages
- Google Generative AI library
- Matplotlib and NumPy
- NetworkX
- Redis client
- Gunicorn

## Compliance

This application handles:
- User-generated content (mathematical drawings)
- API interactions with Google Gemini
- No personal identifiable information (PII) storage
- No financial or health data

## Security Audit History

- **September 2025**: Initial security implementation with rate limiting, CORS, and safe code execution
- Regular security reviews planned quarterly

## Contact

For security-related inquiries:
- Email: devcrewx@gmail.com
- GitHub: @ArindamTripathi619

## Acknowledgments

We thank the security community for helping us maintain a secure application.
