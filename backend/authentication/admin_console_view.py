import json
from django.views import View
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.conf import settings
from django.contrib.auth import get_user_model
from memory.models import Persona, PersonaChatMessage

User = get_user_model()


class AdminConsoleWebView(View):
    """
    Production Web Admin Console for Amour AI.
    Accessible at /console/.
    Provides real-time analytics, user account administration, persona inspection,
    and chat activity monitoring.
    """

    def get(self, request):
        # Allow superusers / staff logged into Django session
        is_authenticated = (
            hasattr(request, "user")
            and request.user
            and request.user.is_authenticated
            and (getattr(request.user, "is_staff", False) or getattr(request.user, "is_superuser", False))
        )
        
        # Check query param / header key for direct token access
        admin_key = request.GET.get("key", "").strip()
        expected_secret = getattr(settings, "SECRET_KEY", "amour-secret")[:16]
        if admin_key and admin_key == expected_secret:
            is_authenticated = True

        # Calculate high-level stats for fast server-side hydration
        total_users = User.objects.count()
        active_users = User.objects.filter(is_active=True).count()
        verified_users = User.objects.filter(verified_email=True).count()
        staff_users = User.objects.filter(is_staff=True).count()
        google_users = User.objects.filter(auth_provider="google").count()
        local_users = User.objects.filter(auth_provider="local").count()
        total_personas = Persona.objects.count()
        total_chats = PersonaChatMessage.objects.count()

        # Preload personas
        personas = list(
            Persona.objects.all().values(
                "id", "name", "tagline", "age", "border_color", "image_url",
                "greeting", "memory_prompt", "visibility", "is_community",
                "likes_count", "chats_count", "publisher_name", "publisher_handle", "created_at"
            )[:50]
        )
        for p in personas:
            p["id"] = str(p["id"])
            p["created_at"] = p["created_at"].strftime("%Y-%m-%d %H:%M") if p.get("created_at") else ""

        html = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Amour AI — Admin Console</title>
  <link rel="icon" href="https://amour-ai-v3e4.onrender.com/static/favicon.ico">
  <!-- Tailwind CSS -->
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <script>
    tailwind.config = {{
      darkMode: 'class',
      theme: {{
        extend: {{
          colors: {{
            brand: {{
              50: '#fff1f2',
              500: '#f43f5e',
              600: '#e11d48',
              700: '#be123c',
            }},
            dark: {{
              base: '#09090b',
              card: '#121217',
              border: '#27272a',
              input: '#18181b',
              hover: '#1f1f23',
            }}
          }},
          fontFamily: {{
            sans: ['"Plus Jakarta Sans"', 'sans-serif'],
          }}
        }}
      }}
    }}
  </script>
  <style>
    body {{
      background-color: #09090b;
      color: #fafafa;
      font-family: 'Plus Jakarta Sans', sans-serif;
    }}
    ::-webkit-scrollbar {{
      width: 6px;
      height: 6px;
    }}
    ::-webkit-scrollbar-track {{
      background: #09090b;
    }}
    ::-webkit-scrollbar-thumb {{
      background: #27272a;
      border-radius: 4px;
    }}
    ::-webkit-scrollbar-thumb:hover {{
      background: #3f3f46;
    }}
  </style>
