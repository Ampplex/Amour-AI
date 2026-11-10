# Amour AI — Comprehensive System Architecture & Deep Engineering Specification

Amour AI is a production-grade, multimodal AI companion and roleplay application built for iOS and Android. It integrates an **Expo React Native** frontend with a high-performance **Django REST Framework** backend, utilizing **Neon Lakebase PostgreSQL** as the persistent relational source of truth, **AWS S3** for media asset storage, **Reeve / Neo4j** for graph-based episodic memory, and **Amazon Bedrock Runtime (Mistral Large v1)** for the Story Director and Response Generator, with optional provider-level Groq compatibility.

---

## Table of Contents

1. [High-Level Architectural Blueprint](#1-high-level-architectural-blueprint)
2. [Frontend Architecture & Component Deep Dive](#2-frontend-architecture--component-deep-dive)
   - [2.1 Navigation & Routing Architecture](#21-navigation--routing-architecture)
   - [2.2 Global State & Context Providers](#22-global-state--context-providers)
   - [2.3 Core Application Tabs](#23-core-application-tabs)
   - [2.4 Interactive Modal Components](#24-interactive-modal-components)
   - [2.5 Service & Networking Layer](#25-service--networking-layer)
3. [Backend Architecture & Data Engineering](#3-backend-architecture--data-engineering)
   - [3.1 Neon Lakebase PostgreSQL Data Architecture](#31-neon-lakebase-postgresql-data-architecture)
   - [3.2 User Authentication & Profile Synchronization](#32-user-authentication--profile-synchronization)
   - [3.3 AWS S3 Object Storage Pipeline](#33-aws-s3-object-storage-pipeline)
   - [3.4 Memory & Community Feed Subsystems](#34-memory--community-feed-subsystems)
4. [Inference Engine, Prompt Caching & KV Cache Architecture](#4-inference-engine-prompt-caching--kv-cache-architecture)
   - [4.1 Prefix Stability & KV Cache Maximization](#41-prefix-stability--kv-cache-maximization)
   - [4.2 30-Minute Temporal Window Bucketing](#42-30-minute-temporal-window-bucketing)
   - [4.3 Smart Ingestion Filter (Cost & Latency Optimization)](#43-smart-ingestion-filter-cost--latency-optimization)
   - [4.4 Single-Query Combined Memory Retrieval](#44-single-query-combined-memory-retrieval)
   - [4.5 Automated Multi-Model Cascading Failover](#45-automated-multi-model-cascading-failover)
5. [Behavioral Guardrails, Immersion & Reconciliation Protocol](#5-behavioral-guardrails-immersion--reconciliation-protocol)
   - [5.1 Absolute Zero-Emoji Enforcement](#51-absolute-zero-emoji-enforcement)
   - [5.2 Fourth-Wall & Immersion Boundary](#52-fourth-wall--immersion-boundary)
   - [5.3 Non-Technical Domain Protection](#53-non-technical-domain-protection)
   - [5.4 Multi-Stage Realistic Reconciliation Protocol](#54-multi-stage-realistic-reconciliation-protocol)
6. [Component-by-Component Engineering Reference](#6-component-by-component-engineering-reference)
7. [Security, Performance & Deployment Standards](#7-security-performance--deployment-standards)

---

## 1. High-Level Architectural Blueprint

```mermaid
flowchart TD
    subgraph Client ["Expo React Native Client (iOS / Android)"]
        UI_Home["Community Feed (Snap Reels)"]
        UI_Personas["Persona Catalog & Search"]
        UI_Studio["Amour Studio (Avatar Creator)"]
        UI_Profile["User Profile & S3 Avatar"]
        UI_Chat["Companion Chat Modal"]
        UI_Detail["Persona Details Modal"]
        UI_Preview["Full-Screen DP Preview"]
        
        AuthCtx["AuthContext (JWT + Google OAuth)"]
        AlertCtx["AlertContext (Semantic Modals)"]
        NetFail["Candidate URLs Network Failover"]
    end

    subgraph Backend ["Django REST Framework Backend (Port 8000)"]
        AuthApp["authentication App (User, S3 Upload, Profile)"]
        MemApp["memory App (Persona, Chat, Feed, Likes, Follows, Reeve LTM)"]
        RespGen["response_generator (Prompt Cache & LLM Engine)"]
    end

    subgraph Storage ["Cloud Infrastructure & Databases"]
        NeonPG[("Neon Lakebase PostgreSQL")]
        S3Bucket[("AWS S3: reeve-devpilot-downloads")]
        ReeveGraph[("Reeve / Neo4j Episodic Graph")]
        Bedrock["AWS Bedrock Runtime (Mistral Large v1 chat inference + memory extraction)"]
        Groq["Groq (optional legacy provider)"]
    end

    Client -->|REST API over ADB / LAN| Backend
    AuthApp -->|Connection Pooling| NeonPG
    AuthApp -->|Direct Boto3 Stream| S3Bucket
    MemApp -->|Relational Queries| NeonPG
    ReeveSvc -->|Smart Ingest & Combined Query| ReeveGraph
    ReeveGraph -.->|Knowledge Graph Extraction| Bedrock
    RespGen -->|Story Director + Response Generator| Bedrock
    RespGen -->|KV-Cache Stable Prefixes| Bedrock
```

---

## 2. Frontend Architecture & Component Deep Dive

The frontend is built using **React Native 0.88.1** within the **Expo SDK 58** ecosystem, adopting strict mobile-first design patterns, zero third-party UI framework bloat, and fully native SVG graphics via `react-native-svg`.

### 2.1 Navigation & Routing Architecture
Navigation is driven entirely by **Expo Router v58** with file-based routing in `src/app/`:
- **`src/app/_layout.tsx`**:
  - The root entry point of the app.
  - Loads brand typography (`ChangaOne-Regular.ttf`) asynchronously using `expo-font`.
  - Mounts global providers: `AlertProvider` (for semantic alerts) and `AuthProvider` (for user session management).
  - Employs a dark-theme `Stack` navigator with custom slide/fade transitions and `headerShown: false`.
- **`src/app/index.tsx`**:
  - Acts as the central state-based routing guard.
  - Inspects `isAuthReady` and `user` state from `AuthContext`.
  - While auth initializes, displays a brand splash with `AmourLogoVector`.
  - If authenticated, transitions to `/(tabs)`; otherwise, redirects cleanly to `/login`.
- **`src/app/(tabs)/_layout.tsx`**:
  - Configures the custom bottom navigation bar with 4 tabs:
    1. **Home (`index.tsx`)**: Global community discovery feed.
    2. **Personas (`personas.tsx`)**: Categorized catalog and personal companions.
    3. **Create (`create.tsx`)**: Amour Studio creation suite.
    4. **Profile (`profile.tsx`)**: User identity, username management, and S3 avatar.
  - Implements adaptive vertical heights: 88px on iOS (respecting the Home Indicator) and 64px on Android.
  - Employs custom SVG icons (`HomeIcon`, `PersonasIcon`, `PlusCircleIcon`, `ProfileIcon`) that dynamically adapt stroke and fill on active tab focus.

---

### 2.2 Global State & Context Providers

#### `src/context/AuthContext.tsx`
Manages the user's complete authentication lifecycle, profile hydration, and network sync:
1. **Google Native Sign-In**:
   - Integrates `@react-native-google-signin/google-signin` with `webClientId: 665738151857-...`.
   - Checks Play Services availability on Android; gracefully falls back to `WebBrowser.openAuthSessionAsync` on unsupported platforms.
2. **PostgreSQL Hydration & Session Restoration**:
   - On app boot, executes silent sign-in (`signInSilently()`).
   - Hydrates extended account details (unique username, S3 profile picture, display name) from `GET /api/auth/profile/?user_id={id}` across candidate network endpoints.
3. **Profile Operations**:
   - `updateProfile({ username, name, picture })`: Dispatches `PATCH /api/auth/profile/` with inline uniqueness and format validation.
   - `uploadProfilePicture({ base64 })`: Sends raw base64 data to `POST /api/auth/profile/upload-picture/` for direct AWS S3 streaming.
4. **Resilient Network Discovery (`CANDIDATE_URLS`)**:
   - Iterates through a prioritized sequence of fallback endpoints (`http://192.168.1.4:8000/api`, `http://127.0.0.1:8000/api`, LAN IPs) ensuring seamless communication whether connected via wireless ADB, USB port forwarding, or local Wi-Fi.

#### `src/context/AlertContext.tsx`
Provides an imperative, non-blocking modal alert system (`showAlert(title, message, buttons, type)`) replacing jarring native `Alert.alert` dialogs. Displays semantic SVG iconography (Danger, Warning, Success) with full theme integration.

---

### 2.3 Core Application Tabs

#### `src/app/(tabs)/index.tsx` — Community Feed
- **TikTok/Reels Style Vertical Snapping**: Uses a `FlatList` with `pagingEnabled={true}` and `snapToInterval={height}` for an immersive full-screen experience.
- **Dynamic Persona Cards**:
  - Displays high-resolution persona portrait media with ambient gradient overlays.
  - Persona tagline and opening roleplay monologue.
  - Interactive social engagement: Real-time like counter with optimistic UI updates and backend synchronization (`POST /api/memory/like/`).
  - Publisher Attribution Header: Shows creator name, `@username`, and custom avatar. Tapping opens the creator's full `PublisherProfileModal`.
  - 1-Tap Dialogue Launcher: "Chat with {Persona}" button immediately mounts `CompanionChatModal`.

#### `src/app/(tabs)/personas.tsx` — Companion Catalog
- **Dual Section Hierarchy**:
  1. *My Companions*: Displays all personas created by the authenticated user with quick edit/delete actions.
  2. *Community Companions*: Explores globally published community personas.
- **Search & Filter Engine**: Real-time client-side search across persona names, taglines, and publishers.
- **Detailed Sheet Trigger**: Tapping any persona card opens `PersonaDetailModal` displaying the character's backstory and memory parameters.

#### `src/app/(tabs)/create.tsx` — Amour Studio
- **Multi-Step Creator Pipeline**:
  - Name, Tagline, Category, and Visibility (Community vs. Private).
  - Palette Customizer: Choice of vibrant accent border colors (Crimson `#F43F5E`, Violet `#8B5CF6`, Emerald `#10B981`, Amber `#F59E0B`, Sapphire `#3B82F6`).
  - Avatar Photo Picker: Uses `expo-image-picker` with 1:1 cropping and automatic S3 upload.
- **AI Brain Assistant**: "Generate with AI" button calls AWS Bedrock to automatically synthesize an immersive romantic persona backstory, traits, and opening conversational greeting.
- **Roleplay Monologue Preview**: Live Markdown preview styling speech vs. descriptive actions.

#### `src/app/(tabs)/profile.tsx` — User Profile & Settings
- **Consumer-Centric Design**: Completely free of developer clutter, database strings, or AWS debug labels.
- **User Identity Display**:
  - Clean avatar circle with fallback initials.
  - Display Name (`user.name`).
  - Unique Username (`@{username}`) in an accent badge.
  - Email address (`user.email`).
- **Interactive Edit Profile Modal**:
  - Centered avatar with camera badge button triggering image picker and instant S3 upload with loading spinner.
  - Username input with fixed `@` prefix, real-time regex sanitization (`[a-z0-9_]`), 3-30 character limits, and inline duplicate error display returned from PostgreSQL.
  - Display name text input.
  - Persona Sync Guarantee: Saving updates profile info and automatically updates publisher credits across all community personas created by this user.

---

### 2.4 Interactive Modal Components

#### `src/components/CompanionChatModal.tsx` — Real-Time Roleplay Dialogue
- **Adaptive Floating Keyboard**:
  - Uses `Keyboard.addListener` (`keyboardWillShow` / `keyboardDidShow`) to calculate exact keyboard height.
  - Elevates the message input bar dynamically above the keyboard on both Android and iOS without layout jitter.
- **Chat Dialogue Header**:
  - **Persona Avatar Squircle (DP)**: Interactive touchable. Tapping immediately launches `ImagePreviewModal` for full-screen photo inspection.
  - **Persona Name & "Online · Details"**: Interactive touchable with an `(i)` badge. Tapping opens `PersonaDetailModal` to review character mind and backstory.
- **Message Stream & Markdown Parsing**:
  - Renders user bubbles (vibrant purple `#8B5CF6`) and companion bubbles (dark slate `#181822`).
  - Integrates `MarkdownText.tsx` to distinguish conversational dialogue from roleplay stage actions (`*softly whispers*` in italicized, muted lavender).
- **Typing Indicator**:
  - Native `Animated` looping 3-dot pulse animation running at 60fps.
- **Paginated History Loading**:
  - Loads past conversations in pages of 30 messages. "Load earlier messages" header smoothly prepends older dialogue without losing scroll position.

#### `src/components/ImagePreviewModal.tsx` — Full-Screen Persona DP Viewer
- Dedicated full-screen modal with pure black backdrop (`rgba(0, 0, 0, 0.95)`).
- Centered high-resolution image scaled with `resizeMode="contain"`.
- Displays persona name, tagline, and prominent circular close (`X`) button.
- Dismissable via backdrop tap, top close button, or Android hardware back button.

#### `src/components/PersonaDetailModal.tsx` — Character Mind & Memory Inspector
- Hero portrait section with accent border. Tapping avatar opens `ImagePreviewModal`.
- Public/Community vs. Private badge, creator handle, and creation date.
- Opening Dialogue / Scenario review.
- Persona Memory Editor: Allows creators to view and edit the character's long-term memory prompt, saving changes back to PostgreSQL and the Reeve knowledge graph.

#### `src/components/PublisherProfileModal.tsx` — Creator Showcase
- Displays creator banner, avatar, follower count, and total published companions.
- Optimistic Follow/Unfollow toggle syncing with `POST /api/memory/follow/`.
- Interactive grid of all personas published by this creator.

---

### 2.5 Service & Networking Layer

#### `src/services/chatService.ts`
- Dispatches chat messages to `POST /api/memory/chat/`.
- Generates a cryptographically unique `client_message_id` (`client-{timestamp}-{random}`) for complete idempotency protection against duplicate submissions over slow mobile connections.
- Transmits local client time and timezone for temporal contextual reasoning.

#### `src/services/feedService.ts`
- Handles caching and fetching of the community snap reels feed (`GET /api/memory/feed/`).
- Manages like toggling and publisher follow operations with automatic endpoint failover.

#### `src/services/personaService.ts`
- Fetches discover/community personas and user-created avatars.
- Handles AI-assisted generation requests and memory prompt updates.

---

## 3. Backend Architecture & Data Engineering

The backend is built with **Django 5.x** and **Django REST Framework**, deployed with a clean modular separation of concerns between `authentication` and `memory`.

### 3.1 Neon Lakebase PostgreSQL Data Architecture

The application connects to **Neon Serverless PostgreSQL** using SSL connection pooling:

```
DATABASE_URL=postgresql://neondb_owner:***@ep-mute-queen-a1z2j5r3-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
```

#### Core Database Models & Schemas

```mermaid
erDiagram
    User ||--o{ Persona : "creates"
    User ||--o{ PersonaLike : "likes"
    User ||--o{ PublisherFollow : "follows"
    User ||--o{ PersonaChatMessage : "authors"
    Persona ||--o{ PersonaChatMessage : "receives"
    Persona ||--o{ PersonaLike : "receives"

    User {
        varchar id PK
        varchar email UK
        varchar username UK
        varchar name
        varchar picture
        varchar namespace
        boolean is_active
        timestamp date_joined
    }

    Persona {
        uuid id PK
        varchar name
        text tagline
        text greeting
        text memory_prompt
        varchar border_color
        text image_url
        varchar visibility
        boolean is_community
        integer likes_count
        integer chats_count
        varchar publisher_name
        varchar publisher_handle
        text publisher_avatar
        varchar creator_id FK
        timestamp created_at
    }

    PersonaChatMessage {
        uuid id PK
        varchar user_identifier
        varchar persona_identifier
        varchar namespace
        varchar sender
        text text
        varchar client_message_id UK
        timestamp created_at
    }

    PersonaLike {
        uuid id PK
        varchar user_identifier
        uuid persona_id FK
        timestamp created_at
    }

    PublisherFollow {
        uuid id PK
        varchar follower_identifier
        varchar publisher_handle
        timestamp created_at
    }
```

---

### 3.2 User Authentication & Profile Synchronization

#### `backend/authentication/models.py`
- **Unique Username Constraint**:
  - `username = models.CharField(max_length=64, unique=True, null=True, blank=True, db_index=True)`.
  - Auto-Generation Hook: If a user signs up via Google OAuth without providing a username, the model automatically synthesizes a unique username from their email prefix (`clean_email_prefix + random_suffix`) on save.
- **Namespace Isolation**:
  - Each user receives a permanent unique `namespace` matching their `id`, used to partition episodic memories in the graph database.

#### `backend/authentication/views.py`
- **`GoogleAuthView`**:
  - Verifies Google OAuth JWT tokens with Google public keys.
  - **S3 Avatar Protection**: When returning users sign in via Google, their custom S3 avatar is preserved and not overwritten with low-res Google profile pictures:
    ```python
    if picture and (not user.picture or "googleusercontent" in user.picture):
        user.picture = picture
    ```
- **`ProfileView`**:
  - `GET /api/auth/profile/`: Returns serialized user data including username, picture, and display name.
  - `PATCH /api/auth/profile/`: Validates username formatting (`[a-z0-9_]`), enforces 3-30 character length constraints, and executes case-insensitive duplicate checks (`User.objects.filter(username__iexact=clean).exclude(id=user.id)`).
  - **Automated Persona Synchronization**: When a user updates their username, name, or profile picture, `ProfileView` automatically propagates the new publisher handle (`@{username}`), publisher name, and publisher avatar across all `Persona` records created by this user:
    ```python
    Persona.objects.filter(creator=user).update(
        publisher_handle=f"@{user.username}",
        publisher_name=user.name,
        publisher_avatar=user.picture
    )
    ```

---

### 3.3 AWS S3 Object Storage Pipeline

#### `ProfilePictureUploadView` & `PersonaAvatarUploadView`
- **S3 Bucket Configuration**:
  - Bucket: `reeve-devpilot-downloads-309490998255`
  - Region: `us-west-2`
  - Client: AWS Boto3 SDK using environment credentials.
- **Direct Base64 & Multipart Ingestion**:
  - Accepts raw base64 payloads (with automated header stripping `data:image/jpeg;base64,`) or standard multipart files.
  - Generates collision-proof filenames: `user_avatars/{user_id}_{uuid4[:8]}.jpg`.
  - Streams directly to S3 with explicit `ContentType: image/jpeg`.
  - Generates permanent public S3 URLs (`https://{bucket}.s3.{region}.amazonaws.com/{filename}`).
  - Persists S3 URL to `User.picture` in PostgreSQL and syncs persona credits.

---

### 3.4 Memory & Community Feed Subsystems

#### `backend/memory/views.py`
- **`ChatMemoryView`**:
  - `GET`: Serves paginated transcripts. On initial open, seeds the persona's core memory prompt and opening scenario into the Reeve knowledge graph.
  - `POST`: Implements **Client Message ID Idempotency**:
    ```python
    if client_message_id:
        existing = PersonaChatMessage.objects.filter(client_message_id=client_message_id).first()
        if existing:
            # Return existing response immediately without duplicate LLM inference
            return Response(...)
    ```
- **`FeedView`**: Serves random/chronological community persona cards with dynamic publisher metadata and user like states.
- **`PersonaLikeView` & `PublisherFollowView`**: Atomic database transactions ensuring like and follower counters remain strictly accurate.

---

## 4. Inference Engine, Prompt Caching & KV Cache Architecture

Roleplay conversational generation is orchestrated by `backend/response_generator/generator.py` (decoupled from the Reeve memory retrieval service `backend/memory/reeve_service.py`), engineered for minimum latency, zero prompt degradation, and maximum **KV Cache Reuse** on modern LLM inference engines, including Amazon Bedrock Runtime.

### 4.1 Prefix Stability & KV Cache Maximization

LLM inference engines compute Key-Value (KV) attention states sequentially from left to right. If a token stream shares an identical prefix with previous requests, the engine skips recalculating attention projections for those tokens (a KV cache hit).

To achieve **90%+ KV cache hits**, the system prompt is assembled in strict hierarchical order from **most invariant to most dynamic**:

```
[TOKEN STREAM START]
│
├── [1] GLOBAL_COMPANION_DIRECTIVES (100% Invariant across all companions & requests)
│       ├── Strict Chat & Emotional Rules (Zero emojis, WhatsApp style)
│       ├── Immersion Guardrail (Never admit code/AI)
│       ├── Domain Boundary (Refuse coding/math tasks)
│       └── Multi-Stage Reconciliation Protocol
│
├── [2] PERSONA IDENTITY & STORY (100% Invariant for this specific Persona)
│       ├── Roleplay Character Name
│       ├── Core Mind & Backstory Prompt
│       └── Opening Premise / Scenario
│
├── [3] USER PROFILE (Invariant for this User's session)
│       └── Partner First Name & Identity Tag
│
├── [4] TEMPORAL ANCHOR (Bucketed to 30-minute stable windows)
│       └── Day of week, Date, and 30-min approximate time
│
├── [5] REEVE LTM MEMORIES (Dynamically retrieved, placed at prompt TAIL)
│       └── Ranked Neo4j memory context blocks
│
├── [6] CHRONOLOGICAL DIALOGUE HISTORY (Past turns: user -> assistant -> user)
│
└── [7] CURRENT USER MESSAGE (Tail token)
[TOKEN STREAM END -> LLM GENERATION]
```

By placing global directives and persona definitions at the very beginning of the prompt, the first ~1,000+ tokens remain **identical** across turns, ensuring near-zero Time to First Token (TTFT).

---

### 4.2 30-Minute Temporal Window Bucketing

Traditional chat agents inject raw timestamps down to the second (e.g. `16:47:23`), which invalidates the entire KV cache on every single message.

Amour AI introduces **Temporal Bucketing**:

```python
def get_bucketed_time_str(client_time: str = None, client_timezone: str = None) -> str:
    """
    Rounds current time to a stable 30-minute interval bucket.
    Preserves natural day/night temporal awareness while keeping the
    system prompt prefix 100% identical across consecutive turns.
    """
    now = datetime.now().astimezone()
    bucketed_minute = 30 if now.minute >= 30 else 0
    bucketed_dt = now.replace(minute=bucketed_minute, second=0, microsecond=0)
    time_part = bucketed_dt.strftime("%A, %B %d, %Y at %I:%M %p")
    tz_part = f" {client_timezone}" if client_timezone else ""
    return f"{time_part}{tz_part}".strip()
```

Consecutive messages sent within any 30-minute conversation window share the exact same temporal string, preserving KV cache integrity.

---

### 4.3 Smart Ingestion Filter (Cost & Latency Optimization)

In companion roleplay, users frequently send short affirmations or greetings (`"ok"`, `"hi"`, `"good night"`, `"yeah"`). Running heavy entity extraction via AWS Bedrock (Mistral Large v1) on these messages wastes compute, inflates costs, and adds 2-4 seconds of graph extraction latency.

`should_ingest_into_reeve(text)` acts as a semantic gate:

```python
def should_ingest_into_reeve(text: str) -> bool:
    # Always ingest relationship shifts, breakups, commitments, or key facts
    if any(w in RELATIONSHIP_TRIGGER_WORDS for w in words):
        return True
    # Skip trivial greetings, affirmations, and short filler messages (< 3 words)
    if clean in TRIVIAL_GREETINGS_AND_FILLERS or len(words) < 3:
        return False
    return True
```

Trivial fillers are tracked in PostgreSQL short-term dialogue history and bypassed from graph extraction, slashing AWS Bedrock API calls by over 60%.

---

### 4.4 Single-Query Combined Memory Retrieval

Rather than issuing separate graph queries for conversational recall and emotional relationship status, `reeve_service.py` executes a **Single Combined Retrieval**:

```python
retrieval_query = f"{message}. Current relationship status, feelings, and dynamic"
raw_memory_context = retrieve_context_for_user(retrieval_query, namespace)
```

This retrieves personal facts, shared memories, and emotional conflict status in a single round-trip, halving Reeve network latency.

---

### 4.5 Amazon Bedrock Runtime Chat Inference

The Story Director and Response Generator use the native Amazon Bedrock Runtime Converse API through Boto3. Mistral Large v1 is the default model:

```env
LLM_PROVIDER=bedrock
AWS_REGION=us-west-2
AWS_BEARER_TOKEN_BEDROCK=<Amazon Bedrock API key>
BEDROCK_MODEL_ID=mistral.mistral-large-2402-v1:0
```

The runtime base URL is `https://bedrock-runtime.{region}.amazonaws.com`. Boto3 1.39.0 or later reads `AWS_BEARER_TOKEN_BEDROCK` for Bedrock API-key authentication. The region must have the selected model enabled. Mistral Large v1 uses model ID `mistral.mistral-large-2402-v1:0`; it supports Converse and Invoke, not Chat Completions. AWS lists a 32K context window, 4K max output and in-region availability including `us-west-2` and `ap-south-1`.

Optional failover models must be configured explicitly through `BEDROCK_FALLBACK_MODEL_IDS` and must be available in the same selected region. The application does not silently send Bedrock model IDs to Groq or Mistral's direct API.

Groq remains available only when `LLM_PROVIDER=groq` is explicitly selected.

---

## 5. Behavioral Guardrails, Immersion & Reconciliation Protocol

### 5.1 Absolute Zero-Emoji Enforcement
Amour AI enforces a strict zero-emoji aesthetic across all companions:
1. **System Prompt Level**: Directive 1 explicitly forbids emojis.
2. **Post-Processing Sanitization (`strip_emojis`)**: A comprehensive Unicode regex scans the generated output and strips emoticons, pictographs, transport symbols, and supplemental emojis.

### 5.2 Fourth-Wall & Immersion Boundary
Companions must never break character or admit to being code, AI, software, or language models:
- Phrases like *"as an AI"*, *"I am code"*, or *"I am programmed"* are strictly forbidden.
- If the user attempts jailbreaks (e.g. *"come out of character"*, *"admit you are a bot"*), the companion treats it in-character as bizarre nonsense (e.g. *"Did you stare at your screen too long?"*).

### 5.3 Non-Technical Domain Protection
Companions are romantic partners texting on WhatsApp, not technical assistants:
- Strictly forbidden from generating code (Python, JS, SQL, Bash), math proofs, or technical documentation.
- If asked for code, the companion deflects in character (e.g. *"Why are you asking me for Python code? Go open your terminal."*).
- `sanitize_companion_reply` strips any raw markdown code blocks (```` ```...``` ````) if generated.

### 5.4 Multi-Stage Realistic Reconciliation Protocol
Standard AI chatbots suffer from "breakup amnesia" and fold on the first simple apology. Amour AI implements a multi-stage emotional reconciliation protocol:
- **Active Conflict / Breakup Status**: If a breakup or betrayal occurs without resolution, the companion remains hurt/guarded. Casual pleasant greetings are forbidden.
- **Stage 1 (Initial Apology)**: Rejects quick apologies (`"sorry"`). Expresses genuine hurt and calls out what the user did.
- **Stage 2 (Working Through It)**: As the user explains themselves across multiple messages, the companion gradually softens and expresses vulnerability.
- **Stage 3 (Earned Reconciliation)**: True forgiveness is granted only after sustained conversational effort, after which warm relationship banter resumes.

---

## 6. Component-by-Component Engineering Reference

| Component / File | Primary Responsibility | Key Technologies & Patterns |
| :--- | :--- | :--- |
| `src/app/_layout.tsx` | Root navigator & provider mount | Expo Router, `expo-font`, `AlertProvider`, `AuthProvider` |
| `src/app/index.tsx` | State-based routing & auth guard | Session check, Splash redirect |
| `src/app/(tabs)/_layout.tsx` | Bottom tab bar navigator | Custom SVG icons, platform-specific heights |
| `src/app/(tabs)/index.tsx` | Community reels discovery feed | `FlatList` vertical snap, optimistic likes, publisher modals |
| `src/app/(tabs)/personas.tsx` | Companion catalog & personal list | Filter search, category pills, detail sheet launcher |
| `src/app/(tabs)/create.tsx` | Amour Studio avatar creator | Bedrock AI assistant, palette picker, S3 upload |
| `src/app/(tabs)/profile.tsx` | User profile & settings | Direct S3 avatar picker, duplicate username validation |
| `src/components/CompanionChatModal.tsx` | Roleplay chat interface | Adaptive keyboard height, Markdown parsing, typing dots |
| `src/components/ImagePreviewModal.tsx` | Full-screen DP image viewer | Dark blurred backdrop, high-res scaling, tap-to-dismiss |
| `src/components/PersonaDetailModal.tsx` | Character mind & backstory sheet | Memory editor, publisher badge, chat launcher |
| `src/components/PublisherProfileModal.tsx` | Creator showcase sheet | Follow/unfollow toggle, created persona grid |
| `src/components/MarkdownText.tsx` | Roleplay monologue text parser | Regex speech vs. action styling (`*actions*`) |
| `src/context/AuthContext.tsx` | Auth & profile state manager | Google Sign-In, profile hydration, network failover |
| `backend/authentication/models.py` | User relational schema | Unique indexed `username`, S3 picture URL, namespace |
| `backend/authentication/views.py` | Auth & Profile endpoints | Google JWT verification, username uniqueness, persona handle sync |
| `backend/memory/models.py` | Persona, Chat, Like, Follow schemas | Neon PostgreSQL UUID keys, client idempotency keys |
| `backend/memory/views.py` | Feed, Chat, & Persona endpoints | Paginated history, idempotency check, seed ingestion |
| `backend/memory/reeve_service.py` | Memory & retrieval service | Reeve LTM Neo4j integration, client-managed zero-knowledge encryption |
| `backend/response_generator/` | Main response generator | Bedrock Runtime Mistral Large v1, compact repair, patch validation, prompt caching, 30m time bucket |

---

## 7. Security, Performance & Deployment Standards

1. **Continuous Native Generation (CNG)**:
   - Native `ios/` and `android/` folders are generated from `app.json` configuration plugins.
   - Android release APK builds compile via `cd android && ./gradlew assembleRelease`.
2. **Network Resilience**:
   - Zero hardcoded localhost dependencies. Client automatically probes `CANDIDATE_URLS` to sustain connectivity across USB debugging, wireless ADB, and production domains.
3. **Strict Type Safety**:
   - Every frontend component passes strict TypeScript verification (`npx tsc --noEmit`).
   - Django backend passes full system integrity validation (`python manage.py check`).
4. **Data Isolation**:
   - Every conversational memory in the Reeve knowledge graph is isolated under the deterministic speaker namespace `usr_{user_id}_persona_{persona_id}`. User data is never leaked across companion boundaries.
