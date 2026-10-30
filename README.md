# Amour AI

Amour AI is a next-generation AI companion and roleplay platform built for iOS and Android with Expo (React Native) and a high-performance Django + PostgreSQL backend powered by AWS Bedrock (Llama 3.1 8B).

---

## Features

- **Amour Studio**: Multi-stage avatar creation suite:
  - Custom border palette styling for avatar portraits (Crimson, Violet, Emerald, Amber, Sapphire).
  - AI-assisted persona generation (name, tagline, opener, and memory synthesis via AWS Bedrock Llama 3.1 8B).
  - Markdown roleplay preview with differentiated formatting for speech and descriptive actions.
  - S3 cloud portrait image uploads with automatic base64 fallback.
- **Persistent Companions**:
  - PostgreSQL database of record linking user accounts to avatar identities and chat transcripts.
  - Episodic memory architecture with vector embeddings for semantic recall.
- **Authentication**:
  - JWT-based authentication with token refresh and guest explore mode.
  - Google OAuth integration.
- **Mobile Experience**:
  - Dark mode aesthetic tailored for mobile devices.
  - Fluid bottom navigation and native responsiveness.

---

## Architecture

```
Amour Chat/
├── assets/                  # Brand vectors, custom fonts (Changa One) & app icons
├── backend/                 # Django REST Framework backend
│   ├── amour_backend/       # Django settings and routing
│   ├── authentication/      # User auth, JWT, profile management
│   ├── memory/              # Avatar models, Bedrock generation, S3 uploads
│   └── requirements.txt     # Python backend dependencies
├── src/                     # Expo React Native frontend
│   ├── app/                 # Expo Router file-based screens
│   │   ├── (tabs)/          # Tabs: Explore, Create (Amour Studio), Profile
│   │   ├── login.tsx        # Login screen
│   │   └── signup.tsx       # Sign up screen
│   ├── components/          # Reusable UI components & SVG icons
│   ├── constants/           # Themes, colors, typography, endpoints
│   └── context/             # AuthContext session state
└── app.json                 # Expo app configuration
```

---

## Getting Started

### Prerequisites

- Node.js (v18+)
- Python 3.10+
- PostgreSQL
- AWS Bedrock access (or configured credentials in `.env`)

### 1. Backend Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit backend/.env with your DB and AWS credentials

# Apply migrations
python manage.py migrate

# Run Django development server
python manage.py runserver 0.0.0.0:8000
```

### 2. Frontend Setup

```bash
# Return to root directory
cd ..

# Install dependencies
npm install

# Start Expo development server
npx expo start -c
```

Press `a` to open in Android emulator/device or `i` for iOS simulator.

---

## Type Checking & Quality

```bash
npx tsc --noEmit
```

---

## License

Proprietary / All Rights Reserved.
