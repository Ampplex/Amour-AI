# Amour AI — Angular Web Application

This directory contains the standalone web version of **Amour AI**, built with **Angular (v22)** and **TypeScript**. It replicates the exact mobile interface, OLED dark design system, and client-side zero-knowledge encryption architecture of the React Native mobile app, while connecting to the same shared backend.

---

## Architecture & Features

### 1. Shared Backend & Endpoints
The web version shares the same PostgreSQL (Neon) and Django REST backend:
- **Base API URL**: `https://amour-ai-v3e4.onrender.com/api` (with automatic fallback to local `http://127.0.0.1:8000/api`)
- **Authentication**: Email/Password login, Signup with email verification, Password recovery, and Profile picture upload to AWS S3.
- **Companion Memory & Reeve Graph**: Message streaming and memory indexing via `/api/memory/chat/`.
- **Public Feed & Discovery**: `/api/memory/personas/?visibility=public` with double-tap like, follower sync, and community showcase.
- **Persona Studio**: `/api/memory/personas/` with AI Persona Spark generation (`/api/memory/generate-persona/`).

### 2. Zero-Knowledge Memory Security
- Uses the browser's standard **Web Crypto API** (`window.crypto.getRandomValues`, `window.crypto.subtle.digest`).
- Automatically generates and persists a 256-bit client-side encryption key for Reeve Memory Graph (`X-Memory-User-Key`).
- Supports generating a human-readable 12-word recovery phrase, deriving a Key Encryption Key (KEK) via 2,000 SHA-256 iterations, and backing up or restoring encrypted memory keys with `/api/memory/key-backup/`.

### 3. Screen Structure & Navigation
- **Start / Splash Screen**: Animated vector emblem with brand typography.
- **Auth**: Login, Signup, Forgot Password, and Demo User sessions.
- **Tabs Shell**: Bottom navigation bar mirroring the mobile layout:
  1. **Home**: Community Feed with double-tap heart pop animation, floating chat bubble, like counter, and opener preview.
  2. **Personas**: Personal companion roster with All / Private / Public filters, squircle avatars, edit, delete, and direct chat CTA.
  3. **Chats**: Active conversation threads with latest messages and relative timestamps.
  4. **Create (Amour Studio)**: 4-stage creation wizard (Portal, Visuals with S3 photo upload & border colors, Mind & Voice with AI generation, Launch Review & Deploy).
  5. **Profile**: User card, companion reply length preferences (Short, Balanced, Narrative), Memory Security modal, and account management.
- **Full Companion Chat Experience**:
  - Spoken dialogue in quotes (`"..."`) rendered as bright white text.
  - Narration and actions in asterisks (`*...*`) rendered as dim italicized text.
  - Bot response regeneration with variant switching (`< 1/3 >`).
  - In-place editing of messages.
  - Animated typing indicator.

---

## Quick Start

### Run the development server
From the repository root:
```bash
npm run web:app
```
Or directly from the `web/` folder:
```bash
cd web
npm start
```
Navigate to `http://localhost:4200/`.

### Build for production
From the repository root:
```bash
npm run web:build
```
Or from the `web/` folder:
```bash
cd web
npm run build
```
Production assets are generated in `web/dist/web`.