</head>
<body class="min-h-screen bg-dark-base text-zinc-100 flex flex-col">

  <!-- TOP NAVIGATION BAR -->
  <header class="border-b border-dark-border bg-dark-card/80 backdrop-blur sticky top-0 z-40 px-4 lg:px-8 py-3.5">
    <div class="max-w-7xl mx-auto flex items-center justify-between">
      <div class="flex items-center space-x-3.5">
        <div class="w-9 h-9 rounded-xl bg-gradient-to-tr from-brand-600 to-rose-400 flex items-center justify-center shadow-lg shadow-brand-500/20 font-bold text-white text-lg">
          ♥
        </div>
        <div>
          <div class="flex items-center space-x-2">
            <span class="font-extrabold text-base tracking-tight text-white">Amour AI</span>
            <span class="text-xs uppercase tracking-wider font-semibold px-2 py-0.5 rounded-full bg-brand-500/10 text-brand-500 border border-brand-500/20">Admin</span>
          </div>
          <span class="text-[11px] text-zinc-400">Live Production Operations</span>
        </div>
      </div>

      <div class="flex items-center space-x-3 text-sm">
        <a href="/admin/" target="_blank" class="px-3.5 py-1.5 rounded-lg border border-dark-border bg-dark-input hover:bg-dark-hover transition text-xs font-semibold text-zinc-300 flex items-center space-x-1.5">
          <span>Django Portal</span>
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/></svg>
        </a>
        <div class="hidden sm:flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-zinc-900 border border-dark-border">
          <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          <span class="text-xs text-zinc-300 font-medium">{'ankeshpune@gmail.com' if is_authenticated else 'Guest Mode'}</span>
        </div>
      </div>
    </div>
  </header>

  <!-- MAIN CONTAINER -->
  <main class="flex-1 max-w-7xl w-full mx-auto px-4 lg:px-8 py-6 space-y-6">

    <!-- METRICS OVERVIEW CARDS -->
    <section class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3.5">
      <div class="p-4 rounded-xl bg-dark-card border border-dark-border">
        <p class="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">Total Users</p>
        <p class="text-2xl font-bold mt-1 text-white" id="stat-total">{total_users}</p>
        <div class="mt-2 text-[11px] text-emerald-400 flex items-center space-x-1">
          <span>● {active_users} active</span>
        </div>
      </div>
      <div class="p-4 rounded-xl bg-dark-card border border-dark-border">
        <p class="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">Google Auth</p>
        <p class="text-2xl font-bold mt-1 text-sky-400">{google_users}</p>
        <div class="mt-2 text-[11px] text-zinc-400">
          <span>{round((google_users / max(total_users, 1)) * 100)}% of total</span>
        </div>
      </div>
      <div class="p-4 rounded-xl bg-dark-card border border-dark-border">
        <p class="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">Email Auth</p>
        <p class="text-2xl font-bold mt-1 text-indigo-400">{local_users}</p>
        <div class="mt-2 text-[11px] text-zinc-400">
          <span>{verified_users} verified</span>
        </div>
      </div>
      <div class="p-4 rounded-xl bg-dark-card border border-dark-border">
        <p class="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">Staff Users</p>
        <p class="text-2xl font-bold mt-1 text-amber-400">{staff_users}</p>
        <div class="mt-2 text-[11px] text-zinc-400">
          <span>Superusers: 1</span>
        </div>
      </div>
      <div class="p-4 rounded-xl bg-dark-card border border-dark-border">
        <p class="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">Personas</p>
        <p class="text-2xl font-bold mt-1 text-brand-500">{total_personas}</p>
        <div class="mt-2 text-[11px] text-zinc-400">
          <span>Active catalog</span>
        </div>
      </div>
      <div class="p-4 rounded-xl bg-dark-card border border-dark-border">
        <p class="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">Chats Logged</p>
        <p class="text-2xl font-bold mt-1 text-purple-400">{total_chats}</p>
        <div class="mt-2 text-[11px] text-zinc-400">
          <span>Messages safe in DB</span>
        </div>
      </div>
    </section>

    <!-- NAVIGATION TABS -->
    <div class="flex items-center space-x-2 border-b border-dark-border pb-3">
      <button onclick="switchTab('users')" id="tab-btn-users" class="px-4 py-2 rounded-lg text-xs font-bold transition flex items-center space-x-2 bg-brand-500 text-white">
        <span>👥 User Accounts</span>
      </button>
      <button onclick="switchTab('personas')" id="tab-btn-personas" class="px-4 py-2 rounded-lg text-xs font-bold transition flex items-center space-x-2 text-zinc-400 hover:text-white hover:bg-dark-hover">
        <span>🎭 Personas ({total_personas})</span>
      </button>
      <button onclick="switchTab('llm')" id="tab-btn-llm" class="px-4 py-2 rounded-lg text-xs font-bold transition flex items-center space-x-2 text-zinc-400 hover:text-white hover:bg-dark-hover">
        <span>📊 LLM Usage</span>
      </button>
    </div>

    <!-- TAB 1: USERS MANAGEMENT -->
    <section id="tab-users" class="space-y-4">
      <!-- Search & Filters -->
      <div class="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <div class="relative flex-1 max-w-md">
          <input 
            type="text" 
            id="user-search-input" 
            placeholder="Search by name, email, username, or ID..." 
            oninput="handleSearch()"
            class="w-full pl-9 pr-4 py-2 rounded-lg bg-dark-card border border-dark-border text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-brand-500 transition"
          >
          <svg class="w-4 h-4 text-zinc-500 absolute left-3 top-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
        </div>

        <div class="flex items-center space-x-2 overflow-x-auto pb-1 sm:pb-0">
          <select id="filter-provider" onchange="loadUsers()" class="px-3 py-2 rounded-lg bg-dark-card border border-dark-border text-xs text-zinc-300 focus:outline-none">
            <option value="all">All Providers</option>
            <option value="google">Google</option>
            <option value="local">Email / Local</option>
          </select>
          <select id="filter-active" onchange="loadUsers()" class="px-3 py-2 rounded-lg bg-dark-card border border-dark-border text-xs text-zinc-300 focus:outline-none">
            <option value="all">All Status</option>
            <option value="true">Active Only</option>
            <option value="false">Inactive Only</option>
          </select>
          <button onclick="openCreateUserModal()" class="px-3.5 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 transition text-xs font-bold text-white flex items-center space-x-1.5 shadow-md shadow-brand-600/20">
            <span>+ Add User</span>
          </button>
        </div>
      </div>

      <!-- Users Table -->
      <div class="overflow-x-auto rounded-xl border border-dark-border bg-dark-card">
        <table class="w-full text-left text-xs text-zinc-300">
          <thead class="bg-zinc-900/60 uppercase tracking-wider text-[10px] text-zinc-400 border-b border-dark-border">
            <tr>
              <th class="px-4 py-3">User</th>
              <th class="px-4 py-3">Username</th>
              <th class="px-4 py-3">Auth</th>
              <th class="px-4 py-3">Roles</th>
              <th class="px-4 py-3">Status</th>
              <th class="px-4 py-3">Joined</th>
              <th class="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody id="users-table-body" class="divide-y divide-dark-border">
            <tr>
              <td colspan="7" class="px-4 py-8 text-center text-zinc-500">
                <div class="inline-block animate-spin rounded-full h-5 w-5 border-2 border-brand-500 border-t-transparent mr-2"></div>
                Loading user database...
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- TAB 2: PERSONAS CATALOG -->
    <section id="tab-personas" class="hidden space-y-4">
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {"".join([f'''
        <div class="rounded-xl border border-dark-border bg-dark-card p-4 flex flex-col space-y-3 relative overflow-hidden">
          <div class="flex items-start space-x-3">
            <img src="{p.get('image_url') or 'https://images.unsplash.com/photo-1534528741775-53994a69daeb'}" class="w-14 h-14 rounded-xl object-cover border-2 border-zinc-700">
            <div class="flex-1 min-w-0">
              <div class="flex items-center justify-between">
                <h4 class="font-bold text-sm text-white truncate">{p.get('name')}</h4>
                <span class="text-[10px] px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-400 font-semibold">{p.get('age', 21)} yrs</span>
              </div>
              <p class="text-xs text-brand-400 font-medium truncate mt-0.5">{p.get('tagline') or 'Companion'}</p>
              <p class="text-[11px] text-zinc-500 mt-1">Publisher: {p.get('publisher_name', 'Amour')}</p>
            </div>
          </div>

          <div class="p-2.5 rounded-lg bg-dark-input border border-dark-border text-[11px] text-zinc-300 italic line-clamp-3">
            "{p.get('greeting')[:140]}..."
          </div>

          <div class="flex items-center justify-between text-[11px] text-zinc-400 pt-1 border-t border-dark-border">
            <span class="flex items-center space-x-1">
              <span class="text-brand-500 font-bold">♥</span>
              <span>{p.get('likes_count', 0)} likes</span>
            </span>
            <span class="text-[10px] text-zinc-500">ID: {p.get('id')[:8]}...</span>
          </div>
        </div>
        ''' for p in personas])}
      </div>
    </section>

    <!-- TAB 3: LLM USAGE AND QUOTA -->
    <section id="tab-llm" class="hidden space-y-4">
      <div class="flex items-center justify-between gap-3">
        <div>
          <h2 class="text-sm font-bold text-white">LLM usage &amp; provider quota</h2>
          <p class="text-[11px] text-zinc-400 mt-1">Observed request/token totals and the latest Groq rate-limit headers. No prompts or user identifiers are stored.</p>
        </div>
        <button onclick="loadLLMUsage()" class="shrink-0 px-3 py-2 rounded-lg border border-dark-border bg-dark-card hover:bg-dark-hover text-xs font-semibold text-zinc-300">Refresh</button>
      </div>

      <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div class="p-4 rounded-xl bg-dark-card border border-dark-border">
          <p class="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">Requests · 24h</p>
          <p id="llm-requests" class="text-2xl font-bold mt-1 text-white">—</p>
          <p id="llm-request-breakdown" class="mt-2 text-[11px] text-zinc-400">Waiting for telemetry</p>
        </div>
        <div class="p-4 rounded-xl bg-dark-card border border-dark-border">
          <p class="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">Tokens · 24h</p>
          <p id="llm-tokens" class="text-2xl font-bold mt-1 text-sky-400">—</p>
          <p id="llm-token-breakdown" class="mt-2 text-[11px] text-zinc-400">Input + output tokens</p>
        </div>
        <div class="p-4 rounded-xl bg-dark-card border border-dark-border">
          <p class="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">Success rate · 24h</p>
          <p id="llm-success-rate" class="text-2xl font-bold mt-1 text-emerald-400">—</p>
          <p class="mt-2 text-[11px] text-zinc-400">Provider responses</p>
        </div>
        <div class="p-4 rounded-xl bg-dark-card border border-dark-border">
          <p class="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">Avg latency · 24h</p>
          <p id="llm-latency" class="text-2xl font-bold mt-1 text-amber-400">—</p>
          <p class="mt-2 text-[11px] text-zinc-400">Across observed attempts</p>
        </div>
      </div>

      <div class="rounded-xl border border-dark-border bg-dark-card p-4 space-y-3">
        <div>
          <h3 class="text-xs font-bold text-white">Latest Groq quota snapshot</h3>
          <p class="text-[11px] text-zinc-500 mt-1">Quota data is supplied by Groq response headers and can be model-specific.</p>
        </div>
        <div id="llm-quota-cards" class="grid grid-cols-1 md:grid-cols-2 gap-3">
          <p class="text-xs text-zinc-500">Waiting for telemetry</p>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div class="rounded-xl border border-dark-border bg-dark-card p-4">
          <h3 class="text-xs font-bold text-white mb-3">Daily token volume · 7 days</h3>
          <div id="llm-daily-usage" class="space-y-3 text-xs text-zinc-400">Waiting for telemetry</div>
        </div>
        <div class="rounded-xl border border-dark-border bg-dark-card p-4 overflow-x-auto">
          <h3 class="text-xs font-bold text-white mb-3">Usage by model · 7 days</h3>
          <table class="w-full text-left text-xs text-zinc-300">
            <thead class="text-[10px] uppercase tracking-wider text-zinc-500 border-b border-dark-border">
              <tr><th class="py-2 pr-3">Provider / model</th><th class="py-2 px-2 text-right">Requests</th><th class="py-2 px-2 text-right">Tokens</th><th class="py-2 pl-2 text-right">Avg ms</th></tr>
            </thead>
            <tbody id="llm-model-usage" class="divide-y divide-dark-border">
              <tr><td colspan="4" class="py-4 text-center text-zinc-500">Waiting for telemetry</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="rounded-xl border border-dark-border bg-dark-card p-4 overflow-x-auto">
        <h3 class="text-xs font-bold text-white mb-3">Recent provider attempts · 24h</h3>
        <table class="w-full text-left text-xs text-zinc-300">
          <thead class="text-[10px] uppercase tracking-wider text-zinc-500 border-b border-dark-border">
            <tr><th class="py-2 pr-3">Time</th><th class="py-2 px-2">Provider / model</th><th class="py-2 px-2">Status</th><th class="py-2 px-2 text-right">Tokens</th><th class="py-2 px-2 text-right">Latency</th><th class="py-2 pl-2">Details</th></tr>
          </thead>
          <tbody id="llm-recent-usage" class="divide-y divide-dark-border">
            <tr><td colspan="6" class="py-4 text-center text-zinc-500">Waiting for telemetry</td></tr>
          </tbody>
        </table>
      </div>
    </section>

  </main>

  <!-- EDIT USER MODAL -->
  <div id="edit-user-modal" class="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
    <div class="bg-dark-card border border-dark-border rounded-2xl w-full max-w-lg p-6 space-y-4 shadow-2xl">
      <div class="flex items-center justify-between border-b border-dark-border pb-3">
        <h3 class="text-base font-bold text-white">Edit User Profile</h3>
        <button onclick="closeEditModal()" class="text-zinc-400 hover:text-white text-lg">&times;</button>
      </div>

      <form id="edit-user-form" onsubmit="saveUserEdit(event)" class="space-y-3.5">
        <input type="hidden" id="edit-user-id">
        <div>
          <label class="block text-[11px] font-semibold text-zinc-400 uppercase tracking-wider mb-1">Email</label>
          <input type="email" id="edit-email" required class="w-full px-3 py-2 rounded-lg bg-dark-input border border-dark-border text-xs text-white focus:outline-none focus:border-brand-500">
        </div>
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-[11px] font-semibold text-zinc-400 uppercase tracking-wider mb-1">Display Name</label>
            <input type="text" id="edit-name" class="w-full px-3 py-2 rounded-lg bg-dark-input border border-dark-border text-xs text-white focus:outline-none focus:border-brand-500">
          </div>
          <div>
            <label class="block text-[11px] font-semibold text-zinc-400 uppercase tracking-wider mb-1">Username</label>
            <input type="text" id="edit-username" class="w-full px-3 py-2 rounded-lg bg-dark-input border border-dark-border text-xs text-white focus:outline-none focus:border-brand-500">
          </div>
        </div>
        <div>
          <label class="block text-[11px] font-semibold text-zinc-400 uppercase tracking-wider mb-1">Profile Picture URL</label>
          <input type="text" id="edit-picture" class="w-full px-3 py-2 rounded-lg bg-dark-input border border-dark-border text-xs text-white focus:outline-none focus:border-brand-500">
        </div>

        <div class="pt-2 border-t border-dark-border space-y-2">
          <label class="flex items-center space-x-2 text-xs text-zinc-300">
            <input type="checkbox" id="edit-is-active" class="rounded bg-dark-input border-dark-border text-brand-600 focus:ring-0">
            <span>Active Account</span>
          </label>
          <label class="flex items-center space-x-2 text-xs text-zinc-300">
            <input type="checkbox" id="edit-verified-email" class="rounded bg-dark-input border-dark-border text-brand-600 focus:ring-0">
            <span>Verified Email</span>
          </label>
          <label class="flex items-center space-x-2 text-xs text-zinc-300">
            <input type="checkbox" id="edit-is-staff" class="rounded bg-dark-input border-dark-border text-brand-600 focus:ring-0">
            <span>Staff Member (Admin Portal Access)</span>
          </label>
          <label class="flex items-center space-x-2 text-xs text-zinc-300">
            <input type="checkbox" id="edit-is-superuser" class="rounded bg-dark-input border-dark-border text-brand-600 focus:ring-0">
            <span>Superuser</span>
          </label>
        </div>

        <div class="flex items-center justify-end space-x-2 pt-3 border-t border-dark-border">
          <button type="button" onclick="closeEditModal()" class="px-4 py-2 rounded-lg bg-zinc-800 text-zinc-300 hover:bg-zinc-700 text-xs font-semibold">Cancel</button>
          <button type="submit" class="px-4 py-2 rounded-lg bg-brand-600 text-white hover:bg-brand-500 text-xs font-bold">Save Changes</button>
        </div>
      </form>
    </div>
  </div>

  <!-- JAVASCRIPT CONTROLLER -->
  <script>
    let currentUsers = [];
    let searchTimeout = null;
    const adminUserId = "111822298300726667407"; // ankeshpune@gmail.com
    const consoleAdminKey = new URLSearchParams(window.location.search).get('key') || '';

    function switchTab(tab) {{
      document.getElementById('tab-users').classList.toggle('hidden', tab !== 'users');
      document.getElementById('tab-personas').classList.toggle('hidden', tab !== 'personas');
      document.getElementById('tab-llm').classList.toggle('hidden', tab !== 'llm');

      ['users', 'personas', 'llm'].forEach(t => {{
        const btn = document.getElementById(`tab-btn-${{t}}`);
        if (t === tab) {{
          btn.className = "px-4 py-2 rounded-lg text-xs font-bold transition flex items-center space-x-2 bg-brand-500 text-white";
        }} else {{
          btn.className = "px-4 py-2 rounded-lg text-xs font-bold transition flex items-center space-x-2 text-zinc-400 hover:text-white hover:bg-dark-hover";
        }}
      }});
      if (tab === 'llm') loadLLMUsage();
    }}

    function escapeHtml(value) {{
      return String(value ?? '').replace(/[&<>"']/g, char => ({{
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
      }}[char]));
    }}

    function formatNumber(value) {{
      return Number(value || 0).toLocaleString();
    }}

    async function loadLLMUsage() {{
      const quotaCards = document.getElementById('llm-quota-cards');
      try {{
        const headers = {{}};
        if (consoleAdminKey) headers['x-console-admin-key'] = consoleAdminKey;
        const response = await fetch('/api/llm/usage/', {{ headers }});
        if (!response.ok) throw new Error(`HTTP ${{response.status}}`);
        const data = await response.json();
        const summary = data.summary || {{}};
        const requestCount = Number(summary.requests || 0);
        const successes = Number(summary.successes || 0);
        const tokensIn = Number(summary.input_tokens || 0);
        const tokensOut = Number(summary.output_tokens || 0);
        const totalTokens = tokensIn + tokensOut;
        document.getElementById('llm-requests').textContent = formatNumber(requestCount);
        document.getElementById('llm-request-breakdown').textContent =
          `${{formatNumber(successes)}} succeeded · ${{formatNumber(summary.failures)}} failed · ${{formatNumber(summary.rate_limited)}} rate limited`;
        document.getElementById('llm-tokens').textContent = formatNumber(totalTokens);
        document.getElementById('llm-token-breakdown').textContent =
          `${{formatNumber(tokensIn)}} input · ${{formatNumber(tokensOut)}} output`;
        document.getElementById('llm-success-rate').textContent =
          `${{requestCount ? Math.round((successes / requestCount) * 100) : 0}}%`;
        document.getElementById('llm-latency').textContent =
          `${{formatNumber(Math.round(summary.average_latency_ms || 0))}} ms`;

        const quotas = data.quota_snapshots || [];
        quotaCards.innerHTML = quotas.length ? quotas.map(quota => {{
          const model = escapeHtml(quota.model);
          const tokenLimit = quota.rate_limit_limit_tokens;
          const tokenRemaining = quota.rate_limit_remaining_tokens;
          const requestLimit = quota.rate_limit_limit_requests;
          const requestRemaining = quota.rate_limit_remaining_requests;
          const tokenPercent = tokenLimit > 0 && tokenRemaining !== null
            ? Math.max(0, Math.min(100, (tokenRemaining / tokenLimit) * 100)) : null;
          const observedAt = new Date(quota.observed_at).toLocaleString();
          return `
            <div class="rounded-lg bg-dark-input border border-dark-border p-3 space-y-2">
              <div class="flex items-center justify-between gap-2">
                <span class="text-xs font-bold text-white">${{model}}</span>
                <span class="text-[10px] text-zinc-500">Observed ${{escapeHtml(observedAt)}}</span>
              </div>
              ${{tokenLimit !== null && tokenRemaining !== null ? `
                <div class="flex justify-between text-[11px] text-zinc-400"><span>Tokens remaining</span><span>${{formatNumber(tokenRemaining)}} / ${{formatNumber(tokenLimit)}}</span></div>
                <div class="h-1.5 rounded-full bg-zinc-800 overflow-hidden"><div class="h-full bg-sky-500 rounded-full" style="width:${{tokenPercent}}%"></div></div>
                <p class="text-[10px] text-zinc-500">Reset: ${{escapeHtml(quota.rate_limit_reset_tokens || 'not reported')}}</p>
              ` : '<p class="text-[11px] text-zinc-500">Token quota headers not reported</p>'}}
              ${{requestLimit !== null && requestRemaining !== null
                ? `<p class="text-[11px] text-zinc-400">Requests remaining: ${{formatNumber(requestRemaining)}} / ${{formatNumber(requestLimit)}} · reset ${{escapeHtml(quota.rate_limit_reset_requests || 'unknown')}}</p>`
                : ''}}
            </div>`;
        }}).join('') : '<p class="text-xs text-zinc-500">No Groq quota headers observed yet. Make a request and refresh to populate this snapshot.</p>';

        const daily = data.daily || [];
        const maxDailyTokens = Math.max(1, ...daily.map(day =>
          Number(day.input_tokens || 0) + Number(day.output_tokens || 0)));
        document.getElementById('llm-daily-usage').innerHTML = daily.length ? daily.map(day => {{
          const count = Number(day.input_tokens || 0) + Number(day.output_tokens || 0);
          const width = Math.max(2, (count / maxDailyTokens) * 100);
          return `<div>
            <div class="flex justify-between mb-1"><span>${{escapeHtml(day.day)}}</span><span>${{formatNumber(count)}} tokens · ${{formatNumber(day.requests)}} requests</span></div>
            <div class="h-1.5 rounded-full bg-zinc-800 overflow-hidden"><div class="h-full bg-brand-500 rounded-full" style="width:${{width}}%"></div></div>
          </div>`;
        }}).join('') : '<p class="text-xs text-zinc-500">No recorded usage in the last 7 days.</p>';

        const models = data.models || [];
        document.getElementById('llm-model-usage').innerHTML = models.length ? models.map(model => {{
          const tokens = Number(model.input_tokens || 0) + Number(model.output_tokens || 0);
          return `<tr>
            <td class="py-2 pr-3"><span class="text-zinc-400">${{escapeHtml(model.provider)}}</span><br><span class="font-medium text-white">${{escapeHtml(model.model)}}</span></td>
            <td class="py-2 px-2 text-right">${{formatNumber(model.requests)}}</td>
            <td class="py-2 px-2 text-right">${{formatNumber(tokens)}}</td>
            <td class="py-2 pl-2 text-right">${{formatNumber(Math.round(model.average_latency_ms || 0))}}</td>
          </tr>`;
        }}).join('') : '<tr><td colspan="4" class="py-4 text-center text-zinc-500">No recorded usage in the last 7 days.</td></tr>';

        const recent = data.recent || [];
        document.getElementById('llm-recent-usage').innerHTML = recent.length ? recent.map(item => {{
          const tokens = item.input_tokens == null && item.output_tokens == null
            ? '—' : formatNumber(Number(item.input_tokens || 0) + Number(item.output_tokens || 0));
          const detail = item.error_type || (item.response_status ? `HTTP ${{item.response_status}}` : '—');
          const statusColor = item.status === 'success' ? 'text-emerald-400'
            : item.status === 'rate_limited' ? 'text-amber-400' : 'text-rose-400';
          return `<tr>
            <td class="py-2 pr-3 whitespace-nowrap">${{escapeHtml(new Date(item.created_at).toLocaleString())}}</td>
            <td class="py-2 px-2"><span class="text-zinc-400">${{escapeHtml(item.provider)}}</span><br><span class="text-white">${{escapeHtml(item.model)}}</span></td>
            <td class="py-2 px-2 ${{statusColor}}">${{escapeHtml(item.status)}}</td>
            <td class="py-2 px-2 text-right">${{tokens}}</td>
            <td class="py-2 px-2 text-right">${{formatNumber(item.duration_ms)}} ms</td>
            <td class="py-2 pl-2 text-zinc-500">${{escapeHtml(detail)}}</td>
          </tr>`;
        }}).join('') : '<tr><td colspan="6" class="py-4 text-center text-zinc-500">No provider attempts in the last 24 hours.</td></tr>';
      }} catch (err) {{
        console.error('Failed to load LLM usage:', err);
        quotaCards.innerHTML = `<p class="text-xs text-rose-400">Unable to load LLM usage (${{
          escapeHtml(err.message)
        }}). Check admin access and database migrations.</p>`;
      }}
    }}

    async function loadUsers() {{
      const search = document.getElementById('user-search-input').value.trim();
      const provider = document.getElementById('filter-provider').value;
      const active = document.getElementById('filter-active').value;

      let url = `/api/auth/admin/users/?admin_user_id=${{adminUserId}}`;
      if (search) url += `&search=${{encodeURIComponent(search)}}`;
      if (provider !== 'all') url += `&auth_provider=${{provider}}`;
      if (active !== 'all') url += `&is_active=${{active}}`;

      try {{
        const res = await fetch(url, {{
          headers: {{
            'x-admin-user-id': adminUserId
          }}
        }});
        if (!res.ok) throw new Error(`HTTP ${{res.status}}`);
        const data = await res.json();
        currentUsers = data.users || [];
        renderUsers(currentUsers);
      }} catch (err) {{
        console.error('Failed to load users:', err);
        document.getElementById('users-table-body').innerHTML = `
          <tr><td colspan="7" class="px-4 py-6 text-center text-rose-400">Failed to load users. (${{err.message}})</td></tr>
        `;
      }}
    }}

    function renderUsers(users) {{
      const tbody = document.getElementById('users-table-body');
      if (!users.length) {{
        tbody.innerHTML = `<tr><td colspan="7" class="px-4 py-6 text-center text-zinc-500">No users found.</td></tr>`;
        return;
      }}

      tbody.innerHTML = users.map(u => `
        <tr class="hover:bg-dark-hover/50 transition">
          <td class="px-4 py-3">
            <div class="flex items-center space-x-3">
              <img src="${{u.picture || 'https://images.unsplash.com/photo-1535713875002-d1d0cf377fde'}}" class="w-8 h-8 rounded-full object-cover border border-zinc-700">
              <div>
                <p class="font-bold text-white text-xs">${{u.name || 'Unnamed'}}</p>
                <p class="text-[11px] text-zinc-400">${{u.email}}</p>
              </div>
            </div>
          </td>
          <td class="px-4 py-3 font-mono text-[11px] text-zinc-300">
            @${{u.username || '—'}}
          </td>
          <td class="px-4 py-3">
            <span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase ${{u.auth_provider === 'google' ? 'bg-sky-500/10 text-sky-400 border border-sky-500/20' : 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20'}}">
              ${{u.auth_provider}}
            </span>
          </td>
          <td class="px-4 py-3">
            <div class="flex items-center space-x-1">
              ${{u.is_superuser ? '<span class="px-1.5 py-0.5 rounded text-[9px] bg-amber-500/10 text-amber-400 font-bold">SUPER</span>' : ''}}
              ${{u.is_staff ? '<span class="px-1.5 py-0.5 rounded text-[9px] bg-purple-500/10 text-purple-400 font-bold">STAFF</span>' : ''}}
              ${{!u.is_staff && !u.is_superuser ? '<span class="text-zinc-500 text-[11px]">User</span>' : ''}}
            </div>
          </td>
          <td class="px-4 py-3">
            <span class="inline-flex items-center space-x-1.5 px-2 py-0.5 rounded text-[10px] font-semibold ${{u.is_active ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'}}">
              <span class="w-1.5 h-1.5 rounded-full ${{u.is_active ? 'bg-emerald-500' : 'bg-rose-500'}}"></span>
              <span>${{u.is_active ? 'Active' : 'Disabled'}}</span>
            </span>
          </td>
          <td class="px-4 py-3 text-[11px] text-zinc-400">
            ${{u.created_at ? u.created_at.split('T')[0] : '—'}}
          </td>
          <td class="px-4 py-3 text-right space-x-1.5">
            <button onclick="openEditModal('${{u.id}}')" class="px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-[11px] font-semibold transition">
              Edit
            </button>
            <button onclick="confirmDeleteUser('${{u.id}}', '${{u.email}}')" class="px-2 py-1 rounded bg-rose-950/40 hover:bg-rose-900/60 text-rose-300 border border-rose-800/40 text-[11px] font-semibold transition">
              Delete
            </button>
          </td>
        </tr>
      `).join('');
    }}

    function handleSearch() {{
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(loadUsers, 250);
    }}

    function openEditModal(userId) {{
      const user = currentUsers.find(u => u.id === userId);
      if (!user) return;

      document.getElementById('edit-user-id').value = user.id;
      document.getElementById('edit-email').value = user.email || '';
      document.getElementById('edit-name').value = user.name || '';
      document.getElementById('edit-username').value = user.username || '';
      document.getElementById('edit-picture').value = user.picture || '';
      document.getElementById('edit-is-active').checked = !!user.is_active;
      document.getElementById('edit-verified-email').checked = !!user.verified_email;
      document.getElementById('edit-is-staff').checked = !!user.is_staff;
      document.getElementById('edit-is-superuser').checked = !!user.is_superuser;

      document.getElementById('edit-user-modal').classList.remove('hidden');
    }}

    function closeEditModal() {{
      document.getElementById('edit-user-modal').classList.add('hidden');
    }}

    async function saveUserEdit(e) {{
      e.preventDefault();
      const userId = document.getElementById('edit-user-id').value;
      const payload = {{
        email: document.getElementById('edit-email').value.trim(),
        name: document.getElementById('edit-name').value.trim(),
        username: document.getElementById('edit-username').value.trim(),
        picture: document.getElementById('edit-picture').value.trim(),
        is_active: document.getElementById('edit-is-active').checked,
        verified_email: document.getElementById('edit-verified-email').checked,
        is_staff: document.getElementById('edit-is-staff').checked,
        is_superuser: document.getElementById('edit-is-superuser').checked,
      }};

      try {{
        const res = await fetch(`/api/auth/admin/users/${{userId}}/?admin_user_id=${{adminUserId}}`, {{
          method: 'PUT',
          headers: {{
            'Content-Type': 'application/json',
            'x-admin-user-id': adminUserId,
          }},
          body: JSON.stringify(payload),
        }});
        if (!res.ok) {{
          const err = await res.json();
          alert('Error: ' + JSON.stringify(err));
          return;
        }}
        closeEditModal();
        loadUsers();
      }} catch (err) {{
        alert('Network error: ' + err.message);
      }}
    }}

    async function confirmDeleteUser(userId, email) {{
      if (!confirm(`Are you sure you want to permanently delete ${{email}}?\\n\\nThis cascades through PostgreSQL and removes all associated memory nodes.`)) {{
        return;
      }}

      try {{
        const res = await fetch(`/api/auth/admin/users/${{userId}}/?admin_user_id=${{adminUserId}}`, {{
          method: 'DELETE',
          headers: {{
            'x-admin-user-id': adminUserId,
          }}
        }});
        if (!res.ok) throw new Error(`HTTP ${{res.status}}`);
        loadUsers();
      }} catch (err) {{
        alert('Delete failed: ' + err.message);
      }}
    }}

    // Initial load
    document.addEventListener('DOMContentLoaded', loadUsers);
    setInterval(() => {{
      if (!document.getElementById('tab-llm').classList.contains('hidden')) loadLLMUsage();
    }}, 30000);
  </script>
</body>
</html>"""
        return HttpResponse(html, content_type="text/html")
