export const GOOGLE_CONFIG = {
  clientId: '665738151857-0f765nnvu4no6qhbdbua132vfv2iu10k.apps.googleusercontent.com',
  redirectUri: typeof window !== 'undefined' ? `${window.location.origin}/login` : 'https://amour-ai-v3e4.onrender.com/login',
};

export const API_CONFIG = {
  baseUrl: 'https://amour-ai-v3e4.onrender.com/api',
  candidateUrls: [
    'https://amour-ai-v3e4.onrender.com/api',
  ]
};
